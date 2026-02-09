from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""

    # Environment
    env: str = "development"

    # LLM - OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4o"
    openai_timeout: int = 30

    # Google Maps
    google_maps_api_key: Optional[str] = None

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/erabu"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Session
    session_ttl_hours: int = 24
    max_messages_cached: int = 20

    # Rate Limiting
    rate_limit_per_minute: int = 30

    # Logging
    log_level: str = "INFO"

    # Langfuse (可观测性)
    langfuse_enabled: bool = False
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_host: str = "https://cloud.langfuse.com"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
