from typing import Any

from pydantic import SecretStr, model_validator
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

    # Background jobs (Inngest, app/jobs/). The endpoint Inngest calls exists only when one of these is set:
    # - inngest_signing_key: production. Every request must be signed with this key.
    # - inngest_dev: the local Inngest Dev Server, which doesn't sign requests. Local development only:
    #   refused unless DEV_AUTH is on, so it can't be switched on for a deployed server.
    inngest_signing_key: SecretStr | None = None
    inngest_dev: bool = False

    @model_validator(mode="after")
    def _inngest_dev_is_local_only(self) -> "Settings":
        if self.inngest_dev and not self.dev_auth:
            raise ValueError("INNGEST_DEV skips request signing; it's allowed only with DEV_AUTH (local development)")
        return self

    @property
    def jobs_enabled(self) -> bool:
        return self.inngest_dev or self.inngest_signing_key is not None

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
