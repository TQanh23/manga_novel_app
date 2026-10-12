from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]

# Long enough for HS256, and obviously not a real secret.
_DEV_JWT_SECRET = "local-development-jwt-secret-do-not-use-elsewhere"  # noqa: S105


class Settings(BaseSettings):
    """Runtime configuration, read from the environment.

    Defaults match the Compose stack so a fresh clone runs without a .env file.
    Every secret here must be overridden outside local development.
    """

    model_config = SettingsConfigDict(env_file=_REPO_ROOT / ".env", extra="ignore")

    # Anything other than "local" turns on Secure cookies and refuses dev secrets.
    environment: Literal["local", "production"] = "local"

    # 127.0.0.1, not localhost: Compose publishes on IPv4 only, and on Windows a
    # localhost lookup tries ::1 first and costs two seconds per connection.
    # The API and worker connect as app_rw, which owns no tables (migration 0001).
    database_url: str = "postgresql+asyncpg://app_rw:app_rw@127.0.0.1:5432/manga_novel"
    # Owner role. Only Alembic and the test fixtures connect with it.
    migration_database_url: str = (
        "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/manga_novel"
    )
    # Password the baseline migration sets on app_rw; must match database_url.
    app_rw_password: SecretStr = SecretStr("app_rw")

    redis_url: str = "redis://127.0.0.1:6379/0"
    # Prepended to every key, so several stacks or a test run can share one Redis.
    redis_key_prefix: str = "mn:"

    log_level: str = "INFO"

    # --- Auth (NFR-05) ---
    jwt_secret: SecretStr = SecretStr(_DEV_JWT_SECRET)
    access_token_ttl_seconds: int = 15 * 60
    refresh_token_ttl_seconds: int = 30 * 24 * 60 * 60
    # A refresh token presented again this soon after it was used is a duplicate
    # request (two browser tabs share one cookie), not theft: it is refused but
    # the session survives. After the window, reuse revokes the whole family.
    refresh_reuse_grace_seconds: int = 10

    # argon2id cost. The defaults are the library's (RFC 9106, low-memory profile).
    argon2_time_cost: int = 3
    argon2_memory_cost_kib: int = 65536
    argon2_parallelism: int = 4

    # Browser origins allowed to call the API with credentials. In the
    # environment this is a JSON list: CORS_ORIGINS='["https://app.example"]'.
    cors_origins: list[str] = ["http://localhost:8081"]

    # Password of the accounts `python -m api.scripts.seed` creates. Local only:
    # the seed script refuses to run in any other environment.
    seed_password: SecretStr = SecretStr("local-dev-password")

    # Fixed-window rate limits on auth routes, per window.
    rate_limit_window_seconds: int = 60
    rate_limit_auth_per_ip: int = 30
    rate_limit_auth_per_identity: int = 5
    # Author write routes, per account. Well above the auth limit: an editor
    # that autosaves calls the draft route every few seconds.
    rate_limit_author_writes_per_user: int = 120
    # Catalogue and search, per address. Browsing makes several calls a screen.
    rate_limit_catalogue_per_ip: int = 300

    @property
    def cookie_secure(self) -> bool:
        return self.environment != "local"

    @model_validator(mode="after")
    def _refuse_dev_secrets_outside_local(self) -> Self:
        if self.environment != "local" and self.jwt_secret.get_secret_value() == _DEV_JWT_SECRET:
            raise ValueError("JWT_SECRET must be set when ENVIRONMENT is not 'local'")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
