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


def test_outbound_rbac_enforces_access_type_levels() -> None:
    """Xác nhận mức quyền access_type (V vs X/G): quanly chỉ có quyền V ở DG-1 nên bị 403."""
    quanly_token = _login("quanly")
    resp_pkg = client.post(
        f"/api/v1/outbound-orders/{uuid.uuid4()}/packages",
        headers={"Authorization": f"Bearer {quanly_token}"},
        json={"weight_kg": "2.0"},
    )
    assert resp_pkg.status_code == 403
    assert resp_pkg.json()["error"]["code"] == "FORBIDDEN"

    # nv_soan chỉ có mức X_OWN ở SO-1 nên không được tạo phiên soạn (yêu cầu mức G)
    soan_token = _login("nv_soan")
    resp_ps = client.post(
        "/api/v1/pick-sessions",
        headers={"Authorization": f"Bearer {soan_token}"},
        json={"order_ids": [str(uuid.uuid4())]},
    )
    assert resp_ps.status_code == 403
    assert resp_ps.json()["error"]["code"] == "FORBIDDEN"


def test_outbound_web_client_renders_200_for_all_outbound_roles() -> None:
    """Xác nhận /outbound render 200 cho thukho, nv_soan, nv_dongoi với cookie abest_session."""
    from client.app.core.api_client import ApiClient
    from client.app.main import app as client_app

    orig = ApiClient.backend_app
    ApiClient.backend_app = app
    try:
        web = TestClient(client_app)
        for u in ("thukho", "nv_soan", "nv_dongoi"):
            r = web.get("/outbound", cookies={"abest_session": _login(u)}, follow_redirects=False)
            assert r.status_code == 200
            assert "Phân hệ Xuất kho" in r.text
    finally:
        ApiClient.backend_app = orig


def test_outbound_c08_picking_and_packing_views_and_rbac() -> None:
    """Xác nhận giao diện C-08 /outbound/picking, /outbound/packing và route báo ngoại lệ."""
    from client.app.core.api_client import ApiClient
    from client.app.main import app as client_app

    orig = ApiClient.backend_app
    ApiClient.backend_app = app
    try:
        web = TestClient(client_app)

        soan = _login("nv_soan")
        r_pick = web.get(
            "/outbound/picking", cookies={"abest_session": soan}, follow_redirects=False
        )
        assert r_pick.status_code == 200
        assert "Khu vực Soạn hàng" in r_pick.text
        assert (
            web.get(
                "/outbound/packing", cookies={"abest_session": soan}, follow_redirects=False
            ).status_code
            == 403
        )

        r_exc = web.post(
            f"/outbound/pick-sessions/{uuid.uuid4()}/lines/{uuid.uuid4()}/exception",
            data={
                "exception_type": "EXCEPTION_SHORT",
                "exception_reason": "SHORTAGE",
                "qty_actual": "0",
            },
            headers={"HX-Request": "true"},
            cookies={"abest_session": soan},
        )
        assert r_exc.status_code == 200
        assert "NOT_FOUND" in r_exc.text

        dongoi = _login("nv_dongoi")
        r_pack = web.get(
            "/outbound/packing", cookies={"abest_session": dongoi}, follow_redirects=False
        )
        assert r_pack.status_code == 200
        assert "Khu vực Đóng gói" in r_pack.text
        assert (
            web.get(
                "/outbound/picking", cookies={"abest_session": dongoi}, follow_redirects=False
            ).status_code
            == 403
        )
    finally:
        ApiClient.backend_app = orig
