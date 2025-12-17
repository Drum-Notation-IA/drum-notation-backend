from fastapi import APIRouter, Depends, HTTPException 
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.modules.users.schemas import UserCreate, UserRead 
from app.modules.users.service import UserService

router = APIRouter(prefix="/users", tags=["users"])
service = UserService()

@router.post("/", response_model=UserRead)
async def create_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await service.create_user(db, user_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))