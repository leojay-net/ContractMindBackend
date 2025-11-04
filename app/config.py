"""
Configuration management for ContractMind backend
"""

from typing import Any
from pydantic import Field, field_validator, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )

    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "ContractMind Backend"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4

    # Blockchain
    SOMNIA_RPC_URL: str
    # Somnia Testnet chain ID (updated)
    CHAIN_ID: int = 50312

    # Deployed Contracts
    AGENT_REGISTRY_ADDRESS: str
    CONTRACT_MIND_HUB_ADDRESS: str

    # AI Services - Multi-LLM Support
    DEFAULT_LLM_PROVIDER: str = "gemini"  # gemini, claude, or openai

    # Gemini (Google)
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-1.5-pro"

    # Claude (Anthropic)
    ANTHROPIC_API_KEY: str | None = None
    CLAUDE_MODEL: str = "claude-3-5-sonnet-20241022"

    # OpenAI
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4-turbo-preview"

    # LLM Generation Settings
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2000
    LLM_TIMEOUT: int = 30

    # Database - Supabase Connection (psycopg2 style with lowercase env vars)
    user: str
    password: str
    host: str
    port: int = 5432
    dbname: str
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: str
    REDIS_CACHE_TTL: int = 300

    # Authentication
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = Field(default_factory=list)

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 10

    # WebSocket
    WS_HEARTBEAT_INTERVAL: int = 30
    WS_MAX_CONNECTIONS_PER_USER: int = 3

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # MCP
    MCP_SERVER_NAME: str = "ContractMind"
    MCP_VERSION: str = "1.0.0"

    # Analytics
    ANALYTICS_BATCH_SIZE: int = 100
    ANALYTICS_FLUSH_INTERVAL: int = 60


# Global settings instance
settings = Settings()
