"""ABEST WMS - Chuẩn hóa envelope phản hồi API và Middleware Request ID."""

import uuid
from contextvars import ContextVar
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# Context variable lưu trữ request_id cho request hiện tại
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def get_current_request_id() -> str:
    """Lấy request_id của request hiện tại hoặc sinh mới nếu chưa có."""
    req_id = request_id_ctx.get()
    if not req_id:
        req_id = str(uuid.uuid4())
        request_id_ctx.set(req_id)
    return req_id


def success_response(
    data: Any,
    page: int | None = None,
    page_size: int | None = None,
    total: int | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Tạo cấu trúc phản hồi thành công chuẩn theo Mục 2 Chuẩn API.

    Định dạng:
    {"data": ..., "meta": {"request_id": "...", ...}}
    """
    req_id = request_id or get_current_request_id()
    meta: dict[str, Any] = {"request_id": req_id}

    if page is not None:
        meta["page"] = page
    if page_size is not None:
        meta["page_size"] = page_size
    if total is not None:
        meta["total"] = total

    return {"data": data, "meta": meta}


def error_response(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Tạo cấu trúc phản hồi lỗi chuẩn theo Mục 2 Chuẩn API.

    Định dạng:
    {"error": {"code": "MÃ_LỖI", "message": "tiếng Việt", "details": {}}}
    """
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware gắn X-Request-ID vào context và response header."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        header_request_id = request.headers.get("X-Request-ID")
        req_id = header_request_id if header_request_id else str(uuid.uuid4())
        token = request_id_ctx.set(req_id)

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            request_id_ctx.reset(token)
