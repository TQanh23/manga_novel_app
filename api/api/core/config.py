from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Runtime configuration, read from the environment.

    Defaults match the Compose stack so a fresh clone runs without a .env file.
    Every secret here must be overridden outside local development.
    """

    model_config = SettingsConfigDict(env_file=_REPO_ROOT / ".env", extra="ignore")

    # The API and worker connect as app_rw, which owns no tables (migration 0001).
    database_url: str = "postgresql+asyncpg://app_rw:app_rw@localhost:5432/manga_novel"
    # Owner role. Only Alembic and the test fixtures connect with it.
    migration_database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/manga_novel"
    )
    # Password the baseline migration sets on app_rw; must match database_url.
    app_rw_password: SecretStr = SecretStr("app_rw")


@lru_cache
def get_settings() -> Settings:
    return Settings()
