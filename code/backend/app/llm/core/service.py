import json
import logging
import os
from typing import Dict, List, Optional, Any

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold


logger = logging.getLogger(__name__)


class LLMService:
    """Service for interacting with LLM APIs (Gemini)."""
    
    def __init__(self):
        """Initialize the LLM service with configuration."""
        self._initialize_gemini()
    
    def _initialize_gemini(self):
        """Initialize the Gemini API client."""
        try:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            
            # Configure safety settings
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }
            
            # Initialize the model
            self.model = genai.GenerativeModel(
                model_name=os.getenv("GEMINI_MODEL"),
                safety_settings=safety_settings
            )
            
            logger.info(f"Initialized Gemini model: {os.getenv('GEMINI_MODEL')}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {str(e)}")
            raise
    
    async def generate_response(
        self,
        prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_output_tokens: int = 1024
    ) -> str:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: The prompt to send to the LLM
            conversation_history: Previous conversation messages
            temperature: Controls randomness (0.0-1.0)
            max_output_tokens: Maximum number of tokens to generate
            
        Returns:
            The generated text response
        """
        try:
            # Prepare the conversation
            if conversation_history:
                # Convert history to Gemini format
                gemini_history = []
                for message in conversation_history:
                    role = "user" if message["role"] == "user" else "model"
                    gemini_history.append({
                        "role": role,
                        "parts": [{"text": message["content"]}]
                    })
                
                # Start a chat with history
                chat = self.model.start_chat(history=gemini_history)
                response = await chat.send_message_async(
                    prompt,
                    generation_config={
                        "temperature": temperature,
                        "max_output_tokens": max_output_tokens,
                    }
                )
            else:
                # Simple prompt without history
                response = await self.model.generate_content_async(
                    prompt,
                    generation_config={
                        "temperature": temperature,
                        "max_output_tokens": max_output_tokens,
                    }
                )
            
            # Check if the response was filtered
            if not response.candidates:
                logger.error("Gemini returned no candidates. prompt=%r", prompt[:200])
                return "I'm having trouble generating a response right now. Could you please try again?"

            candidate = next(
                (
                    c for c in response.candidates
                    if getattr(c, "content", None)
                    and getattr(c.content, "parts", None)
                ),
                response.candidates[0]
            )

            finish_reason = getattr(candidate, "finish_reason", None)
            finish_reason_name = getattr(finish_reason, "name", str(finish_reason))

            if finish_reason_name == "SAFETY":
                logger.warning("Response was filtered for safety reasons. prompt=%r", prompt[:200])
                return "I apologize, but I cannot provide a response to that request due to safety guidelines."
            if finish_reason_name == "MAX_TOKENS":
                history_chars = 0
                if conversation_history:
                    history_chars = sum(len(entry.get("content", "")) for entry in conversation_history)
                logger.warning(
                    "Gemini hit token limit. prompt_chars=%d history_chars=%d max_output_tokens=%s",
                    len(prompt),
                    history_chars,
                    max_output_tokens,
                )

            text_parts: List[str] = []
            if getattr(candidate, "content", None) and getattr(candidate.content, "parts", None):
                for part in candidate.content.parts:
                    part_text = getattr(part, "text", None)
                    if part_text:
                        text_parts.append(part_text)

            generated_text = "".join(text_parts).strip()

            if generated_text:
                return generated_text

            # Fall back to response.text accessor if available
            try:
                generated_text = getattr(response, "text", "").strip()
                if generated_text:
                    return generated_text
            except Exception as text_error:  # pylint: disable=broad-except
                logger.error(
                    "Gemini response.text accessor failed: %s. finish_reason=%s",
                    text_error,
                    finish_reason_name
                )

            logger.error(
                "Gemini returned no textual content. finish_reason=%s prompt_preview=%r",
                finish_reason_name,
                prompt[:200]
            )
            if finish_reason_name == "MAX_TOKENS":
                logger.info(
                    "User prompt exceeded generation limits; ask the user to simplify input."
                )
            return "I'm having trouble generating a response right now. Could you please try again?"
        except Exception as e:
            logger.exception("Unexpected Gemini error for prompt %r: %s", prompt[:200], e)
            # Return a fallback response instead of raising an exception
            return "I'm having trouble generating a response right now. Could you please try again?"
    
    async def extract_structured_data(
        self, 
        prompt: str, 
        schema: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Extract structured data from text using the LLM.
        
        Args:
            prompt: The prompt containing text to extract from
            schema: JSON schema describing the expected structure
            conversation_history: Previous conversation messages
            
        Returns:
            Extracted data as a dictionary
        """
        extraction_prompt = f"""
        Extract the following information from the text and respond with valid JSON only:
        
        Schema: {json.dumps(schema)}
        
        Text: {prompt}
        
        Response:
        """
        
        response = await self.generate_response(
            extraction_prompt,
            conversation_history,
            temperature=0.2  # Lower temperature for more consistent extraction
        )
        
        try:
            # Handle response wrapped in markdown code blocks
            if response.startswith('```json'):
                response = response[7:]  # Remove ```json
            if response.startswith('```'):
                response = response[3:]   # Remove ```
            if response.endswith('```'):
                response = response[:-3]  # Remove ```
            
            # Strip whitespace
            response = response.strip()
            
            # Parse the JSON response
            return json.loads(response)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON response: {response}")
            # Return empty structure with the same schema
            return {key: None for key in schema.keys()}


# Create a singleton instance
llm_service = LLMService()
