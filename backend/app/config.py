from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql://radar:radar@localhost:5432/radar_regulatorio"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Anthropic AI
    anthropic_api_key: str = ""

    # Email (Resend)
    resend_api_key: str = ""

    # Security
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Application
    environment: str = "development"
    debug: bool = False
    app_name: str = "Radar Regulatório"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"

    # CORS
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Collector settings
    dou_search_keywords: list[str] = [
        "infraestrutura",
        "regulação",
        "concessão",
        "energia elétrica",
        "telecomunicações",
        "transportes",
        "aviação civil",
        "mineração",
        "saneamento",
        "petróleo",
        "gás natural",
    ]
    collector_timeout_seconds: int = 30
    collector_max_retries: int = 3
    max_normativos_per_run: int = 100

    # AI Processing
    ai_model: str = "claude-sonnet-4-6"
    ai_max_tokens: int = 2048
    ai_temperature: float = 0.1

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        # Render provides postgres:// — normalize first
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("sqlite:///") and "+aiosqlite" not in url:
            url = url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        return url

    @property
    def sync_database_url(self) -> str:
        """psycopg2-compatible URL for Alembic (sync)."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.database_url

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
