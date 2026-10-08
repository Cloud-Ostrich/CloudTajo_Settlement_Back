from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.models import Category


class CategoryRepository:
    def find_active(self, db: Session) -> list[Category]:
        statement = (
            select(Category)
            .where(Category.active.is_(True))
            .order_by(Category.id)
        )
        return list(db.scalars(statement).all())


category_repository = CategoryRepository()
