from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import settings
from app.db.base import Base

# IMPORTANT: Import all models to ensure they are registered with SQLAlchemy
from app.modules.jobs.models import ProcessingJob
from app.modules.media.models import AudioFile, Video
from app.modules.notation.models import DrumNotation, OpenAIEnrichment
from app.modules.roles.models import Role, UserRole
from app.modules.users.models import User

config = context.config

if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_online():
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL_SYNC)

    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
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
