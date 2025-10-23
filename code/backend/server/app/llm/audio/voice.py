import base64
import io
import logging
from typing import Optional

try:
    from google.cloud import speech_v1p1beta1 as speech
    from google.cloud import texttospeech
    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    GOOGLE_CLOUD_AVAILABLE = False
    logging.warning("Google Cloud Speech libraries not available. Using fallback implementation.")

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False
    logging.warning("pyttsx3 not available. Text-to-speech will not work without Google Cloud.")

from ..core.config import llm_config

logger = logging.getLogger(__name__)


class VoiceService:
    """Service for speech-to-text and text-to-speech conversion."""
    
    def __init__(self):
        """Initialize the voice service."""
        self.config = llm_config
        self._init_speech_client()
        self._init_tts_client()
        self._init_fallback_tts()
    
    def _init_speech_client(self):
        """Initialize the Google Cloud Speech-to-Text client."""
        if not GOOGLE_CLOUD_AVAILABLE:
            logger.warning("Google Cloud Speech libraries not available")
            self.speech_client = None
            return
            
        try:
            # In a real implementation, you would use Google Cloud credentials
            # For now, we'll create a placeholder
            self.speech_client = None
            logger.info("Speech-to-Text client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Speech-to-Text client: {str(e)}")
            self.speech_client = None
    
    def _init_tts_client(self):
        """Initialize the Google Cloud Text-to-Speech client."""
        if not GOOGLE_CLOUD_AVAILABLE:
            logger.warning("Google Cloud Speech libraries not available")
            self.tts_client = None
            return
            
        try:
            # In a real implementation, you would use Google Cloud credentials
            # For now, we'll create a placeholder
            self.tts_client = None
            logger.info("Text-to-Speech client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Text-to-Speech client: {str(e)}")
            self.tts_client = None
    
    def _init_fallback_tts(self):
        """Initialize the fallback text-to-speech engine."""
        if not PYTTSX3_AVAILABLE:
            logger.warning("pyttsx3 not available for fallback TTS")
            self.fallback_tts_engine = None
            return
            
        try:
            self.fallback_tts_engine = pyttsx3.init()
            logger.info("Fallback TTS engine initialized")
        except Exception as e:
            logger.error(f"Failed to initialize fallback TTS engine: {str(e)}")
            self.fallback_tts_engine = None
    
    async def speech_to_text(self, audio_data: str, language_code: str = "en-US") -> str:
        """
        Convert audio data to text using speech-to-text.
        
        Args:
            audio_data: Base64 encoded audio data
            language_code: Language code for the audio (e.g., "en-US")
            
        Returns:
            Transcribed text
        """
        if not self.speech_client:
            # Placeholder implementation
            logger.warning("Speech-to-Text client not initialized, returning placeholder")
            return "This is a placeholder for speech-to-text conversion"
        
        try:
            # Decode the base64 audio data
            audio_bytes = base64.b64decode(audio_data)
            
            # Configure the request
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
                sample_rate_hertz=48000,
                language_code=language_code,
                enable_automatic_punctuation=True,
            )
            
            # Create the audio content
            audio = speech.RecognitionAudio(content=audio_bytes)
            
            # Perform the recognition
            response = self.speech_client.recognize(config=config, audio=audio)
            
            # Extract the transcript
            if response.results:
                transcript = response.results[0].alternatives[0].transcript
                return transcript
            else:
                return ""
        except Exception as e:
            logger.error(f"Error in speech-to-text conversion: {str(e)}")
            return ""
    
    async def text_to_speech(
        self, 
        text: str, 
        language_code: str = "en-US",
        voice_name: Optional[str] = None
    ) -> str:
        """
        Convert text to audio using text-to-speech.
        
        Args:
            text: Text to convert to speech
            language_code: Language code for the voice (e.g., "en-US")
            voice_name: Name of the voice to use (optional)
            
        Returns:
            Base64 encoded audio data
        """
        if self.tts_client:
            try:
                # Set the voice selection parameters
                if not voice_name:
                    # Default voice based on language
                    voice_name = "en-US-Neural2-J" if language_code.startswith("en") else "default"
                
                voice = texttospeech.VoiceSelectionParams(
                    language_code=language_code,
                    name=voice_name
                )
                
                # Select the type of audio file
                audio_config = texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.MP3
                )
                
                # Perform the text-to-speech request
                synthesis_input = texttospeech.SynthesisInput(text=text)
                response = self.tts_client.synthesize_speech(
                    input=synthesis_input, voice=voice, audio_config=audio_config
                )
                
                # Encode the audio data as base64
                audio_base64 = base64.b64encode(response.audio_content).decode("utf-8")
                return audio_base64
            except Exception as e:
                logger.error(f"Error in Google Cloud text-to-speech conversion: {str(e)}")
                # Fall back to local TTS if Google Cloud fails
        
        # Fallback to local TTS if available
        if self.fallback_tts_engine:
            try:
                # Save the speech to a temporary file
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                    temp_path = temp_file.name
                
                # Generate speech using pyttsx3
                self.fallback_tts_engine.save_to_file(text, temp_path)
                self.fallback_tts_engine.runAndWait()
                
                # Read the file and encode as base64
                with open(temp_path, "rb") as audio_file:
                    audio_data = audio_file.read()
                
                # Clean up the temporary file
                import os
                os.unlink(temp_path)
                
                # Return the base64 encoded audio
                return base64.b64encode(audio_data).decode("utf-8")
            except Exception as e:
                logger.error(f"Error in fallback text-to-speech conversion: {str(e)}")
        
        # If all else fails, return a placeholder
        logger.warning("No text-to-speech engine available, returning placeholder")
        return ""


# Create a singleton instance
voice_service = VoiceService()
