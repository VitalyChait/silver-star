import json
import logging
import os
from typing import Dict, List, Optional, Tuple, Any
import re
import os
import time
from urllib.parse import urlencode

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
        self.retry_counts: Dict[str, int] = {}
        self._pending_correction: Optional[Dict[str, str]] = None
        self._last_geo_lookup_ts: float = 0.0

    def _next_missing_field(self) -> Optional[str]:
        for key in self.FIELD_KEYS:
            if not self.candidate_info.get(key):
                return key
        return None

    async def _auto_extract_all(self, message: str) -> set:
        """Attempt to extract any missing fields from a single user message.

        Only fills fields that are currently empty to avoid overwriting.
        """
        filled: set = set()
        if not message:
            return filled
        schema = {
            "full_name": "string",
            "location": "string",
            "age": "string",
            "physical_condition": "string",
            "interests": "string",
            "limitations": "string",
        }
        try:
            prompt = (
                "Extract any of the following that the person clearly provided in the text. "
                "Return null for items not present."
                f" Text: {message}"
            )
            data = await llm_service.extract_structured_data(prompt, schema, self.conversation_history)
        except Exception:
            data = {}

        # Heuristics first for name/location/condition/limits/interests
        if not self.candidate_info.get("full_name"):
            name_inline = self._detect_full_name_from_message(message)
            if name_inline:
                self.candidate_info["full_name"] = name_inline
                filled.add("full_name")
        if not self.candidate_info.get("location"):
            loc_inline = self._detect_location_from_message(message)
            if loc_inline:
                self.candidate_info["location"] = loc_inline
                filled.add("location")
        if not self.candidate_info.get("physical_condition"):
            cond_inline = self._detect_physical_condition_from_message(message)
            if cond_inline:
                self.candidate_info["physical_condition"] = cond_inline
                filled.add("physical_condition")
        if not self.candidate_info.get("interests"):
            interests_inline = self._detect_interests_from_message(message)
            if interests_inline:
                self.candidate_info["interests"] = interests_inline
                filled.add("interests")
        if not self.candidate_info.get("limitations"):
            limits_inline = self._detect_limitations_from_message(message)
            if limits_inline:
                self.candidate_info["limitations"] = limits_inline
                filled.add("limitations")

        # LLM extraction fallback for anything still missing
        try:
            if not self.candidate_info.get("full_name") and data.get("full_name"):
                self.candidate_info["full_name"] = str(data.get("full_name")).strip()
                filled.add("full_name")
            if not self.candidate_info.get("location") and data.get("location"):
                raw_loc = str(data.get("location")).strip()
                verified = self._validate_and_format_location(raw_loc)
                self.candidate_info["location"] = verified or raw_loc
                filled.add("location")
            if not self.candidate_info.get("age") and data.get("age"):
                # normalize age to number string
                digits = re.findall(r"\d{1,3}", str(data.get("age")))
                if digits:
                    try:
                        age_int = int(digits[0])
                        if 10 <= age_int <= 120:
                            self.candidate_info["age"] = str(age_int)
                            filled.add("age")
                    except ValueError:
                        pass
            if not self.candidate_info.get("physical_condition") and data.get("physical_condition"):
                self.candidate_info["physical_condition"] = str(data.get("physical_condition")).strip()
                filled.add("physical_condition")
            if not self.candidate_info.get("interests") and data.get("interests"):
                self.candidate_info["interests"] = str(data.get("interests")).strip()
                filled.add("interests")
            if not self.candidate_info.get("limitations") and data.get("limitations"):
                self.candidate_info["limitations"] = self._normalize_limitations(str(data.get("limitations")).strip())
                filled.add("limitations")
        except Exception:
            pass
        return filled

    def _advance_state_if_filled(self):
        """Advance the conversation state past fields that are already filled."""
        mapping = [
            ("collecting_full_name", "full_name"),
            ("collecting_location", "location"),
            ("collecting_age", "age"),
            ("collecting_physical_condition", "physical_condition"),
            ("collecting_interests", "interests"),
            ("collecting_limitations", "limitations"),
        ]
        # Iterate at most length of mapping to prevent infinite loops
        for _ in range(len(mapping)):
            progressed = False
            for state, field in mapping:
                if self.conversation_state == state and self.candidate_info.get(field):
                    # Move to next logical state
                    idx = [s for s, _ in mapping].index(state)
                    if idx + 1 < len(mapping):
                        self.conversation_state = mapping[idx + 1][0]
                    else:
                        self.conversation_state = "validating_profile"
                    progressed = True
                    break
            if not progressed:
                break

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

    @staticmethod
    def _detect_location_from_message(message: str) -> Optional[str]:
        """Detect a likely location phrase without scooping other fields."""
        if not message:
            return None
        sentences = re.split(r"[\.!?]+\s+", message)
        leadins = re.compile(r"(?:\b(?:i(?:'m| am)?|i live|i reside|i work|i'm based|i am based|i'm located|i am located|based|located)\s+(?:in|at|near|around)\s+|\bfrom\s+)", re.IGNORECASE)
        exclusion = re.compile(r"\b(health|condition|issues?|interests?|limitations?|remote|computer|drive|driving|teacher|wood|work\s+with\s+wood)\b", re.IGNORECASE)
        for sent in sentences:
            s = sent.strip()
            if not s or exclusion.search(s):
                continue
            m = leadins.search(s)
            if not m:
                continue
            candidate = s[m.end():]
            candidate = re.split(r"[\.;!]\s*", candidate, maxsplit=1)[0]
            candidate = candidate.strip(" ,.!?")
            if not candidate or len(candidate) < 2 or len(candidate) > 80:
                continue
            if not re.search(r"[A-Za-z]", candidate):
                continue
            if re.search(r"\b(\d{2,4}\s*(years|yrs)\b|\bI\s+am\s+\d+\b)", candidate, re.IGNORECASE):
                continue
            return re.sub(r"\s+", " ", candidate)
        return None

    def _validate_and_format_location(self, candidate: str) -> Optional[str]:
        """Optionally validate a free-text location using Nominatim and return a clean display string.

        Controlled by env GEO_VALIDATE (default: on). Uses a short timeout and polite User-Agent.
        """
        if not candidate:
            return None
        # Basic clean-up
        q = re.sub(r"\s+", " ", candidate).strip(" ,")
        if not q or len(q) < 2:
            return None
        # Skip network if disabled
        enabled = os.getenv("GEO_VALIDATE", "1") not in {"0", "false", "False"}
        if not enabled:
            return q
        # Rate-limit a bit to be polite
        now = time.time()
        if now - getattr(self, "_last_geo_lookup_ts", 0) < 1.0:
            return q
        self._last_geo_lookup_ts = now
        try:
            import requests
            params = {"q": q, "format": "json", "addressdetails": 1, "limit": 1}
            url = f"https://nominatim.openstreetmap.org/search?{urlencode(params)}"
            headers = {"User-Agent": "SilverStar-Asteroid/1.0 (contact: support@silverstar.local)"}
            resp = requests.get(url, headers=headers, timeout=4)
            if resp.ok:
                data = resp.json()
                if isinstance(data, list) and data:
                    item = data[0]
                    display = item.get("display_name") or q
                    # Try to format as City, State, Country when possible
                    addr = item.get("address") or {}
                    parts = [addr.get("city") or addr.get("town") or addr.get("village") or addr.get("municipality"), addr.get("state"), addr.get("country")]
                    compact = ", ".join([p for p in parts if p])
                    return compact or display or q
        except Exception:
            return q
        return q

    @staticmethod
    def _detect_physical_condition_from_message(message: str) -> Optional[str]:
        """Heuristically detect a physical condition summary from a message."""
        if not message:
            return None
        phys_patterns = [
            r"\bphysical\s+condition\s*(?:is|:)?\s*([^.!?]{2,120})",
            r"\b(?:health|health\s+problems|medical\s+issues)\s*(?:is|are|:)?\s*([^.!?]{2,120})",
            r"\b(?:in|with)\s+(?:excellent|good|fair|poor)\s+(?:health|shape|condition)\b",
            r"\bno\s+health\s+problems?\b",
        ]
        for pattern in phys_patterns:
            m = re.search(pattern, message, re.IGNORECASE)
            if m:
                value = m.group(1) if m.lastindex else m.group(0)
                value = re.sub(r"\s+", " ", value).strip(" .,!")
                if value:
                    return value
        return None

    @staticmethod
    def _detect_common_corrections(field: str, value: str) -> Optional[str]:
        """Detect simple, high-confidence typo corrections for specific fields.

        Returns the corrected string if a likely typo was found; otherwise None.
        """
        if not value:
            return None
        text = value
        # Physical condition: common 'no' -> 'ho' slip
        if field == "physical_condition":
            corrected = re.sub(r"\b[hg]o\s+health\b", "no health", text, flags=re.IGNORECASE)
            if corrected != text:
                return corrected
        return None

    def _maybe_confirm_correction(self, field: str, original: str, corrected: str) -> Optional[str]:
        """Ask the user to confirm an auto-correction. Returns a prompt if asked."""
        if not corrected or corrected.strip().lower() == original.strip().lower():
            return None
        label = self.FIELD_LABEL_MAP.get(field, field.replace("_", " "))
        self._pending_correction = {
            "field": field,
            "original": original,
            "corrected": corrected,
        }
        prompt = (
            f"Just to confirm, for your {label}, did you mean \"{corrected}\" instead of \"{original}\"? "
            "You can say yes or no."
        )
        self.last_question = prompt
        self.last_question_type = "confirm_correction"
        return prompt

    @staticmethod
    def _detect_interests_from_message(message: str) -> Optional[str]:
        """Detect interests from free text (e.g., "I'd like to be a teacher")."""
        if not message:
            return None
        patterns = [
            r"\b(?:i\s+would\s+like\s+to\s+be|i\s+want\s+to\s+be|i['\s]m\s+interested\s+in|i\s+am\s+interested\s+in|i\s+like\s+to\s+work\s+as|my\s+interests\s+are)\s+([^.!?]{2,120})",
            r"^\s*(teacher|tutor|driver|cashier|nurse|caregiver|coordinator)\s*$",
        ]
        for pat in patterns:
            m = re.search(pat, message, re.IGNORECASE)
            if m:
                val = (m.group(1) if m.lastindex else m.group(0)).strip(" .,!")
                return re.sub(r"\s+", " ", val)
        return None

    @staticmethod
    def _normalize_limitations(value: str) -> str:
        """Normalize common limitation phrasings to avoid inversions (e.g., remote)."""
        if not value:
            return value
        text = value.lower()
        # Remote work negatives
        remote_negative = any(
            phrase in text
            for phrase in [
                "not remote",
                "no remote",
                "don't want to work remotely",
                "do not want to work remotely",
                "no remote work",
                "prefer in-person",
                "in person only",
                "on-site only",
                "onsite only",
                "not work remotely",
                "avoid remote",
            ]
        )
        if remote_negative:
            return "prefers non-remote (in-person); no remote work"
        return value

    @staticmethod
    def _detect_limitations_from_message(message: str) -> Optional[str]:
        """Detect limitations, with special handling for remote preference negatives."""
        if not message:
            return None
        patterns = [
            r"\b(?:not|no)\s+remote\b",
            r"\bprefer\s+(?:no|not)\s+remote\b",
            r"\b(?:in\s*person|on-?site|onsite)\s+only\b",
            r"\b(?:do\s+not|don't)\s+want\s+to\s+work\s+remotely\b",
            r"\b(?:cannot|can't|do\s+not\s+want\s+to)\s+lift\s+\d+\s*(?:lbs|pounds)?\b",
            r"\bprefer\s+to\s+avoid\s+([^.!?]{2,120})",
        ]
        for pat in patterns:
            m = re.search(pat, message, re.IGNORECASE)
            if m:
                val = (m.group(1) if m.lastindex else m.group(0)).strip(" .,!")
                norm = CandidateChatbot._normalize_limitations(val)
                return norm
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
            # Handle pending correction confirmation first
            if self.last_question_type == "confirm_correction" and self._pending_correction:
                norm = (message or "").strip().lower()
                yes = {"yes", "yep", "yeah", "correct", "right", "ok", "okay"}
                no = {"no", "nope", "nah", "incorrect", "wrong"}
                if any(w == norm or norm.startswith(w) for w in yes):
                    fld = self._pending_correction["field"]
                    val = self._pending_correction["corrected"]
                    self.candidate_info[fld] = val
                    self._pending_correction = None
                    self.last_question = None
                    self.last_question_type = None
                    # Continue as normal after applying
                elif any(w == norm or norm.startswith(w) for w in no):
                    # Keep original, discard correction
                    self._pending_correction = None
                    self.last_question = None
                    self.last_question_type = None
                else:
                    # Ask again briefly
                    response = "Please reply yes or no so I can confirm the correction."
                    self.conversation_history.append({"role": "assistant", "content": response})
                    return response, self.candidate_info

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
                # Clear retry count on success
                if self.last_question_type:
                    self.retry_counts[self.last_question_type] = 0
            else:
                # Stuck-loop breaker: escalate clarity after 2 attempts
                qtype = self.last_question_type
                self.retry_counts[qtype] = self.retry_counts.get(qtype, 0) + 1

                # Allow user to skip
                if message.strip().lower() == "skip":
                    # Move on without setting the field
                    self.last_question = None
                    self.last_question_type = None
                    self.conversation_state = "validating_profile"
                    return await self._validate_profile(), self.candidate_info

                if self.retry_counts[qtype] >= 2:
                    label = self.FIELD_LABEL_MAP.get(qtype, qtype.replace("_", " "))
                    examples = {
                        "full_name": "e.g., 'Jane Doe'",
                        "location": "e.g., 'Boston, MA'",
                        "age": "e.g., '65'",
                        "physical_condition": "e.g., 'excellent health'",
                        "interests": "e.g., 'teaching'",
                        "limitations": "e.g., 'no remote work'",
                    }
                    example = examples.get(qtype, "")
                    response = (
                        f"I still need your {label}. {example} If you'd rather come back to this later, say 'skip'."
                    )
                else:
                    # Re-ask simply without LLM to avoid repetition loops
                    label = self.FIELD_LABEL_MAP.get(self.last_question_type, self.last_question_type)
                    response = f"Could you please share your {label}?"

                self.conversation_history.append({"role": "assistant", "content": response})
                if self.enable_audio:
                    await self._play_response_audio(response)
                self.last_question = response
                return response, self.candidate_info
        
        inline_name = None
        if message:
            inline_name = self._detect_full_name_from_message(message)
        if inline_name:
            current_name = self.candidate_info.get("full_name")
            name_mentioned = "name" in message.lower()
            if inline_name != current_name and (self.conversation_state in {"collecting_full_name"} or name_mentioned or not current_name):
                self.candidate_info["full_name"] = inline_name

        # Try to auto-fill any missing fields from this message
        filled_now = await self._auto_extract_all(message)
        # If we just filled what we were asking about, clear the pending question
        if self.last_question_type and self.last_question_type in filled_now:
            self.last_question = None
            self.last_question_type = None
        # Advance state if the currently awaited field is already filled
        self._advance_state_if_filled()

        # Process based on current conversation state
        if self.conversation_state == "greeting":
            detected_name = self._detect_full_name_from_message(message)
            if detected_name:
                self.candidate_info["full_name"] = detected_name
                # Try to also detect location from the same message to avoid re-asking
                inline_location = self._detect_location_from_message(message)
                if inline_location:
                    verified = self._validate_and_format_location(inline_location)
                    self.candidate_info["location"] = verified or inline_location
                    self.conversation_state = "collecting_age"
                    preferred_name = self._preferred_name()
                    name_fragment = f", {preferred_name}" if preferred_name else ""
                    response = f"Thanks{name_fragment}! To make sure opportunities are appropriate, could you share your age?"
                    self.last_question = response
                    self.last_question_type = "age"
                else:
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
        elif self.conversation_state == "awaiting_recommendation_consent":
            # Ask user if they want job positions generated now
            normalized = (message or "").strip().lower()
            yes = {"yes", "yep", "yeah", "sure", "please", "ok", "okay", "go ahead", "do it", "generate", "yes please"}
            no = {"no", "nope", "nah", "not now", "later", "skip"}
            if any(normalized.startswith(tok) for tok in yes):
                self.conversation_state = "recommending_jobs"
                response = await self._recommend_jobs()
                # After sending recs, mark profile complete
                self.conversation_state = "profile_complete"
                self.last_question = None
                self.last_question_type = None
            elif any(normalized.startswith(tok) for tok in no):
                response = "No problem — we can generate job matches whenever you're ready."
                self.conversation_state = "profile_complete"
                self.last_question = None
                self.last_question_type = None
            else:
                response = "Would you like me to generate job positions now?"
                self.last_question = response
                self.last_question_type = "recommendations_consent"
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
        Your name is Asteroid, you are the 'Silver Star' job platform helpful recruitment chatbot assistant.
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
            logger.error("[chatbot.py] LLM judge failed: %s", exc)
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
            "[chatbot.py] Field change judge result | field=%s | should_replace=%s | confidence=%.2f | reason=%s | proposed=%s",
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
            logger.error(f"[chatbot.py] Error playing audio response: {str(e)}")

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
        # Before asking for confirmation, check what we actually have
        missing = [key for key in self.FIELD_KEYS if not self.candidate_info.get(key)]

        # If nothing is filled in, skip confirmation and start collecting from the top
        if len(missing) == len(self.FIELD_KEYS):
            self.conversation_state = "collecting_full_name"
            response = "Let's get started. Could you please share your full name?"
            self.last_question = response
            self.last_question_type = "full_name"
            return response

        # If some fields are missing but not all, ask only for the next missing field
        if missing:
            next_field = missing[0]
            self.conversation_state = self.FIELD_STATE_MAP.get(next_field, "collecting_full_name")
            return await self._ask_for_field(next_field)

        # If we have all fields, proceed to validation/summary as usual
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
        
        response = "Hello! My name is Asteroid, I am the Silver Star job platform chatbot assistant. Could you please share your full name so we can get started?"
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
            # Try to capture location from the same message to skip redundant prompt
            inline_location = self._detect_location_from_message(message)
            if inline_location:
                self.candidate_info["location"] = inline_location
                self.conversation_state = "collecting_age"
                preferred_name = self._preferred_name()
                name_fragment = f", {preferred_name}" if preferred_name else ""
                response = f"Thanks{name_fragment}! To make sure opportunities are appropriate, could you share your age?"
                self.last_question = response
                self.last_question_type = "age"
                return response
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
            logger.error(f"[chatbot.py] Error extracting full name: {str(e)}")
            response = "I'm having trouble understanding. Could you please tell me your full name?"
            self.last_question = response
            self.last_question_type = "full_name"
            return response
    
    async def _extract_location(self, message: str, validated_value: Optional[str] = None) -> str:
        """Extract the candidate's location from their message."""
        schema = {"location": "string"}
        location = None
        
        def _extract_age_inline(text: str) -> Optional[str]:
            if not text:
                return None
            digits = re.findall(r"\b(\d{1,3})\b", text)
            for d in digits:
                try:
                    val = int(d)
                    if 10 <= val <= 120:
                        return str(val)
                except ValueError:
                    continue
            return None
        
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
                verified = self._validate_and_format_location(location)
                self.candidate_info["location"] = verified or location
                # Try to capture age from the same message to avoid re-asking
                inline_age = _extract_age_inline(message)
                if inline_age:
                    self.candidate_info["age"] = inline_age
                    # Proceed to physical condition next
                    inline_condition = self._detect_physical_condition_from_message(message)
                    if inline_condition:
                        self.candidate_info["physical_condition"] = inline_condition
                        self.conversation_state = "collecting_interests"
                        response = "Thanks for sharing. What kinds of activities or roles are you most interested in doing?"
                        self.last_question = response
                        self.last_question_type = "interests"
                        return response
                    self.conversation_state = "collecting_physical_condition"
                    response = "Thank you. Could you describe your current physical condition or anything I should keep in mind?"
                    self.last_question = response
                    self.last_question_type = "physical_condition"
                    return response

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
            logger.error(f"[chatbot.py] Error extracting location: {str(e)}")
            
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
                logger.error(f"[chatbot.py] Error extracting age: {str(e)}")

        if age_value:
            self.candidate_info["age"] = age_value
            # Try to detect physical condition if provided in the same message
            inline_condition = self._detect_physical_condition_from_message(message)
            if inline_condition:
                self.candidate_info["physical_condition"] = inline_condition
                self.conversation_state = "collecting_interests"
                response = "Thanks for sharing. What kinds of activities or roles are you most interested in doing?"
                self.last_question = response
                self.last_question_type = "interests"
                return response

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
                condition = condition.strip()
                # Check for simple, high-confidence typo corrections
                corrected = self._detect_common_corrections("physical_condition", condition)
                if corrected:
                    maybe = self._maybe_confirm_correction("physical_condition", condition, corrected)
                    if maybe:
                        return maybe
                self.candidate_info["physical_condition"] = condition
                # Also attempt to capture interests from the same message to avoid re-asking
                inline_interests = self._detect_interests_from_message(message)
                if inline_interests:
                    self.candidate_info["interests"] = inline_interests
                    self.conversation_state = "collecting_limitations"
                    response = "That's helpful. Are there any limitations or things you prefer to avoid so we can plan around them?"
                    self.last_question = response
                    self.last_question_type = "limitations"
                    return response

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
            logger.error(f"[chatbot.py] Error extracting physical condition: {str(e)}")

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
                # Try to parse limitations from the same message
                inline_limits = self._detect_limitations_from_message(message)
                if inline_limits:
                    self.candidate_info["limitations"] = inline_limits
                    self.conversation_state = "validating_profile"
                    return await self._validate_profile()

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
            logger.error(f"[chatbot.py] Error extracting interests: {str(e)}")

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
                proposed = self._normalize_limitations(limitations.strip())
                # sanity: do not accept if this clearly looks like a location or interest spillover
                if re.search(r"\b(Boston|MA|USA|street|road|avenue|interest|teaching|wood)\b", proposed, re.IGNORECASE):
                    # Ask for clarification instead of setting a wrong value
                    response = "Could you confirm your limitations (e.g., 'no remote work', 'no driving over 3 hours')?"
                    self.last_question = response
                    self.last_question_type = "limitations"
                    return response
                self.candidate_info["limitations"] = proposed
            else:
                self.candidate_info["limitations"] = None

            self.conversation_state = "validating_profile"
            return await self._validate_profile()
        except Exception as e:
            logger.error(f"[chatbot.py] Error extracting limitations: {str(e)}")

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
                Your name is Asteroid, you are the 'Silver Star' job platform helpful recruitment chatbot assistant.
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

        message_parts = []
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
            # Only include the basic validation summary if we do not have an executive summary
            if summary:
                message_parts.insert(0, summary.strip())

        # Ask for consent before generating job positions
        consent_question = "Would you like me to generate job positions now?"
        message_parts.append(consent_question)

        self.conversation_state = "awaiting_recommendation_consent"
        self.last_question = consent_question
        self.last_question_type = "recommendations_consent"

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
        Your name is Asteroid, you are the 'Silver Star' job platform helpful recruitment chatbot assistant.
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
        - Strictly honor explicit constraints in "limitations". If the candidate says they do not want remote work,
          reflect that as a non-remote preference and DO NOT invert it into a remote preference.
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
            logger.error("[chatbot.py] Error generating executive summary: %s", exc)
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
                            recommendation_text += f"{i}. {job_details['title']} at {job_details['company'] or 'A great company'}\n"
                            recommendation_text += f"   Location: {job_details['location'] or 'Various locations'}\n"
                            recommendation_text += f"   Match Score: {rec['match_score']}%\n"
                            recommendation_text += f"   Why it's a good fit: {rec['match_reason']}\n\n"
                    
                    recommendation_text = "\n===BEGIN_RECS===\n" + recommendation_text
                    recommendation_text += "Would you like more details about any of these positions, or would you like to see more recommendations?\n"
                    recommendation_text += "===END_RECS===\n"
                    
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
                
                Important constraints:
                - Respect the candidate's "limitations" strictly. If they state they do NOT want remote work, only suggest non-remote (in-person) roles.
                - Do not contradict the profile; never invert negative preferences into positives.
                
                Format your response in a friendly, conversational way.
                """
                
                text = await llm_service.generate_response(prompt)
                # Wrap fallback block so UI preserves newlines nicely
                return "\n===BEGIN_RECS===\n" + text + "\n===END_RECS===\n"
        except Exception as e:
            logger.error(f"[chatbot.py] Error generating job recommendations: {str(e)}")
            
            # Fallback to a generic response
            return "I'm having trouble finding specific job recommendations right now. Based on your profile, I'd suggest looking for positions that match your skills and availability. Would you like me to provide some general job search advice instead?"
    
    async def _handle_general_query(self, message: str) -> str:
        """Handle general queries outside the main conversation flow."""
        prompt = f"""
        Your name is Asteroid, you are the 'Silver Star' job platform helpful recruitment chatbot assistant.
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
