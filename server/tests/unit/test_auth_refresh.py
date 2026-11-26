"""Test làm mới phiên (A-03): POST /auth/refresh và middleware tự gia hạn của client."""

import uuid
from collections.abc import Generator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from client.app.core.api_client import ApiClient
from client.app.core.session import token_seconds_left
from client.app.main import app as client_app
from server.app.core.database import SessionLocal
from server.app.core.security import create_access_token
from server.app.main import app as backend_app

api = TestClient(backend_app)
NV_NHAN = uuid.UUID("c0000000-0000-0000-0000-000000000001")


def _login(username: str = "nv_nhan") -> str:
    resp = api.post("/api/v1/auth/login", json={"username": username, "password": "Demo@123456"})
    assert resp.status_code == 200
    return str(resp.json()["data"]["access_token"])


def _token_expiring_in(minutes: int) -> str:
    """Token của nv_nhan, cùng claim như khi đăng nhập, sắp hết hạn."""
    return create_access_token(
        {
            "sub": str(NV_NHAN),
            "username": "nv_nhan",
            "role_code": "nv-nhan",
            "warehouse_id": "a0000000-0000-0000-0000-000000000001",
        },
        expires_delta=timedelta(minutes=minutes),
    )


def test_refresh_issues_new_eight_hour_token() -> None:
    old = _token_expiring_in(10)
    resp = api.post("/api/v1/auth/refresh", headers={"Authorization": f"Bearer {old}"})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["expires_in_hours"] == 8
    seconds = token_seconds_left(data["access_token"])
    assert seconds is not None and seconds > 7 * 3600
    me = api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert me.status_code == 200 and me.json()["data"]["username"] == "nv_nhan"


def test_refresh_rejects_missing_expired_and_locked() -> None:
    assert api.post("/api/v1/auth/refresh").status_code == 401
    expired = _token_expiring_in(-1)
    resp = api.post("/api/v1/auth/refresh", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401 and resp.json()["error"]["code"] == "AUTH_TOKEN_EXPIRED"

    token = _login()
    db = SessionLocal()
    try:
        db.execute(text("UPDATE users SET status = 'LOCKED' WHERE user_id = :u"), {"u": NV_NHAN})
        db.commit()
        resp = api.post("/api/v1/auth/refresh", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "AUTH_ACCOUNT_LOCKED"
    finally:
        db.execute(text("UPDATE users SET status = 'ACTIVE' WHERE user_id = :u"), {"u": NV_NHAN})
        db.commit()
        db.close()


@pytest.fixture
def web() -> Generator[TestClient, None, None]:
    original = ApiClient.backend_app
    ApiClient.backend_app = backend_app
    yield TestClient(client_app, base_url="http://localhost:3000")
    ApiClient.backend_app = original


def test_client_middleware_refreshes_cookie_near_expiry(web: TestClient) -> None:
    near = _token_expiring_in(20)
    resp = web.get("/inventory", cookies={"abest_session": near}, follow_redirects=False)
    assert resp.status_code == 200
    new_cookie = resp.cookies.get("abest_session")
    assert new_cookie and new_cookie != near
    seconds = token_seconds_left(new_cookie)
    assert seconds is not None and seconds > 7 * 3600


def test_client_middleware_keeps_fresh_cookie(web: TestClient) -> None:
    fresh = _login()
    resp = web.get("/inventory", cookies={"abest_session": fresh}, follow_redirects=False)
    assert resp.status_code == 200
    assert resp.cookies.get("abest_session") is None, "còn nhiều thời gian thì không đổi token"


def test_token_seconds_left_handles_garbage() -> None:
    assert token_seconds_left("khong-phai-jwt") is None
