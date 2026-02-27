from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine as sa_create_async_engine

from event_dedup.config.settings import get_settings

_engine: AsyncEngine | None = None


def get_engine(echo: bool = False) -> AsyncEngine:
    """Return a cached async engine instance."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = sa_create_async_engine(settings.database_url, echo=echo)
    return _engine
