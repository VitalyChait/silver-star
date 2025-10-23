import asyncio
import logging
import sys

from .chatbot import CandidateChatbot

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_audio_chatbot():
    """Test the audio-enabled chatbot."""
    print("Testing Audio-Enabled Chatbot")
    print("=" * 40)
    
    # Create a chatbot with audio enabled
    chatbot = CandidateChatbot(enable_audio=True)
    
    # Simulate a conversation
    test_messages = [
        "Hi, I'm John",
        "I'm from New York",
        "I'm looking for a software engineering position",
        "I have experience with Python, JavaScript, and React",
        "I'm available to start immediately"
    ]
    
    for message in test_messages:
        print(f"\nUser: {message}")
        
        # Process the message and get a response
        response, candidate_info = await chatbot.process_message(message)
        
        print(f"Chatbot: {response}")
        print("(Audio should be playing now...)")
        
        # Wait a moment for the audio to play
        await asyncio.sleep(2)
    
    print("\nConversation complete!")
    print("Candidate Info:", candidate_info)


if __name__ == "__main__":
    try:
        asyncio.run(test_audio_chatbot())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Error during test: {str(e)}")
        sys.exit(1)
