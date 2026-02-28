"""FastAPI dependency injection for async DB sessions."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from event_dedup.db.session import get_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session for request handling."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
