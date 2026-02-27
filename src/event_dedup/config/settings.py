from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EVENT_DEDUP_")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/event_dedup"
    database_url_sync: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/event_dedup"
    dead_letter_dir: Path = Path("./dead_letters")
    event_data_dir: Path = Path("./eventdata")


@lru_cache
def get_settings() -> Settings:
    return Settings()
