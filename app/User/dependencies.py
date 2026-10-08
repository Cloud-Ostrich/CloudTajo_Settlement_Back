from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.Auth.repository import user_repository
from app.Auth.security import decode_access_token, is_jti_revoked
from app.common.database import get_db
from app.common.errors import raise_api_error
from app.common.models import User


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise_api_error("로그인이 필요합니다.", "AUTH_REQUIRED")

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise_api_error("유효하지 않은 인증 토큰입니다.", "AUTH_REQUIRED")

    user = user_repository.find_by_id(db, payload["sub"])
    if user is None:
        raise_api_error("유효하지 않은 인증 토큰입니다.", "AUTH_REQUIRED")
    jti = payload.get("jti")
    if not isinstance(jti, str) or is_jti_revoked(jti):
        raise_api_error("폐기된 인증 토큰입니다.", "AUTH_REQUIRED")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "ADMIN":
        raise_api_error("관리자 권한이 필요합니다.", "FORBIDDEN_ROLE", 403)
    return current_user


def require_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "USER":
        raise_api_error("일반 구성원 권한이 필요합니다.", "FORBIDDEN_ROLE", 403)
    return current_user
