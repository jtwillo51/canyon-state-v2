"""Turning a hosted provider's DATABASE_URL into what the async driver needs."""

from app.config import Settings


def test_neon_style_url_becomes_asyncpg_with_ssl() -> None:
    s = Settings(database_url="postgresql://u:p@ep-cool-name-123.us-east-2.aws.neon.tech/canyon?sslmode=require&channel_binding=require")
    assert s.sqlalchemy_url.drivername == "postgresql+asyncpg"
    assert dict(s.sqlalchemy_url.query) == {}  # libpq-only options removed
    assert s.connect_args == {"ssl": "require"}


def test_pooler_host_disables_prepared_statement_cache() -> None:
    s = Settings(database_url="postgresql://u:p@ep-cool-name-123-pooler.us-east-2.aws.neon.tech/canyon?sslmode=require")
    assert s.connect_args == {"ssl": "require", "statement_cache_size": 0}


def test_local_url_is_unchanged() -> None:
    s = Settings(database_url="postgresql+asyncpg://postgres:pw@localhost:5432/canyon_dev")
    assert (s.sqlalchemy_url.drivername, s.connect_args) == ("postgresql+asyncpg", {})


def test_header_auth_in_dev_or_demo_only() -> None:
    base = "postgresql://u:p@localhost/db"
    assert not Settings(database_url=base, dev_auth=False, demo_mode=False).header_auth
    assert Settings(database_url=base, demo_mode=True).header_auth
    assert Settings(database_url=base, dev_auth=True).header_auth
