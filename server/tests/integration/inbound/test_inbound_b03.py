"""Integration tests B-03: ba endpoint đọc PO, ASN yêu cầu đăng nhập."""

import pytest
from fastapi.testclient import TestClient

from server.app.main import app

client = TestClient(app)


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/purchase-orders",
        "/api/v1/purchase-orders/00000000-0000-0000-0000-000000000001",
        "/api/v1/asns",
    ],
)
def test_po_asn_read_requires_login(path: str) -> None:
    resp = client.get(path)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_REQUIRED"
