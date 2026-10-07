from itertools import count

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.Auth.router import router as auth_router
from app.Cat.router import router as category_router
from app.User.router import router as user_router


app = FastAPI(
    title="CloudTajo Settlement API",
    version="0.1.0",
    description=(
        "구름 정산소의 영수증 제출·검토·정산을 위한 API입니다.\n\n"
        "인증이 필요한 API는 `Authorization: Bearer {accessToken}` 헤더를 사용합니다."
    ),
    openapi_tags=[
        {"name": "기본", "description": "서버 상태와 기본 확인 API"},
        {"name": "인증", "description": "로그인과 access token 발급 API"},
        {"name": "사용자", "description": "현재 로그인한 사용자 정보 API"},
        {"name": "카테고리", "description": "활성 지출 카테고리 조회 API"},
        {"name": "샘플 항목", "description": "초기 개발 환경 확인용 샘플 API"},
    ],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and exc.detail.get("success") is False:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, description="항목 이름")
    amount: int = Field(ge=0, description="항목 금액")


class Item(ItemCreate):
    id: int


items: list[Item] = []
item_id = count(1)


@app.get(
    "/",
    tags=["기본"],
    summary="서버 기본 상태 확인",
    description="CloudTajo Settlement API가 실행 중인지 확인합니다.",
)
def read_root() -> dict[str, str]:
    return {"message": "CloudTajo Settlement API is running"}


@app.get(
    "/health",
    tags=["기본"],
    summary="헬스 체크",
    description="로드 밸런서나 운영 모니터링에서 서버 상태를 확인할 때 사용합니다.",
)
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    "/api/v1/items",
    response_model=list[Item],
    tags=["샘플 항목"],
    summary="샘플 항목 목록 조회",
    description="초기 개발 단계에서 동작을 확인하기 위한 샘플 항목 목록을 반환합니다.",
)
def list_items() -> list[Item]:
    return items


@app.post(
    "/api/v1/items",
    response_model=Item,
    status_code=status.HTTP_201_CREATED,
    tags=["샘플 항목"],
    summary="샘플 항목 생성",
    description="초기 개발 단계에서 동작을 확인하기 위한 샘플 항목을 생성합니다.",
)
def create_item(payload: ItemCreate) -> Item:
    item = Item(id=next(item_id), **payload.model_dump())
    items.append(item)
    return item


@app.get(
    "/api/v1/items/{item_id}",
    response_model=Item,
    tags=["샘플 항목"],
    summary="샘플 항목 상세 조회",
    description="항목 ID에 해당하는 샘플 항목을 조회합니다.",
)
def get_item(item_id: int) -> Item:
    for item in items:
        if item.id == item_id:
            return item
    raise HTTPException(status_code=404, detail="Item not found")


app.include_router(auth_router)
app.include_router(user_router)
app.include_router(category_router)
