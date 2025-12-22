from fastapi import FastAPI

# Import models to ensure they are registered with SQLAlchemy
import app.db.models  # noqa: F401
from app.modules.audio_processing.router import router as audio_router
from app.modules.jobs.router import router as jobs_router
from app.modules.jobs.worker import start_job_processor, stop_job_processor
from app.modules.media.routers import router as video_router
from app.modules.notation.router import router as notation_router
from app.modules.roles.routers import router as roles_router
from app.modules.users.router import router as users_router

app = FastAPI(
    title="Drum Notation Backend",
    description="API for processing drum videos and generating musical notation",
    version="1.0.0",
)

app.include_router(users_router)
app.include_router(roles_router)
app.include_router(video_router)
app.include_router(audio_router)
app.include_router(jobs_router)
app.include_router(notation_router)


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
