# Import all models here to ensure they are registered with SQLAlchemy
# This file should be imported in main.py or wherever the database is initialized

from app.modules.jobs.models import ProcessingJob
from app.modules.media.models import AudioFile, Video
from app.modules.notation.models import DrumNotation, OpenAIEnrichment
from app.modules.roles.models import Role, UserRole
from app.modules.users.models import User

# Future modules can be imported here as they are created

__all__ = [
    "User",
    "Role",
    "UserRole",
    "Video",
    "AudioFile",
    "ProcessingJob",
    "DrumNotation",
    "OpenAIEnrichment",
]
