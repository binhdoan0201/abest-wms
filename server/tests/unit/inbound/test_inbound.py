"""Unit tests cho module inbound."""

from fastapi.testclient import TestClient

from server.app.main import app

client = TestClient(app)


def test_inbound_grn_endpoint_returns_200_and_enforces_rbac() -> None:
    """Xác nhận endpoint GET /api/v1/grns hoạt động và kiểm soát quyền truy cập."""
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
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["data"], list)
    assert "meta" in body

    # Nhân viên kiểm kê không có quyền nhập kho -> 403
    login_other = client.post(
        "/api/v1/auth/login",
        json={"username": "nv_kiemke", "password": "Demo@123456"},
    )
    other_token = login_other.json()["data"]["access_token"]
    resp_forbidden = client.get(
        "/api/v1/grns",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp_forbidden.status_code == 403
