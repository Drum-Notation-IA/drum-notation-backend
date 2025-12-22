import asyncio
import subprocess
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.media.models import AudioFile
from app.modules.media.repository import AudioFileRepository, VideoRepository

# Import audio processing libraries with error handling
try:
    import librosa
    import soundfile as sf

    AUDIO_LIBS_AVAILABLE = True
except ImportError:
    AUDIO_LIBS_AVAILABLE = False
    librosa = None
    sf = None


class AudioProcessingService:
    """Service for audio processing operations including extraction from video files"""

    def __init__(self):
        self.video_repository = VideoRepository()
        self.audio_repository = AudioFileRepository()
        self.temp_dir = Path("temp")
        self.temp_dir.mkdir(exist_ok=True)

    async def extract_audio_from_video(
        self,
        db: AsyncSession,
        video_id: UUID,
        user_id: UUID,
        sample_rate: int = 44100,
        channels: int = 1,
        format: str = "wav",
    ) -> AudioFile:
        """
        Extract audio from a video file using FFmpeg

        Args:
            db: Database session
            video_id: UUID of the video to process
            user_id: UUID of the user requesting the extraction
            sample_rate: Target sample rate (default: 44100 Hz)
            channels: Number of audio channels (default: 1 for mono)
            format: Output audio format (default: wav)

        Returns:
            AudioFile: The created audio file record

        Raises:
            HTTPException: If video not found, access denied, or processing fails
        """
        # Get the video
        video = await self.video_repository.get_by_id(db, video_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        # Check ownership
        if str(video.user_id) != str(user_id):
            raise HTTPException(
                status_code=403, detail="Not authorized to process this video"
            )

        # Check if audio already exists
        existing_audio = await self.audio_repository.get_by_video_id(db, video_id)
        if existing_audio:
            raise HTTPException(
                status_code=400, detail="Audio already extracted from this video"
            )

        # Verify video file exists
        video_path = Path(str(video.storage_path))
        if not video_path.exists():
            raise HTTPException(status_code=404, detail="Video file not found")

        try:
            # Generate output audio filename
            audio_filename = f"{video_id}.{format}"
            audio_dir = Path("uploads") / "audio"
            audio_dir.mkdir(parents=True, exist_ok=True)
            audio_path = audio_dir / audio_filename

            # Extract audio using FFmpeg
            success = await self._extract_audio_ffmpeg(
                str(video_path), str(audio_path), sample_rate, channels
            )

            if not success:
                raise HTTPException(
                    status_code=500, detail="Failed to extract audio from video"
                )

            # Get audio duration and validate
            duration = await self._get_audio_duration(str(audio_path))
            file_size = audio_path.stat().st_size

            # Validate extracted audio
            if duration <= 0 or file_size < 1000:  # Less than 1KB is suspicious
                audio_path.unlink(missing_ok=True)  # Clean up
                raise HTTPException(
                    status_code=500, detail="Extracted audio file is invalid"
                )

            # Create audio file record in database
            audio_file = await self.audio_repository.create(
                db=db,
                video_id=video_id,
                sample_rate=sample_rate,
                channels=channels,
                storage_path=str(audio_path),
                duration_seconds=duration,
            )

            await db.commit()
            return audio_file

        except Exception as e:
            # Clean up any partial files
            try:
                if "audio_path" in locals():
                    audio_path_obj = locals().get("audio_path")
                    if audio_path_obj and Path(str(audio_path_obj)).exists():
                        Path(str(audio_path_obj)).unlink(missing_ok=True)
            except Exception:
                pass  # Ignore cleanup errors

            if isinstance(e, HTTPException):
                raise e
            else:
                raise HTTPException(
                    status_code=500, detail=f"Audio extraction failed: {str(e)}"
                )

    async def _extract_audio_ffmpeg(
        self,
        video_path: str,
        audio_path: str,
        sample_rate: int,
        channels: int,
    ) -> bool:
        """
        Use FFmpeg to extract audio from video

        Args:
            video_path: Path to input video file
            audio_path: Path for output audio file
            sample_rate: Target sample rate
            channels: Number of channels (1=mono, 2=stereo)

        Returns:
            bool: True if extraction successful, False otherwise
        """
        try:
            # Check if FFmpeg is available
            if not self._check_ffmpeg_available():
                raise RuntimeError("FFmpeg not found. Please install FFmpeg.")

            # Build FFmpeg command
            cmd = [
                "ffmpeg",
                "-i",
                video_path,  # Input video
                "-vn",  # No video output
                "-ar",
                str(sample_rate),  # Audio sample rate
                "-ac",
                str(channels),  # Audio channels
                "-acodec",
                "pcm_s16le",  # Audio codec (16-bit PCM)
                "-f",
                "wav",  # Output format
                "-y",  # Overwrite output file if exists
                audio_path,  # Output file
            ]

            # Run FFmpeg
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return True
            else:
                print(f"FFmpeg error: {stderr.decode()}")
                return False

        except Exception as e:
            print(f"FFmpeg extraction failed: {e}")
            return False

    def _check_ffmpeg_available(self) -> bool:
        """Check if FFmpeg is available in the system"""
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    async def _get_audio_duration(self, audio_path: str) -> float:
        """
        Get the duration of an audio file

        Args:
            audio_path: Path to the audio file

        Returns:
            float: Duration in seconds
        """
        if not AUDIO_LIBS_AVAILABLE:
            raise HTTPException(
                status_code=500, detail="Audio processing libraries not available"
            )

        try:
            # Use librosa to get audio info without loading the full file
            if librosa is not None:
                duration = librosa.get_duration(path=audio_path)
                return float(duration)
            else:
                raise Exception("librosa not available")
        except Exception:
            # Fallback: try with soundfile
            try:
                if sf is not None:
                    with sf.SoundFile(audio_path) as f:
                        duration = len(f) / f.samplerate
                        return float(duration)
                else:
                    raise Exception("soundfile not available")
            except Exception:
                return 0.0

    async def get_audio_info(self, audio_path: str) -> dict:
        """
        Get detailed information about an audio file

        Args:
            audio_path: Path to the audio file

        Returns:
            dict: Audio information including duration, sample rate, channels, etc.
        """
        if not AUDIO_LIBS_AVAILABLE:
            raise HTTPException(
                status_code=500, detail="Audio processing libraries not available"
            )

        try:
            if sf is not None:
                with sf.SoundFile(audio_path) as f:
                    info = {
                        "duration_seconds": len(f) / f.samplerate,
                        "sample_rate": f.samplerate,
                        "channels": f.channels,
                        "frames": len(f),
                        "format": f.format,
                        "subtype": f.subtype,
                        "file_size_bytes": Path(audio_path).stat().st_size,
                    }
                    return info
            else:
                raise Exception("soundfile not available")
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to get audio info: {str(e)}"
            )

    async def validate_audio_file(self, audio_path: str) -> bool:
        """
        Validate that an audio file is properly formatted

        Args:
            audio_path: Path to the audio file

        Returns:
            bool: True if valid, False otherwise
        """
        if not AUDIO_LIBS_AVAILABLE:
            return False

        try:
            path = Path(audio_path)
            if not path.exists() or path.stat().st_size < 1000:
                return False

            # Try to read audio info
            if sf is not None:
                with sf.SoundFile(audio_path) as f:
                    # Check basic properties
                    if f.samplerate <= 0 or f.channels <= 0 or len(f) <= 0:
                        return False

                    # Try to read a small sample to ensure file is not corrupted
                    f.read(1024)
                    return True
            else:
                return False

        except Exception:
            return False

    async def convert_audio_format(
        self,
        input_path: str,
        output_path: str,
        sample_rate: Optional[int] = None,
        channels: Optional[int] = None,
    ) -> bool:
        """
        Convert audio file to different format/settings

        Args:
            input_path: Path to input audio file
            output_path: Path for output audio file
            sample_rate: Target sample rate (optional)
            channels: Target channels (optional)

        Returns:
            bool: True if conversion successful
        """
        if not AUDIO_LIBS_AVAILABLE:
            print("Audio processing libraries not available")
            return False

        try:
            # Load audio
            if librosa is not None and sf is not None:
                y, sr = librosa.load(input_path, sr=sample_rate, mono=(channels == 1))

                # If stereo to mono conversion needed
                if channels == 1 and y.ndim > 1:
                    y = librosa.to_mono(y)

                # Save converted audio
                sf.write(output_path, y, sr or sr)
            else:
                raise Exception("Audio libraries not available")
            return True

        except Exception as e:
            print(f"Audio conversion failed: {e}")
            return False

    async def normalize_audio(self, input_path: str, output_path: str) -> bool:
        """
        Normalize audio levels

        Args:
            input_path: Path to input audio file
            output_path: Path for normalized output file

        Returns:
            bool: True if normalization successful
        """
        if not AUDIO_LIBS_AVAILABLE:
            print("Audio processing libraries not available")
            return False

        try:
            # Load audio
            if librosa is not None and sf is not None:
                y, sr = librosa.load(input_path)

                # Normalize to [-1, 1] range
                y_normalized = librosa.util.normalize(y)

                # Save normalized audio
                sf.write(output_path, y_normalized, sr)
            else:
                raise Exception("Audio libraries not available")
            return True

        except Exception as e:
            print(f"Audio normalization failed: {e}")
            return False

    async def get_audio_features(self, audio_path: str) -> dict:
        """
        Extract basic audio features for analysis

        Args:
            audio_path: Path to the audio file

        Returns:
            dict: Dictionary containing audio features
        """
        if not AUDIO_LIBS_AVAILABLE:
            print("Audio processing libraries not available")
            return {}

        try:
            if librosa is not None:
                # Load audio
                y, sr = librosa.load(audio_path)

                # Calculate basic features
                features = {
                    "rms_energy": float(librosa.feature.rms(y=y).mean()),
                    "zero_crossing_rate": float(
                        librosa.feature.zero_crossing_rate(y).mean()
                    ),
                    "spectral_centroid": float(
                        librosa.feature.spectral_centroid(y=y, sr=sr).mean()
                    ),
                    "spectral_rolloff": float(
                        librosa.feature.spectral_rolloff(y=y, sr=sr).mean()
                    ),
                    "mfcc_mean": librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
                    .mean(axis=1)
                    .tolist(),
                    "tempo": float(librosa.feature.tempo(y=y, sr=sr)[0]),
                    "duration": float(len(y) / sr),
                    "sample_rate": int(sr),
                }
            else:
                raise Exception("librosa not available")

            return features

        except Exception as e:
            print(f"Feature extraction failed: {e}")
            return {}

    async def cleanup_temp_files(self) -> int:
        """
        Clean up temporary files

        Returns:
            int: Number of files cleaned up
        """
        cleaned_count = 0
        try:
            if self.temp_dir.exists():
                for file_path in self.temp_dir.glob("*"):
                    if file_path.is_file():
                        file_path.unlink()
                        cleaned_count += 1
        except Exception as e:
            print(f"Cleanup failed: {e}")

        return cleaned_count

    def get_supported_audio_formats(self) -> list:
        """Get list of supported audio formats"""
        return [
            {
                "format": "wav",
                "description": "Uncompressed WAV audio",
                "recommended": True,
                "quality": "Lossless",
            },
            {
                "format": "mp3",
                "description": "Compressed MP3 audio",
                "recommended": False,
                "quality": "Lossy",
            },
            {
                "format": "flac",
                "description": "Lossless FLAC audio",
                "recommended": True,
                "quality": "Lossless",
            },
        ]

    def get_recommended_settings(self) -> dict:
        """Get recommended audio processing settings for drum analysis"""
        return {
            "sample_rate": 44100,  # Standard sample rate
            "channels": 1,  # Mono for drum detection
            "format": "wav",  # Uncompressed for quality
            "bit_depth": 16,  # 16-bit is sufficient for most applications
            "normalization": True,  # Recommended for consistent levels
        }
