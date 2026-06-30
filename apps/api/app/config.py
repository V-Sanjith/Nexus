from typing import Optional
from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    ENV: str = Field(default="development")
    DEBUG: bool = Field(default=True)
    PORT: int = Field(default=8000)
    HOST: str = Field(default="127.0.0.1")

    # Databases
    DATABASE_PROVIDER: str = Field(default="sqlite") # "sqlite" | "postgresql"
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./nexus.db"
    )
    REDIS_URL: RedisDsn = Field(
        default="redis://localhost:6379/0"
    )

    # AI Provider
    GEMINI_API_KEY: Optional[str] = Field(default=None)

    # Observability
    SENTRY_DSN: Optional[str] = Field(default=None)
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = Field(default="http://localhost:4317")
    ENABLE_TELEMETRY: bool = Field(default=False)

settings = Settings()
