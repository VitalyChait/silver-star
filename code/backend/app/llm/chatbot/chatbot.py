import json
import logging
from typing import Dict, List, Optional, Tuple, Any
import re

from ..core.service import llm_service
from .recommendations import job_recommendation_service
from .validation import answer_validator
from ..audio.audio_player import audio_player

logger = logging.getLogger(__name__)


class CandidateChatbot:
    """Chatbot for gathering candidate information and recommending jobs."""
    
    def __init__(self, enable_audio: bool = False):
        """
        Initialize the chatbot.
        
        Args:
            enable_audio: Whether to enable audio playback of responses
        """
        self.conversation_state = "greeting"
        self.candidate_info = {
            "name": None,
            "location": None,
            "looking_for": None,
            "skills": None,
            "availability": None
        }
        self.conversation_history = []
        self.db_session = None  # Will be set when processing messages
        self.last_question = None  # Track the last question asked
        self.last_question_type = None  # Track the type of the last question
        self.enable_audio = enable_audio  # Whether to play audio responses
    
    async def process_message(
        self, 
        message: str, 
        conversation_id: Optional[str] = None,
        db_session=None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Process a user message and generate a response.
        
        Args:
            message: The user's message
            conversation_id: Optional conversation identifier
            db_session: Database session for job recommendations
            
        Returns:
            Tuple of (response_text, updated_candidate_info)
        """
        # Store the database session for use in recommendations
        self.db_session = db_session
        
        # Add user message to history
        self.conversation_history.append({"role": "user", "content": message})
        
        validated_value = None
        # If we asked a question in the previous turn, validate the answer
        if self.last_question and self.last_question_type:
            validation_result = await answer_validator.validate_answer(
                self.last_question,
                message,
                self.last_question_type,
                self.conversation_history
            )
            
            # If the answer is not valid, ask the question again
            if validation_result.get("is_valid", False):
                validated_value = validation_result.get("extracted_value")
                if isinstance(validated_value, str):
                    validated_value = validated_value.strip()
            else:
                prompt = f"""
                You are a job recruitment assistant for Silver Star.
                The user didn't answer your question properly.
                Ask them the same question again in a different way.
                Do not mention being an AI or assistant.
                Your previous question was: "{self.last_question}"
                """
                
                response = await llm_service.generate_response(prompt)
                self.conversation_history.append({"role": "assistant", "content": response})
                
                # Play the response as audio if enabled
                if self.enable_audio:
                    await self._play_response_audio(response)
                
                # Update the last question
                self.last_question = response
                # Keep the same question type
                
                return response, self.candidate_info
        
        # Process based on current conversation state
        if self.conversation_state == "greeting":
            response = await self._handle_greeting()
        elif self.conversation_state == "collecting_name":
            response = await self._extract_name(message, validated_value)
        elif self.conversation_state == "collecting_location":
            response = await self._extract_location(message, validated_value)
        elif self.conversation_state == "collecting_looking_for":
            response = await self._extract_looking_for(message, validated_value)
        elif self.conversation_state == "collecting_skills":
            response = await self._extract_skills(message, validated_value)
        elif self.conversation_state == "collecting_availability":
            response = await self._extract_availability(message, validated_value)
        elif self.conversation_state == "recommending_jobs":
            response = await self._recommend_jobs()
        else:
            response = await self._handle_general_query(message)
        
        # Add bot response to history
        self.conversation_history.append({"role": "assistant", "content": response})
        
        # Play the response as audio if enabled
        if self.enable_audio:
            await self._play_response_audio(response)
        
        return response, self.candidate_info
    
    async def _play_response_audio(self, response: str) -> None:
        """
        Play the response as audio.
        
        Args:
            response: The text response to play as audio
        """
        try:
            await audio_player.play_text(response)
        except Exception as e:
            logger.error(f"Error playing audio response: {str(e)}")
    
    async def _handle_greeting(self) -> str:
        """Handle the initial greeting."""
        self.conversation_state = "collecting_name"
        
        prompt = """
        You are a job recruitment assistant for Silver Star. 
        Greet the candidate and ask for their name to get started.
        Keep it brief and professional. Do not mention being an AI or assistant.
        """
        
        response = await llm_service.generate_response(prompt)
        self.last_question = response
        self.last_question_type = "name"
        return response
    
    async def _extract_name(self, message: str, validated_value: Optional[str] = None) -> str:
        """Extract the candidate's name from their message."""
        # First, try a simple pattern match for common name introductions
        
        extracted_name = None
        if validated_value:
            extracted_name = re.sub(r"[^A-Za-z\s'-]", "", validated_value).strip()
            extracted_name = re.sub(r"\s+", " ", extracted_name)
            if extracted_name:
                extracted_name = extracted_name.title()
        
        # Check for patterns like "My name is X", "I'm X", "I am X", "Call me X"
        # Also handle just the name by itself
        if not extracted_name:
            patterns = [
                r"(?:my name is|i'm|i am|call me)\s+([A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*)*)",
                r"^(?:hi|hello|hey)[,\s]*(?:i'm|i am)?\s*([A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*)*)",
                r"^([A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*)*)$",  # Just a name by itself
            ]
            
            for pattern in patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    candidate_name = match.group(1).strip(" ,.!?")
                    # Basic validation - should be 2-60 characters
                    if 2 <= len(candidate_name) <= 60:
                        extracted_name = re.sub(r"\s+", " ", candidate_name).title()
                        break
        
        if extracted_name:
            self.candidate_info["name"] = extracted_name
            self.conversation_state = "collecting_location"
            
            prompt = f"""
            You are a job recruitment assistant for Silver Star. A candidate named {extracted_name} has just introduced themselves.
            Respond in a friendly, professional manner and ask for their location.
            Do not mention being an AI or assistant. Just be a helpful recruiter.
            """
            
            response = await llm_service.generate_response(prompt)
            self.last_question = response
            self.last_question_type = "location"
            return response
        
        # If pattern matching fails, try LLM extraction with clearer instructions
        schema = {"name": "string"}
        
        try:
            # Create a more specific extraction prompt
            extraction_prompt = f"""
            Extract the person's name from this message: "{message}"
            The person is introducing themselves to a job recruiter.
            Only extract their name, nothing else.
            If there's no clear name, respond with null.
            """
            
            extracted = await llm_service.extract_structured_data(
                extraction_prompt, schema, self.conversation_history
            )
            
            if extracted.get("name"):
                self.candidate_info["name"] = extracted["name"]
                self.conversation_state = "collecting_location"
                
                prompt = f"""
                You are a job recruitment assistant for Silver Star. A candidate named {extracted['name']} has just introduced themselves.
                Respond in a friendly, professional manner and ask for their location.
                Do not mention being an AI or assistant. Just be a helpful recruiter.
                """
                
                response = await llm_service.generate_response(prompt)
                self.last_question = response
                self.last_question_type = "location"
                return response
            else:
                prompt = """
                You are a job recruitment assistant for Silver Star.
                I didn't catch the person's name. Ask them to tell you their name in a friendly way.
                Do not mention being an AI or assistant.
                """
                
                response = await llm_service.generate_response(prompt)
                self.last_question = response
                self.last_question_type = "name"
                return response
        except Exception as e:
            logger.error(f"Error extracting name: {str(e)}")
            
            prompt = """
            You are a job recruitment assistant for Silver Star.
            I'm having trouble understanding. Could you please tell me your name?
            Do not mention being an AI or assistant.
            """
            
            response = await llm_service.generate_response(prompt)
            self.last_question = response
            self.last_question_type = "name"
            return response
    
    async def _extract_location(self, message: str, validated_value: Optional[str] = None) -> str:
        """Extract the candidate's location from their message."""
        schema = {"location": "string"}
        location = None
        
        if validated_value:
            location = validated_value.strip(" .,!")
        
        if not location:
            patterns = [
                r"(?:i(?:'m| am)?|i live|i reside|i work|i'm based|i am based|i'm located|i am located|based|located)\s+(?:in|at|near|around)\s+([A-Za-z0-9 ,'-]+)",
                r"(?:from)\s+([A-Za-z0-9 ,'-]+)",
                r"^(?:in\s+)?([A-Za-z0-9 ,'-]+)$",
            ]
            
            for pattern in patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    candidate_location = match.group(1).strip(" .,!")
                    if 2 <= len(candidate_location) <= 100:
                        location = re.sub(r"\s+", " ", candidate_location)
                        break
        
        try:
            if not location:
                extraction_prompt = f"""
                Extract the candidate's location from the following message. The location may be a city, state, or country.
                Provide the location as a single concise string without additional commentary.
                If no location is mentioned, respond with null.
                
                Message: "{message}"
                
                Respond with JSON like {{"location": "San Francisco, CA"}} or {{"location": null}}.
                """
                
                extracted = await llm_service.extract_structured_data(
                    extraction_prompt, schema, self.conversation_history
                )
                
                if extracted.get("location"):
                    location = extracted["location"].strip(" .,!")
            
            if location:
                self.candidate_info["location"] = location
                self.conversation_state = "collecting_looking_for"
                
                prompt = f"""
                Great! Now, what kind of job are you looking for? 
                Please describe the type of position, industry, or role you're interested in.
                """
                
                response = await llm_service.generate_response(prompt)
                self.last_question = response
                self.last_question_type = "looking_for"
                return response
            else:
                prompt = """
                I didn't catch your location. Could you please tell me where you're located?
                """
                
                response = await llm_service.generate_response(prompt)
                self.last_question = response
                self.last_question_type = "location"
                return response
        except Exception as e:
            logger.error(f"Error extracting location: {str(e)}")
            
            prompt = """
            I'm having trouble understanding. Could you please tell me your location?
            """
            
            response = await llm_service.generate_response(prompt)
            self.last_question = response
            self.last_question_type = "location"
            return response
    
    async def _extract_looking_for(self, message: str, validated_value: Optional[str] = None) -> str:
        """Extract what the candidate is looking for from their message."""
        schema = {"looking_for": "string"}
        looking_for = validated_value.strip() if isinstance(validated_value, str) and validated_value.strip() else None
        
        try:
            if not looking_for:
                extracted = await llm_service.extract_structured_data(
                    message, schema, self.conversation_history
                )
                looking_for = extracted.get("looking_for") if extracted else None
            
            if looking_for:
                self.candidate_info["looking_for"] = looking_for
                self.conversation_state = "collecting_skills"
                
                prompt = f"""
                Thanks for sharing! Now, could you tell me about your skills and experience?
                What can you do well? Please include any relevant skills, certifications, or experience.
                """
                
                response = await llm_service.generate_response(prompt)
                self.last_question = response
                self.last_question_type = "skills"
                return response
            else:
                prompt = """
                I didn't quite understand what you're looking for. Could you please describe the type of job or position you're interested in?
                """
                
                response = await llm_service.generate_response(prompt)
                self.last_question = response
                self.last_question_type = "looking_for"
                return response
        except Exception as e:
            logger.error(f"Error extracting what they're looking for: {str(e)}")
            
            prompt = """
            I'm having trouble understanding. Could you please describe what type of job you're looking for?
            """
            
            response = await llm_service.generate_response(prompt)
            self.last_question = response
            self.last_question_type = "looking_for"
            return response
    
    async def _extract_skills(self, message: str, validated_value: Optional[str] = None) -> str:
        """Extract the candidate's skills from their message."""
        schema = {"skills": "string"}
        skills = validated_value.strip() if isinstance(validated_value, str) and validated_value.strip() else None
        
        try:
            if not skills:
                extracted = await llm_service.extract_structured_data(
                    message, schema, self.conversation_history
                )
                skills = extracted.get("skills") if extracted else None
            
            if skills:
                self.candidate_info["skills"] = skills
                self.conversation_state = "collecting_availability"
                
                prompt = f"""
                Great! Finally, when are you available to start work?
                Please let me know your availability (immediately, specific date, etc.).
                """
                
                response = await llm_service.generate_response(prompt)
                self.last_question = response
                self.last_question_type = "availability"
                return response
            else:
                prompt = """
                I didn't catch your skills. Could you please tell me about your skills and experience?
                """
                
                response = await llm_service.generate_response(prompt)
                self.last_question = response
                self.last_question_type = "skills"
                return response
        except Exception as e:
            logger.error(f"Error extracting skills: {str(e)}")
            
            prompt = """
            I'm having trouble understanding. Could you please tell me about your skills and experience?
            """
            
            response = await llm_service.generate_response(prompt)
            self.last_question = response
            self.last_question_type = "skills"
            return response
    
    async def _extract_availability(self, message: str, validated_value: Optional[str] = None) -> str:
        """Extract the candidate's availability from their message."""
        schema = {"availability": "string"}
        availability = validated_value.strip() if isinstance(validated_value, str) and validated_value.strip() else None
        
        try:
            if not availability:
                extracted = await llm_service.extract_structured_data(
                    message, schema, self.conversation_history
                )
                availability = extracted.get("availability") if extracted else None
            
            if availability:
                self.candidate_info["availability"] = availability
                self.conversation_state = "recommending_jobs"
                
                # Move to job recommendations
                return await self._recommend_jobs()
            else:
                prompt = """
                I didn't catch your availability. Could you please tell me when you're available to start work?
                """
                
                response = await llm_service.generate_response(prompt)
                self.last_question = response
                self.last_question_type = "availability"
                return response
        except Exception as e:
            logger.error(f"Error extracting availability: {str(e)}")
            
            prompt = """
            I'm having trouble understanding. Could you please tell me when you're available to start work?
            """
            
            response = await llm_service.generate_response(prompt)
            self.last_question = response
            self.last_question_type = "availability"
            return response
    
    async def _recommend_jobs(self) -> str:
        """Generate job recommendations based on candidate information."""
        try:
            # Get job recommendations using the recommendation service
            if self.db_session:
                recommendations = await job_recommendation_service.get_recommendations(
                    self.candidate_info, 
                    self.db_session, 
                    limit=3
                )
                
                if recommendations:
                    # Format the recommendations for the response
                    recommendation_text = "Based on your profile, I've found some great job opportunities for you:\n\n"
                    
                    for i, rec in enumerate(recommendations, 1):
                        # Get job details
                        job_details = await job_recommendation_service.get_job_details_for_recommendation(
                            rec["job_id"], 
                            self.db_session
                        )
                        
                        if job_details:
                            recommendation_text += f"{i}. **{job_details['title']}** at {job_details['company'] or 'A great company'}\n"
                            recommendation_text += f"   Location: {job_details['location'] or 'Various locations'}\n"
                            recommendation_text += f"   Match Score: {rec['match_score']}%\n"
                            recommendation_text += f"   Why it's a good fit: {rec['match_reason']}\n\n"
                    
                    recommendation_text += "Would you like more details about any of these positions, or would you like to see more recommendations?"
                    
                    return recommendation_text
                else:
                    return "I couldn't find any specific job matches in our database at the moment. This might be because we're still building our job listings. Let me provide some general advice based on your profile instead."
            else:
                # Fallback to mock recommendations if no database session
                candidate_summary = json.dumps(self.candidate_info, indent=2)
                
                prompt = f"""
                Based on the following candidate information, provide personalized job recommendations:
                
                {candidate_summary}
                
                Generate 3 job recommendations that would be a good fit for this candidate.
                For each recommendation, include:
                1. Job title
                2. Company name
                3. Location
                4. Brief description of why it's a good fit
                
                Format your response in a friendly, conversational way.
                """
                
                return await llm_service.generate_response(prompt)
        except Exception as e:
            logger.error(f"Error generating job recommendations: {str(e)}")
            
            # Fallback to a generic response
            return "I'm having trouble finding specific job recommendations right now. Based on your profile, I'd suggest looking for positions that match your skills and availability. Would you like me to provide some general job search advice instead?"
    
    async def _handle_general_query(self, message: str) -> str:
        """Handle general queries outside the main conversation flow."""
        prompt = f"""
        You are a helpful job recruitment assistant for Silver Star.
        The user has asked: "{message}"
        
        Provide a helpful response. If they seem to want to restart the conversation,
        suggest starting over by asking for their name again.
        """
        
        return await llm_service.generate_response(prompt)
    
    def reset_conversation(self):
        """Reset the conversation state and candidate information."""
        self.conversation_state = "greeting"
        self.candidate_info = {
            "name": None,
            "location": None,
            "looking_for": None,
            "skills": None,
            "availability": None
        }
        self.conversation_history = []
        self.db_session = None
        self.last_question = None
        self.last_question_type = None
