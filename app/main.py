from itertools import count

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field


app = FastAPI(
    title="CloudTajo Settlement API",
    version="0.1.0",
    description="CloudTajo 정산 백엔드 API",
)


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    amount: int = Field(ge=0)


class Item(ItemCreate):
    id: int


items: list[Item] = []
item_id = count(1)


@app.get("/", tags=["기본"])
def read_root() -> dict[str, str]:
    return {"message": "CloudTajo Settlement API is running"}


@app.get("/health", tags=["기본"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/items", response_model=list[Item], tags=["items"])
def list_items() -> list[Item]:
    return items


@app.post(
    "/api/v1/items",
    response_model=Item,
    status_code=status.HTTP_201_CREATED,
    tags=["items"],
)
def create_item(payload: ItemCreate) -> Item:
    item = Item(id=next(item_id), **payload.model_dump())
    items.append(item)
    return item


@app.get("/api/v1/items/{item_id}", response_model=Item, tags=["items"])
def get_item(item_id: int) -> Item:
    for item in items:
        if item.id == item_id:
            return item
    raise HTTPException(status_code=404, detail="Item not found")

