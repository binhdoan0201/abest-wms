"""Integration tests cho module approvals."""

from fastapi.testclient import TestClient

from server.app.main import app

client = TestClient(app)


def test_approvals_access_control_integration() -> None:
    """Xác nhận nhân viên không có quyền duyệt (nv-nhan) bị chặn 403 khi vào hàng chờ duyệt."""
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "nv_nhan", "password": "Demo@123456"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["data"]["access_token"]

    resp = client.get(
        "/api/v1/approvals",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"
