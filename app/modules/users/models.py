import uuid

from sqlalchemy import Column, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.shared.base_model import BaseModel


class User(BaseModel):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(Text, unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=False)

    # Relationship to roles (imported from roles module)
    roles = relationship("Role", secondary="user_roles", back_populates="users")

    # Relationship to media files
    media_files = relationship("Media", back_populates="user")
