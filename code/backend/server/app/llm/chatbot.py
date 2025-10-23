import json
import logging
from typing import Dict, List, Optional, Tuple, Any

from .service import llm_service
from .recommendations import job_recommendation_service

logger = logging.getLogger(__name__)


class CandidateChatbot:
    """Chatbot for gathering candidate information and recommending jobs."""
    
    def __init__(self):
        """Initialize the chatbot."""
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
        
        # Process based on current conversation state
        if self.conversation_state == "greeting":
            response = await self._handle_greeting()
        elif self.conversation_state == "collecting_name":
            response = await self._extract_name(message)
        elif self.conversation_state == "collecting_location":
            response = await self._extract_location(message)
        elif self.conversation_state == "collecting_looking_for":
            response = await self._extract_looking_for(message)
        elif self.conversation_state == "collecting_skills":
            response = await self._extract_skills(message)
        elif self.conversation_state == "collecting_availability":
            response = await self._extract_availability(message)
        elif self.conversation_state == "recommending_jobs":
            response = await self._recommend_jobs()
        else:
            response = await self._handle_general_query(message)
        
        # Add bot response to history
        self.conversation_history.append({"role": "assistant", "content": response})
        
        return response, self.candidate_info
    
    async def _handle_greeting(self) -> str:
        """Handle the initial greeting."""
        self.conversation_state = "collecting_name"
        
        prompt = """
        You are a friendly job recruitment assistant for Silver Star. 
        Greet the candidate and ask for their name to get started.
        Keep it brief and welcoming.
        """
        
        return await llm_service.generate_response(prompt)
    
    async def _extract_name(self, message: str) -> str:
        """Extract the candidate's name from their message."""
        schema = {"name": "string"}
        
        try:
            extracted = await llm_service.extract_structured_data(
                message, schema, self.conversation_history
            )
            
            if extracted.get("name"):
                self.candidate_info["name"] = extracted["name"]
                self.conversation_state = "collecting_location"
                
                prompt = f"""
                Thanks, {extracted['name']}! Now I need to know your location. 
                Could you please tell me where you're located?
                """
                
                return await llm_service.generate_response(prompt)
            else:
                prompt = """
                I didn't catch your name. Could you please tell me your name?
                """
                
                return await llm_service.generate_response(prompt)
        except Exception as e:
            logger.error(f"Error extracting name: {str(e)}")
            
            prompt = """
            I'm having trouble understanding. Could you please tell me your name?
            """
            
            return await llm_service.generate_response(prompt)
    
    async def _extract_location(self, message: str) -> str:
        """Extract the candidate's location from their message."""
        schema = {"location": "string"}
        
        try:
            extracted = await llm_service.extract_structured_data(
                message, schema, self.conversation_history
            )
            
            if extracted.get("location"):
                self.candidate_info["location"] = extracted["location"]
                self.conversation_state = "collecting_looking_for"
                
                prompt = f"""
                Great! Now, what kind of job are you looking for? 
                Please describe the type of position, industry, or role you're interested in.
                """
                
                return await llm_service.generate_response(prompt)
            else:
                prompt = """
                I didn't catch your location. Could you please tell me where you're located?
                """
                
                return await llm_service.generate_response(prompt)
        except Exception as e:
            logger.error(f"Error extracting location: {str(e)}")
            
            prompt = """
            I'm having trouble understanding. Could you please tell me your location?
            """
            
            return await llm_service.generate_response(prompt)
    
    async def _extract_looking_for(self, message: str) -> str:
        """Extract what the candidate is looking for from their message."""
        schema = {"looking_for": "string"}
        
        try:
            extracted = await llm_service.extract_structured_data(
                message, schema, self.conversation_history
            )
            
            if extracted.get("looking_for"):
                self.candidate_info["looking_for"] = extracted["looking_for"]
                self.conversation_state = "collecting_skills"
                
                prompt = f"""
                Thanks for sharing! Now, could you tell me about your skills and experience?
                What can you do well? Please include any relevant skills, certifications, or experience.
                """
                
                return await llm_service.generate_response(prompt)
            else:
                prompt = """
                I didn't quite understand what you're looking for. Could you please describe the type of job or position you're interested in?
                """
                
                return await llm_service.generate_response(prompt)
        except Exception as e:
            logger.error(f"Error extracting what they're looking for: {str(e)}")
            
            prompt = """
            I'm having trouble understanding. Could you please describe what type of job you're looking for?
            """
            
            return await llm_service.generate_response(prompt)
    
    async def _extract_skills(self, message: str) -> str:
        """Extract the candidate's skills from their message."""
        schema = {"skills": "string"}
        
        try:
            extracted = await llm_service.extract_structured_data(
                message, schema, self.conversation_history
            )
            
            if extracted.get("skills"):
                self.candidate_info["skills"] = extracted["skills"]
                self.conversation_state = "collecting_availability"
                
                prompt = f"""
                Great! Finally, when are you available to start work?
                Please let me know your availability (immediately, specific date, etc.).
                """
                
                return await llm_service.generate_response(prompt)
            else:
                prompt = """
                I didn't catch your skills. Could you please tell me about your skills and experience?
                """
                
                return await llm_service.generate_response(prompt)
        except Exception as e:
            logger.error(f"Error extracting skills: {str(e)}")
            
            prompt = """
            I'm having trouble understanding. Could you please tell me about your skills and experience?
            """
            
            return await llm_service.generate_response(prompt)
    
    async def _extract_availability(self, message: str) -> str:
        """Extract the candidate's availability from their message."""
        schema = {"availability": "string"}
        
        try:
            extracted = await llm_service.extract_structured_data(
                message, schema, self.conversation_history
            )
            
            if extracted.get("availability"):
                self.candidate_info["availability"] = extracted["availability"]
                self.conversation_state = "recommending_jobs"
                
                # Move to job recommendations
                return await self._recommend_jobs()
            else:
                prompt = """
                I didn't catch your availability. Could you please tell me when you're available to start work?
                """
                
                return await llm_service.generate_response(prompt)
        except Exception as e:
            logger.error(f"Error extracting availability: {str(e)}")
            
            prompt = """
            I'm having trouble understanding. Could you please tell me when you're available to start work?
            """
            
            return await llm_service.generate_response(prompt)
    
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
