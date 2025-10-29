import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from .utils import strip_json_code_fences

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore


logger = logging.getLogger(__name__)


class LLMService:
    """Service for interacting with LLM APIs (Gemini with OpenAI fallback)."""

    GENERIC_ERROR_MESSAGE = "I'm having trouble generating a response right now. Could you please try again?"

    def __init__(self):
        """Initialize the LLM service with configuration."""
        self.model = None
        self.openai_client = None
        self.openai_model = None
        self._initialize_gemini()
        self._initialize_openai()

    def _initialize_gemini(self) -> None:
        """Initialize the Gemini API client."""
        try:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }

            self.model = genai.GenerativeModel(
                model_name=os.getenv("GEMINI_MODEL"),
                safety_settings=safety_settings,
            )

            logger.info("[service.py] Initialized Gemini model: %s", os.getenv("GEMINI_MODEL"))
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("[service.py] Failed to initialize Gemini: %s", exc)
            raise

    def _initialize_openai(self) -> None:
        """Initialize the OpenAI fallback client if credentials are provided."""
        api_key = os.getenv("LLM_API_KEY")
        model = os.getenv("LLM_MODEL")
        base_url = os.getenv("LLM_BASE_URL")

        if not api_key or not model:
            logger.info("[service.py] OpenAI fallback not configured (missing LLM_API_KEY or LLM_MODEL).")
            return

        if OpenAI is None:
            logger.warning("[service.py] OpenAI package is not installed; fallback will be disabled.")
            return

        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url

        try:
            self.openai_client = OpenAI(**kwargs)  # type: ignore
            self.openai_model = model
            logger.info("[service.py] Initialized OpenAI fallback model: %s", model)
        except Exception as exc:  # pylint: disable=broad-except
            self.openai_client = None
            self.openai_model = None
            logger.error("Failed to initialize OpenAI fallback: %s", exc)

    async def generate_response(
        self,
        prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_output_tokens: int = 1024 * int(os.getenv("TOKENS_MULT")),
    ) -> str:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: The prompt to send to the LLM
            conversation_history: Previous conversation messages
            temperature: Controls randomness (0.0-1.0)
            max_output_tokens: Maximum number of tokens to generate
            
        Returns:
            The generated text response
        """
        for attempt in range(2):
            text = await self._generate_with_gemini(
                prompt,
                conversation_history=conversation_history,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
            if text:
                if attempt > 0:
                    logger.info("[service.py] Gemini succeeded on retry %d.", attempt)
                return text
            logger.debug("[service.py] Gemini attempt %d returned no content.", attempt + 1)

        logger.warning("[service.py] Gemini failed after 2 attempts; evaluating OpenAI fallback.")
        fallback = await self._generate_with_openai(
            prompt,
            conversation_history=conversation_history,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        if fallback:
            logger.info("[service.py] Response served via OpenAI fallback.")
            return fallback

        logger.error("[service.py] All LLM backends failed to generate a response.")
        return self.GENERIC_ERROR_MESSAGE

    async def _generate_with_gemini(
        self,
        prompt: str,
        *,
        conversation_history: Optional[List[Dict[str, str]]],
        temperature: float,
        max_output_tokens: int,
    ) -> Optional[str]:
        """Attempt to generate a response using Gemini, returning None on failure."""
        if not self.model:
            logger.error("[service.py] Gemini model is not initialized.")
            return None

        try:
            if conversation_history:
                gemini_history = []
                for message in conversation_history:
                    role = "user" if message.get("role") == "user" else "model"
                    gemini_history.append(
                        {
                            "role": role,
                            "parts": [{"text": message.get("content", "")}],
                        }
                    )
                chat = self.model.start_chat(history=gemini_history)
                response = await chat.send_message_async(
                    prompt,
                    generation_config={
                        "temperature": temperature,
                        "max_output_tokens": max_output_tokens,
                    },
                )
            else:
                response = await self.model.generate_content_async(
                    prompt,
                    generation_config={
                        "temperature": temperature,
                        "max_output_tokens": max_output_tokens,
                    },
                )

            if not response.candidates:
                logger.error("[service.py] Gemini returned no candidates. prompt=%r", prompt[:200])
                return None

            candidate = next(
                (
                    cand
                    for cand in response.candidates
                    if getattr(cand, "content", None)
                    and getattr(cand.content, "parts", None)
                ),
                response.candidates[0],
            )

            finish_reason = getattr(candidate, "finish_reason", None)
            finish_reason_name = getattr(finish_reason, "name", str(finish_reason))

            if finish_reason_name == "SAFETY":
                logger.warning(
                    "[service.py] Response was filtered for safety reasons. prompt=%r", prompt[:200]
                )
                return "I apologize, but I cannot provide a response to that request due to safety guidelines."

            if finish_reason_name == "MAX_TOKENS":
                history_chars = 0
                if conversation_history:
                    history_chars = sum(len(entry.get("content", "")) for entry in conversation_history)
                logger.warning(
                    "[service.py] Gemini hit token limit. prompt_chars=%d history_chars=%d max_output_tokens=%s",
                    len(prompt),
                    history_chars,
                    max_output_tokens,
                )

            text_parts: List[str] = []
            if getattr(candidate, "content", None) and getattr(candidate.content, "parts", None):
                for part in candidate.content.parts:
                    part_text = getattr(part, "text", None)
                    if part_text:
                        text_parts.append(part_text)

            generated_text = "".join(text_parts).strip()
            if generated_text:
                return generated_text

            try:
                generated_text = getattr(response, "text", "").strip()
                if generated_text:
                    return generated_text
            except Exception as text_error:  # pylint: disable=broad-except
                logger.error(
                    "[service.py] Gemini response.text accessor failed: %s. finish_reason=%s",
                    text_error,
                    finish_reason_name,
                )

            logger.error(
                "[service.py] Gemini returned no textual content. finish_reason=%s prompt_preview=%r",
                finish_reason_name,
                prompt[:200],
            )
            return None
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("[service.py] Unexpected Gemini error for prompt %r: %s", prompt[:200], exc)
            return None

    async def _generate_with_openai(
        self,
        prompt: str,
        *,
        conversation_history: Optional[List[Dict[str, str]]],
        temperature: float,
        max_output_tokens: int,
    ) -> Optional[str]:
        """Attempt to generate a response using the OpenAI compatible API."""
        if not self.openai_client or not self.openai_model:
            return None

        messages: List[Dict[str, str]] = []
        if conversation_history:
            for item in conversation_history:
                role = item.get("role", "user")
                mapped_role = "assistant" if role == "assistant" else "user"
                messages.append({"role": mapped_role, "content": item.get("content", "")})
        messages.append({"role": "user", "content": prompt})

        try:
            def _call_openai() -> Optional[str]:
                response = self.openai_client.chat.completions.create(  # type: ignore[attr-defined]
                    model=self.openai_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_output_tokens,
                )
                if not response.choices:
                    return None
                message = response.choices[0].message
                if not message or not getattr(message, "content", None):
                    return None
                return message.content

            text = await asyncio.to_thread(_call_openai)
            if text:
                return text.strip()
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("[service.py] OpenAI fallback failed: %s", exc)
        return None
    
    async def extract_structured_data(
        self, 
        prompt: str, 
        schema: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Extract structured data from text using the LLM.
        
        Args:
            prompt: The prompt containing text to extract from
            schema: JSON schema describing the expected structure
            conversation_history: Previous conversation messages
            
        Returns:
            Extracted data as a dictionary
        """
        extraction_prompt = f"""
        Extract the following information from the text and respond with valid JSON only:
        
        Schema: {json.dumps(schema)}
        
        Text: {prompt}
        
        Response:
        """
        
        history_tail = conversation_history[-6:] if conversation_history else None
        response = await self.generate_response(
            extraction_prompt,
            history_tail,
            temperature=0.2  # Lower temperature for more consistent extraction
        )
        
        try:
            # Handle response wrapped in markdown code blocks
            cleaned = strip_json_code_fences(response)
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.error(f"[service.py] Failed to parse JSON response: {response}")
            # Return empty structure with the same schema
            return {key: None for key in schema.keys()}


# Create a singleton instance
llm_service = LLMService()
