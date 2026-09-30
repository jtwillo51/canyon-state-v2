from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    """App configuration, read from environment variables or api/.env (git-ignored)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # postgresql://user:password@host:5432/dbname (hosted providers add ?sslmode=require)
    database_url: str

    # Development-only sign-in: requests name their user in an X-Dev-User header (see app/auth.py).
    # Off unless set, so a deployed API never accepts it by accident.
    dev_auth: bool = False

    # The public demo: the same header sign-in (a "View as" switcher), and the seed script may run
    # against this non-local database. SYNTHETIC DATA ONLY: never set this where real data lives.
    demo_mode: bool = False

    @property
    def header_auth(self) -> bool:
        """Whether X-Dev-User is accepted: local development or the public demo."""
        return self.dev_auth or self.demo_mode

    @property
    def sqlalchemy_url(self) -> URL:
        """DATABASE_URL for the async driver: hosted providers hand out postgresql:// URLs with libpq
        options (sslmode, channel_binding) that asyncpg doesn't accept; those become connect_args."""
        url = make_url(self.database_url)
        if url.drivername in ("postgres", "postgresql"):
            url = url.set(drivername="postgresql+asyncpg")
        query = {k: v for k, v in url.query.items() if k not in ("sslmode", "channel_binding")}
        return url.set(query=query)

    @property
    def connect_args(self) -> dict[str, Any]:
        url = make_url(self.database_url)
        args: dict[str, Any] = {}
        if url.query.get("sslmode") in ("require", "verify-ca", "verify-full"):
            args["ssl"] = "require"
        # A transaction-pooling endpoint (Neon's "-pooler" hosts) can't keep prepared statements.
        if url.host and "-pooler" in url.host:
            args["statement_cache_size"] = 0
        return args


settings = Settings()  # type: ignore[call-arg]  # values come from the environment
