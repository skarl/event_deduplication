import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, engine_from_config, pool

# Add the project root to sys.path so we can import our models
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root / "src"))

from event_dedup.models import Base  # noqa: E402

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Allow overriding the database URL via environment variable
    url_override = os.environ.get("ALEMBIC_DATABASE_URL")

    if url_override:
        connectable = create_engine(url_override, poolclass=pool.NullPool)
    else:
        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
