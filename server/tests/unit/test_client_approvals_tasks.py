"""Test Web Client cho phân hệ Phê duyệt (Approvals) và Nhiệm vụ (Tasks) — Task D-08."""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from client.app.core.api_client import ApiClient
from client.app.main import app as client_app
from server.app.main import app as backend_app

ORIGIN = {"Origin": "http://localhost:3000"}


@pytest.fixture(autouse=True)
def in_memory_backend() -> Generator[None, None, None]:
    original = ApiClient.backend_app
    ApiClient.backend_app = backend_app
    yield
    ApiClient.backend_app = original


@pytest.fixture
def web() -> TestClient:
    return TestClient(client_app, base_url="http://localhost:3000")


def _login(web: TestClient, username: str) -> str:
    resp = web.post(
        "/login",
        data={"username": username, "password": "Demo@123456"},
        headers=ORIGIN,
        follow_redirects=False,
    )
    assert resp.status_code == 303
    return resp.cookies.get("abest_session") or ""


def test_approvals_access_control(web: TestClient) -> None:
    thukho_cookie = _login(web, "thukho")
    resp_tk = web.get("/approvals", cookies={"abest_session": thukho_cookie})
    assert resp_tk.status_code == 200
    assert "Hàng chờ Phê duyệt Chênh lệch" in resp_tk.text

    quanly_cookie = _login(web, "quanly")
    resp_ql = web.get(
        "/approvals?status=PENDING_D2&tier=D2_QUANLY&expired=true",
        cookies={"abest_session": quanly_cookie},
    )
    assert resp_ql.status_code == 200
    assert "Danh sách hồ sơ" in resp_ql.text

    staff_cookie = _login(web, "nv_nhan")
    resp_nv = web.get("/approvals", cookies={"abest_session": staff_cookie})
    assert resp_nv.status_code == 403


