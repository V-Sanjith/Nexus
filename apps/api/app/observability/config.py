from pydantic_settings import BaseSettings

class ObservabilitySettings(BaseSettings):
    class Config:
        env_file = ".env"
        extra = "ignore"

    SENTRY_DSN: str | None = None
    OTEL_SERVICE_NAME: str = "nexus-api"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    ENABLE_TELEMETRY: bool = False

obs_settings = ObservabilitySettings()
