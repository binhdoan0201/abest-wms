"""Unit tests cho module cycle_count."""

from fastapi.testclient import TestClient

from server.app.main import app

client = TestClient(app)


def test_cycle_count_endpoint_returns_200_and_enforces_rbac() -> None:
    """Xác nhận endpoint GET /api/v1/cycle-counts hoạt động và kiểm soát quyền truy cập."""
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "nv_kiemke", "password": "Demo@123456"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["data"]["access_token"]

    resp = client.get(
        "/api/v1/cycle-counts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["data"], list)
    assert "meta" in body

    # Nhân viên đóng gói không có quyền kiểm kê -> 403
    login_other = client.post(
        "/api/v1/auth/login",
        json={"username": "nv_dongoi", "password": "Demo@123456"},
    )
    other_token = login_other.json()["data"]["access_token"]
    resp_forbidden = client.get(
        "/api/v1/cycle-counts",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp_forbidden.status_code == 403
