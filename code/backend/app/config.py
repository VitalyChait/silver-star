from pydantic_settings import BaseSettings
from pydantic import Field
import secrets
import os


class Settings(BaseSettings):
    app_name: str = "Silver Star API"
    environment: str = Field(default="development")
    database_url: str = Field(default="sqlite:///./data.db", alias="DATABASE_URL")
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32), alias="SECRET_KEY")
    access_token_expire_minutes: int = 60 * 24  # 24 hours
    frontend_origin: str = Field(default=f"http://localhost:{int(os.getenv('NODE_APP_PORT'))}")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
        "populate_by_name": True,
    }


settings = Settings()
