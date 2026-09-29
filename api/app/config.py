from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, read from environment variables or api/.env (git-ignored)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # postgresql+asyncpg://user:password@host:5432/dbname
    database_url: str

    # Development-only sign-in: requests name their user in an X-Dev-User header (see app/auth.py).
    # Off unless set, so a deployed API never accepts it.
    dev_auth: bool = False


settings = Settings()  # type: ignore[call-arg]  # values come from the environment
