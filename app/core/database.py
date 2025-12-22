import os

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# Create async engine
# SQL logging controlled by environment variable: DEBUG_SQL=true
sql_echo = os.getenv("DEBUG_SQL", "false").lower() in ("true", "1", "yes")
engine = create_async_engine(
    settings.DATABASE_URL_ASYNC,
    echo=sql_echo,  # Enable with DEBUG_SQL=true environment variable
    future=True,
)

# Create async session factory
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Base class for models
Base = declarative_base()


# Dependency for FastAPI
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
