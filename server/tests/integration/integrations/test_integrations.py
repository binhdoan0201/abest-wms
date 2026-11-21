"""Integration tests cho module integrations."""

from fastapi.testclient import TestClient

from server.app.main import app

client = TestClient(app)


def test_integrations_rbac_protection() -> None:
    """Xác nhận các route ERP mock chỉ cho phép admin truy cập."""
    resp = client.post("/api/v1/integrations/erp/purchase-orders", json={})
    assert resp.status_code == 401

    # Đăng nhập bằng nv_nhan (không có quyền AD-1)
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "nv_nhan", "password": "Demo@123456"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["data"]["access_token"]

    resp = client.post(
        "/api/v1/integrations/erp/purchase-orders",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "po_number": "PO-TEST-001",
            "warehouse_id": "00000000-0000-0000-0000-000000000001",
            "supplier_id": "00000000-0000-0000-0000-000000000001",
            "expected_delivery_date": "2026-12-01T08:00:00Z",
            "lines": [],
        },
    )
    assert resp.status_code == 403
