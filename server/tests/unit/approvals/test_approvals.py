"""Unit tests cho module approvals."""

from fastapi.testclient import TestClient

from server.app.main import app

client = TestClient(app)


def test_approvals_endpoint_returns_501_not_implemented() -> None:
    """Xác nhận router approvals đã khai báo và trả 501 Not Implemented cho chủ module D."""
    # Đăng nhập bằng thukho để có quyền TK-3.2
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "thukho", "password": "Demo@123456"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["data"]["access_token"]

    resp = client.get(
        "/api/v1/approvals",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 501
    assert resp.json()["error"]["code"] == "NOT_IMPLEMENTED"
