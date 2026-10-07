from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.Auth.repository import UserRecord, user_repository
from app.Auth.security import decode_access_token
from app.common.errors import raise_api_error


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> UserRecord:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise_api_error("로그인이 필요합니다.", "AUTH_REQUIRED")

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise_api_error("유효하지 않은 인증 토큰입니다.", "AUTH_REQUIRED")

    user = user_repository.find_by_id(payload["sub"])
    if user is None:
        raise_api_error("유효하지 않은 인증 토큰입니다.", "AUTH_REQUIRED")
    return user
