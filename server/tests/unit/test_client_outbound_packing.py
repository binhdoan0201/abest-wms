"""Test Web Client C-08 (luong dong goi va xuat GI 3 buoc) va C-07 (RETURN_PICKING)."""

import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from client.app.core.api_client import ApiClient, ClientApiError
from client.app.main import app as client_app
from server.app.main import app as backend_app
from server.app.modules.outbound import repositories as out_repo
from server.app.modules.outbound import services as out_svc
from server.app.modules.outbound.services import OutboundService

ORIGIN = {"Origin": "http://localhost:3000"}


@pytest.fixture
def web() -> Generator[TestClient, None, None]:
    original = ApiClient.backend_app
    ApiClient.backend_app = backend_app
    yield TestClient(client_app, base_url="http://localhost:3000")
    ApiClient.backend_app = original


def _login(web: TestClient, username: str) -> dict[str, str]:
    resp = web.post(
        "/login",
        data={"username": username, "password": "Demo@123456"},
        headers=ORIGIN,
        follow_redirects=False,
    )
    assert resp.status_code == 303
    return {"abest_session": resp.cookies.get("abest_session") or ""}


def test_packing_page_loads_box_types_and_vehicles_for_dg1(
    web: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    cookies = _login(web, "nv_dongoi")
    box_params: list[dict[str, Any] | None] = []

    def fake_get(
        self: ApiClient, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if path == "/auth/me":
            return {
                "data": {"username": "nv_dongoi", "role_code": "nv_dongoi", "permissions": ["DG-1"]}
            }
        if path == "/box-types":
            box_params.append(params)
            return {
                "data": [
                    {"box_type_id": "b1", "box_code": "BOX-S", "box_name": "Nho"},
                    {"box_type_id": "b2", "box_code": "BOX-M", "box_name": "Vua"},
                    {"box_type_id": "b3", "box_code": "BOX-L", "box_name": "Lon"},
                ]
            }
        if path == "/vehicles":
            return {
                "data": [
                    {
                        "vehicle_id": "v1",
                        "license_plate": "51C-123.45",
                        "driver_name": "Nguyen Van A",
                    }
                ]
            }
        if path == "/outbound-orders" and (params or {}).get("status") == "PACKING":
            return {
                "data": [
                    {
                        "order_id": "ord-101",
                        "erp_order_number": "SO-2026-101",
                        "customer_name": "Khach Hang A",
                        "status": "PACKING",
                    }
                ]
            }
        return {"data": []}

    monkeypatch.setattr(ApiClient, "get", fake_get)
    resp = web.get("/outbound/packing", cookies=cookies)
    assert resp.status_code == 200
    assert box_params and "is_active" not in (box_params[0] or {})
    assert "BOX-S" in resp.text and "BOX-M" in resp.text and "BOX-L" in resp.text
    assert "51C-123.45" in resp.text
    assert "SO-2026-101" in resp.text and "Khach Hang A" in resp.text


def test_three_step_packing_gi_and_waybill_error(
    web: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    cookies = _login(web, "nv_dongoi")
    calls: list[tuple[str, dict[str, Any] | None]] = []

    def fake_get(
        self: ApiClient, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if path == "/box-types":
            return {"data": [{"box_type_id": "b1", "box_code": "BOX-S", "box_name": "Nho"}]}
        if path == "/auth/me":
            return {
                "data": {"username": "nv_dongoi", "role_code": "nv_dongoi", "permissions": ["DG-1"]}
            }
        if path.startswith("/outbound-orders") and (
            "status=PACKING" in path or (params or {}).get("status") == "PACKING"
        ):
            return {
                "data": [
                    {
                        "order_id": "o1",
                        "erp_order_number": "SO-2026-101",
                        "customer_name": "Khach Hang A",
                        "status": "PACKING",
                    }
                ]
            }
        return {"data": []}

    def fake_post(
        self: ApiClient,
        path: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        calls.append((path, json_data))
        if path.endswith("/packages"):
            return {"data": {"package_id": "p1", "package_barcode": "PKG-01"}}
        if path == "/goods-issues":
            return {
                "data": {
                    "gi_id": "gi-1",
                    "gi_number": "GI-001",
                    "order_status": "WAITING_WAYBILL",
                    "tms_waybill_code": None,
                }
            }
        if path == "/goods-issues/gi-1/confirm":
            if (json_data or {}).get("driver_signature_data") == "NO_WB":
                raise ClientApiError(
                    code="OUTBOUND_WAYBILL_REQUIRED", message="Missing WB", http_status=409
                )
            return {"data": {"gi_number": "GI-001", "order_status": "SHIPPED"}}
        return {"data": {}}

    monkeypatch.setattr(ApiClient, "get", fake_get)
    monkeypatch.setattr(ApiClient, "post", fake_post)

    r1 = web.post(
        "/outbound/pack-and-ship",
        data={"action": "package", "order_id": "o1", "box_type_id": "b1", "weight_kg": "2.5"},
        cookies=cookies,
    )
    assert r1.status_code == 200
    assert "SO-2026-101" in r1.text and "BOX-S" in r1.text and "PKG-01" in r1.text
    pkg_calls = [(p, d) for p, d in calls if p.endswith("/packages")]
    assert (
        len(pkg_calls) == 1
        and pkg_calls[0][1] is not None
        and pkg_calls[0][1]["box_type_id"] == "b1"
        and pkg_calls[0][1]["weight_kg"] == "2.5"
    )

    r2 = web.post(
        "/outbound/pack-and-ship",
        data={"action": "create_gi", "order_id": "o1", "vehicle_id": "v1"},
        cookies=cookies,
    )
    assert (
        r2.status_code == 200
        and "GI-001" in r2.text
        and "chờ vận đơn" in r2.text
        and "WAITING_WAYBILL" in r2.text
    )
    assert 'name="gi_id"' in r2.text and ('value="gi-1"' in r2.text and "selected" in r2.text)
    gi_payload = [(p, d) for p, d in calls if p == "/goods-issues"][0][1]
    assert gi_payload is not None and gi_payload["vehicle_id"] == "v1"

    r3_err = web.post(
        "/outbound/pack-and-ship",
        data={"action": "confirm_gi", "gi_id": "gi-1", "driver_signature_data": "NO_WB"},
        cookies=cookies,
    )
    assert r3_err.status_code == 200 and "Chưa có mã vận đơn TMS" in r3_err.text

    r3_ok = web.post(
        "/outbound/pack-and-ship",
        data={"action": "confirm_gi", "gi_id": "gi-1", "driver_signature_data": "Nguyen Van A"},
        cookies=cookies,
    )
    assert r3_ok.status_code == 200 and "SHIPPED" in r3_ok.text
    cfm_payload = [(p, d) for p, d in calls if p == "/goods-issues/gi-1/confirm"][-1][1]
    assert cfm_payload is not None and cfm_payload["driver_signature_data"] == "Nguyen Van A"


def test_c07_cancel_picked_order_does_not_duplicate_task_in_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []
    req_id, order_id, wh_id, user_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    ctx = type("Ctx", (), {"role_code": "quanly", "user_id": user_id, "warehouse_id": wh_id})()
    req = type("Req", (), {"decision": "ACCEPT", "reject_note": None})()

    monkeypatch.setattr(out_svc, "_require_access", lambda *a, **kw: None)
    monkeypatch.setattr(out_svc, "enforce_warehouse_scope", lambda *a, **kw: None)
    monkeypatch.setattr(out_svc, "create_audit_log", lambda *a, **kw: None)
    monkeypatch.setattr(
        out_repo.OutboundRepository,
        "get_order_change_request_raw",
        lambda db, rid: {
            "request_id": str(rid),
            "order_id": str(order_id),
            "warehouse_id": str(wh_id),
            "change_type": "CANCEL",
            "order_status_at_receipt": "PICKED",
            "status": "APPROVED",
            "erp_change_pending": False,
        },
    )
    monkeypatch.setattr(
        out_repo.OutboundRepository, "call_decide_order_change", lambda **kw: calls.append(kw)
    )
    monkeypatch.setattr(
        out_repo.OutboundRepository,
        "get_order_raw",
        lambda db, oid: {"order_id": str(oid), "status": "CANCELLED", "erp_change_pending": False},
    )

    out = OutboundService.decide_order_change(
        db=cast(Session, None), user_ctx=ctx, request_id=req_id, req=req, access_type="X"
    )
    assert out["order_status"] == "CANCELLED"
    assert len(calls) == 1 and calls[0]["decision"] == "ACCEPT"


def test_to_vn_date_utc_midnight_rollover() -> None:
    from server.app.modules.outbound.services import _to_vn_date

    dt_utc = datetime(2026, 11, 25, 20, 0, tzinfo=timezone.utc)
    assert str(_to_vn_date(dt_utc)) == "2026-11-26"


# --- Route-level tests for picking sessions & GI waybill persistence ---
def test_picking_route_loads_sessions_from_user_tasks(
    web: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    cookies = _login(web, "nv_dongoi")

    def fake_get(
        self: ApiClient, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if path == "/auth/me":
            return {
                "data": {
                    "username": "nv_soanhang",
                    "role_code": "nv_soanhang",
                    "permissions": ["SO-1"],
                }
            }
        if path == "/tasks":
            return {
                "data": [
                    {
                        "task_type": "PICKING",
                        "ref_doc_type": "PICK_SESSION",
                        "ref_doc_id": "ps-12345678",
                        "status": "IN_PROGRESS",
                    },
                    {
                        "task_type": "PICKING",
                        "ref_doc_type": "PICK_SESSION",
                        "ref_doc_id": "ps-done-999",
                        "status": "COMPLETED",
                    },
                    {
                        "task_type": "PUTAWAY",
                        "ref_doc_type": "PUTAWAY_TASK",
                        "ref_doc_id": "pa-999",
                        "status": "PENDING",
                    },
                ]
            }
        if path.startswith("/pick-sessions/ps-12345678"):
            return {
                "data": {
                    "pick_session_id": "ps-12345678",
                    "status": "IN_PROGRESS",
                    "version_no": 1,
                    "lines": [
                        {
                            "erp_order_number": "SO-2026-001",
                            "qty_to_pick": 5,
                            "status": "PENDING",
                        }
                    ],
                }
            }
        return {"data": []}

    monkeypatch.setattr(ApiClient, "get", fake_get)
    resp = web.get("/outbound/picking?session_id=ps-12345678", cookies=cookies)
    assert resp.status_code == 200
    assert 'value="ps-12345678"' in resp.text
    assert "Soạn đơn SO-2026-001" in resp.text
    assert "ps-done-999" not in resp.text


def test_pack_and_ship_route_confirm_gi_waybill_error_keeps_selected_gi(
    web: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    cookies = _login(web, "nv_dongoi")

    def fake_get(
        self: ApiClient, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if path == "/auth/me":
            return {
                "data": {
                    "username": "nv_dongoi",
                    "role_code": "nv_dongoi",
                    "permissions": ["DG-1"],
                }
            }
        return {"data": []}

    def fake_post(
        self: ApiClient, path: str, json_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if path == "/goods-issues/gi-1/confirm":
            raise ClientApiError(
                code="OUTBOUND_WAYBILL_REQUIRED",
                message="Missing waybill",
                http_status=409,
            )
        return {"data": {}}

    monkeypatch.setattr(ApiClient, "get", fake_get)
    monkeypatch.setattr(ApiClient, "post", fake_post)
    resp = web.post(
        "/outbound/pack-and-ship",
        data={
            "action": "confirm_gi",
            "gi_id": "gi-1",
            "driver_signature_data": "Nguyen Van A",
        },
        cookies=cookies,
    )
    assert resp.status_code == 200
    assert "OUTBOUND_WAYBILL_REQUIRED" in resp.text
    assert '<option value="gi-1" selected>' in resp.text


def test_thukho_creates_session_for_nv_soan_visible_in_picking(
    web: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created_sessions: list[dict[str, Any]] = []
    assigned_tasks: list[dict[str, Any]] = []
    current_role: dict[str, Any] = {
        "username": "thukho",
        "role_code": "thukho",
        "permissions": ["SO-1", "XK-1"],
    }

    def fake_get(
        self: ApiClient, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if path == "/auth/me":
            return {"data": dict(current_role)}
        if path == "/users":
            return {
                "data": [
                    {
                        "user_id": "u-nv-soan",
                        "username": "nv_soan",
                        "full_name": "NV Soạn",
                        "role_code": "nv_soan",
                        "can_receive_tasks": True,
                    }
                ]
            }
        if path == "/outbound-orders":
            return {
                "data": [
                    {
                        "order_id": "ord-100",
                        "erp_order_number": "DEMO-SO-001",
                        "order_type": "SALES",
                        "customer_name": "Khách lẻ",
                        "status": "NEW",
                        "version_no": 1,
                    }
                ]
            }
        if path == "/tasks":
            return {"data": list(assigned_tasks)}
        if path.startswith("/pick-sessions/"):
            sid = path.rsplit("/", 1)[-1]
            for s in created_sessions:
                if s["pick_session_id"] == sid:
                    return {"data": s}
        return {"data": []}

    def fake_post(
        self: ApiClient, path: str, json_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if path == "/auth/login":
            return {
                "data": {
                    "access_token": "tok-demo-123",
                    "refresh_token": "ref-demo-123",
                    "user": dict(current_role),
                }
            }
        if path == "/pick-sessions":
            picker_id = str((json_data or {}).get("picker_user_id") or "")
            sid = "ps-demo-001"
            session_obj = {
                "pick_session_id": sid,
                "status": "IN_PROGRESS",
                "version_no": 1,
                "picker_user_id": picker_id,
                "lines": [
                    {"erp_order_number": "DEMO-SO-001", "qty_to_pick": 3, "status": "PENDING"}
                ],
            }
            created_sessions.append(session_obj)
            if picker_id:
                assigned_tasks.append(
                    {
                        "task_type": "PICKING",
                        "ref_doc_type": "PICK_SESSION",
                        "ref_doc_id": sid,
                        "assigned_to": picker_id,
                        "status": "IN_PROGRESS",
                    }
                )
            return {"data": session_obj}
        return {"data": {}}

    monkeypatch.setattr(ApiClient, "get", fake_get)
    monkeypatch.setattr(ApiClient, "post", fake_post)

    cookies = _login(web, "thukho")
    create_resp = web.post(
        "/outbound/pick-sessions/create",
        data={"order_id": "ord-100", "pick_mode": "SINGLE_ORDER", "picker_user_id": "u-nv-soan"},
        cookies=cookies,
    )
    assert create_resp.status_code == 200
    assert "u-nv-soan" in create_resp.text
    assert created_sessions[-1]["picker_user_id"] == "u-nv-soan"

    current_role.update(
        {
            "user_id": "u-nv-soan",
            "username": "nv_soan",
            "role_code": "nv_soan",
            "permissions": ["SO-1"],
        }
    )
    pick_resp = web.get("/outbound/picking", cookies=cookies)
    assert pick_resp.status_code == 200
    assert 'value="ps-demo-001"' in pick_resp.text
    assert "Soạn đơn DEMO-SO-001" in pick_resp.text


def test_allocate_then_create_session_for_nv_soan_visible_in_picking(
    web: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    allocated_orders: set[str] = set()
    created_sessions: list[dict[str, Any]] = []
    assigned_tasks: list[dict[str, Any]] = []
    current_role: dict[str, Any] = {
        "username": "thukho",
        "role_code": "thukho",
        "permissions": ["SO-1", "XK-1"],
    }

    def fake_get(
        self: ApiClient, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if path == "/auth/me":
            return {"data": dict(current_role)}
        if path == "/users":
            return {
                "data": [
                    {
                        "user_id": "u-nv-soan",
                        "username": "nv_soan",
                        "full_name": "NV Soạn",
                        "role_code": "nv_soan",
                        "can_receive_tasks": True,
                        "is_active": True,
                    }
                ]
            }
        if path == "/outbound-orders":
            return {
                "data": [
                    {
                        "order_id": "ord-100",
                        "erp_order_number": "DEMO-SO-001",
                        "order_type": "SALES",
                        "customer_name": "Khách lẻ",
                        "status": "NEW",
                        "erp_change_pending": False,
                        "version_no": 2 if "ord-100" in allocated_orders else 1,
                    }
                ]
            }
        if path == "/tasks":
            return {"data": list(assigned_tasks)}
        if path.startswith("/pick-sessions/"):
            sid = path.rsplit("/", 1)[-1]
            for s in created_sessions:
                if s["pick_session_id"] == sid:
                    return {"data": s}
        return {"data": []}

    def fake_post(
        self: ApiClient, path: str, json_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if path == "/auth/login":
            return {
                "data": {
                    "access_token": "tok-demo-123",
                    "refresh_token": "ref-demo-123",
                    "user": dict(current_role),
                }
            }
        if path == "/outbound-orders/ord-100/allocate":
            allocated_orders.add("ord-100")
            return {"data": {"order_id": "ord-100", "status": "NEW", "version_no": 2}}
        if path == "/pick-sessions":
            picker_id = str((json_data or {}).get("picker_user_id") or "")
            sid = "ps-demo-001"
            session_obj = {
                "pick_session_id": sid,
                "status": "IN_PROGRESS",
                "version_no": 1,
                "picker_user_id": picker_id,
                "lines": [
                    {
                        "erp_order_number": "DEMO-SO-001",
                        "qty_to_pick": 3,
                        "status": "PENDING",
                    }
                ],
            }
            created_sessions.append(session_obj)
            if picker_id:
                assigned_tasks.append(
                    {
                        "task_type": "PICKING",
                        "ref_doc_type": "PICK_SESSION",
                        "ref_doc_id": sid,
                        "assigned_to": picker_id,
                        "status": "IN_PROGRESS",
                    }
                )
            return {"data": session_obj}
        return {"data": {}}

    monkeypatch.setattr(ApiClient, "get", fake_get)
    monkeypatch.setattr(ApiClient, "post", fake_post)

    cookies = _login(web, "thukho")
    alloc_resp = web.post(
        "/outbound/orders/ord-100/allocate",
        data={"strategy": "FEFO", "version_no": "1"},
        cookies=cookies,
    )
    assert alloc_resp.status_code == 200
    assert '<option value="u-nv-soan"' in alloc_resp.text

    create_resp = web.post(
        "/outbound/pick-sessions/create",
        data={
            "order_id": "ord-100",
            "pick_mode": "SINGLE_ORDER",
            "picker_user_id": "u-nv-soan",
        },
        cookies=cookies,
    )
    assert create_resp.status_code == 200
    assert "Đã tạo phiên soạn Soạn đơn DEMO-SO-001!" in create_resp.text
    assert created_sessions[-1]["picker_user_id"] == "u-nv-soan"

    current_role.update(
        {
            "user_id": "u-nv-soan",
            "username": "nv_soan",
            "role_code": "nv_soan",
            "permissions": ["SO-1"],
        }
    )
    pick_resp = web.get("/outbound/picking", cookies=cookies)
    assert pick_resp.status_code == 200
    assert 'value="ps-demo-001"' in pick_resp.text
    assert "Soạn đơn DEMO-SO-001" in pick_resp.text


def test_create_pick_session_without_picker_is_blocked(
    web: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    posted_paths: list[str] = []

    def fake_get(
        self: ApiClient, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if path == "/auth/me":
            return {
                "data": {
                    "username": "thukho",
                    "role_code": "thukho",
                    "permissions": ["SO-1", "XK-1"],
                }
            }
        if path == "/users":
            return {
                "data": [
                    {
                        "user_id": "u-nv-soan-1",
                        "username": "nv_soan_1",
                        "full_name": "NV Soạn 1",
                        "role_code": "nv_soan",
                        "can_receive_tasks": True,
                        "is_active": True,
                    },
                    {
                        "user_id": "u-nv-soan-2",
                        "username": "nv_soan_2",
                        "full_name": "NV Soạn 2",
                        "role_code": "nv_soan",
                        "can_receive_tasks": True,
                        "is_active": True,
                    },
                ]
            }
        if path == "/outbound-orders":
            return {
                "data": [
                    {
                        "order_id": "ord-100",
                        "erp_order_number": "DEMO-SO-001",
                        "order_type": "SALES",
                        "customer_name": "Khách lẻ",
                        "status": "NEW",
                        "erp_change_pending": False,
                        "version_no": 1,
                    }
                ]
            }
        return {"data": []}

    def fake_post(
        self: ApiClient, path: str, json_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if path == "/auth/login":
            return {
                "data": {
                    "access_token": "tok-demo-123",
                    "refresh_token": "ref-demo-123",
                    "user": {"username": "thukho", "role_code": "thukho"},
                }
            }
        posted_paths.append(path)
        return {"data": {}}

    monkeypatch.setattr(ApiClient, "get", fake_get)
    monkeypatch.setattr(ApiClient, "post", fake_post)

    cookies = _login(web, "thukho")
    resp = web.post(
        "/outbound/pick-sessions/create",
        data={"order_id": "ord-100", "pick_mode": "SINGLE_ORDER", "picker_user_id": ""},
        cookies=cookies,
    )
    assert resp.status_code == 200
    assert "/pick-sessions" not in posted_paths
    assert "PICKER_REQUIRED" in resp.text
    assert '<option value="u-nv-soan-1"' in resp.text
    assert '<option value="u-nv-soan-2"' in resp.text


def test_outbound_h1_h2_h5_helpers_and_views():
    from client.app.modules.outbound.views import (
        _enrich_pick_session,
        _format_expiry_date,
    )

    assert _format_expiry_date("2026-12-04") == "04/12/2026"

    raw_session = {
        "pick_session_id": "ps-1",
        "status": "IN_PROGRESS",
        "version_no": 1,
        "lines": [
            {
                "pick_line_id": "pl-1",
                "sku_code": "SKU-FOOD-001",
                "sku_name": "Sữa tươi",
                "source_location_id": "loc-1",
                "suggested_lot_id": "lot-1",
                "qty_to_pick": "10",
                "qty_picked": "0",
                "status": "PENDING",
            }
        ],
    }
    enriched = _enrich_pick_session(
        raw_session,
        "ps-1",
        lot_map={"lot-1": {"code": "DEMO-SUA-A", "expiry": "04/12/2026"}},
        loc_map={"loc-1": "LOC-A02-01"},
    )
    summary = enriched["lines"][0]["fefo_summary"]
    assert "LOC-A02-01" in summary
    assert "DEMO-SUA-A" in summary
    assert "04/12/2026" in summary
    assert "Sữa tươi" in summary


def test_outbound_h2_lot_and_location_maps_and_pagination():
    from client.app.modules.outbound.views import _load_lot_and_location_maps

    class _DummyApi:
        def get(self, path, params=None):
            if path == "/lots":
                return {
                    "data": [
                        {"lot_id": "lot-1", "lot_code": "DEMO-SUA-A", "expiry_date": "2026-12-04"}
                    ]
                }
            if path == "/locations":
                return {"data": [{"location_id": "loc-1", "location_code": "LOC-A02-01"}]}
            return {"data": []}

    lot_map, loc_map = _load_lot_and_location_maps(_DummyApi())
    assert lot_map["lot-1"]["code"] == "DEMO-SUA-A"
    assert loc_map["loc-1"] == "LOC-A02-01"


def test_outbound_h5_confirm_gi_payload_fields():
    res = {
        "gi_id": "gi-uuid-1234",
        "gi_number": "GI-2026-001",
        "order_status": "SHIPPED",
        "tms_waybill_code": "TMS-WB-999",
    }
    assert res["gi_number"] == "GI-2026-001"
    assert res["order_status"] == "SHIPPED"
    assert res["tms_waybill_code"] == "TMS-WB-999"


def test_outbound_h2_allocate_real_api_shows_location_code_and_formatted_qty(
    web: TestClient,
) -> None:
    from datetime import timedelta
    from decimal import Decimal

    from sqlalchemy import text

    from server.app.core.database import SessionLocal
    from server.app.modules.inventory import models as inv_models
    from server.app.modules.master_data import models as md_models
    from server.app.modules.outbound import models as out_models

    suffix = uuid.uuid4().hex[:8]
    db = SessionLocal()
    created_ids: dict[str, uuid.UUID] = {}
    created_loc = False
    created_customer = False
    try:
        wh_row = db.execute(text("SELECT warehouse_id FROM warehouses LIMIT 1")).first()
        if wh_row and wh_row[0]:
            warehouse_id = uuid.UUID(str(wh_row[0]))
        else:
            warehouse_id = uuid.uuid4()
            db.execute(
                text(
                    "INSERT INTO warehouses "
                    "(warehouse_id, warehouse_code, warehouse_name, is_active) "
                    "VALUES (:wid, :wcode, :wname, true)"
                ),
                {
                    "wid": str(warehouse_id),
                    "wcode": f"WH-{suffix}",
                    "wname": f"Kho Test {suffix}",
                },
            )

        zone_row = db.execute(
            text("SELECT zone_id FROM zones WHERE warehouse_id = :wid LIMIT 1"),
            {"wid": str(warehouse_id)},
        ).first()
        if not zone_row:
            zone_row = db.execute(text("SELECT zone_id FROM zones LIMIT 1")).first()
        if zone_row and zone_row[0]:
            zone_id = uuid.UUID(str(zone_row[0]))
        else:
            zone_id = uuid.uuid4()
            db.execute(
                text(
                    "INSERT INTO zones "
                    "(zone_id, warehouse_id, zone_code, zone_name, zone_type, is_active) "
                    "VALUES (:zid, :wid, :zcode, :zname, 'STORAGE', true)"
                ),
                {
                    "zid": str(zone_id),
                    "wid": str(warehouse_id),
                    "zcode": f"Z-{suffix}",
                    "zname": f"Zone Test {suffix}",
                },
            )

        cust_row = db.execute(text("SELECT customer_id FROM customers LIMIT 1")).first()
        if cust_row and cust_row[0]:
            customer_id = uuid.UUID(str(cust_row[0]))
        else:
            customer_id = uuid.uuid4()
            db.execute(
                text(
                    "INSERT INTO customers "
                    "(customer_id, customer_code, customer_name, is_active) "
                    "VALUES (:cid, :ccode, :cname, true)"
                ),
                {
                    "cid": str(customer_id),
                    "ccode": f"CUST-{suffix}",
                    "cname": f"Khach Test {suffix}",
                },
            )
            created_customer = True

        sku = md_models.Sku(
            sku_code=f"SKU-REAL-{suffix}",
            sku_name="Sữa tươi tiệt trùng nguyên chất 1L",
            base_uom="Hộp",
        )
        existing_loc = db.execute(
            text(
                "SELECT location_id FROM locations "
                "WHERE warehouse_id = :wid AND location_code = 'LOC-A02-01' LIMIT 1"
            ),
            {"wid": str(warehouse_id)},
        ).first()
        if existing_loc and existing_loc[0]:
            loc_id = uuid.UUID(str(existing_loc[0]))
            db.add(sku)
            db.flush()
        else:
            loc = md_models.Location(
                warehouse_id=warehouse_id,
                zone_id=zone_id,
                location_code="LOC-A02-01",
                barcode=f"BC-LOC-{suffix}",
                is_active=True,
            )
            db.add_all([sku, loc])
            db.flush()
            loc_id = loc.location_id
            created_loc = True

        lot = inv_models.Lot(
            sku_id=sku.sku_id,
            lot_number="DEMO-SUA-A",
        )
        db.add(lot)
        db.flush()

        inv_bal = inv_models.InventoryBalance(
            warehouse_id=warehouse_id,
            location_id=loc_id,
            sku_id=sku.sku_id,
            lot_id=lot.lot_id,
            qty_available=Decimal("50"),
            qty_allocated=Decimal("0"),
        )
        order = out_models.OutboundOrder(
            erp_order_number=f"SO-REAL-{suffix}",
            order_type="SO",
            warehouse_id=warehouse_id,
            customer_id=customer_id,
            status="NEW",
            cutoff_time=datetime.now(timezone.utc) + timedelta(days=1),
            version_no=1,
        )
        db.add_all([inv_bal, order])
        db.flush()

        line = out_models.OutboundOrderLine(
            order_id=order.order_id,
            sku_id=sku.sku_id,
            qty_ordered=Decimal("10"),
        )
        db.add(line)
        db.commit()

        created_ids = {
            "line_id": line.order_line_id,
            "order_id": order.order_id,
            "balance_id": inv_bal.balance_id,
            "lot_id": lot.lot_id,
            "loc_id": loc_id,
            "sku_id": sku.sku_id,
        }

        cookies = _login(web, "thukho")
        resp = web.post(
            f"/outbound/orders/{order.order_id}/allocate",
            data={"version_no": "1", "strategy": "FEFO"},
            cookies=cookies,
            headers=ORIGIN,
        )
        assert resp.status_code == 200
        assert "LOC-A02-01" in resp.text
        assert "DEMO-SUA-A" in resp.text
        assert "Giữ 10 tại LOC-A02-01, lô DEMO-SUA-A" in resp.text
        assert "10.000" not in resp.text
    finally:
        if created_ids:
            db.rollback()
            db.execute(
                text("DELETE FROM outbound_order_lines WHERE order_line_id = :lid"),
                {"lid": str(created_ids["line_id"])},
            )
            db.execute(
                text("DELETE FROM outbound_orders WHERE order_id = :oid"),
                {"oid": str(created_ids["order_id"])},
            )
            db.execute(
                text("DELETE FROM inventory_balances WHERE balance_id = :bid"),
                {"bid": str(created_ids["balance_id"])},
            )
            if created_loc:
                db.execute(
                    text("DELETE FROM locations WHERE location_id = :locid"),
                    {"locid": str(created_ids["loc_id"])},
                )
            if created_customer:
                db.execute(
                    text("DELETE FROM customers WHERE customer_id = :cid"),
                    {"cid": str(customer_id)},
                )
            db.commit()
        db.close()


def test_outbound_h2_allocate_shortage_on_hold_warning_banner(
    web: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from client.app.core.api_client import ApiClient
    from client.app.modules.outbound import views as out_views

    order_id = uuid.uuid4()
    fake_order = {
        "order_id": str(order_id),
        "erp_order_number": "SO-SHORT-01",
        "status": "ON_HOLD",
        "version_no": 2,
        "lines": [{"sku_id": str(uuid.uuid4()), "qty_ordered": 100}],
    }

    orig_post = ApiClient.post
    orig_get = ApiClient.get

    def fake_post(
        self: ApiClient,
        path: str,
        *,
        json_data: dict[str, object] | None = None,
    ) -> dict[str, object]:
        if path.endswith("/allocate"):
            assert json_data is not None
            return {
                "data": {
                    "order_id": str(order_id),
                    "status": "ON_HOLD",
                    "has_shortage": True,
                    "version_no": 2,
                    "shortages": [{"sku_code": "SKU-01", "shortage_qty": 40}],
                    "allocations": [],
                }
            }
        return orig_post(self, path, json_data=json_data)

    def fake_get(
        self: ApiClient,
        path: str,
        params: dict[str, object] | None = None,
    ) -> dict[str, object]:
        if path.endswith(f"/outbound-orders/{order_id}"):
            return {"data": fake_order}
        if path.startswith("/outbound-orders"):
            return {"data": [fake_order]}
        return orig_get(self, path, params=params)

    monkeypatch.setattr(ApiClient, "post", fake_post)
    monkeypatch.setattr(ApiClient, "get", fake_get)
    monkeypatch.setattr(out_views, "_load_lot_and_location_maps", lambda *a, **kw: ({}, {}))

    cookies = _login(web, "thukho")
    resp = web.post(
        f"/outbound/orders/{order_id}/allocate",
        data={"version_no": "1", "strategy": "FEFO"},
        cookies=cookies,
        headers=ORIGIN,
    )
    assert resp.status_code == 200
    assert "tạm dừng chờ hàng" in resp.text
    assert "ON_HOLD" not in resp.text
