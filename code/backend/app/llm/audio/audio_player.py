import asyncio
import base64
import io
import logging
import os
import tempfile
from typing import Optional

import pygame
from .voice import voice_service

logger = logging.getLogger(__name__)


class AudioPlayer:
    """Service for playing audio responses from the chatbot."""
    
    def __init__(self):
        """Initialize the audio player."""
        self._initialized = False
        self._temp_dir = None
        self._init_audio()
    
    def _init_audio(self):
        """Initialize the audio system."""
        try:
            # Initialize pygame mixer for audio playback
            pygame.mixer.init()
            self._initialized = True
            
            # Create a temporary directory for audio files
            self._temp_dir = tempfile.mkdtemp()
            logger.info("[audio_player.py] Audio player initialized successfully")
        except Exception as e:
            logger.error(f"[audio_player.py] Failed to initialize audio player: {str(e)}")
            self._initialized = False
    
    async def play_text(self, text: str, language_code: str = "en-US", voice_name: Optional[str] = None) -> bool:
        """
        Convert text to speech and play it.
        
        Args:
            text: Text to convert to speech and play
            language_code: Language code for the voice (e.g., "en-US")
            voice_name: Name of the voice to use (optional)
            
        Returns:
            True if playback was successful, False otherwise
        """
        if not self._initialized:
            logger.warning("[audio_player.py] Audio player not initialized, cannot play text")
            return False
        
        try:
            # Convert text to speech using the voice service
            audio_base64 = await voice_service.text_to_speech(
                text=text,
                language_code=language_code,
                voice_name=voice_name
            )
            
            if not audio_base64:
                logger.error("[audio_player.py] Failed to convert text to speech")
                return False
            
            # Decode the base64 audio data
            audio_bytes = base64.b64decode(audio_base64)
            
            # Create a temporary file for the audio
            with tempfile.NamedTemporaryFile(dir=self._temp_dir, suffix=".mp3", delete=False) as temp_file:
                temp_file.write(audio_bytes)
                temp_file_path = temp_file.name
            
            # Play the audio file
            success = await self._play_audio_file(temp_file_path)
            
            # Clean up the temporary file
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"[audio_player.py] Failed to delete temporary audio file: {str(e)}")
            
            return success
        except Exception as e:
            logger.error(f"[audio_player.py] Error playing text: {str(e)}")
            return False
    
    async def _play_audio_file(self, file_path: str) -> bool:
        """
        Play an audio file.
        
        Args:
            file_path: Path to the audio file
            
        Returns:
            True if playback was successful, False otherwise
        """
        try:
            # Load and play the audio file
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            
            # Wait for the audio to finish playing
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.1)
            
            return True
        except Exception as e:
            logger.error(f"[audio_player.py] Error playing audio file: {str(e)}")
            return False
    
    def cleanup(self):
        """Clean up resources."""
        try:
            if self._temp_dir and os.path.exists(self._temp_dir):
                import shutil
                shutil.rmtree(self._temp_dir)
                logger.info("[audio_player.py] Cleaned up temporary audio files")
        except Exception as e:
            logger.error(f"[audio_player.py] Error during cleanup: {str(e)}")


# Create a singleton instance
audio_player = AudioPlayer()
