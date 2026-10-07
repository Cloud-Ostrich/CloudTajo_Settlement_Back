from fastapi.testclient import TestClient

from app.main import app, items


client = TestClient(app)


def setup_function() -> None:
    items.clear()


def test_health_check() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_and_get_item() -> None:
    create_response = client.post(
        "/api/v1/items",
        json={"name": "테스트 정산", "amount": 10000},
    )

    assert create_response.status_code == 201
    created_item = create_response.json()
    assert created_item["name"] == "테스트 정산"
    assert created_item["amount"] == 10000

    get_response = client.get(f"/api/v1/items/{created_item['id']}")
    assert get_response.status_code == 200
    assert get_response.json() == created_item


def test_create_item_validates_amount() -> None:
    response = client.post(
        "/api/v1/items",
        json={"name": "잘못된 정산", "amount": -1},
    )

    assert response.status_code == 422

