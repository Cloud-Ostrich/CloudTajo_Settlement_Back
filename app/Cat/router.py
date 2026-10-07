from typing import Any

from fastapi import APIRouter

from app.Cat.repository import category_repository


router = APIRouter(prefix="/api/categories", tags=["카테고리"])


@router.get(
    "",
    summary="활성 카테고리 목록 조회",
    description=(
        "DB의 `categories.active = TRUE`인 지출 카테고리만 조회합니다.\n\n"
        "현재 기본 카테고리는 식비, 교통비, 인쇄비, 소모품비, 기타입니다."
    ),
    response_description="활성 카테고리 목록",
)
def list_active_categories() -> dict[str, Any]:
    categories = [
        {
            "id": category.id,
            "name": category.name,
            "description": category.description,
        }
        for category in category_repository.find_active()
    ]
    return {
        "success": True,
        "message": "활성 카테고리 조회에 성공했습니다.",
        "data": categories,
    }
