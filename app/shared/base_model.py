from datetime import datetime
from sqlalchemy import Column, DateTime
from app.db.base import Base

class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

class SoftDeleteMixin:
    deleted_at = Column(DateTime, nullable=True)

class BaseModel(Base, TimestampMixin, SoftDeleteMixin):
    __abstract__ = True
