from dataclasses import dataclass


@dataclass(frozen=True)
class CategoryRecord:
    id: int
    name: str
    description: str | None
    active: bool


class InMemoryCategoryRepository:
    """Temporary repository to replace with a categories-table repository later."""

    def __init__(self) -> None:
        self._categories = [
            CategoryRecord(1, "식비", "식사 관련 지출", True),
            CategoryRecord(2, "교통비", "교통 관련 지출", True),
            CategoryRecord(3, "인쇄비", "인쇄 관련 지출", True),
            CategoryRecord(4, "소모품비", "소모품 관련 지출", True),
            CategoryRecord(5, "기타", "그 외 지출", True),
        ]

    def find_active(self) -> list[CategoryRecord]:
        return [category for category in self._categories if category.active]


category_repository = InMemoryCategoryRepository()
