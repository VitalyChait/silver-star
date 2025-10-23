#!/usr/bin/env python3
"""
Test script for the Silver Star chatbot functionality.
This script tests the basic chatbot flow without requiring a full server setup.
"""

import asyncio
import sys
import os

# Add the parent directory to the path so we can import the modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm import CandidateChatbot


async def test_chatbot():
    """Test the chatbot conversation flow."""
    print("Starting Silver Star Chatbot Test")
    print("=" * 50)
    
    # Create a new chatbot instance
    chatbot = CandidateChatbot()
    
    # Simulate a conversation
    test_messages = [
        "Hello",
        "My name is John Doe",
        "I'm located in New York",
        "I'm looking for a software engineering position",
        "I have experience with Python, JavaScript, and React",
        "I'm available to start immediately"
    ]
    
    for message in test_messages:
        print(f"\nUser: {message}")
        
        # Process the message
        response, candidate_info = await chatbot.process_message(message)
        
        print(f"Bot: {response}")
        print(f"State: {chatbot.conversation_state}")
        print(f"Info: {candidate_info}")
    
    print("\n" + "=" * 50)
    print("Test completed successfully!")


if __name__ == "__main__":
    # Run the test
    asyncio.run(test_chatbot())
