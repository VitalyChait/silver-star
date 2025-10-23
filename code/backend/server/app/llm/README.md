# Silver Star LLM Module

This module provides LLM-powered chatbot functionality for the Silver Star job recruitment platform.

## Components

### 1. Configuration (`config.py`)
- Handles configuration for LLM services
- Reads from `.llm_config` file for API keys and settings
- Supports both Google Gemini AI Studio and Vertex AI providers

### 2. LLM Service (`service.py`)
- Provides a wrapper around Google's Gemini API
- Handles text generation and structured data extraction
- Manages conversation history and context

### 3. Voice Service (`voice.py`)
- Provides speech-to-text and text-to-speech capabilities
- Uses Google Cloud Speech-to-Text and Text-to-Speech APIs
- Handles audio encoding/decoding

### 4. Chatbot (`chatbot.py`)
- Implements the conversation flow for gathering candidate information
- Collects: name, location, what they're looking for, skills, availability
- Provides job recommendations based on candidate profile

### 5. Job Recommendations (`recommendations.py`)
- Generates personalized job recommendations using LLM
- Matches candidates with jobs based on skills, location, and preferences
- Provides match scores and reasoning for recommendations

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

Create a `.llm_config` file in the `backend/llm/` directory with the following format:

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

- `google-generativeai`: For Gemini API integration
- `google-cloud-speech`: For speech-to-text
- `google-cloud-texttospeech`: For text-to-speech

## Usage

1. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure your API keys in the `.llm_config` file

3. Start the backend server:
   ```bash
   cd backend/server
   uvicorn app.main:app --reload
   ```

4. Access the chatbot UI at `http://localhost:3000/chatbot`

## Features

- Text-based conversation with the chatbot
- Voice input/output capabilities
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
