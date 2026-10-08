from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """AUTH-001 로그인 요청 본문."""

    email: str = Field(
        min_length=1,
        max_length=320,
        description="로그인에 사용하는 이메일 주소",
        examples=["admin@test.com"],
    )
    password: str = Field(
        min_length=1,
        max_length=128,
        description="로그인 비밀번호",
        examples=["1234"],
    )