def test_approvals_htmx_panel_and_decisions(
    web: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    quanly_cookie = _login(web, "quanly")
    approval_id = str(uuid.uuid4())
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    sample_detail = {
        "approval_id": approval_id,
        "warehouse_id": str(uuid.uuid4()),
        "object_type": "CYCLE_COUNT_DIFF",
        "object_id": str(uuid.uuid4()),
        "proposer_user_id": str(uuid.uuid4()),
        "current_tier": "D1_THUKHO",
        "status": "PENDING_D1",
        "execution_status": "PENDING",
        "discrepancy_value_amount": "1500000.00",
        "sla_due_at": "2026-11-26T10:00:00Z",
        "locked_by_viewer_id": str(uuid.uuid4()),
        "version_no": 2,
        "object_ref": "CC-20261125-ABC123 / LOC-A01-01",
        "source": {
            "doc_type": "CYCLE_COUNT",
            "doc_number": "CC-20261125-ABC123",
            "doc_status": "PENDING_APPROVAL",
            "recount_count": 0,
            "parent_doc_number": None,
            "proposer_name": "Nguyễn Kiểm Kê (nv_kiemke)",
            "lines": [
                {
                    "sku_code": "SKU-ELEC-003",
                    "sku_name": "Bàn ủi hơi nước",
                    "uom_code": "PCS",
                    "lot_number": None,
                    "location_code": "LOC-A01-01",
                    "qty_expected": "40.000",
                    "qty_counted": "37.000",
                    "qty_damaged": None,
                    "qty_variance": "-3.000",
                    "variance_amount": "-1500000.00",
                    "reason_code": None,
                    "reason_description": None,
                }
            ],
        },
        "histories": [
            {
                "tier": "D1_THUKHO",
                "action": "SUBMITTED",
                "recommendation_or_reason": "Chênh lệch kiểm kê kệ A1",
                "created_at": "2026-11-25T08:00:00Z",
            }
        ],
    }

    orig_get = ApiClient.get

    def fake_get(
        self: ApiClient, path: str, params: dict[str, object] | None = None
    ) -> dict[str, object]:
        if path.startswith("/auth"):
            return orig_get(self, path, params=params)
        calls.append(("GET", path, params))
        return {"data": sample_detail}

    def fake_post(
        self: ApiClient, path: str, json_data: dict[str, object] | None = None
    ) -> dict[str, object]:
        calls.append(("POST", path, json_data))
        return {"data": sample_detail}

    monkeypatch.setattr(ApiClient, "get", fake_get)
    monkeypatch.setattr(ApiClient, "post", fake_post)

    panel = web.get(
        f"/approvals/{approval_id}/panel?lock=true",
        headers={"HX-Request": "true"},
        cookies={"abest_session": quanly_cookie},
    )
    assert panel.status_code == 200
    assert "Chênh lệch kiểm kê" in panel.text
    assert "Mở khóa xem" in panel.text
    # Bảng lệch của chứng từ nguồn: số phiếu, người đề xuất, sổ sách 40 / đếm 37 / lệch -3
    assert "CC-20261125-ABC123 / LOC-A01-01" in panel.text
    assert "Nguyễn Kiểm Kê (nv_kiemke)" in panel.text
    for text_value in ("Sổ sách", ">40<", ">37<", "-3", "Vị trí LOC-A01-01"):
        assert text_value in panel.text, text_value
    assert "26/11/2026 17:00" in panel.text, "SLA theo giờ Việt Nam"
    # Hồ sơ lệch kiểm kê: nút đếm lại gửi thẳng request_recount, không còn ô tick dễ quên
    assert 'value="request_recount"' in panel.text
    assert 'name="request_recount"' not in panel.text
    assert "1.500.000 ₫" in panel.text

    # Đang NEED_INFO: chỉ còn Từ chối, không còn nút duyệt/đếm lại bấm nhầm
    sample_detail["status"] = "NEED_INFO"
    waiting = web.get(
        f"/approvals/{approval_id}/panel?lock=true",
        headers={"HX-Request": "true"},
        cookies={"abest_session": quanly_cookie},
    )
    assert "Đang chờ nhân viên khác đếm lại" in waiting.text
    assert 'value="reject"' in waiting.text
    assert 'value="approve"' not in waiting.text
    assert 'value="request_recount"' not in waiting.text
    sample_detail["status"] = "PENDING_D1"

    unlock = web.post(
        f"/approvals/{approval_id}/unlock",
        headers={"HX-Request": "true", **ORIGIN},
        cookies={"abest_session": quanly_cookie},
    )
    assert unlock.status_code == 200
    assert "Đã giải phóng khóa xem hồ sơ." in unlock.text

    approve = web.post(
        f"/approvals/{approval_id}/decide",
        data={
            "action": "approve",
            "version_no": "2",
            "reason_or_note": "Đã đối chiếu biên bản",
            "reauth_method": "PASSWORD",
            "reauth_password": "Demo@123456",
        },
        headers={"HX-Request": "true", **ORIGIN},
        cookies={"abest_session": quanly_cookie},
    )
    assert approve.status_code == 200
    assert "Đã phê duyệt hồ sơ thành công." in approve.text

    reject = web.post(
        f"/approvals/{approval_id}/decide",
        data={
            "action": "reject",
            "version_no": "2",
            "reason_or_note": "Chứng từ chưa hợp lệ",
        },
        headers={"HX-Request": "true", **ORIGIN},
        cookies={"abest_session": quanly_cookie},
    )
    assert reject.status_code == 200
    assert "Đã từ chối hồ sơ phê duyệt." in reject.text

    recount = web.post(
        f"/approvals/{approval_id}/decide",
        data={
            "action": "request_recount",
            "version_no": "2",
            "reason_or_note": "Đếm lại lô hàng B2",
        },
        headers={"HX-Request": "true", **ORIGIN},
        cookies={"abest_session": quanly_cookie},
    )
    assert recount.status_code == 200
    assert "Đã gửi yêu cầu đếm lại." in recount.text
    recount_payload = next(
        c[2] for c in reversed(calls) if c[1] == f"/approvals/{approval_id}/request-info"
    )
    assert recount_payload is not None and recount_payload["request_recount"] is True

    escalate = web.post(
        f"/approvals/{approval_id}/decide",
        data={
            "action": "escalate",
            "version_no": "2",
            "reason_or_note": "Vượt hạn mức Thủ kho",
        },
        headers={"HX-Request": "true", **ORIGIN},
        cookies={"abest_session": quanly_cookie},
    )
    assert escalate.status_code == 200
    assert "Đã chuyển hồ sơ lên cấp phê duyệt cao hơn." in escalate.text

    posted_paths = [c[1] for c in calls if c[0] == "POST"]
    assert f"/approvals/{approval_id}/unlock" in posted_paths
    assert f"/approvals/{approval_id}/approve" in posted_paths
    assert f"/approvals/{approval_id}/reject" in posted_paths
    assert f"/approvals/{approval_id}/request-info" in posted_paths
    assert f"/approvals/{approval_id}/escalate" in posted_paths


def test_tasks_access_and_supervisor_dispatch_htmx(
    web: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    thukho_cookie = _login(web, "thukho")
    resp_page = web.get("/tasks", cookies={"abest_session": thukho_cookie})
    assert resp_page.status_code == 200
    assert "Điều phối &amp; Quản lý Nhiệm vụ Kho" in resp_page.text
    assert "Phân công tự động hàng đợi" in resp_page.text
    assert "Tạo nhiệm vụ thủ công" not in resp_page.text

    bgd_cookie = _login(web, "bgd")
    resp_bgd = web.get("/tasks", cookies={"abest_session": bgd_cookie})
    assert resp_bgd.status_code == 403

    task_id = str(uuid.uuid4())
    worker_id = str(uuid.uuid4())
    ref_id = str(uuid.uuid4())
    posted: list[tuple[str, dict[str, object] | None]] = []
    orig_get = ApiClient.get

    def fake_get(
        self: ApiClient, path: str, params: dict[str, object] | None = None
    ) -> dict[str, object]:
        if path.startswith("/auth"):
            return orig_get(self, path, params=params)
        if path == "/users":
            return {
                "data": [
                    {
                        "user_id": worker_id,
                        "username": "nv_soan",
                        "role_code": "nv-soan",
                        "is_active": True,
                    }
                ]
            }
        return {
            "data": [
                {
                    "task_id": task_id,
                    "task_type": "PICKING",
                    "stage": "SOAN_HANG",
                    "ref_doc_type": "SO",
                    "ref_doc_id": ref_id,
                    "priority": "URGENT",
                    "status": "UNASSIGNED",
                    "assigned_to": None,
                    "version_no": 1,
                }
            ]
        }

    def fake_post(
        self: ApiClient, path: str, json_data: dict[str, object] | None = None
    ) -> dict[str, object]:
        posted.append((path, json_data))
        return {"data": {"task_id": task_id}}

    monkeypatch.setattr(ApiClient, "get", fake_get)
    monkeypatch.setattr(ApiClient, "post", fake_post)

    created = web.post(
        "/tasks/create",
        data={
            "task_type": "PICKING",
            "stage": "SOAN_HANG",
            "ref_doc_type": "SO",
            "ref_doc_id": ref_id,
            "priority": "URGENT",
        },
        headers={"HX-Request": "true", **ORIGIN},
        cookies={"abest_session": thukho_cookie},
    )
    assert created.status_code == 200
    assert "Đã tạo nhiệm vụ mới" in created.text

    assigned = web.post(
        f"/tasks/{task_id}/dispatch",
        data={"action": "assign", "version_no": "1", "worker_user_id": worker_id},
        headers={"HX-Request": "true", **ORIGIN},
        cookies={"abest_session": thukho_cookie},
    )
    assert assigned.status_code == 200
    assert "Đã giao nhiệm vụ cho nhân viên." in assigned.text

    reassigned = web.post(
        f"/tasks/{task_id}/dispatch",
        data={
            "action": "reassign",
            "version_no": "2",
            "worker_user_id": worker_id,
            "note_or_reason": "Tăng cường ca chiều",
        },
        headers={"HX-Request": "true", **ORIGIN},
        cookies={"abest_session": thukho_cookie},
    )
    assert reassigned.status_code == 200
    assert "Đã điều chuyển nhiệm vụ sang nhân viên khác." in reassigned.text

    cancelled = web.post(
        f"/tasks/{task_id}/dispatch",
        data={
            "action": "cancel",
            "version_no": "3",
            "note_or_reason": "Đơn hàng tạm hoãn",
        },
        headers={"HX-Request": "true", **ORIGIN},
        cookies={"abest_session": thukho_cookie},
    )
    assert cancelled.status_code == 200
    assert "Đã hủy nhiệm vụ." in cancelled.text

    prio_res = web.post(
        f"/tasks/{task_id}/dispatch",
        data={"action": "priority", "version_no": "4", "priority": "URGENT"},
        headers={"HX-Request": "true", **ORIGIN},
        cookies={"abest_session": thukho_cookie},
    )
    assert prio_res.status_code == 200
    assert "URGENT" in prio_res.text

    auto_res = web.post(
        "/tasks/auto-assign",
        data={"stage": "SOAN_HANG"},
        headers={"HX-Request": "true", **ORIGIN},
        cookies={"abest_session": thukho_cookie},
    )
    assert auto_res.status_code == 200

    assert [p[0] for p in posted] == [
        "/tasks",
        f"/tasks/{task_id}/assign",
        f"/tasks/{task_id}/reassign",
        f"/tasks/{task_id}/cancel",
        f"/tasks/{task_id}/priority",
        "/tasks/auto-assign",
    ]


def test_resolve_task_open_url_and_worker_no_uuid(
    web: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from client.app.modules.tasks.views import _resolve_task_open_url

    doc_id = str(uuid.uuid4())
    assert (
        _resolve_task_open_url(
            {"task_type": "PUTAWAY", "ref_doc_type": "GRN", "ref_doc_id": doc_id}
        )
        == f"/inbound?grn_id={doc_id}"
    )
    assert (
        _resolve_task_open_url(
            {"task_type": "PUTAWAY", "ref_doc_type": "PALLET", "ref_doc_id": doc_id}
        )
        == f"/inbound?pallet_id={doc_id}"
    )
    assert (
        _resolve_task_open_url(
            {"task_type": "PICKING", "ref_doc_type": "PICK_SESSION", "ref_doc_id": doc_id}
        )
        == f"/outbound?session_id={doc_id}"
    )
    assert (
        _resolve_task_open_url({"task_type": "PACKING", "ref_doc_type": "SO", "ref_doc_id": doc_id})
        == "/outbound/packing"
    )
    assert (
        _resolve_task_open_url(
            {"task_type": "CYCLE_COUNT", "ref_doc_type": "CYCLE_COUNT", "ref_doc_id": doc_id}
        )
        == f"/cycle-count?sheet_id={doc_id}"
    )

    nv_cookie = _login(web, "nv_cat")
    worker_uuid = "c0000000-0000-0000-0000-000000000004"
    orig_get = ApiClient.get

    def fake_get(
        self: ApiClient, path: str, params: dict[str, object] | None = None
    ) -> dict[str, object]:
        if path.startswith("/auth"):
            res = orig_get(self, path, params=params)
            if isinstance(res.get("data"), dict):
                res["data"]["user_id"] = worker_uuid
            return res
        return {
            "data": [
                {
                    "task_id": str(uuid.uuid4()),
                    "task_type": "PUTAWAY",
                    "stage": "CAT_HANG",
                    "ref_doc_type": "GRN",
                    "ref_doc_id": doc_id,
                    "priority": "HIGH",
                    "status": "ASSIGNED",
                    "assigned_to": worker_uuid,
                    "version_no": 1,
                }
            ]
        }

    monkeypatch.setattr(ApiClient, "get", fake_get)
    resp = web.get("/tasks", cookies={"abest_session": nv_cookie})
    assert resp.status_code == 200
    assert worker_uuid not in resp.text
    assert f"/inbound?grn_id={doc_id}" in resp.text
