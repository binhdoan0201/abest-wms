"""Integration tests cho module dashboard qua HTTP."""

import uuid

import pytest
from fastapi.testclient import TestClient

from server.app.main import app

client = TestClient(app)
ENDPOINTS = ("tasks", "inventory", "orders")


def _headers(username: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": "Demo@123456"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}


def test_dashboard_rbac_protection() -> None:
    """Chỉ thukho, quanly, bgd (QL-8.1) xem được; admin và nhân viên bị chặn."""
    assert client.get("/api/v1/dashboard/tasks").status_code == 401
    for username in ("nv_nhan", "admin"):
        headers = _headers(username)
        for ep in ENDPOINTS:
            resp = client.get(f"/api/v1/dashboard/{ep}", headers=headers)
            assert resp.status_code == 403, (username, ep)


@pytest.mark.parametrize("username", ["thukho", "quanly", "bgd"])
def test_dashboard_returns_envelope_and_alerts(username: str) -> None:
    headers = _headers(username)
    for ep in ENDPOINTS:
        resp = client.get(f"/api/v1/dashboard/{ep}", headers=headers)
        assert resp.status_code == 200, (username, ep, resp.text)
        data = resp.json()["data"]
        assert isinstance(data["alerts"], list)
        assert data["scope"]["business_date"]


def test_dashboard_inventory_quantities_are_strings_and_param_validated() -> None:
    headers = _headers("bgd")
    data = client.get("/api/v1/dashboard/inventory", headers=headers).json()["data"]
    assert isinstance(data["quantities"]["available"], str)
    assert data["near_expiry_days"] == 30

    resp = client.get("/api/v1/dashboard/inventory?near_expiry_days=0", headers=headers)
    assert resp.status_code == 422


def test_dashboard_other_warehouse_returns_404() -> None:
    headers = _headers("quanly")
    resp = client.get(f"/api/v1/dashboard/orders?warehouse_id={uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"
