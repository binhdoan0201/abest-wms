"""Unit tests cho module outbound."""

import uuid

from fastapi.testclient import TestClient

from server.app.main import app

client = TestClient(app)


def _login(username: str) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Demo@123456"},
    )
    assert resp.status_code == 200
    return str(resp.json()["data"]["access_token"])


def test_outbound_orders_list_returns_200_for_thukho() -> None:
    """Xác nhận Thủ kho (thukho) truy cập danh sách đơn xuất thành công với envelope chuẩn."""
    token = _login("thukho")
    resp = client.get(
        "/api/v1/outbound-orders",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert isinstance(body["data"], list)
    assert "meta" in body
    assert "request_id" in body["meta"]


def test_outbound_order_not_found_returns_404() -> None:
    """Xác nhận trả về 404 NOT_FOUND khi đơn xuất không tồn tại."""
    token = _login("thukho")
    random_id = uuid.uuid4()
    resp = client.get(
        f"/api/v1/outbound-orders/{random_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_outbound_rbac_blocks_unauthorized_roles() -> None:
    """Xác nhận kiểm tra RBAC chặt chẽ trên các endpoint Outbound."""
    # nv-soan không được phép gọi allocate (chỉ thukho/quanly)
    soan_token = _login("nv_soan")
    resp = client.post(
        f"/api/v1/outbound-orders/{uuid.uuid4()}/allocate",
        headers={"Authorization": f"Bearer {soan_token}"},
        json={},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"

    # thukho không được phép chốt yêu cầu đổi/hủy đơn từ ERP (chỉ quanly)
    thukho_token = _login("thukho")
    resp_decide = client.post(
        f"/api/v1/order-changes/{uuid.uuid4()}/decide",
        headers={"Authorization": f"Bearer {thukho_token}"},
        json={"decision": "ACCEPT"},
    )
    assert resp_decide.status_code == 403
    assert resp_decide.json()["error"]["code"] == "FORBIDDEN"
