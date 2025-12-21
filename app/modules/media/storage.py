import uuid
from pathlib import Path
from typing import Optional, Tuple

from fastapi import UploadFile


class VideoStorage:
    def __init__(self, base_upload_dir: str = "uploads"):
        self.base_upload_dir = Path(base_upload_dir)
        self.videos_dir = self.base_upload_dir / "videos"
        self.audio_dir = self.base_upload_dir / "audio"
        self.ensure_directories()

    def ensure_directories(self):
        """Ensure all necessary directories exist"""
        self.videos_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    def is_allowed_video_type(self, content_type: str, filename: str) -> bool:
        """Check if video file type is allowed"""
        allowed_video_types = [
            "video/mp4",
            "video/quicktime",  # mov
            "video/x-msvideo",  # avi
            "video/x-matroska",  # mkv
            "video/webm",
        ]

        allowed_extensions = [".mp4", ".mov", ".avi", ".mkv", ".webm"]

        # Check both content type and file extension
        content_type_valid = content_type.lower() in allowed_video_types

        file_extension = Path(filename).suffix.lower()
        extension_valid = file_extension in allowed_extensions

        return content_type_valid and extension_valid

    def get_file_extension(self, filename: str) -> str:
        """Extract file extension from filename"""
        return Path(filename).suffix.lower()

    def generate_unique_video_filename(self, original_filename: str) -> str:
        """Generate a unique filename for video storage"""
        extension = self.get_file_extension(original_filename)
        unique_id = str(uuid.uuid4())
        return f"{unique_id}{extension}"

    def get_video_storage_path(self, stored_filename: str) -> Path:
        """Get the full path where a video file should be stored"""
        return self.videos_dir / stored_filename

    def get_audio_storage_path(self, audio_filename: str) -> Path:
        """Get the full path where an extracted audio file should be stored"""
        return self.audio_dir / audio_filename

    async def save_video_file(
        self, upload_file: UploadFile, user_id: str
    ) -> Tuple[str, str, int]:
        """
        Save uploaded video file to storage

        Returns:
            Tuple of (stored_filename, storage_path, file_size)
        """
        # Generate unique filename
        if not upload_file.filename:
            raise ValueError("Upload file must have a filename")
        stored_filename = self.generate_unique_video_filename(upload_file.filename)

        # Get storage path
        storage_path = self.get_video_storage_path(stored_filename)

        # Read file content
        content = await upload_file.read()
        file_size = len(content)

        # Save file
        with open(storage_path, "wb") as f:
            f.write(content)

        # Reset file pointer for potential future use
        await upload_file.seek(0)

        return stored_filename, str(storage_path), file_size

    def delete_video_file(self, storage_path: str) -> bool:
        """Delete a video file from storage"""
        try:
            path = Path(storage_path)
            if path.exists() and path.is_file():
                path.unlink()
                return True
            return False
        except Exception:
            return False

    def delete_audio_file(self, storage_path: str) -> bool:
        """Delete an audio file from storage"""
        try:
            path = Path(storage_path)
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

    def validate_video_file_size(self, file_size: int) -> bool:
        """Validate video file size against limits"""
        max_video_size = 500 * 1024 * 1024  # 500MB for video files
        return file_size <= max_video_size

    def get_video_duration_estimate(self, file_size: int) -> Optional[float]:
        """
        Estimate video duration based on file size
        This is a rough approximation - actual duration should be detected using ffmpeg
        """
        # Very rough estimate: assume ~1MB per second for average quality video
        estimated_seconds = file_size / (1024 * 1024)
        return estimated_seconds if estimated_seconds > 0 else None

    def generate_audio_filename_for_video(self, video_filename: str) -> str:
        """Generate audio filename based on video filename"""
        video_stem = Path(video_filename).stem
        return f"{video_stem}.wav"  # Always use WAV for extracted audio

    def get_storage_info(self) -> dict:
        """Get storage information and statistics"""
        from typing import Any, Dict

        info: Dict[str, Any] = {
            "base_directory": str(self.base_upload_dir),
            "videos_directory": str(self.videos_dir),
            "audio_directory": str(self.audio_dir),
        }

        # Get video storage stats
        if self.videos_dir.exists():
            video_files = list(self.videos_dir.glob("*"))
            video_total_size = sum(f.stat().st_size for f in video_files if f.is_file())
            info["videos"] = {
                "file_count": len([f for f in video_files if f.is_file()]),
                "total_size_bytes": video_total_size,
                "total_size_mb": round(video_total_size / (1024 * 1024), 2),
            }

        # Get audio storage stats
        if self.audio_dir.exists():
            audio_files = list(self.audio_dir.glob("*"))
            audio_total_size = sum(f.stat().st_size for f in audio_files if f.is_file())
            info["audio"] = {
                "file_count": len([f for f in audio_files if f.is_file()]),
                "total_size_bytes": audio_total_size,
                "total_size_mb": round(audio_total_size / (1024 * 1024), 2),
            }

        return info

    def cleanup_orphaned_video_files(self, existing_video_filenames: list[str]) -> int:
        """Remove video files that are no longer referenced in the database"""
        orphaned_count = 0

        if not self.videos_dir.exists():
            return orphaned_count

        for file_path in self.videos_dir.glob("*"):
            if file_path.is_file() and file_path.name not in existing_video_filenames:
                try:
                    file_path.unlink()
                    orphaned_count += 1
                except Exception:
                    pass

        return orphaned_count

    def cleanup_orphaned_audio_files(self, existing_audio_filenames: list[str]) -> int:
        """Remove audio files that are no longer referenced in the database"""
        orphaned_count = 0

        if not self.audio_dir.exists():
            return orphaned_count

        for file_path in self.audio_dir.glob("*"):
            if file_path.is_file() and file_path.name not in existing_audio_filenames:
                try:
                    file_path.unlink()
                    orphaned_count += 1
                except Exception:
                    pass

        return orphaned_count

    def get_supported_formats_info(self) -> dict:
        """Get information about supported video formats"""
        return {
            "supported_video_types": [
                {
                    "extension": ".mp4",
                    "mime_type": "video/mp4",
                    "description": "MPEG-4 Video",
                },
                {
                    "extension": ".mov",
                    "mime_type": "video/quicktime",
                    "description": "QuickTime Movie",
                },
                {
                    "extension": ".avi",
                    "mime_type": "video/x-msvideo",
                    "description": "Audio Video Interleave",
                },
                {
                    "extension": ".mkv",
                    "mime_type": "video/x-matroska",
                    "description": "Matroska Video",
                },
                {
                    "extension": ".webm",
                    "mime_type": "video/webm",
                    "description": "WebM Video",
                },
            ],
            "max_file_size_mb": 500,
            "max_file_size_bytes": 500 * 1024 * 1024,
        }
