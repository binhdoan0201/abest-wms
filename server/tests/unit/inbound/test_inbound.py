"""Unit tests cho module inbound."""

from fastapi.testclient import TestClient

from server.app.main import app

client = TestClient(app)


def test_inbound_grn_endpoint_returns_501_not_implemented() -> None:
    """Xác nhận router inbound đã khai báo và trả 501 Not Implemented cho chủ module B."""
    # Đăng nhập bằng nv-nhan để có quyền NH-1
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "nv_nhan", "password": "Demo@123456"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["data"]["access_token"]

    resp = client.get(
        "/api/v1/grns",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 501
    assert resp.json()["error"]["code"] == "NOT_IMPLEMENTED"
