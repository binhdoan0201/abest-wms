"""Integration tests cho module master_data qua API (đối chiếu docs/api/master_data.md).

Mỗi lần chạy dùng mã ngẫu nhiên nên chạy lại nhiều lần trên cùng CSDL không bị trùng.
Kho tạo trong test được xóa khi kết thúc module để test seed (`đúng 1 kho`) vẫn qua
khi chạy lại `make ci` trên cùng CSDL.
"""

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from server.app.core.database import SessionLocal
from server.app.main import app

client = TestClient(app)
_created_warehouses: list[str] = []


@pytest.fixture(scope="module", autouse=True)
def _cleanup_created_warehouses() -> Iterator[None]:
    yield
    if not _created_warehouses:
        return
    db = SessionLocal()
    try:
        db.execute(
            text("DELETE FROM warehouses WHERE warehouse_id = ANY(CAST(:ids AS uuid[]))"),
            {"ids": _created_warehouses},
        )
        db.commit()
    finally:
        db.close()


def _token(username: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": "Demo@123456"})
    assert resp.status_code == 200, resp.text
    return str(resp.json()["data"]["access_token"])


def _h(username: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(username)}"}


@pytest.fixture(scope="module")
def admin() -> dict[str, str]:
    return _h("admin")


@pytest.fixture(scope="module")
def worker() -> dict[str, str]:
    return _h("nv_nhan")


def _code(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:8].upper()}"


def _create(headers: dict[str, str], res: str, body: dict[str, Any]) -> dict[str, Any]:
    resp = client.post(f"/api/v1/{res}", headers=headers, json=body)
    assert resp.status_code == 201, resp.text
    data: dict[str, Any] = resp.json()["data"]
    if res == "warehouses":
        _created_warehouses.append(data["warehouse_id"])
    return data


def _error(resp: Any) -> str:
    return str(resp.json()["error"]["code"])


# ----------------------------------------------------------------------------- quyền


def test_read_any_role_write_admin_only(admin: dict[str, str], worker: dict[str, str]) -> None:
    """Đọc: mọi vai trò; ghi: chỉ AD-1 (admin) -> nhân viên bị 403."""
    resp = client.get("/api/v1/skus", headers=worker)
    assert resp.status_code == 200
    assert resp.json()["meta"]["total"] >= 1

    resp = client.post(
        "/api/v1/skus",
        headers=worker,
        json={"sku_code": _code("SKU"), "sku_name": "X", "base_uom": "PCS"},
    )
    assert resp.status_code == 403
    assert _error(resp) == "FORBIDDEN"

    assert client.get("/api/v1/skus").status_code == 401


# ----------------------------------------------------------------------------- tạo, trùng mã


def test_create_sku_defaults_numeric_as_string_and_duplicate(admin: dict[str, str]) -> None:
    code = _code("SKU")
    sku = _create(
        admin,
        "skus",
        {
            "sku_code": code,
            "sku_name": "Sữa tươi 1L",
            "base_uom": "PCS",
            "unit_cost": "18500",
            "storage_requirement": "COLD",
            "unit_weight_kg": "1.05",
        },
    )
    assert sku["unit_cost"] == "18500.0000"
    assert sku["unit_weight_kg"] == "1.0500"
    assert sku["unit_volume_m3"] is None
    assert sku["is_lot_tracked"] is True
    assert sku["is_expiry_tracked"] is True
    assert sku["is_serial_tracked"] is False
    assert sku["is_active"] is True

    resp = client.patch(
        f"/api/v1/skus/{sku['sku_id']}", headers=admin, json={"unit_volume_m3": "-1"}
    )
    assert resp.status_code == 422

    detail = client.get(f"/api/v1/skus/{sku['sku_id']}", headers=admin)
    assert detail.status_code == 200
    assert detail.json()["data"]["sku_code"] == code

    dup = client.post(
        "/api/v1/skus",
        headers=admin,
        json={"sku_code": code, "sku_name": "Trùng", "base_uom": "PCS"},
    )
    assert dup.status_code == 409
    assert _error(dup) == "MASTER_DATA_DUPLICATE"
    assert dup.json()["error"]["details"]["fields"] == ["sku_code"]


