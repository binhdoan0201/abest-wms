"""Test Web Client: màn hình Admin (A-11, chỉ đọc) và trang tồn kho có lọc, lô, lịch sử."""

import re
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from client.app.core.api_client import ApiClient
from client.app.core.auth_guard import home_path
from client.app.main import app as client_app
from server.app.main import app as backend_app

ORIGIN = {"Origin": "http://localhost:3000"}


@pytest.fixture
def web() -> Generator[TestClient, None, None]:
    original = ApiClient.backend_app
    ApiClient.backend_app = backend_app
    yield TestClient(client_app, base_url="http://localhost:3000")
    ApiClient.backend_app = original


def _login(web: TestClient, username: str) -> tuple[dict[str, str], str]:
    resp = web.post(
        "/login",
        data={"username": username, "password": "Demo@123456"},
        headers=ORIGIN,
        follow_redirects=False,
    )
    assert resp.status_code == 303
    return {"abest_session": resp.cookies.get("abest_session") or ""}, resp.headers["location"]


def _caption(html: str) -> str:
    match = re.search(r"<caption[^>]*>(.*?)</caption>", html, re.S)
    assert match
    return " ".join(match.group(1).split())


def test_admin_lands_on_master_data_and_reads_every_tab(web: TestClient) -> None:
    assert home_path({"role_code": "admin"}) == "/master-data"
    cookies, location = _login(web, "admin")
    assert location == "/master-data"
    for res, label in (
        ("warehouses", "Kho"),
        ("skus", "SKU"),
        ("vehicles", "Xe"),
        ("users", "Người dùng"),
    ):
        resp = web.get(f"/master-data?res={res}", cookies=cookies)
        assert resp.status_code == 200, res
        assert _caption(resp.text).startswith(label), res
    search = web.get("/master-data?res=skus&q=FOOD", cookies=cookies)
    assert "SKU-FOOD-001" in search.text and "SKU-ELEC-003" not in search.text


def test_master_data_page_forbidden_without_ad1(web: TestClient) -> None:
    cookies, _ = _login(web, "thukho")
    assert web.get("/master-data?res=users", cookies=cookies).status_code == 403


def test_inventory_page_shows_codes_filters_and_history_for_manager(web: TestClient) -> None:
    cookies, _ = _login(web, "quanly")
    page = web.get("/inventory", cookies=cookies)
    assert page.status_code == 200
    assert "Lịch sử giao dịch" in page.text and "Hạn dùng" in page.text
    sku_id = re.search(r'value="([0-9a-f-]{36})"[^>]*>SKU-FOOD-001', page.text)
    assert sku_id, "bộ lọc SKU hiện mã SKU"
    history = web.get("/inventory?tab=history", cookies=cookies)
    assert history.status_code == 200 and "Chứng từ" in history.text


def test_inventory_history_hidden_for_staff_and_blind_counter_blocked(web: TestClient) -> None:
    cookies, _ = _login(web, "nv_soan")
    page = web.get("/inventory?tab=history", cookies=cookies)
    assert page.status_code == 200
    assert "Lịch sử giao dịch" not in page.text and "Khả dụng" in page.text
    kiemke, _ = _login(web, "nv_kiemke")
    assert web.get("/inventory", cookies=kiemke).status_code == 403
