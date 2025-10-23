"""
LLM module for Silver Star chatbot functionality.
"""

import sys
import os

# Set up global error handling to terminate fast on errors
def handle_exception(exc_type, exc_value, exc_traceback):
    """Global exception handler to terminate fast on errors."""
    import traceback
    print(f"Fatal error in LLM module: {exc_type.__name__}: {exc_value}", file=sys.stderr)
    print("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)), file=sys.stderr)
    sys.exit(1)

# Install the global exception handler
sys.excepthook = handle_exception

# Try to import the components, but don't exit if dependencies are missing
# This allows the module to be imported for testing purposes
try:
    from .config import LLMConfig
    from .service import LLMService
    from .chatbot import CandidateChatbot
    from .voice import VoiceService
    from .audio_player import AudioPlayer
    
    __all__ = ["LLMConfig", "LLMService", "CandidateChatbot", "VoiceService", "AudioPlayer"]
except ImportError as e:
    print(f"Warning: Could not import LLM module components: {e}", file=sys.stderr)
    print("This may be due to missing dependencies. The chatbot functionality will not be available.", file=sys.stderr)
    
    # Create placeholder classes to prevent import errors
    class LLMConfig:
        def __init__(self):
            raise ImportError("LLM dependencies not installed")
    
    class LLMService:
        def __init__(self):
            raise ImportError("LLM dependencies not installed")
    
    class CandidateChatbot:
        def __init__(self):
            raise ImportError("LLM dependencies not installed")
    
    class VoiceService:
        def __init__(self):
            raise ImportError("LLM dependencies not installed")
    
    class AudioPlayer:
        def __init__(self):
            raise ImportError("LLM dependencies not installed")
    
    __all__ = ["LLMConfig", "LLMService", "CandidateChatbot", "VoiceService", "AudioPlayer"]
