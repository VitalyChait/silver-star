"""
Audio functionality for the LLM module.
"""

from .voice import voice_service, VoiceService
from .audio_player import audio_player, AudioPlayer

__all__ = ["voice_service", "VoiceService", "audio_player", "AudioPlayer"]
