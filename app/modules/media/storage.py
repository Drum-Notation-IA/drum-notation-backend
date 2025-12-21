import os
import uuid
from pathlib import Path
from typing import Optional, Tuple

from fastapi import UploadFile

from app.modules.media.models import MediaType


class FileStorage:
    def __init__(self, base_upload_dir: str = "uploads"):
        self.base_upload_dir = Path(base_upload_dir)
        self.ensure_directories()

    def ensure_directories(self):
        """Ensure all necessary directories exist"""
        for media_type in MediaType:
            type_dir = self.base_upload_dir / media_type.value
            type_dir.mkdir(parents=True, exist_ok=True)

    def get_media_type_from_content_type(
        self, content_type: str
    ) -> Optional[MediaType]:
        """Determine media type from content type"""
        content_type = content_type.lower()

        if content_type.startswith("audio/"):
            return MediaType.AUDIO
        elif content_type.startswith("video/"):
            return MediaType.VIDEO
        elif content_type.startswith("image/"):
            return MediaType.IMAGE

        return None

    def is_allowed_file_type(self, content_type: str, filename: str) -> bool:
        """Check if file type is allowed"""
        allowed_types = {
            MediaType.AUDIO: [
                "audio/mpeg",  # mp3
                "audio/wav",  # wav
                "audio/x-wav",  # wav alternative
                "audio/mp4",  # m4a
                "audio/flac",  # flac
                "audio/ogg",  # ogg
            ],
            MediaType.VIDEO: [
                "video/mp4",
                "video/quicktime",  # mov
                "video/x-msvideo",  # avi
                "video/x-matroska",  # mkv
                "video/webm",
            ],
            MediaType.IMAGE: [
                "image/jpeg",
                "image/jpg",
                "image/png",
                "image/gif",
                "image/webp",
            ],
        }

        media_type = self.get_media_type_from_content_type(content_type)
        if not media_type:
            return False

        return content_type.lower() in allowed_types[media_type]

    def get_file_extension(self, filename: str) -> str:
        """Extract file extension from filename"""
        return Path(filename).suffix.lower()

    def generate_unique_filename(self, original_filename: str) -> str:
        """Generate a unique filename to avoid conflicts"""
        extension = self.get_file_extension(original_filename)
        unique_id = str(uuid.uuid4())
        return f"{unique_id}{extension}"

    def get_file_path(self, media_type: MediaType, stored_filename: str) -> Path:
        """Get the full path where a file should be stored"""
        return self.base_upload_dir / media_type.value / stored_filename

    async def save_file(
        self, upload_file: UploadFile, media_type: MediaType
    ) -> Tuple[str, str, int]:
        """
        Save uploaded file to storage

        Returns:
            Tuple of (stored_filename, file_path, file_size)
        """
        # Generate unique filename
        stored_filename = self.generate_unique_filename(upload_file.filename)

        # Get file path
        file_path = self.get_file_path(media_type, stored_filename)

        # Read file content
        content = await upload_file.read()
        file_size = len(content)

        # Save file
        with open(file_path, "wb") as f:
            f.write(content)

        # Reset file pointer for potential future use
        await upload_file.seek(0)

        return stored_filename, str(file_path), file_size

    def delete_file(self, file_path: str) -> bool:
        """Delete a file from storage"""
        try:
            path = Path(file_path)
            if path.exists() and path.is_file():
                path.unlink()
                return True
            return False
        except Exception:
            return False

    def file_exists(self, file_path: str) -> bool:
        """Check if a file exists in storage"""
        return Path(file_path).exists()

    def get_file_size(self, file_path: str) -> Optional[int]:
        """Get file size in bytes"""
        try:
            path = Path(file_path)
            if path.exists():
                return path.stat().st_size
            return None
        except Exception:
            return None

    def validate_file_size(self, file_size: int, media_type: MediaType) -> bool:
        """Validate file size against limits"""
        max_sizes = {
            MediaType.VIDEO: 100 * 1024 * 1024,  # 100MB
            MediaType.AUDIO: 50 * 1024 * 1024,  # 50MB
            MediaType.IMAGE: 10 * 1024 * 1024,  # 10MB
        }

        return file_size <= max_sizes.get(media_type, 0)

    def get_storage_info(self) -> dict:
        """Get storage information and statistics"""
        info = {"base_directory": str(self.base_upload_dir), "media_types": {}}

        for media_type in MediaType:
            type_dir = self.base_upload_dir / media_type.value
            if type_dir.exists():
                files = list(type_dir.glob("*"))
                total_size = sum(f.stat().st_size for f in files if f.is_file())
                info["media_types"][media_type.value] = {
                    "directory": str(type_dir),
                    "file_count": len(files),
                    "total_size_bytes": total_size,
                    "total_size_mb": round(total_size / (1024 * 1024), 2),
                }

        return info

    def cleanup_orphaned_files(self, existing_stored_filenames: list[str]):
        """Remove files that are no longer referenced in the database"""
        orphaned_count = 0

        for media_type in MediaType:
            type_dir = self.base_upload_dir / media_type.value
            if not type_dir.exists():
                continue

            for file_path in type_dir.glob("*"):
                if (
                    file_path.is_file()
                    and file_path.name not in existing_stored_filenames
                ):
                    try:
                        file_path.unlink()
                        orphaned_count += 1
                    except Exception:
                        pass

        return orphaned_count
