"""Integration tests cho module master_data."""

from fastapi.testclient import TestClient

from server.app.main import app

client = TestClient(app)


def test_master_data_access_control_integration() -> None:
    """Xác nhận người dùng không có quyền AD-1 (nv-nhan) bị chặn 403 khi ghi master data."""
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "nv_nhan", "password": "Demo@123456"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["data"]["access_token"]

    resp = client.post(
        "/api/v1/warehouses",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": "WH_TEST", "name": "Kho Thử Nghiệm", "extra": {}},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"
