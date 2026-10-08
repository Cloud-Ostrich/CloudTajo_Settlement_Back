from typing import Any

from fastapi import APIRouter, Depends

from app.User.dependencies import get_current_user
from app.User.schemas import UserResponse
from app.common.models import User


router = APIRouter(prefix="/api/users", tags=["사용자"])


@router.get(
    "/me",
    response_model=dict[str, Any],
    summary="내 정보와 권한 조회",
    description=(
        "Bearer access token의 사용자 정보를 조회합니다.\n\n"
        "요청 헤더: `Authorization: Bearer {accessToken}`"
    ),
    response_description="현재 로그인한 사용자의 식별 정보와 역할",
)
def get_me(current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    user = UserResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        role=current_user.role,
    )
    return {
        "success": True,
        "message": "내 정보 조회에 성공했습니다.",
        "data": user.model_dump(),
    }
