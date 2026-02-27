from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Default config paths relative to the package config directory
_CONFIG_DIR = Path(__file__).parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EVENT_DEDUP_")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/event_dedup"
    database_url_sync: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/event_dedup"
    dead_letter_dir: Path = Path("./dead_letters")
    event_data_dir: Path = Path("./eventdata")
    prefixes_config_path: Path = _CONFIG_DIR / "prefixes.yaml"
    city_aliases_path: Path = _CONFIG_DIR / "city_aliases.yaml"


@lru_cache
def get_settings() -> Settings:
    return Settings()
