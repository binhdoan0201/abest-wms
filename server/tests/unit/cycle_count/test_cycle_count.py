"""Unit tests cho module cycle_count."""

from fastapi.testclient import TestClient

from server.app.main import app

client = TestClient(app)


def test_cycle_count_endpoint_returns_501_not_implemented() -> None:
    """Xác nhận router cycle_count đã khai báo và trả về 501 Not Implemented cho chủ module D."""
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
    assert resp.status_code == 501
    assert resp.json()["error"]["code"] == "NOT_IMPLEMENTED"
