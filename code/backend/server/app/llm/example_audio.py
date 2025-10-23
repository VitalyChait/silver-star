import asyncio
import logging

from .audio_player import audio_player

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Example of using the audio player directly."""
    print("Audio Player Example")
    print("=" * 30)
    
    # Test messages to play
    messages = [
        "Hello, welcome to Silver Star recruitment.",
        "We're excited to help you find your dream job.",
        "Our chatbot can guide you through the application process.",
        "Thank you for your interest in joining our team."
    ]
    
    for i, message in enumerate(messages, 1):
        print(f"\nPlaying message {i}: {message}")
        
        # Play the message as audio
        success = await audio_player.play_text(message)
        
        if success:
            print("Audio played successfully!")
        else:
            print("Failed to play audio.")
        
        # Wait a moment between messages
        await asyncio.sleep(1)
    
    print("\nExample complete!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExample interrupted by user")
    except Exception as e:
        print(f"Error during example: {str(e)}")
