"""Integration tests cho module cycle_count."""

from fastapi.testclient import TestClient

from server.app.main import app

client = TestClient(app)


def test_cycle_count_rbac_protection() -> None:
    """Xác nhận các route cycle_count chặn người dùng không có quyền hoặc chưa đăng nhập."""
    resp = client.get("/api/v1/cycle-counts")
    assert resp.status_code == 401

    # Đăng nhập bằng user không có quyền KK-1 (vd: nv_nhan chỉ có NH-1..4)
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "nv_nhan", "password": "Demo@123456"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["data"]["access_token"]

    resp = client.get(
        "/api/v1/cycle-counts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
