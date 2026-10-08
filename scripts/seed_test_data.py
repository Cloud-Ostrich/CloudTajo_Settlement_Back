from sqlalchemy import select

from app.Auth.security import hash_password
from app.common.database import SessionLocal
from app.common.models import Category, User


TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "test1234!"


def seed() -> None:
    with SessionLocal.begin() as db:
        user = db.scalar(select(User).where(User.email == TEST_EMAIL))
        if user is None:
            user = User(
                name="테스트 사용자",
                email=TEST_EMAIL,
                password_hash=hash_password(TEST_PASSWORD),
                role="USER",
            )
            db.add(user)
        else:
            user.name = "테스트 사용자"
            user.password_hash = hash_password(TEST_PASSWORD)
            user.role = "USER"

        categories = [
            ("식비", "식사 관련 지출"),
            ("교통비", "교통 관련 지출"),
            ("인쇄비", "인쇄 관련 지출"),
            ("소모품비", "소모품 관련 지출"),
            ("기타", "그 외 지출"),
        ]
        for name, description in categories:
            category = db.scalar(select(Category).where(Category.name == name))
            if category is None:
                db.add(Category(name=name, description=description, active=True))
            else:
                category.description = description
                category.active = True

    print(f"Seeded login account: {TEST_EMAIL}")


if __name__ == "__main__":
    seed()
