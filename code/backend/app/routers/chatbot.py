import sys
import os
from pathlib import Path
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_current_user_optional
from ..db import get_db

# Add the llm module to the Python path
app_root = Path(__file__).resolve().parent.parent
app_root_str = str(app_root)
if app_root_str not in sys.path:
    sys.path.insert(0, app_root_str)

try:
    import llm
    from llm import CandidateChatbot
    from llm.audio.voice import voice_service
    chatbot_available = True
except ImportError as e:
    print(f"Warning: Could not import chatbot module: {e}", file=sys.stderr)
    print("Chatbot functionality will not be available.", file=sys.stderr)
    chatbot_available = False
    
    # Create placeholder classes to prevent import errors
    class CandidateChatbot:
        def __init__(self):
            raise ImportError("LLM dependencies not installed")
    
    class voice_service:
        @staticmethod
        async def speech_to_text(audio_data):
            return "Speech to text not available"
        
        @staticmethod
        async def text_to_speech(text):
            return "Text to speech not available"

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chatbot", tags=["chatbot"])

# In-memory storage for chatbot instances (in production, use Redis or database)
chatbot_sessions: Dict[str, CandidateChatbot] = {}


class ChatMessage(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    candidate_info: Dict[str, Any]
    conversation_id: str


class VoiceRequest(BaseModel):
    audio_data: str  # Base64 encoded audio
    conversation_id: Optional[str] = None


class VoiceResponse(BaseModel):
    response_text: str
    response_audio: str  # Base64 encoded audio
    transcribed_text: str  # The transcribed text from the voice input
    candidate_info: Dict[str, Any]
    conversation_id: str


class ProfileData(BaseModel):
    full_name: Optional[str] = None
    location: Optional[str] = None
    age: Optional[str] = None
    physical_condition: Optional[str] = None
    interests: Optional[str] = None
    limitations: Optional[str] = None


class ProfileUpdateRequest(BaseModel):
    conversation_id: str
    updates: ProfileData


class ProfileUpdateResponse(BaseModel):
    message: str
    candidate_info: Dict[str, Any]
    conversation_id: str


class FieldChangeJudgeRequest(BaseModel):
    conversation_id: str
    field: str
    proposed_value: str
    current_value: Optional[str] = None
    message: str


class FieldChangeJudgeResponse(BaseModel):
    should_prompt: bool
    confidence: float
    reason: Optional[str] = None


@router.post("/chat", response_model=ChatResponse)
async def chat_with_bot(
    message: ChatMessage,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional),
):
    """
    Send a text message to the chatbot and get a response.
    """
    if not chatbot_available:
        raise HTTPException(status_code=503, detail="Chatbot functionality is not available")
    
    try:
        # Get or create chatbot instance for this conversation
        conversation_id = message.conversation_id or f"anon_{datetime.now().timestamp()}"
        
        if conversation_id not in chatbot_sessions:
            # Disable server-side audio playback by default to avoid noisy decoder errors
            chatbot_sessions[conversation_id] = CandidateChatbot(enable_audio=False)
        
        chatbot = chatbot_sessions[conversation_id]

        # If a user is authenticated and has a saved profile, seed it once per session
        try:
            if current_user is not None and getattr(chatbot, "_seeded_from_profile", False) is not True:
                from .. import crud
                profile = crud.get_candidate_profile(db, current_user.id)
                if profile:
                    chatbot.seed_profile({
                        "full_name": profile.full_name,
                        "location": profile.location,
                        "age": profile.age,
                        "physical_condition": profile.physical_condition,
                        "interests": profile.interests,
                        "limitations": profile.limitations,
                    })
                    chatbot._seeded_from_profile = True  # mark to avoid re-seeding
        except Exception:
            # Non-fatal; continue without seeding
            pass
        
        # Process the message with database session
        response, candidate_info = await chatbot.process_message(
            message.message, 
            conversation_id,
            db_session=db
        )
        
        return ChatResponse(
            response=response,
            candidate_info=candidate_info,
            conversation_id=conversation_id
        )
    except Exception as e:
        logger.exception("[chatbot.py] Error in chat endpoint: %s", e)
        raise HTTPException(status_code=500, detail="Failed to process chat message")


