from fastapi import FastAPI

# Import models to ensure they are registered with SQLAlchemy
import app.db.models  # noqa: F401
from app.modules.media.routers import router as media_router
from app.modules.roles.routers import router as roles_router
from app.modules.users.router import router as users_router

app = FastAPI()

app.include_router(users_router)
app.include_router(roles_router)
app.include_router(media_router)


@app.get("/")
async def root():
    return {"message": "Welcome to Drum Notation Backend"}
