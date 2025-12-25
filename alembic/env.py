from logging.config import fileConfig
from typing import Any, Dict

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import settings
from app.db.base import Base

# IMPORTANT: Import all models to ensure they are registered with SQLAlchemy
# These imports appear "unused" but are required for Alembic to detect models
# pyright: reportUnusedImport=false
from app.modules.jobs.models import ProcessingJob  # noqa: F401
from app.modules.media.models import AudioFile, Video  # noqa: F401
from app.modules.notation.models import DrumNotation, OpenAIEnrichment  # noqa: F401
from app.modules.roles.models import Role, UserRole  # noqa: F401
from app.modules.users.models import User  # noqa: F401

config = context.config

if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = settings.DATABASE_URL_SYNC
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode."""
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL_SYNC)

    # Get configuration section and ensure it's not None
    configuration: Dict[str, Any] = config.get_section(config.config_ini_section) or {}

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# Determine if we're running in offline or online mode
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
