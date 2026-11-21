"""Unit tests cho module master_data."""

from fastapi.testclient import TestClient

from server.app.main import app

client = TestClient(app)


def test_master_data_crud_endpoint_returns_501_not_implemented() -> None:
    """Xác nhận router master_data đã khai báo và trả 501 Not Implemented cho chủ module B."""
    # Đăng nhập bằng admin để có quyền AD-1
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "Demo@123456"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["data"]["access_token"]

    resp = client.post(
        "/api/v1/warehouses",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": "WH_TEST", "name": "Kho Thử Nghiệm", "extra": {}},
    )
    assert resp.status_code == 501
    assert resp.json()["error"]["code"] == "NOT_IMPLEMENTED"
