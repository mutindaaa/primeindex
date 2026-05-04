from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = Field(default="sqlite:///./primeindex.db")

    anthropic_api_key: str = ""
    google_places_api_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "prime-index/0.1 by u/TBD"

    environment: str = "development"
    allowed_origins: str = "http://localhost:3000"
    log_level: str = "INFO"
    sentry_dsn: str = ""

    classifier_version: str = "haiku-4-5-v1"
    anthropic_model: str = "claude-haiku-4-5-20251001"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
