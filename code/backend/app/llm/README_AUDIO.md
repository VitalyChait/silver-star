# Audio-Enabled Chatbot

This module provides text-to-speech functionality for the Silver Star chatbot, allowing users to have a full conversation without looking at the screen.

## Location

The audio functionality is located in the `audio/` subdirectory of the LLM module:

```
llm/audio/
├── __init__.py              # Package exports
├── voice.py                 # Speech-to-text and text-to-speech
└── audio_player.py          # Audio playback functionality
```

## Features

- Converts chatbot text responses to speech
- Plays audio directly to the user
- Supports both Google Cloud Text-to-Speech and local fallback (pyttsx3)
- Easy integration with existing chatbot functionality

## Installation

To use the audio functionality, you'll need to install the following dependencies:

```bash
# Dependencies are managed in backend/pyproject.toml
cd backend
uv sync
```

The audio-specific dependencies are:
- **pygame**: Required for audio playback
- **pyttsx3**: Local text-to-speech engine (fallback)
- **google-cloud-texttospeech**: Google Cloud Text-to-Speech (optional)

## Usage

### Basic Usage

```python
from llm import CandidateChatbot

# Create a chatbot with audio enabled
chatbot = CandidateChatbot(enable_audio=True)

# Process a message - the response will be played as audio
response, candidate_info = await chatbot.process_message("Hi, I'm looking for a job")
```

### Direct Audio Playback

```python
from llm.audio import AudioPlayer

# Create an audio player instance
player = AudioPlayer()

# Play text as speech
await player.play_text("Hello, this is a test message")
```

### Voice Service

```python
from llm.audio import VoiceService

# Create a voice service instance
voice_service = VoiceService()

# Convert text to speech (returns base64 encoded audio)
audio_base64 = await voice_service.text_to_speech("Hello, this is a test message")
```

## Configuration

The audio functionality uses the same environment variables defined in `code/.env` for Google Cloud Text-to-Speech configuration. If Google Cloud is not available, it will fall back to the local pyttsx3 engine.

## Dependencies

- **pygame**: Required for audio playback
- **pyttsx3**: Local text-to-speech engine (fallback)
- **google-cloud-texttospeech**: Google Cloud Text-to-Speech (optional)

## Notes

- The audio player creates temporary files for audio playback and cleans them up automatically
- If audio playback fails, the chatbot will continue to function normally with text responses
- The audio player is initialized as a singleton to avoid resource conflicts

## Troubleshooting

1. **Audio not playing**: Make sure pygame is installed and your system has audio capabilities
2. **Text-to-speech not working**: Check that either Google Cloud credentials are configured or pyttsx3 is installed
3. **Import errors**: Ensure all dependencies are properly installed

## Examples

See the `examples/` directory for example scripts:
- `example_audio.py`: Demonstrates direct audio playback
- `test_audio_chatbot.py`: Shows how to use the audio-enabled chatbot
