"""Integration tests cho module dashboard."""

from fastapi.testclient import TestClient

from server.app.main import app

client = TestClient(app)


def test_dashboard_rbac_protection() -> None:
    """Xác nhận các route dashboard chặn người dùng không có quyền QL-8.1."""
    resp = client.get("/api/v1/dashboard/tasks")
    assert resp.status_code == 401

    # Đăng nhập bằng nv_nhan (chỉ có QL-1.1 và NH-1..4, không có QL-8.1)
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "nv_nhan", "password": "Demo@123456"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["data"]["access_token"]

    resp = client.get(
        "/api/v1/dashboard/tasks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
