import json
import logging
import os
from typing import Dict, List, Optional, Tuple, Any
import re

from ..core.service import llm_service
from ..core.utils import compact_json, strip_json_code_fences
from .recommendations import job_recommendation_service
from .validation import answer_validator
from .profile_validator import profile_validation_service
from ..audio.audio_player import audio_player

logger = logging.getLogger(__name__)


class CandidateChatbot:
    """Chatbot for gathering candidate information and recommending jobs."""
    
    FIELD_KEYS = (
        "full_name",
        "location",
        "age",
        "physical_condition",
        "interests",
        "limitations",
    )

    FIELD_STATE_MAP = {
        "full_name": "collecting_full_name",
        "location": "collecting_location",
        "age": "collecting_age",
        "physical_condition": "collecting_physical_condition",
        "interests": "collecting_interests",
        "limitations": "collecting_limitations",
    }

    FIELD_TYPE_MAP = {
        "full_name": "full_name",
        "location": "location",
        "age": "age",
        "physical_condition": "physical_condition",
        "interests": "interests",
        "limitations": "limitations",
    }

    FIELD_LABEL_MAP = {
        "full_name": "full name",
        "location": "location",
        "age": "age",
        "physical_condition": "physical condition",
        "interests": "areas of interest",
        "limitations": "limitations",
    }
    NON_NAME_TOKENS = {
        "hi",
        "hello",
        "hey",
        "hiya",
        "greetings",
        "morning",
        "afternoon",
        "evening",
        "thanks",
        "thank",
        "yo",
        "hola",
        "sup",
        "in",
        "at",
        "from",
        "on",
        "of",
        "the",
        "good",
        "great",
        "fine",
        "okay",
        "ok",
        "awesome",
        "well",
        "alright",
        "cool",
        "tired",
    }
    
    def __init__(self, enable_audio: bool = False):
        """
        Initialize the chatbot.
        
        Args:
            enable_audio: Whether to enable audio playback of responses
        """
        self.conversation_state = "greeting"
        self.candidate_info = {
            "full_name": None,
            "location": None,
            "age": None,
            "physical_condition": None,
            "interests": None,
            "limitations": None,
            "validation": None,
            "executive_summary": None,
            "job_suggestions": None,
        }
        self.conversation_history = []
        self.db_session = None  # Will be set when processing messages
        self.last_question = None  # Track the last question asked
        self.last_question_type = None  # Track the type of the last question
        self.enable_audio = enable_audio  # Whether to play audio responses

    def seed_profile(self, profile: Dict[str, Any]) -> None:
        """Seed the chatbot with a pre-existing user profile and move to confirmation state.

        This does not overwrite values with empty strings; only truthy strings are applied.
        """
        for key in self.FIELD_KEYS:
            val = profile.get(key)
            if isinstance(val, str):
                val = val.strip()
            if val:
                self.candidate_info[key] = val
        # Ask for confirmation on the next user turn
        self.conversation_state = "confirming_profile"

    def _preferred_name(self) -> Optional[str]:
        """Return a friendly form of the candidate's name for responses."""
        full_name = self.candidate_info.get("full_name")
        if full_name:
            parts = full_name.split()
            if parts:
                return parts[0]
        return None
    
    def _conversation_snippet(self, turns: int = 6) -> str:
        """Return the last few conversation turns formatted for prompts."""
        if not self.conversation_history:
            return "No prior conversation."
        snippet = self.conversation_history[-turns:]
        lines = []
        for turn in snippet:
            role = turn.get("role", "assistant")
            content = turn.get("content", "")
            lines.append(f"{role.capitalize()}: {content}")
        return "\n".join(lines)

    @classmethod
    def _detect_full_name_from_message(cls, message: str) -> Optional[str]:
        """Attempt to extract a full name using lightweight heuristics."""
        if not message:
            return None

        correction_candidates: List[str] = []
        if "name" in message.lower():
            for match in re.finditer(
                r"(?:it\s+(?:is|s))\s+([A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*)+)",
                message,
                re.IGNORECASE,
            ):
                correction_candidates.append(match.group(1))
        patterns = [
            r"(?:my name is|i'm|i am|call me)\s+([A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*)*)",
            r"^(?:hi|hello|hey)[,\s]*(?:i'm|i am)?\s*([A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*)*)",
            r"^([A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*)*)$",
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                correction_candidates.append(match.group(1))

        for raw_candidate in correction_candidates:
            if not raw_candidate:
                continue
            candidate_name = re.sub(r"\s+", " ", raw_candidate).strip(" ,.!?")
            correction_match = re.search(
                r"(?:it\s+(?:is|s))\s+([A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*)+)$",
                candidate_name,
                re.IGNORECASE,
            )
            if correction_match:
                candidate_name = correction_match.group(1).strip(" ,.!?")

            if not (2 <= len(candidate_name) <= 80):
                continue
            if candidate_name.lower().startswith("not "):
                continue
            if any(char.isdigit() for char in candidate_name):
                continue

            tokens = candidate_name.split()
            first_token_lower = tokens[0].lower()
            if first_token_lower in cls.NON_NAME_TOKENS:
                continue

            cleaned = " ".join(token.capitalize() for token in tokens)
            if cleaned.lower() in cls.NON_NAME_TOKENS:
                continue
            return cleaned
        return None

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
        
        inline_name = None
        if message:
            inline_name = self._detect_full_name_from_message(message)
        if inline_name:
            current_name = self.candidate_info.get("full_name")
            name_mentioned = "name" in message.lower()
            if inline_name != current_name and (self.conversation_state in {"collecting_full_name"} or name_mentioned or not current_name):
                self.candidate_info["full_name"] = inline_name

        # Process based on current conversation state
        if self.conversation_state == "greeting":
            detected_name = self._detect_full_name_from_message(message)
            if detected_name:
                self.candidate_info["full_name"] = detected_name
                self.conversation_state = "collecting_location"
                response = f"Nice to meet you, {detected_name}! Where are you currently located?"
                self.last_question = response
                self.last_question_type = "location"
            else:
                response = await self._handle_greeting()
        elif self.conversation_state == "confirming_profile":
            response = await self._confirm_profile(message)
        elif self.conversation_state == "awaiting_field_selection":
            response = await self._choose_field_to_edit(message)
        elif self.conversation_state == "collecting_full_name":
            response = await self._extract_full_name(message, validated_value)
        elif self.conversation_state == "collecting_location":
            response = await self._extract_location(message, validated_value)
        elif self.conversation_state == "collecting_age":
            response = await self._extract_age(message, validated_value)
        elif self.conversation_state == "collecting_physical_condition":
            response = await self._extract_physical_condition(message, validated_value)
        elif self.conversation_state == "collecting_interests":
            response = await self._extract_interests(message, validated_value)
        elif self.conversation_state == "collecting_limitations":
            response = await self._extract_limitations(message, validated_value)
        elif self.conversation_state == "profile_complete":
            response = await self._handle_general_query(message)
        elif self.conversation_state == "validating_profile":
            response = await self._validate_profile()
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
    
    async def judge_field_change(
        self,
        field: str,
        proposed_value: str,
        current_value: Optional[str],
        source_message: str
    ) -> Dict[str, Any]:
        """Use LLM to judge whether a field change is intentional."""
        label = self.FIELD_LABEL_MAP.get(field, field)
        schema = {
            "should_replace": "boolean",
            "confidence": "number",
            "reason": "string"
        }

        prompt = f"""
        You help maintain an intake profile for a community job placement program.
        Determine whether the candidate is intentionally providing a new value for the field "{label}".

        Current recorded value: {json.dumps(current_value) if current_value else "null"}
        Proposed new value: {json.dumps(proposed_value)}
        Latest user message: {json.dumps(source_message)}

        Recent conversation:
        {self._conversation_snippet()}

        Evaluate if the latest user message clearly updates the {label}.
        Respond in JSON with:
        {{
          "should_replace": true/false,
          "confidence": number between 0 and 1,
          "reason": "brief explanation"
        }}

        Only set "should_replace" to true when the user explicitly provides a new {label}.
        Otherwise, return false with confidence reflecting uncertainty.
        """

        try:
            decision = await llm_service.extract_structured_data(
                prompt,
                schema,
                self.conversation_history
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("LLM judge failed: %s", exc)
            return {"should_replace": False, "confidence": 0.0, "reason": "judge_error"}

        raw_should = decision.get("should_replace")
        if isinstance(raw_should, bool):
            should_replace = raw_should
        elif isinstance(raw_should, str):
            should_replace = raw_should.strip().lower() in {"true", "yes", "1", "y"}
        else:
            should_replace = False
        confidence = decision.get("confidence")
        try:
            confidence_value = float(confidence) if confidence is not None else 0.0
        except (TypeError, ValueError):
            confidence_value = 0.0

        reason = decision.get("reason") or "no_reason_provided"
        logger.info(
            "Field change judge result | field=%s | should_replace=%s | confidence=%.2f | reason=%s | proposed=%s",
            field,
            should_replace,
            confidence_value,
            reason,
            proposed_value
        )

        threshold = 0.75
        return {
            "should_replace": should_replace and confidence_value >= threshold,
            "confidence": confidence_value,
            "raw_decision": should_replace,
            "reason": reason
        }
    
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

    def _profile_summary_snippet(self) -> str:
        parts = []
        for key in self.FIELD_KEYS:
            value = self.candidate_info.get(key)
            if value:
                label = self.FIELD_LABEL_MAP.get(key, key.replace("_", " "))
                parts.append(f"{label}: {value}")
        return "; ".join(parts) if parts else "no details yet"

    async def _confirm_profile(self, message: str) -> str:
        """Handle the profile confirmation flow."""
        # If we haven't asked yet, present the summary and ask for confirmation
        if self.last_question_type != "confirm_profile":
            summary = self._profile_summary_snippet()
            prompt = (
                f"I have your current profile as {summary}. Is the information presented on the page still correct? "
                "You can say 'all good' or tell me what to update."
            )
            self.last_question = prompt
            self.last_question_type = "confirm_profile"
            return prompt

        normalized = (message or "").strip().lower()
        if not normalized:
            return "Could you confirm if your profile details are correct, or tell me what to update?"

        affirmative = {"yes", "yep", "yeah", "correct", "all good", "looks good", "good", "ok", "okay"}
        negative = {"no", "nope", "not quite", "update", "change", "edit"}

        if any(word in normalized for word in affirmative):
            # Proceed to validation to fill any gaps, else move to profile_complete
            self.conversation_state = "validating_profile"
            self.last_question = None
            self.last_question_type = None
            return await self._validate_profile()

        if any(word in normalized for word in negative):
            self.conversation_state = "awaiting_field_selection"
            question = (
                "Sure — which field would you like to update first? "
                "You can say full name, location, age, physical condition, interests, or limitations."
            )
            self.last_question = question
            self.last_question_type = "choose_field"
            return question

        # Try to detect if they directly provided a value (e.g., a new location)
        quick_field = self._guess_field_from_message(normalized)
        if quick_field:
            self.conversation_state = self.FIELD_STATE_MAP.get(quick_field, "collecting_full_name")
            return await self._ask_for_field(quick_field)

        return (
            "Thanks. To update, tell me which field to change (e.g., 'update location'), "
            "or say 'all good' to keep everything as-is."
        )

    def _guess_field_from_message(self, text: str) -> Optional[str]:
        mapping = {
            "name": "full_name",
            "full name": "full_name",
            "location": "location",
            "age": "age",
            "condition": "physical_condition",
            "physical": "physical_condition",
            "interests": "interests",
            "interest": "interests",
            "limitations": "limitations",
            "limitation": "limitations",
        }
        for key, field in mapping.items():
            if key in text:
                return field
        return None

    async def _ask_for_field(self, field: str) -> str:
        prompts = {
            "full_name": "Got it — what is your full name?",
            "location": "Thanks — what city and state are you currently located in?",
            "age": "Thanks — how old are you?",
            "physical_condition": "Thanks — could you describe your physical condition or anything we should keep in mind?",
            "interests": "What kinds of activities or roles are you most interested in doing?",
            "limitations": "Are there any limitations or things you prefer to avoid?",
        }
        response = prompts.get(field, "Please provide the updated value.")
        self.last_question = response
        self.last_question_type = field
        return response

    async def _choose_field_to_edit(self, message: str) -> str:
        field = self._guess_field_from_message((message or "").lower())
        if not field:
            return (
                "Please tell me which field to update: full name, location, age, "
                "physical condition, interests, or limitations."
            )
        self.conversation_state = self.FIELD_STATE_MAP.get(field, "collecting_full_name")
        return await self._ask_for_field(field)
    
    async def _handle_greeting(self) -> str:
        """Handle the initial greeting."""
        self.conversation_state = "collecting_full_name"
        
        response = "Hello! I'm your Asteroid, Silver Star assistant. Could you please share your full name so we can get started?"
        self.last_question = response
        self.last_question_type = "full_name"
        return response
    
    async def _extract_full_name(self, message: str, validated_value: Optional[str] = None) -> str:
        """Extract the candidate's full name from their message."""

        extracted_name = None
        if validated_value:
            extracted_name = re.sub(r"[^A-Za-z\s'-]", "", validated_value).strip()
            extracted_name = re.sub(r"\s+", " ", extracted_name)
            if extracted_name:
                extracted_name = extracted_name.title()

        if not extracted_name:
            extracted_name = self._detect_full_name_from_message(message)

        if extracted_name:
            self.candidate_info["full_name"] = extracted_name
            self.conversation_state = "collecting_location"
            response = f"Nice to meet you, {extracted_name}! Where are you currently located?"
            self.last_question = response
            self.last_question_type = "location"
            return response

        schema = {"full_name": "string"}

        try:
            extraction_prompt = f"""
            Extract the person's full name from this message: "{message}"
            The person is introducing themselves to a job recruiter.
            Only extract their name, nothing else.
            If there's no clear name, respond with null.
            """

            extracted = await llm_service.extract_structured_data(
                extraction_prompt, schema, self.conversation_history
            )

            candidate_name = extracted.get("full_name") if extracted else None
            if candidate_name:
                candidate_name = re.sub(r"\s+", " ", candidate_name).strip()
                self.candidate_info["full_name"] = candidate_name
                self.conversation_state = "collecting_location"
                response = f"Nice to meet you, {candidate_name}! Where are you currently located?"
                self.last_question = response
                self.last_question_type = "location"
                return response
            response = "I didn't catch your name yet. Could you please share your full name?"
            self.last_question = response
            self.last_question_type = "full_name"
            return response
        except Exception as e:
            logger.error(f"Error extracting full name: {str(e)}")
            response = "I'm having trouble understanding. Could you please tell me your full name?"
            self.last_question = response
            self.last_question_type = "full_name"
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
                self.conversation_state = "collecting_age"

                preferred_name = self._preferred_name()
                name_fragment = f", {preferred_name}" if preferred_name else ""
                response = f"Thanks{name_fragment}! To make sure opportunities are appropriate, could you share your age?"
                self.last_question = response
                self.last_question_type = "age"
                return response
            else:
                response = "I didn't catch your location. Could you please tell me where you're located?"
                self.last_question = response
                self.last_question_type = "location"
                return response
        except Exception as e:
            logger.error(f"Error extracting location: {str(e)}")
            
            response = "I'm having trouble understanding. Could you please tell me your location?"
            self.last_question = response
            self.last_question_type = "location"
            return response
    
    async def _extract_age(self, message: str, validated_value: Optional[str] = None) -> str:
        """Extract the candidate's age."""

        def normalize_age(value: str) -> Optional[str]:
            if not value:
                return None
            digits = re.findall(r"\d{1,3}", value)
            if digits:
                try:
                    age_int = int(digits[0])
                    if 10 <= age_int <= 120:
                        return str(age_int)
                except ValueError:
                    return None
            return None

        age_value = normalize_age(validated_value) if validated_value else None

        if not age_value:
            age_value = normalize_age(message)

        if not age_value:
            schema = {"age": "string"}
            try:
                extraction_prompt = f"""
                Extract the person's age from the following message. Return numbers only.
                If age is not provided, respond with null.
                Message: "{message}"
                Respond with JSON like {{"age": "35"}} or {{"age": null}}.
                """

                extracted = await llm_service.extract_structured_data(
                    extraction_prompt, schema, self.conversation_history
                )

                age_value = normalize_age(extracted.get("age") if extracted else None)
            except Exception as e:
                logger.error(f"Error extracting age: {str(e)}")

        if age_value:
            self.candidate_info["age"] = age_value
            self.conversation_state = "collecting_physical_condition"

            response = "Thank you. Could you describe your current physical condition or anything I should keep in mind?"
            self.last_question = response
            self.last_question_type = "physical_condition"
            return response

        response = "I didn't catch your age. Could you please share how old you are?"
        self.last_question = response
        self.last_question_type = "age"
        return response
    
    async def _extract_physical_condition(self, message: str, validated_value: Optional[str] = None) -> str:
        """Capture the candidate's physical condition description."""
        schema = {"physical_condition": "string"}
        condition = validated_value.strip() if isinstance(validated_value, str) and validated_value.strip() else None

        try:
            if not condition:
                extraction_prompt = f"""
                Summarize any description of the person's physical condition from this message.
                If nothing is mentioned, respond with null.
                Message: "{message}"
                Respond with JSON like {{"physical_condition": "Active and able to lift 30 lbs"}} or {{"physical_condition": null}}.
                """

                extracted = await llm_service.extract_structured_data(
                    extraction_prompt, schema, self.conversation_history
                )
                condition = extracted.get("physical_condition") if extracted else None

            if condition:
                self.candidate_info["physical_condition"] = condition.strip()
                self.conversation_state = "collecting_interests"

                response = "Thanks for sharing. What kinds of activities or roles are you most interested in doing?"
                self.last_question = response
                self.last_question_type = "interests"
                return response

            response = "I didn't catch any details about your physical condition. Could you describe it briefly?"
            self.last_question = response
            self.last_question_type = "physical_condition"
            return response
        except Exception as e:
            logger.error(f"Error extracting physical condition: {str(e)}")

            response = "I'm having trouble understanding. Could you tell me a bit about your physical condition?"
            self.last_question = response
            self.last_question_type = "physical_condition"
            return response

    async def _extract_interests(self, message: str, validated_value: Optional[str] = None) -> str:
        """Capture the candidate's interests or preferred activities."""
        schema = {"interests": "string"}
        interests = validated_value.strip() if isinstance(validated_value, str) and validated_value.strip() else None

        try:
            if not interests:
                extraction_prompt = f"""
                Extract the areas of interest or preferred activities the person mentions in this message.
                Provide a concise summary. If none are mentioned, respond with null.
                Message: "{message}"
                Respond with JSON like {{"interests": "Gardening, organizing community events"}} or {{"interests": null}}.
                """

                extracted = await llm_service.extract_structured_data(
                    extraction_prompt, schema, self.conversation_history
                )
                interests = extracted.get("interests") if extracted else None

            if interests:
                self.candidate_info["interests"] = interests.strip()
                self.conversation_state = "collecting_limitations"

                response = "That's helpful. Are there any limitations or things you prefer to avoid so we can plan around them?"
                self.last_question = response
                self.last_question_type = "limitations"
                return response

            response = "I didn't quite catch your areas of interest. Could you tell me what types of activities you enjoy or are open to?"
            self.last_question = response
            self.last_question_type = "interests"
            return response
        except Exception as e:
            logger.error(f"Error extracting interests: {str(e)}")

            response = "I'm having trouble understanding. Could you share the kinds of things you would like to do?"
            self.last_question = response
            self.last_question_type = "interests"
            return response

    async def _extract_limitations(self, message: str, validated_value: Optional[str] = None) -> str:
        """Capture any limitations the candidate mentions."""
        schema = {"limitations": "string"}
        limitations = validated_value.strip() if isinstance(validated_value, str) and validated_value.strip() else None

        try:
            if not limitations:
                extraction_prompt = f"""
                Extract any limitations, restrictions, or constraints the person mentions in this message.
                If none are mentioned, respond with null.
                Message: "{message}"
                Respond with JSON like {{"limitations": "Needs seated work, limited lifting"}} or {{"limitations": null}}.
                """

                extracted = await llm_service.extract_structured_data(
                    extraction_prompt, schema, self.conversation_history
                )
                limitations = extracted.get("limitations") if extracted else None

            if limitations:
                self.candidate_info["limitations"] = limitations.strip()
            else:
                self.candidate_info["limitations"] = None

            self.conversation_state = "validating_profile"
            return await self._validate_profile()
        except Exception as e:
            logger.error(f"Error extracting limitations: {str(e)}")

            response = "I'm having trouble understanding. Could you share any limitations we should be aware of? If there are none, feel free to say so."
            self.last_question = response
            self.last_question_type = "limitations"
            return response

    async def _validate_profile(self) -> str:
        """Validate the collected profile information using the validation service."""

        validation = await profile_validation_service.validate_profile(self.candidate_info)
        self.candidate_info["validation"] = validation

        if not validation.get("is_complete", False):
            missing_fields = validation.get("missing_fields") or []
            if missing_fields:
                next_field = missing_fields[0]
                field_label = self.FIELD_LABEL_MAP.get(next_field, next_field.replace("_", " "))
                self.conversation_state = self.FIELD_STATE_MAP.get(next_field, "collecting_full_name")

                follow_up_prompt = f"""
                You are a job recruitment assistant for Silver Star.
                Let the candidate know we still need their {field_label}.
                Ask politely for that information in a single short message.
                Do not mention being an AI or assistant.
                """

                response = await llm_service.generate_response(follow_up_prompt)
                self.last_question = response
                self.last_question_type = self.FIELD_TYPE_MAP.get(next_field, next_field)
                return response

        summary = validation.get("summary")
        issues = validation.get("issues") or []
        notes = validation.get("notes")

        if not summary:
            profile_snapshot = compact_json(
                {k: self.candidate_info.get(k) for k in self.FIELD_KEYS},
                max_field_length=220,
                max_total_chars=1400,
            )
            summary_prompt = f"""
            Craft a concise, friendly summary of this candidate profile for Silver Star:
            {profile_snapshot}
            """
            summary = await llm_service.generate_response(summary_prompt)

        message_parts = [summary.strip()]
        if issues:
            issues_text = "Here are a few notes I noticed:\n" + "\n".join(f"- {issue}" for issue in issues)
            message_parts.append(issues_text)
        if notes:
            message_parts.append(notes.strip())

        executive_summary = await self._generate_executive_summary()
        if executive_summary:
            formatted_summary = json.dumps(executive_summary, indent=2)
            message_parts.append("Executive Summary:\n```json\n" + formatted_summary + "\n```")
            self.candidate_info["executive_summary"] = executive_summary
            self.candidate_info["job_suggestions"] = executive_summary.get("suggested_roles")
        else:
            self.candidate_info["executive_summary"] = None
            self.candidate_info["job_suggestions"] = None

        recommendations = await self._recommend_jobs()
        if recommendations:
            message_parts.append(recommendations)
        message_parts.append(
            "I've saved these details. If anything looks off, please edit it directly in the profile panel or let me know."
        )

        self.conversation_state = "profile_complete"
        self.last_question = None
        self.last_question_type = None

        return "\n\n".join(part for part in message_parts if part)

    async def _generate_executive_summary(self) -> Optional[Dict[str, Any]]:
        """Produce a structured executive summary and role suggestions."""
        profile_snapshot = {
            "full_name": self.candidate_info.get("full_name"),
            "location": self.candidate_info.get("location"),
            "age": self.candidate_info.get("age"),
            "physical_condition": self.candidate_info.get("physical_condition"),
            "interests": self.candidate_info.get("interests"),
            "limitations": self.candidate_info.get("limitations"),
        }

        prompt = f"""
        You are preparing an executive summary for a job placement team.

        Candidate profile:
        {compact_json(profile_snapshot, max_field_length=220, max_total_chars=1400)}

        Produce a JSON document with this schema:
        {{
            "summary": "2-3 sentence professional overview of the candidate",
            "suggested_roles": [
                {{
                    "role": "Concise role name",
                    "reason": "Why this fits the candidate",
                    "notes": "Optional additional note or null"
                }}
            ],
            "next_steps": [
                "Concise suggestion for what to do next"
            ]
        }}

        Requirements:
        - If data is missing for any field, note that succinctly in the summary.
        - suggested_roles should contain between 2 and 4 entries tailored to the profile.
        - next_steps must contain at least one actionable suggestion.
        - Keep language plain and free from markdown.
        """

        try:
            response = await llm_service.generate_response(
                prompt,
                temperature=0.2,
                max_output_tokens=600 * int(os.getenv("TOKENS_MULT")),
            )

            parsed = json.loads(strip_json_code_fences(response))

            if not isinstance(parsed, dict):
                raise ValueError("Executive summary response is not a JSON object")

            parsed.setdefault("summary", "")
            parsed.setdefault("suggested_roles", [])
            parsed.setdefault("next_steps", [])

            return parsed
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Error generating executive summary: %s", exc)
            return None
    
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

    async def apply_manual_update(self, updates: Dict[str, Any]) -> str:
        """Apply manual profile adjustments and re-validate."""
        for field in self.FIELD_KEYS:
            if field in updates:
                value = updates[field]
                self.candidate_info[field] = value.strip() if isinstance(value, str) and value.strip() else None

        self.conversation_state = "validating_profile"
        return await self._validate_profile()
    
    def reset_conversation(self):
        """Reset the conversation state and candidate information."""
        self.conversation_state = "greeting"
        self.candidate_info = {
            "full_name": None,
            "location": None,
            "age": None,
            "physical_condition": None,
            "interests": None,
            "limitations": None,
            "validation": None,
            "executive_summary": None,
            "job_suggestions": None,
        }
        self.conversation_history = []
        self.db_session = None
        self.last_question = None
        self.last_question_type = None
