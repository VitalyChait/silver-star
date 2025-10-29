import json
import logging
import os
from typing import Any, Dict, List

from ..core.service import llm_service
from ..core.utils import compact_json, strip_json_code_fences

logger = logging.getLogger(__name__)

class ProfileValidationService:
    """Validates the completeness and coherence of a candidate profile."""

    REQUIRED_FIELDS = [
        "full_name",
        "location",
        "age",
        "physical_condition",
        "interests",
        "limitations",
    ]

    async def validate_profile(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the candidate profile using heuristics and LLM assistance."""
        result: Dict[str, Any] = {
            "is_complete": False,
            "missing_fields": [],
            "issues": [],
            "summary": None,
            "notes": None,
        }

        missing_fields: List[str] = [
            field for field in self.REQUIRED_FIELDS if not profile.get(field)
        ]
        result["missing_fields"] = missing_fields

        if missing_fields:
            result["issues"].append(
                "Some required fields are missing: "
                + ", ".join(field.replace("_", " ") for field in missing_fields)
            )

        try:
            profile_snapshot = compact_json(
                {field: profile.get(field) for field in self.REQUIRED_FIELDS},
                max_field_length=220 * int(os.getenv("TOKENS_MULT")),
                max_total_chars=1400 * int(os.getenv("TOKENS_MULT")),
            )

            validation_prompt = f"""
            You are validating a candidate intake form for a community job placement program.
            Review the profile below and determine if it contains meaningful information for each field.

            Candidate Profile:
            {profile_snapshot}

            Respond with JSON using this schema:
            {{
                "is_complete": true/false,
                "missing_fields": ["field_name", ...],
                "issues": ["short explanation", ...],
                "summary": "friendly one or two sentence summary of the candidate",
                "notes": "optional additional note or null"
            }}

            - Treat values like "N/A", "unknown", "none" as missing.
            - The summary should read naturally and reference key details.
            - If everything looks good, keep "issues" as an empty list.
            """

            llm_response = await llm_service.generate_response(
                validation_prompt, temperature=0.2, max_output_tokens=1024 * int(os.getenv("TOKENS_MULT"))
            )

            llm_result = json.loads(strip_json_code_fences(llm_response))

            for key in result:
                if key in llm_result and llm_result[key] is not None:
                    result[key] = llm_result[key]

            # Merge missing field lists
            llm_missing = llm_result.get("missing_fields") or []
            result["missing_fields"] = sorted(
                set(result["missing_fields"]) | {field for field in llm_missing}
            )

            if result["missing_fields"]:
                result["is_complete"] = False
            else:
                result["is_complete"] = bool(llm_result.get("is_complete", True))

        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Profile validation fallback due to error: %s", exc)
            # Fall back to heuristic completeness check
            result["is_complete"] = len(result["missing_fields"]) == 0
            if not result["summary"]:
                result["summary"] = (
                    "I've recorded your details. Everything looks good from what I can see."
                    if result["is_complete"]
                    else "I still need a bit more information before the profile is complete."
                )

        if not result["summary"]:
            result["summary"] = (
                "I've captured all of your details and everything looks complete."
                if result["is_complete"]
                else "I still need a bit more information before the profile is complete."
            )

        if not result["notes"]:
            result["notes"] = None

        return result


profile_validation_service = ProfileValidationService()
