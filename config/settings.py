"""Config — all secrets from env vars."""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # AI Provider (supports both Gemini and OpenAI)
    gemini_api_key: str = ""
    openai_api_key: str = ""
    default_provider: str = "gemini"  # "gemini" or "openai"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"

    # GitHub integration
    github_token: Optional[str] = None
    github_webhook_secret: Optional[str] = None

    # Review settings
    max_file_size_kb: int = 500
    max_diff_lines: int = 2000
    severity_threshold: str = "low"  # low, medium, high, critical

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
