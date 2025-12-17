from sqlalchemy.orm import Session
from app.modules.users.repository import UserRepository
from app.modules.users.schema import UserCreate

class UserService:
    def __init__(self):
        self.repo = UserRepository
    
    async def create_user(self, db: Session, user_in: UserCreate):
        existing = self.repo.get_by_email(db, user_in.email)
        if existing:
            raise ValueError("Email already exists")
        return self.repo.create(db, user_in)