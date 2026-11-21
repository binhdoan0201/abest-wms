"""Integration tests cho module outbound."""

from fastapi.testclient import TestClient

from server.app.main import app

client = TestClient(app)


def test_outbound_access_control_integration() -> None:
    """Xác nhận người dùng không có quyền SO-1 (nv-kiemke) bị chặn 403 khi truy cập đơn xuất."""
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "nv_kiemke", "password": "Demo@123456"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["data"]["access_token"]

    resp = client.get(
        "/api/v1/outbound-orders",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"
