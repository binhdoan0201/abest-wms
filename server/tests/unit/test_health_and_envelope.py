"""ABEST WMS - Kiểm thử Unit: Endpoint /health và chuẩn hóa Envelope phản hồi API."""

from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel

from server.app.core.exceptions import BusinessError
from server.app.core.responses import success_response
from server.app.main import app

client = TestClient(app)
client_no_raise = TestClient(app, raise_server_exceptions=False)

# Tạo một dummy router cho test phản hồi
dummy_router = APIRouter(prefix="/test-envelope")


class DummyPayload(BaseModel):
    name: str
    amount: int


@dummy_router.get("/success-item")
def dummy_success_item() -> dict:
    return success_response(data={"item_id": "123", "name": "Test Item"})


@dummy_router.get("/success-list")
def dummy_success_list() -> dict:
    return success_response(
        data=[{"id": 1}, {"id": 2}],
        page=1,
        page_size=20,
        total=2,
    )


@dummy_router.get("/business-error")
def dummy_business_error() -> None:
    raise BusinessError(
        code="TEST_BUSINESS_ERROR",
        message="Lỗi nghiệp vụ thử nghiệm",
        http_status=400,
        details={"reason": "test"},
    )


@dummy_router.post("/validation-test")
def dummy_validation_test(payload: DummyPayload) -> dict:
    return success_response(data={"received": payload.name})


@dummy_router.get("/unhandled-error")
def dummy_unhandled_error() -> None:
    raise RuntimeError("Lỗi bất ngờ không được xử lý")


app.include_router(dummy_router)


def test_health_endpoint_root() -> None:
    """Kiểm tra GET /health trả về 200, DB connected và đúng envelope."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert "data" in data
    assert "meta" in data
    assert data["data"]["status"] == "ok"
    assert data["data"]["database"] == "connected"
    assert "request_id" in data["meta"]
    assert len(data["meta"]["request_id"]) > 0
    assert response.headers.get("X-Request-ID") == data["meta"]["request_id"]


def test_health_endpoint_api_v1() -> None:
    """Kiểm tra GET /api/v1/health cũng trả về 200 và cấu trúc đồng nhất."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.json()
    assert data["data"]["status"] == "ok"
    assert data["data"]["database"] == "connected"
    assert "request_id" in data["meta"]


def test_request_id_custom_header_propagation() -> None:
    """Kiểm tra header X-Request-ID tùy biến được giữ nguyên trong meta và header phản hồi."""
    custom_req_id = "custom-req-id-12345"
    response = client.get("/health", headers={"X-Request-ID": custom_req_id})

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_req_id
    assert response.json()["meta"]["request_id"] == custom_req_id


def test_success_response_envelope_single() -> None:
    """Kiểm tra phản hồi đơn tuân thủ cấu trúc envelope Mục 2 Chuẩn API."""
    response = client.get("/test-envelope/success-item")
    assert response.status_code == 200

    body = response.json()
    assert "data" in body
    assert "meta" in body
    assert body["data"]["item_id"] == "123"
    assert "request_id" in body["meta"]


def test_success_response_envelope_list() -> None:
    """Kiểm tra phản hồi danh sách có thêm meta.page, meta.page_size, meta.total."""
    response = client.get("/test-envelope/success-list")
    assert response.status_code == 200

    body = response.json()
    assert len(body["data"]) == 2
    assert body["meta"]["page"] == 1
    assert body["meta"]["page_size"] == 20
    assert body["meta"]["total"] == 2
    assert "request_id" in body["meta"]


def test_business_error_response() -> None:
    """Kiểm tra phản hồi BusinessError trả đúng HTTP status và cấu trúc error envelope."""
    response = client.get("/test-envelope/business-error")
    assert response.status_code == 400

    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "TEST_BUSINESS_ERROR"
    assert body["error"]["message"] == "Lỗi nghiệp vụ thử nghiệm"
    assert body["error"]["details"] == {"reason": "test"}


def test_validation_error_response() -> None:
    """Kiểm tra phản hồi lỗi Pydantic trả về 422 VALIDATION_ERROR theo Mục 3 Chuẩn API."""
    response = client.post("/test-envelope/validation-test", json={"amount": "invalid_number"})
    assert response.status_code == 422

    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "message" in body["error"]
    assert "details" in body["error"]
    assert "errors" in body["error"]["details"]


def test_unhandled_exception_response() -> None:
    """Kiểm tra ngoại lệ chưa biết trả về 500 INTERNAL_SERVER_ERROR không để lộ chi tiết nội bộ."""
    response = client_no_raise.get("/test-envelope/unhandled-error")
    assert response.status_code == 500

    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert body["error"]["details"] == {}
    assert "Lỗi bất ngờ không được xử lý" not in str(body)