def test_create_rejects_unknown_fields_and_bad_references(admin: dict[str, str]) -> None:
    resp = client.post(
        "/api/v1/zones",
        headers=admin,
        json={
            "zone_code": _code("Z"),
            "zone_name": "Z",
            "zone_type": "STORAGE",
            "warehouse_id": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 422
    assert _error(resp) == "VALIDATION_ERROR"

    resp = client.post(
        "/api/v1/locations",
        headers=admin,
        json={"zone_id": str(uuid.uuid4()), "location_code": _code("L"), "barcode": _code("B")},
    )
    assert resp.status_code == 404

    resp = client.post(
        "/api/v1/sku-barcodes",
        headers=admin,
        json={"sku_id": str(uuid.uuid4()), "barcode": _code("BC"), "uom_code": "PCS"},
    )
    assert resp.status_code == 404

    resp = client.post(
        "/api/v1/box-types",
        headers=admin,
        json={
            "box_code": _code("BOX"),
            "box_name": "Thùng",
            "length_cm": "10",
            "width_cm": "10",
            "height_cm": "10",
            "tare_weight_kg": "5",
            "max_weight_kg": "2",
        },
    )
    assert resp.status_code == 422


# ----------------------------------------------------------------------------- danh sách


def test_list_pagination_filter_search_sort(admin: dict[str, str]) -> None:
    prefix = _code("LST")
    for i in range(3):
        _create(
            admin,
            "suppliers",
            {"erp_supplier_code": f"{prefix}-{i}", "supplier_name": f"NCC {prefix} {i}"},
        )

    resp = client.get(
        "/api/v1/suppliers",
        headers=admin,
        params={"q": prefix.lower(), "page_size": 2, "sort": "-erp_supplier_code"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["total"] == 3
    assert body["meta"]["page_size"] == 2
    assert [s["erp_supplier_code"] for s in body["data"]] == [f"{prefix}-2", f"{prefix}-1"]

    resp = client.get(
        "/api/v1/suppliers", headers=admin, params={"q": prefix, "page": 2, "page_size": 2}
    )
    # Mặc định sắp theo mã tăng dần: trang 1 là -0, -1; trang 2 là -2
    assert [s["erp_supplier_code"] for s in resp.json()["data"]] == [f"{prefix}-2"]

    resp = client.get(
        "/api/v1/suppliers", headers=admin, params={"is_active": "false", "q": prefix}
    )
    assert resp.json()["meta"]["total"] == 0

    for params in ({"phone": "1"}, {"sort": "phone"}, {"page_size": 101}, {"is_active": "abc"}):
        resp = client.get("/api/v1/suppliers", headers=admin, params=params)
        assert resp.status_code == 422, params
        assert _error(resp) == "VALIDATION_ERROR"


# ----------------------------------------------------------------------------- phạm vi kho


def test_zone_location_scoped_to_token_warehouse(admin: dict[str, str]) -> None:
    zone = _create(
        admin, "zones", {"zone_code": _code("Z"), "zone_name": "Khu test", "zone_type": "STORAGE"}
    )
    me = client.get("/api/v1/auth/me", headers=admin).json()["data"]
    assert zone["warehouse_id"] == str(me["warehouse_id"])

    location = _create(
        admin,
        "locations",
        {"zone_id": zone["zone_id"], "location_code": _code("L"), "barcode": _code("BC")},
    )
    assert location["status"] == "EMPTY"

    resp = client.post(
        "/api/v1/locations",
        headers=admin,
        json={
            "zone_id": zone["zone_id"],
            "location_code": _code("L"),
            "barcode": _code("BC"),
            "status": "FULL",
        },
    )
    assert resp.status_code == 422

    resp = client.get("/api/v1/locations", headers=admin, params={"zone_id": zone["zone_id"]})
    assert resp.json()["meta"]["total"] == 1

    # Zone còn vị trí hoạt động -> không ngừng sử dụng được
    resp = client.post(f"/api/v1/zones/{zone['zone_id']}/deactivate", headers=admin)
    assert resp.status_code == 409
    assert _error(resp) == "MASTER_DATA_IN_USE"

    resp = client.post(f"/api/v1/locations/{location['location_id']}/deactivate", headers=admin)
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is False

    resp = client.post(f"/api/v1/locations/{location['location_id']}/deactivate", headers=admin)
    assert resp.status_code == 409
    assert _error(resp) == "INVALID_STATE"

    resp = client.post(f"/api/v1/zones/{zone['zone_id']}/deactivate", headers=admin)
    assert resp.status_code == 200


# ----------------------------------------------------------------------------- sửa


def test_patch_rules(admin: dict[str, str]) -> None:
    customer = _create(
        admin, "customers", {"erp_customer_code": _code("KH"), "customer_name": "Khách A"}
    )
    url = f"/api/v1/customers/{customer['customer_id']}"

    assert client.patch(url, headers=admin, json={}).status_code == 422
    assert client.patch(url, headers=admin, json={"erp_customer_code": "MOI"}).status_code == 422
    assert client.patch(url, headers=admin, json={"customer_name": None}).status_code == 422

    resp = client.patch(url, headers=admin, json={"customer_name": "Khách B", "phone": "0909"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["customer_name"] == "Khách B"
    assert data["phone"] == "0909"

    resp = client.patch(url, headers=admin, json={"phone": None})
    assert resp.status_code == 200
    assert resp.json()["data"]["phone"] is None

    assert client.get("/api/v1/customers/khong-phai-uuid", headers=admin).status_code == 404


def test_reason_code_string_key_and_not_deactivatable_box(admin: dict[str, str]) -> None:
    code = _code("RC_")
    _create(
        admin,
        "reason-codes",
        {"reason_code": code, "reason_category": "DAMAGED", "description": "Hư bao bì"},
    )
    resp = client.patch(
        f"/api/v1/reason-codes/{code}", headers=admin, json={"description": "Hư nặng"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["description"] == "Hư nặng"

    resp = client.get("/api/v1/reason-codes", headers=admin, params={"reason_category": "XYZ"})
    assert resp.status_code == 422

    box = _create(
        admin,
        "box-types",
        {
            "box_code": _code("BOX"),
            "box_name": "Thùng nhỏ",
            "length_cm": "20",
            "width_cm": "15",
            "height_cm": "10",
            "tare_weight_kg": "0.3",
            "max_weight_kg": "5",
        },
    )
    resp = client.patch(
        f"/api/v1/box-types/{box['box_type_id']}", headers=admin, json={"max_weight_kg": "0.1"}
    )
    assert resp.status_code == 422

    resp = client.post(f"/api/v1/box-types/{box['box_type_id']}/deactivate", headers=admin)
    assert resp.status_code == 409
    assert _error(resp) == "MASTER_DATA_NOT_DEACTIVATABLE"


# ----------------------------------------------------------------------------- kho và cấu hình


def test_warehouse_create_with_default_config_and_scope(
    admin: dict[str, str], worker: dict[str, str]
) -> None:
    wh = _create(
        admin, "warehouses", {"erp_warehouse_code": _code("WH"), "warehouse_name": "Kho test"}
    )
    cfg = client.get(f"/api/v1/warehouses/{wh['warehouse_id']}/config", headers=admin)
    assert cfg.status_code == 200
    data = cfg.json()["data"]
    assert data["threshold_x_d1_amount"] == "5000000.00"
    assert data["tolerance_z_mode"] == "BOTH_AND"
    assert data["picking_rule"] == "FEFO"
    assert data["max_open_tasks_per_user"] == 3

    # Nhân viên không thấy kho khác và cấu hình kho khác
    assert client.get(f"/api/v1/warehouses/{wh['warehouse_id']}", headers=worker).status_code == 404
    resp = client.get(f"/api/v1/warehouses/{wh['warehouse_id']}/config", headers=worker)
    assert resp.status_code == 404
    assert client.get("/api/v1/warehouses", headers=worker).json()["meta"]["total"] == 1

    # Admin ngừng sử dụng kho mới (không phải kho đang làm việc, chưa có tồn)
    resp = client.post(f"/api/v1/warehouses/{wh['warehouse_id']}/deactivate", headers=admin)
    assert resp.status_code == 200


def test_cannot_deactivate_own_warehouse(admin: dict[str, str]) -> None:
    own = client.get("/api/v1/warehouses", headers=_h("thukho")).json()["data"][0]
    resp = client.post(f"/api/v1/warehouses/{own['warehouse_id']}/deactivate", headers=admin)
    assert resp.status_code == 409
    assert _error(resp) == "MASTER_DATA_IN_USE"


def test_update_config_threshold_rule_and_permissions(
    admin: dict[str, str], worker: dict[str, str]
) -> None:
    wh = _create(
        admin, "warehouses", {"erp_warehouse_code": _code("WH"), "warehouse_name": "Kho cfg"}
    )
    url = f"/api/v1/warehouses/{wh['warehouse_id']}/config"

    resp = client.patch(url, headers=admin, json={"threshold_x_d1_amount": "30000000"})
    assert resp.status_code == 422
    assert _error(resp) == "MASTER_DATA_INVALID_THRESHOLD"

    resp = client.patch(
        url,
        headers=admin,
        json={
            "threshold_x_d1_amount": "4000000",
            "picking_rule": "FIFO",
            "task_sla_minutes": {"PUTAWAY": 20},
            "approval_sla_hours": {"D1": 2, "D2": 6, "D3": 12},
            "max_open_tasks_per_user": 5,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["threshold_x_d1_amount"] == "4000000.00"
    assert data["picking_rule"] == "FIFO"
    assert data["task_sla_minutes"] == {"PUTAWAY": 20}
    assert data["approval_sla_hours"] == {"D1": 2, "D2": 6, "D3": 12}
    assert data["max_open_tasks_per_user"] == 5
    assert data["updated_by"] is not None

    for body in (
        {},
        {"picking_rule": "LIFO"},
        {"task_sla_minutes": {"KHONG_CO": 5}},
        {"approval_sla_hours": {"D1": 2}},
        {"max_open_tasks_per_user": None},
    ):
        assert client.patch(url, headers=admin, json=body).status_code == 422, body

    assert client.patch(url, headers=worker, json={"picking_rule": "FEFO"}).status_code == 403


def test_users_write_and_roles_not_implemented_yet(admin: dict[str, str]) -> None:
    for method, path in (("get", "/api/v1/roles"), ("post", "/api/v1/users")):
        resp = getattr(client, method)(path, headers=admin)
        assert resp.status_code == 501, path
        assert _error(resp) == "NOT_IMPLEMENTED"


# ----------------------------------------------------------------------------- users (đọc)


def test_list_users_admin_sees_all_fields(admin: dict[str, str]) -> None:
    resp = client.get("/api/v1/users", headers=admin)
    assert resp.status_code == 200
    body = resp.json()
    users = {u["username"]: u for u in body["data"]}
    assert {"admin", "thukho", "nv_soan"} <= set(users)
    assert "email" in users["thukho"]
    assert users["nv_soan"]["role_code"] == "nv-soan"
    assert users["nv_soan"]["is_active"] is True
    assert users["nv_soan"]["can_receive_tasks"] is True

    other = client.get(f"/api/v1/users?warehouse_id={uuid.uuid4()}", headers=admin)
    assert other.status_code == 200 and other.json()["data"] == []


def test_list_users_dispatcher_scoped_without_contact_fields() -> None:
    """thukho, quanly (TK-1.1) xem người trong kho mình để giao task, không thấy email, SĐT."""
    for username in ("thukho", "quanly"):
        resp = client.get("/api/v1/users?role_code=nv-soan", headers=_h(username))
        assert resp.status_code == 200, username
        data = resp.json()["data"]
        assert [u["username"] for u in data] == ["nv_soan"]
        assert not {"email", "phone", "last_login_at"} & set(data[0])

    # thukho gửi warehouse_id kho khác thì vẫn chỉ xem kho của mình.
    scoped = client.get(f"/api/v1/users?warehouse_id={uuid.uuid4()}", headers=_h("thukho"))
    assert scoped.status_code == 200 and scoped.json()["data"]


def test_list_users_forbidden_and_validation(admin: dict[str, str]) -> None:
    for username in ("bgd", "nv_soan", "nv_nhan"):
        assert client.get("/api/v1/users", headers=_h(username)).status_code == 403, username
    for query in ("role_code=xx", "status=DELETED", "page_size=101", "page=0", "warehouse_id=abc"):
        resp = client.get(f"/api/v1/users?{query}", headers=admin)
        assert resp.status_code == 422, query
        assert _error(resp) == "VALIDATION_ERROR"
