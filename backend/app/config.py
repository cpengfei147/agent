from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""

    # Environment
    env: str = "development"

    # LLM - OpenAI compatible (supports DeepSeek, etc.)
    openai_api_key: str
    openai_base_url: Optional[str] = None  # 设置为 DeepSeek 等兼容 API 的 base_url
    openai_model: str = "gpt-4o"
    openai_timeout: int = 30

    # Google Maps (地址验证)
    google_maps_api_key: Optional[str] = None

    # Google Gemini (图像识别)
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.0-flash"

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