@router.post("/voice", response_model=VoiceResponse)
async def voice_chat_with_bot(
    request: VoiceRequest,
    db: Session = Depends(get_db)
):
    """
    Send a voice message to the chatbot and get a text and voice response.
    """
    if not chatbot_available:
        raise HTTPException(status_code=503, detail="Chatbot functionality is not available")
    
    try:
        # Get or create chatbot instance for this conversation
        conversation_id = request.conversation_id or f"anon_{datetime.now().timestamp()}"
        
        if conversation_id not in chatbot_sessions:
            # Disable server-side audio playback by default to avoid noisy decoder errors
            chatbot_sessions[conversation_id] = CandidateChatbot(enable_audio=False)
        
        chatbot = chatbot_sessions[conversation_id]
        
        # Convert voice to text (speech-to-text)
        transcribed_text = await voice_service.speech_to_text(request.audio_data)
        
        # Process the transcribed text with database session
        response_text, candidate_info = await chatbot.process_message(
            transcribed_text, 
            conversation_id,
            db_session=db
        )
        
        # Convert response text to speech (text-to-speech)
        response_audio = await voice_service.text_to_speech(response_text)
        
        return VoiceResponse(
            response_text=response_text,
            response_audio=response_audio,
            transcribed_text=transcribed_text,
            candidate_info=candidate_info,
            conversation_id=conversation_id
        )
    except Exception as e:
        logger.error(f"[chatbot.py] Error in voice chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process voice message")


@router.post("/profile/update", response_model=ProfileUpdateResponse)
async def update_profile_details(
    request: ProfileUpdateRequest
):
    """Manually update the candidate profile and revalidate it."""
    if not chatbot_available:
        raise HTTPException(status_code=503, detail="Chatbot functionality is not available")

    try:
        conversation_id = request.conversation_id
        if not conversation_id:
            raise HTTPException(status_code=400, detail="conversation_id is required")

        if conversation_id not in chatbot_sessions:
            chatbot_sessions[conversation_id] = CandidateChatbot(enable_audio=True)

        chatbot = chatbot_sessions[conversation_id]

        updates = request.updates.model_dump(exclude_unset=True)
        message = await chatbot.apply_manual_update(updates)

        return ProfileUpdateResponse(
            message=message,
            candidate_info=chatbot.candidate_info,
            conversation_id=conversation_id
        )
    except HTTPException:
        raise
    except Exception as e:  # pylint: disable=broad-except
        logger.error(f"[chatbot.py] Error updating profile: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update profile information")


@router.post("/profile/judge-change", response_model=FieldChangeJudgeResponse)
async def judge_profile_change(request: FieldChangeJudgeRequest):
    """Ask the LLM judge whether a field change likely reflects a new answer."""
    if not chatbot_available:
        raise HTTPException(status_code=503, detail="Chatbot functionality is not available")

    try:
        conversation_id = request.conversation_id
        if not conversation_id:
            raise HTTPException(status_code=400, detail="conversation_id is required")

        if conversation_id not in chatbot_sessions:
            chatbot_sessions[conversation_id] = CandidateChatbot(enable_audio=True)

        chatbot = chatbot_sessions[conversation_id]

        decision = await chatbot.judge_field_change(
            request.field,
            request.proposed_value,
            request.current_value,
            request.message
        )

        return FieldChangeJudgeResponse(
            should_prompt=bool(decision.get("should_replace")),
            confidence=float(decision.get("confidence", 0.0)),
            reason=decision.get("reason")
        )
    except HTTPException:
        raise
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("[chatbot.py] Error judging profile change: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to evaluate profile change")


@router.post("/reset")
async def reset_chatbot(
    conversation_id: Optional[str] = None
):
    """
    Reset the chatbot conversation state.
    """
    if not chatbot_available:
        raise HTTPException(status_code=503, detail="Chatbot functionality is not available")
    
    try:
        conversation_id = conversation_id or f"anon_{datetime.now().timestamp()}"
        
        if conversation_id in chatbot_sessions:
            chatbot_sessions[conversation_id].reset_conversation()
        
        return {"message": "Chatbot conversation reset successfully"}
    except Exception as e:
        logger.error(f"[chatbot.py] Error resetting chatbot: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to reset chatbot")
