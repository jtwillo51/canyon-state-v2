from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

from app.config import settings
from app.models import SoftDelete

# One engine per process: it owns the connection pool.
engine = create_async_engine(settings.database_url)

# expire_on_commit=False: objects stay readable after commit. Under async there is no lazy
# reload, so an expired attribute would raise instead of quietly re-querying.
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@event.listens_for(Session, "do_orm_execute")
def _exclude_soft_deleted(state: ORMExecuteState) -> None:
    """Add `deleted_at IS NULL` to every ORM query, for every table, automatically.

    It also reaches subqueries and related rows loaded with selectinload/joinedload. To see
    deleted rows, a query opts in with .execution_options(include_deleted=True).
    """
    if (
        state.is_select
        and not state.is_column_load
        and not state.is_relationship_load  # already covered: the criteria propagate to loaders
        and not state.execution_options.get("include_deleted", False)
    ):
        state.statement = state.statement.options(
            with_loader_criteria(SoftDelete, lambda cls: cls.deleted_at.is_(None), include_aliases=True)
        )


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, closed when the request ends."""
    async with SessionLocal() as session:
        yield session
