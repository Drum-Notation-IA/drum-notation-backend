from sqlalchemy.orm import Session
from app.modules.users.models import User
from app.modules.users.schema import UserCreate
from app.core.security import hash_password 

class UserRepository:

    def get_by_email(self, db: Session, email: str):
        return (
            db.query(User)
            .filter(User.email == email, User.deleted_at.is_(None))
            .first()
        )

    def create(self, db: Session, user_in: UserCreate):
        user = User(
            email = user_in.email,
            hashed_password=hash_password(user_in.password)
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user