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


def test_auth_001_login_returns_access_token_and_public_user() -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": "member@example.com", "password": "password1234"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["accessToken"]
    assert body["data"]["user"] == {
        "id": 1,
        "name": "홍길동",
        "email": "member@example.com",
        "role": "USER",
    }
    assert "password_hash" not in body
    assert "passwordHash" not in body


def test_auth_001_temporary_test_account_can_login() -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "test1234!"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["user"] == {
        "id": 3,
        "name": "테스트 사용자",
        "email": "test@example.com",
        "role": "USER",
    }


def test_auth_001_login_rejects_invalid_credentials() -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": "member@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "success": False,
        "message": "이메일 또는 비밀번호가 올바르지 않습니다.",
        "errorCode": "AUTH_REQUIRED",
    }


def test_user_001_returns_current_user_from_bearer_token() -> None:
    login_response = client.post(
        "/api/auth/login",
        json={"email": "member@example.com", "password": "password1234"},
    )
    access_token = login_response.json()["data"]["accessToken"]

    response = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "내 정보 조회에 성공했습니다.",
        "data": {
            "id": 1,
            "name": "홍길동",
            "email": "member@example.com",
            "role": "USER",
        },
    }


def test_user_001_requires_bearer_token() -> None:
    response = client.get("/api/users/me")

    assert response.status_code == 401
    assert response.json() == {
        "success": False,
        "message": "로그인이 필요합니다.",
        "errorCode": "AUTH_REQUIRED",
    }


def test_cat_001_returns_active_categories_only() -> None:
    response = client.get("/api/categories")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "활성 카테고리 조회에 성공했습니다."
    assert body["data"] == [
        {"id": 1, "name": "식비", "description": "식사 관련 지출"},
        {"id": 2, "name": "교통비", "description": "교통 관련 지출"},
        {"id": 3, "name": "인쇄비", "description": "인쇄 관련 지출"},
        {"id": 4, "name": "소모품비", "description": "소모품 관련 지출"},
        {"id": 5, "name": "기타", "description": "그 외 지출"},
    ]
