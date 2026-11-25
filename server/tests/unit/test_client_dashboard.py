"""Test Web Client cho màn hình Tổng quan (A-13): trang đầu của bgd, ba khối số liệu, HTMX."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from client.app.core.api_client import ApiClient
from client.app.core.auth_guard import home_path
from client.app.main import app as client_app
from server.app.main import app as backend_app

ORIGIN = {"Origin": "http://localhost:3000"}


@pytest.fixture(autouse=True)
def in_memory_backend() -> Generator[None, None, None]:
    original = ApiClient.backend_app
    ApiClient.backend_app = backend_app
    yield
    ApiClient.backend_app = original


@pytest.fixture
def web() -> TestClient:
    return TestClient(client_app, base_url="http://localhost:3000")


def _login(web: TestClient, username: str) -> tuple[str, str]:
    resp = web.post(
        "/login",
        data={"username": username, "password": "Demo@123456"},
        headers=ORIGIN,
        follow_redirects=False,
    )
    assert resp.status_code == 303
    return resp.headers["location"], resp.cookies.get("abest_session") or ""


def test_home_path_by_role() -> None:
    assert home_path({"role_code": "bgd"}) == "/dashboard"
    assert home_path({"role_code": "thukho"}) == "/inventory"
    assert home_path(None) == "/inventory"


def test_bgd_lands_on_dashboard_with_three_sections(web: TestClient) -> None:
    location, cookie = _login(web, "bgd")
    assert location == "/dashboard"

    resp = web.get("/dashboard", cookies={"abest_session": cookie})
    assert resp.status_code == 200
    for heading in ("Bảng Điều Hành Kho", "Cảnh báo", "Nhiệm vụ", "Tồn kho", "Đơn trong ngày"):
        assert heading in resp.text
    assert 'hx-trigger="every 60s"' in resp.text

    root = web.get("/", cookies={"abest_session": cookie}, follow_redirects=False)
    assert root.headers["location"] == "/dashboard"


def test_dashboard_refresh_htmx_returns_panels(web: TestClient) -> None:
    _, cookie = _login(web, "quanly")
    resp = web.post(
        "/dashboard/refresh",
        headers={"HX-Request": "true", **ORIGIN},
        cookies={"abest_session": cookie},
    )
    assert resp.status_code == 200
    assert "Cập nhật lúc" in resp.text
    assert "<html" not in resp.text


def test_dashboard_forbidden_for_staff(web: TestClient) -> None:
    location, cookie = _login(web, "nv_nhan")
    assert location == "/inventory"
    resp = web.get("/dashboard", cookies={"abest_session": cookie})
    assert resp.status_code == 403
