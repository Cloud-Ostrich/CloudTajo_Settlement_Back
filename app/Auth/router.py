from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.Auth.repository import user_repository
from app.Auth.schemas import LoginRequest
from app.Auth.security import decode_access_token, issue_access_token, revoke_jti, verify_password
from app.common.database import get_db
from app.common.errors import raise_api_error
from app.common.models import User


router = APIRouter(prefix="/api/auth", tags=["인증"])


def public_user(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
    }


@router.post(
    "/login",
    summary="로그인",
    description=(
        "이메일과 비밀번호를 검증하고 access token을 발급합니다.\n\n"
        "성공 응답에는 사용자 ID, 이름, 이메일, 역할만 포함하며 비밀번호 해시는 포함하지 않습니다."
    ),
    response_description="발급된 access token과 사용자 식별·권한 정보",
)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = user_repository.find_by_email(db, payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise_api_error(
            "이메일 또는 비밀번호가 올바르지 않습니다.",
            "AUTH_REQUIRED",
        )

    return {
        "success": True,
        "message": "로그인에 성공했습니다.",
        "data": {
            "accessToken": issue_access_token(user.id, user.role),
            "user": public_user(user),
        },
    }


@router.post("/logout", summary="로그아웃", description="현재 access token을 서버에서 폐기합니다.")
def logout(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    authorization = request.headers.get("Authorization", "")
    if not authorization.lower().startswith("bearer "):
        raise_api_error("로그인이 필요합니다.", "AUTH_REQUIRED")
    payload = decode_access_token(authorization[7:].strip())
    jti = payload.get("jti") if payload else None
    if not isinstance(jti, str):
        raise_api_error("유효하지 않은 인증 토큰입니다.", "AUTH_REQUIRED")
    revoke_jti(jti)
    return {"success": True, "message": "로그아웃에 성공했습니다.", "data": None}
