from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from event_dedup.db.engine import get_engine

_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return a cached session factory bound to the engine."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session. Caller controls commit/rollback."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
