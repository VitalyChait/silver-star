import logging
from typing import Dict, List, Optional, Any

from .service import llm_service

logger = logging.getLogger(__name__)


class AnswerValidator:
    """Validates if user answers address the specific questions asked by the chatbot."""
    
    def __init__(self):
        """Initialize the answer validator."""
        pass
    
    async def validate_answer(
        self, 
        question: str, 
        answer: str, 
        question_type: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Validate if the user's answer addresses the specific question asked.
        
        Args:
            question: The question that was asked to the user
            answer: The user's response
            question_type: The type of question (name, location, etc.)
            conversation_history: Previous conversation messages
            
        Returns:
            Dictionary with validation results including:
            - is_valid: Boolean indicating if the answer is valid
            - extracted_value: The extracted value if valid
            - confidence: Confidence score (0-1)
            - needs_clarification: If the answer needs clarification
        """
        validation_prompt = f"""
        You are an answer validation assistant for a job recruitment chatbot.
        
        The chatbot asked this question: "{question}"
        The user responded with: "{answer}"
        The question type is: {question_type}
        
        Your task is to determine:
        1. Did the user answer the question? (true/false)
        2. If yes, extract the specific value that answers the question
        3. How confident are you in this assessment? (0.0-1.0)
        4. Does the answer need clarification? (true/false)
        
        Important guidelines:
        - If the user says "I'm an AI" or "I don't have a name/location/etc", this is NOT a valid answer
        - If the user provides a name, location, or other requested information, it IS a valid answer
        - If the user asks a question instead of answering, it's NOT a valid answer
        - If the user says they don't know or can't answer, it's NOT a valid answer
        
        Respond with valid JSON only:
        {{
            "is_valid": true/false,
            "extracted_value": "the extracted value or null",
            "confidence": 0.0-1.0,
            "needs_clarification": true/false,
            "reason": "brief explanation of your decision"
        }}
        """
        
        try:
            response = await llm_service.generate_response(
                validation_prompt,
                conversation_history,
                temperature=0.2  # Lower temperature for more consistent validation
            )
            
            # Parse the JSON response
            import json
            result = json.loads(response)
            
            # Ensure all required fields are present
            if not all(key in result for key in ["is_valid", "extracted_value", "confidence", "needs_clarification", "reason"]):
                logger.warning(f"Validation response missing required fields: {response}")
                return {
                    "is_valid": False,
                    "extracted_value": None,
                    "confidence": 0.0,
                    "needs_clarification": True,
                    "reason": "Invalid validation response format"
                }
            
            return result
        except Exception as e:
            logger.error(f"Error validating answer: {str(e)}")
            return {
                "is_valid": False,
                "extracted_value": None,
                "confidence": 0.0,
                "needs_clarification": True,
                "reason": f"Validation error: {str(e)}"
            }


# Create a singleton instance
answer_validator = AnswerValidator()
