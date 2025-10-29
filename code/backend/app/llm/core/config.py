from pathlib import Path
from typing import Optional

from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings


ENV_PATH = Path(__file__).resolve().parents[4] / ".env"


class LLMConfig(BaseSettings):
    """Configuration for LLM services."""
    
    # Gemini API Configuration
    gemini_api_key: str = Field(..., alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")
    gemini_provider: str = Field(default="ai_studio", alias="GEMINI_PROVIDER")
    
    # Vertex AI Settings (only required if GEMINI_PROVIDER=vertex)
    gemini_vertex_region: Optional[str] = Field(default=None, alias="GEMINI_VERTEX_REGION")
    gemini_vertex_project: Optional[str] = Field(default=None, alias="GEMINI_VERTEX_PROJECT")
    
    # OpenRouter fallback configuration (optional)
    openrouter_api_key: Optional[str] = Field(default=None, alias="OPENROUTER_API_KEY")
    openrouter_model: Optional[str] = Field(default=None, alias="OPENROUTER_MODEL")
    openrouter_base_url: Optional[str] = Field(default=None, alias="OPENROUTER_BASE_URL")
    
    model_config = {
        "env_file": (str(ENV_PATH),),
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
        "populate_by_name": True,
    }

    @field_validator("gemini_api_key", "gemini_model")
    @classmethod
    def _require_non_empty(cls, value: str, info):
        stripped = value.strip()
        if not stripped:
            field_alias = cls.model_fields[info.field_name].alias or info.field_name.upper()
            raise ValueError(f"{field_alias} must be set and non-empty.")
        return stripped

    @field_validator("gemini_provider")
    @classmethod
    def _validate_provider(cls, value: str):
        normalized = value.strip().lower()
        allowed = {"ai_studio", "vertex"}
        if normalized not in allowed:
            raise ValueError(f"GEMINI_PROVIDER must be one of {sorted(allowed)}.")
        return normalized

    @field_validator("gemini_vertex_region", "gemini_vertex_project", mode="before")
    @classmethod
    def _empty_vertex_values_to_none(cls, value: Optional[str]):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("openrouter_api_key", "openrouter_model", "openrouter_base_url", mode="before")
    @classmethod
    def _empty_optional_values_to_none(cls, value: Optional[str]):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _validate_provider_dependencies(self):
        if self.gemini_provider == "vertex":
            missing = [name for name in ("gemini_vertex_region", "gemini_vertex_project") if getattr(self, name) is None]
            if missing:
                missing_aliases = [self.model_fields[name].alias for name in missing]
                raise ValueError(
                    "Vertex configuration missing required settings: "
                    + ", ".join(missing_aliases)
                )

        openrouter_fields = {
            "openrouter_api_key": self.openrouter_api_key,
            "openrouter_model": self.openrouter_model,
        }
        provided_openrouter = {name: value for name, value in openrouter_fields.items() if value}
        if provided_openrouter and len(provided_openrouter) != len(openrouter_fields):
            missing = [
                self.model_fields[name].alias
                for name in openrouter_fields
                if not openrouter_fields[name]
            ]
            raise ValueError(
                "OPENROUTER_* settings must include values for: " + ", ".join(missing)
            )

        if self.openrouter_base_url and not self.openrouter_base_url.startswith(("http://", "https://")):
            raise ValueError("OPENROUTER_BASE_URL must start with http:// or https://.")

        return self


# Create a singleton instance
try:
    llm_config = LLMConfig()
except ValidationError as exc:
    def _alias_for(field_name: str) -> str:
        field = LLMConfig.model_fields.get(field_name)
        return field.alias if field and field.alias else field_name.upper()

    missing_vars = []
    other_errors = []
    for error in exc.errors():
        field_name = error.get("loc", ["unknown"])[0]
        alias = _alias_for(field_name)
        msg = error.get("msg", "Invalid value")
        if error.get("type") in {"missing", "string_type", "value_error"} or "Field required" in msg:
            if "Field required" in msg or error.get("type") == "missing":
                missing_vars.append(alias)
            else:
                other_errors.append(f"{alias}: {msg}")
        else:
            other_errors.append(f"{alias}: {msg}")

    error_lines = []
    if missing_vars:
        error_lines.append(
            "Missing required environment variables: "
            + ", ".join(sorted(set(missing_vars)))
        )
    if other_errors:
        error_lines.append("Environment validation errors: " + "; ".join(other_errors))
    error_lines.append("Set these values in code/.env or your shell environment.")

    raise RuntimeError(" ".join(error_lines)) from exc
