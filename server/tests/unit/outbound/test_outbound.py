"""Unit tests cho module outbound."""

from fastapi.testclient import TestClient

from server.app.main import app

client = TestClient(app)


def test_outbound_orders_endpoint_returns_501_not_implemented() -> None:
    """Xác nhận router outbound đã khai báo và trả 501 Not Implemented cho chủ module C."""
    # Đăng nhập bằng nv-soan để có quyền SO-1
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "nv_soan", "password": "Demo@123456"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["data"]["access_token"]

    resp = client.get(
        "/api/v1/outbound-orders",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 501
    assert resp.json()["error"]["code"] == "NOT_IMPLEMENTED"
