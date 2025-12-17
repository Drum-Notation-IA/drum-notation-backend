from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db


app = FastAPI(title="Drum Notation API")


@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    return {"status": "ok"}

