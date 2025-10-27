# Silver Star LLM Module

This module provides LLM-powered chatbot functionality for the Silver Star job recruitment platform.

## Directory Structure

```
llm/
├── __init__.py              # Main module exports
├── README.md                # This file
├── README_AUDIO.md          # Audio functionality documentation
├── .llm_config              # Configuration file (create from llm_config_example)
├── llm_config_example       # Example configuration file
├── core/                    # Core functionality
│   ├── __init__.py
│   ├── config.py            # Configuration management
│   └── service.py           # LLM service wrapper
├── chatbot/                 # Chatbot functionality
│   ├── __init__.py
│   ├── chatbot.py           # Main chatbot implementation
│   ├── recommendations.py   # Job recommendation service
│   └── validation.py        # Answer validation service
├── audio/                   # Audio functionality
│   ├── __init__.py
│   ├── voice.py             # Speech-to-text and text-to-speech
│   └── audio_player.py      # Audio playback functionality
├── examples/                # Example scripts
│   ├── __init__.py
│   ├── example_audio.py     # Audio player example
│   └── test_audio_chatbot.py # Audio-enabled chatbot test
└── tests/                   # Test scripts
    ├── __init__.py
    └── test_chatbot.py      # Chatbot functionality test
```

## Components

### 1. Core (`core/`)
- **Configuration (`config.py`)**: Handles configuration for LLM services, reads from `.llm_config` file
- **LLM Service (`service.py`)**: Provides a wrapper around Google's Gemini API

### 2. Chatbot (`chatbot/`)
- **Chatbot (`chatbot.py`)**: Implements the conversation flow for gathering candidate information
- **Job Recommendations (`recommendations.py`)**: Generates personalized job recommendations
- **Validation (`validation.py`)**: Validates user answers to chatbot questions

### 3. Audio (`audio/`)
- **Voice Service (`voice.py`)**: Provides speech-to-text and text-to-speech capabilities
- **Audio Player (`audio_player.py`)**: Converts chatbot text responses to speech and plays them

## API Endpoints

### Text Chat
```
POST /api/chatbot/chat
{
  "message": "Hello, I'm looking for a job",
  "conversation_id": "optional-conversation-id"
}
```

### Voice Chat
```
POST /api/chatbot/voice
{
  "audio_data": "base64-encoded-audio",
  "conversation_id": "optional-conversation-id"
}
```

### Reset Conversation
```
POST /api/chatbot/reset
{
  "conversation_id": "optional-conversation-id"
}
```

## Configuration

Create a `.llm_config` file in the `backend/app/llm/` directory with the following format:

```
# Required: Gemini API Configuration
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash

# Provider: Choose ONE ("vertex" or "ai_studio")
GEMINI_PROVIDER=ai_studio

# Vertex AI Settings (only required if GEMINI_PROVIDER=vertex)
GEMINI_VERTEX_REGION=us-central1
GEMINI_VERTEX_PROJECT=your-gcp-project-id

# OpenRouter fallback configuration (optional)
OPENROUTER_API_KEY=your-openrouter-api-key
OPENROUTER_MODEL=z-ai/glm-4.6
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1/chat/completions
```

## Dependencies

The following Python packages are required:

### Core Dependencies
- `google-generativeai`: For Gemini API integration
- `google-cloud-speech`: For speech-to-text
- `google-cloud-texttospeech`: For text-to-speech

### Audio Functionality Dependencies
- `pygame`: Required for audio playback
- `pyttsx3`: Local text-to-speech engine (fallback)

All dependencies are listed in the main `requirements.txt` file in the server directory.

## Usage

1. Install the required dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. Configure your API keys in the `.llm_config` file

3. Start the backend server:
   ```bash
   cd backend
   uvicorn app.main:app --reload
   ```

4. Access the chatbot UI at `http://localhost:3000/chatbot`

## Audio-Enabled Chatbot

To enable audio playback of chatbot responses:

```python
from llm import CandidateChatbot

# Create a chatbot with audio enabled
chatbot = CandidateChatbot(enable_audio=True)

# Process a message - the response will be played as audio
response, candidate_info = await chatbot.process_message("Hi, I'm looking for a job")
```

For more details on the audio functionality, see [README_AUDIO.md](README_AUDIO.md).

## Features

- Text-based conversation with the chatbot
- Voice input/output capabilities
- Audio playback of chatbot responses (optional)
- Personalized job recommendations
- Candidate information collection
- Conversation state management
- Error handling and fallback responses

## Future Enhancements

- Integration with more job boards
- Advanced candidate-job matching algorithms
- Multi-language support
- Conversation analytics
- Integration with applicant tracking systems
- Voice-activated conversation flow
