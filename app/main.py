import os
import time
import logging
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

# Configure logging
logger = logging.getLogger(__name__)

# Import models to ensure they are registered with SQLAlchemy
import app.db.models  # noqa: F401
from app.core.database import get_db
from app.modules.users.schemas import UserLogin, UserCreate
from app.modules.audio_processing.router import router as audio_router
from app.modules.jobs.router import router as jobs_router
from app.modules.jobs.worker import start_job_processor, stop_job_processor
from app.modules.media.routers import router as video_router
from app.modules.notation.router import router as notation_router
from app.modules.roles.routers import router as roles_router
from app.modules.users.router import router as users_router
from app.modules.ml.router import router as ml_router

app = FastAPI(
    title="Drum Notation Backend",
    description="API for processing drum videos and generating musical notation",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users_router)
app.include_router(roles_router)
app.include_router(video_router)
app.include_router(audio_router)
app.include_router(jobs_router)
app.include_router(notation_router)
app.include_router(ml_router)


@app.on_event("startup")
async def startup_event():
    """Initialize background job processor on startup"""
    await start_job_processor()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup job processor on shutdown"""
    await stop_job_processor()


@app.get("/")
async def root():
    return {"message": "Welcome to Drum Notation Backend"}


@app.get("/health")
async def health_check():
    """Global health check endpoint."""
    return {
        "status": "healthy",
        "service": "drum-notation-backend",
        "timestamp": time.time(),
        "message": "Backend is running"
    }


# Add root-level endpoints that frontend expects
@app.get("/datasets")
async def get_datasets():
    """Get available datasets information."""
    datasets = [
        {
            "id": "drum-samples-basic",
            "name": "Basic Drum Samples",
            "type": "audio",
            "size": "150 MB",
            "samples": 1200,
            "classes": ["kick", "snare", "hihat", "cymbal"],
            "created": "2024-01-15",
            "status": "available"
        },
        {
            "id": "video-drums-collection",
            "name": "Video Drum Collection",
            "type": "video",
            "size": "2.1 GB",
            "samples": 450,
            "classes": ["kick", "snare", "hihat", "cymbal", "tom"],
            "created": "2024-02-10",
            "status": "available"
        }
    ]

    return {
        "success": True,
        "datasets": datasets,
        "total_datasets": len(datasets),
        "total_samples": sum(d["samples"] for d in datasets),
        "demo_mode": True,
        "timestamp": time.time()
    }


@app.get("/analytics/performance")
async def get_performance_analytics():
    """Get performance analytics data."""
    performance_data = {
        "processing_times": {
            "avg_audio_processing": 1.2,
            "avg_video_processing": 3.8,
            "min_processing_time": 0.3,
            "max_processing_time": 12.5
        },
        "accuracy_metrics": {
            "overall_accuracy": 0.87,
            "kick_accuracy": 0.92,
            "snare_accuracy": 0.85,
            "hihat_accuracy": 0.84,
            "cymbal_accuracy": 0.88
        },
        "system_performance": {
            "cpu_usage": 45.2,
            "memory_usage": 62.1,
            "gpu_usage": 0.0,
            "active_processes": 3
        },
        "throughput": {
            "files_per_hour": 145,
            "avg_file_size_mb": 8.3,
            "success_rate": 0.94
        },
        "last_updated": time.time()
    }

    return {
        "success": True,
        "performance": performance_data,
        "demo_mode": True,
        "timestamp": time.time()
    }


@app.get("/analytics/usage")
async def get_usage_analytics():
    """Get usage analytics data."""
    usage_data = {
        "daily_stats": {
            "files_processed_today": 47,
            "unique_users_today": 8,
            "total_processing_time": 156.3,
            "error_rate": 0.06
        },
        "weekly_stats": {
            "files_processed_week": 312,
            "unique_users_week": 23,
            "avg_daily_files": 44.6,
            "peak_usage_day": "Wednesday"
        },
        "file_type_distribution": {
            "audio_files": 68,
            "video_files": 32
        },
        "popular_formats": [
            {"format": "mp4", "count": 89, "percentage": 28.5},
            {"format": "wav", "count": 76, "percentage": 24.4},
            {"format": "mp3", "count": 63, "percentage": 20.2},
            {"format": "m4a", "count": 45, "percentage": 14.4},
            {"format": "avi", "count": 39, "percentage": 12.5}
        ],
        "geographic_distribution": {
            "US": 45,
            "EU": 32,
            "Asia": 18,
            "Others": 5
        },
        "last_updated": time.time()
    }

    return {
        "success": True,
        "usage": usage_data,
        "demo_mode": True,
        "timestamp": time.time()
    }


@app.post("/analyze")
async def analyze_audio(file: UploadFile = File(...)):
    """Analyze endpoint for compatibility - redirects to ML analyze."""
    from app.modules.ml.router import analyze_audio as ml_analyze

    # Call the actual ML analyze function
    return await ml_analyze(file)


@app.get("/models")
async def get_available_models():
    """Get information about available ML models."""
    return {
        "models": [
            {
                "name": "DrumCNN",
                "type": "cnn",
                "description": "Convolutional Neural Network for drum classification",
                "status": "demo",
                "accuracy": 0.87
            },
            {
                "name": "DrumRNN",
                "type": "rnn",
                "description": "Recurrent Neural Network for sequential drum analysis",
                "status": "demo",
                "accuracy": 0.82
            },
            {
                "name": "DrumTransformer",
                "type": "transformer",
                "description": "Transformer model for advanced drum pattern recognition",
                "status": "demo",
                "accuracy": 0.91
            }
        ],
        "current_model": "DrumCNN",
        "demo_mode": True,
        "timestamp": time.time()
    }


# Add API route aliases for frontend compatibility (simplified for demo)
@app.post("/api/auth/login")
async def api_auth_login(login_data: dict):
    """API auth login endpoint - simplified for demo"""
    # Simplified auth for development/demo
    email = login_data.get("email", "")
    password = login_data.get("password", "")

    if email and password:
        return {
            "access_token": "demo-token-" + str(time.time()),
            "token_type": "bearer",
            "user": {
                "id": "demo-user-id",
                "email": email,
                "name": "Demo User"
            },
            "demo_mode": True,
            "message": "Demo authentication successful"
        }
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Email and password required")


@app.post("/api/auth/register")
async def api_auth_register(user_data: dict):
    """API auth register endpoint - simplified for demo"""
    email = user_data.get("email", "")
    password = user_data.get("password", "")

    if email and password and len(password) >= 6:
        return {
            "id": "demo-user-id",
            "email": email,
            "name": user_data.get("name", "Demo User"),
            "created_at": time.time(),
            "demo_mode": True,
            "message": "Demo registration successful"
        }
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Valid email and password (6+ chars) required")


@app.get("/api/auth/me")
async def api_auth_me():
    """API auth current user endpoint"""
    return {
        "user": {
            "id": "demo-user",
            "email": "demo@example.com",
            "name": "Demo User"
        },
        "authenticated": True,
        "demo_mode": True
    }


@app.post("/api/videos/upload")
async def api_videos_upload(file: UploadFile = File(...)):
    """API videos upload endpoint - simplified for demo"""
    try:
        # Validate file type
        supported_video = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
        file_ext = Path(file.filename).suffix.lower() if file.filename else ""

        if file_ext not in supported_video:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_ext}. Supported: {list(supported_video)}"
            )

        # Read and save file temporarily
        content = await file.read()
        temp_path = f"uploads/temp_{int(time.time())}_{file.filename}"

        # Ensure uploads directory exists
        os.makedirs("uploads", exist_ok=True)

        with open(temp_path, "wb") as f:
            f.write(content)

        # Return upload response
        return {
            "success": True,
            "video_id": f"demo-video-{int(time.time())}",
            "filename": file.filename,
            "file_size_bytes": len(content),
            "file_size_mb": round(len(content) / (1024 * 1024), 2),
            "format": file_ext,
            "upload_path": temp_path,
            "status": "uploaded",
            "demo_mode": True,
            "message": "Video uploaded successfully in demo mode",
            "timestamp": time.time()
        }

    except Exception as e:
        error_msg = f"Video upload failed: {str(e)}"
        print(error_msg)  # Fallback logging
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )


@app.post("/api/videos/analyze/{video_id}")
async def api_videos_analyze(video_id: str):
    """API endpoint to analyze uploaded video by ID"""
    try:
        # Read the uploaded video file
        video_path = f"uploads/videos/{video_id}.mp4"

        if not os.path.exists(video_path):
            # Try alternative path structures
            alt_paths = [
                f"uploads/{video_id}.mp4",
                f"uploads/temp_{video_id}.mp4"
            ]

            video_path = None
            for alt_path in alt_paths:
                if os.path.exists(alt_path):
                    video_path = alt_path
                    break

            if not video_path:
                raise HTTPException(
                    status_code=404,
                    detail=f"Video with ID {video_id} not found"
                )

        # Create a fake UploadFile from the stored file
        class StoredFile:
            def __init__(self, path: str):
                self.filename = Path(path).name
                self.content_type = "video/mp4"
                self._path = path

            async def read(self):
                with open(self._path, 'rb') as f:
                    return f.read()

        stored_file = StoredFile(video_path)

        # Use the existing ML analyze function
        from app.modules.ml.router import analyze_audio as ml_analyze_function

        # Call analysis with the stored file
        result = await ml_analyze_function(stored_file)

        return {
            "success": True,
            "video_id": video_id,
            "analysis": result,
            "message": "Video analysis completed successfully"
        }

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Video file not found for ID: {video_id}"
        )
    except Exception as e:
        error_msg = f"Video analysis failed: {str(e)}"
        print(error_msg)
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )


@app.post("/api/videos/{video_id}/extract-audio")
async def api_videos_extract_audio(video_id: str):
    """API endpoint to extract audio from uploaded video"""
    try:
        video_path = f"uploads/videos/{video_id}.mp4"

        if not os.path.exists(video_path):
            raise HTTPException(
                status_code=404,
                detail=f"Video with ID {video_id} not found"
            )

        # Extract audio using FFmpeg
        import subprocess
        audio_path = f"uploads/audio_{video_id}.wav"

        try:
            subprocess.run([
                "ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
                "-ar", "44100", "-ac", "2", audio_path, "-y"
            ], capture_output=True, check=True, timeout=60)

            return {
                "success": True,
                "video_id": video_id,
                "audio_path": audio_path,
                "message": "Audio extracted successfully"
            }

        except subprocess.CalledProcessError as e:
            raise HTTPException(
                status_code=500,
                detail="Failed to extract audio from video"
            )

    except Exception as e:
        error_msg = f"Audio extraction failed: {str(e)}"
        print(error_msg)
        raise HTTPException(
            status_code=500,
            detail=f"Audio extraction failed: {str(e)}"
        )


@app.post("/api/videos/{video_id}/separate-sources")
async def api_videos_separate_sources(
    video_id: str,
    method: str = "spectral",
    save_sources: bool = True
):
    """API endpoint to separate drum sources from uploaded video audio"""
    try:
        return {
            "success": True,
            "video_id": video_id,
            "separation_method": method,
            "separated_sources": {
                "kick": f"uploads/separated/{video_id}_kick.wav",
                "snare": f"uploads/separated/{video_id}_snare.wav",
                "hihat": f"uploads/separated/{video_id}_hihat.wav",
                "cymbals": f"uploads/separated/{video_id}_cymbals.wav",
                "toms": f"uploads/separated/{video_id}_toms.wav"
            },
            "sources_saved": save_sources,
            "demo_mode": True,
            "message": f"Audio sources separated using {method} method"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Source separation failed: {str(e)}"
        )


@app.post("/api/videos/{video_id}/create-stems")
async def api_videos_create_stems(
    video_id: str,
    export_format: str = "wav",
    bit_depth: int = 24,
    normalize: bool = True
):
    """API endpoint to create professional drum stems"""
    try:
        return {
            "success": True,
            "video_id": video_id,
            "stems_created": {
                "kick_stem": f"uploads/stems/{video_id}_kick.{export_format}",
                "snare_stem": f"uploads/stems/{video_id}_snare.{export_format}",
                "hihat_stem": f"uploads/stems/{video_id}_hihat.{export_format}",
                "cymbals_stem": f"uploads/stems/{video_id}_cymbals.{export_format}",
                "toms_stem": f"uploads/stems/{video_id}_toms.{export_format}",
                "percussion_stem": f"uploads/stems/{video_id}_percussion.{export_format}"
            },
            "export_format": export_format,
            "bit_depth": bit_depth,
            "normalized": normalize,
            "demo_mode": True,
            "message": "Professional drum stems created successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Stem creation failed: {str(e)}"
        )


@app.post("/api/videos/{video_id}/enhance-drums")
async def api_videos_enhance_drums(
    video_id: str,
    drum_type: str = "all",
    enhancement_strength: float = 0.3
):
    """API endpoint to enhance specific drum sounds"""
    try:
        return {
            "success": True,
            "video_id": video_id,
            "enhanced_drum_type": drum_type,
            "enhancement_strength": enhancement_strength,
            "enhanced_audio_path": f"uploads/enhanced/{video_id}_{drum_type}_enhanced.wav",
            "processing_info": {
                "eq_applied": True,
                "compression_applied": True,
                "transient_enhancement": True,
                "noise_reduction": True
            },
            "demo_mode": True,
            "message": f"{drum_type.title()} drums enhanced successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Drum enhancement failed: {str(e)}"
        )


@app.get("/api/audio/processing-options")
async def api_audio_processing_options():
    """Get available audio processing options"""
    return {
        "separation_methods": [
            {
                "name": "spectral",
                "description": "Spectral masking - fast and effective for most cases",
                "recommended": True
            },
            {
                "name": "nmf",
                "description": "Non-negative Matrix Factorization - advanced separation",
                "recommended": False
            },
            {
                "name": "ica",
                "description": "Independent Component Analysis - requires stereo input",
                "recommended": False
            }
        ],
        "enhancement_types": [
            "kick", "snare", "hihat", "cymbals", "toms", "all"
        ],
        "export_formats": [
            "wav", "flac", "aiff"
        ],
        "bit_depths": [16, 24, 32],
        "processing_workflow": [
            "1. Upload video",
            "2. Extract audio",
            "3. Separate sources (optional)",
            "4. Enhance drums (optional)",
            "5. Create stems (optional)",
            "6. Analyze for drum detection"
        ]
    }
