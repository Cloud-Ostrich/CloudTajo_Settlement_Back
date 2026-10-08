from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.models import User


class UserRepository:
    def find_by_email(self, db: Session, email: str) -> User | None:
        statement = select(User).where(User.email == email.strip().lower())
        return db.scalar(statement)

    def find_by_id(self, db: Session, user_id: int) -> User | None:
        return db.get(User, user_id)


user_repository = UserRepository()
