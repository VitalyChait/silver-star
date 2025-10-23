import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


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
        "env_file": str(Path(__file__).parent.parent / ".llm_config"),
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
        "populate_by_name": True,
    }
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Validate provider-specific settings
        if self.gemini_provider == "vertex" and not (self.gemini_vertex_region and self.gemini_vertex_project):
            raise ValueError(
                "GEMINI_VERTEX_REGION and GEMINI_VERTEX_PROJECT are required when GEMINI_PROVIDER=vertex"
            )


# Create a singleton instance
llm_config = LLMConfig()
