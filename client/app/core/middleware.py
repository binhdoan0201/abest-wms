"""Middleware an ninh và chống CSRF bản gọn cho Web Client."""

from urllib.parse import urlparse

from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from client.app.core.api_client import ApiClient, ClientApiError
from client.app.core.config import get_client_settings
from client.app.core.session import get_session_token, set_session_cookie, token_seconds_left

settings = get_client_settings()


class CompactCsrfMiddleware(BaseHTTPMiddleware):
    """Middleware chống CSRF bản gọn theo Mục 8 Chuẩn công nghệ & API:

    1. Chặn POST, PUT, PATCH, DELETE có Origin hoặc Referer không trùng host client.
    2. Request HTMX phải có header HX-Request: true.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            host = request.headers.get("host", "").split(":")[0]
            allowed_hosts = {h.split(":")[0] for h in settings.ALLOWED_HOSTS}
            if host:
                allowed_hosts.add(host)

            # 1. Kiểm tra Origin và Referer
            origin = request.headers.get("origin")
            referer = request.headers.get("referer")

            if origin:
                origin_host = urlparse(origin).netloc.split(":")[0]
                if origin_host and origin_host not in allowed_hosts:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": {
                                "code": "CSRF_ORIGIN_MISMATCH",
                                "message": f"Truy cập bị từ chối: Origin không hợp lệ ({origin})",
                            }
                        },
                    )
            elif referer:
                referer_host = urlparse(referer).netloc.split(":")[0]
                if referer_host and referer_host not in allowed_hosts:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": {
                                "code": "CSRF_REFERER_MISMATCH",
                                "message": f"Truy cập bị từ chối: Referer không hợp lệ ({referer})",
                            }
                        },
                    )

            # 2. Kiểm tra header của request HTMX
            # Một request được xác định là HTMX nếu có bất kỳ header hx-* hoặc gọi vào endpoint HTMX
            is_htmx_call = (
                any(k.lower().startswith("hx-") for k in request.headers.keys())
                or request.url.path.startswith("/hx/")
                or "/refresh" in request.url.path
            )

            if is_htmx_call:
                hx_req = request.headers.get("hx-request")
                if hx_req != "true":
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": {
                                "code": "HTMX_HEADER_MISSING",
                                "message": "Yêu cầu HTMX thiếu hoặc sai header HX-Request: true",
                            }
                        },
                    )

        return await call_next(request)


def _refresh_token(token: str) -> str | None:
    try:
        data = ApiClient(token=token).post("/auth/refresh").get("data") or {}
    except ClientApiError:
        return None
    new_token = data.get("access_token")
    return str(new_token) if new_token else None


class SessionRefreshMiddleware(BaseHTTPMiddleware):
    """Tự làm mới phiên (A-03): token còn dưới `SESSION_REFRESH_BEFORE_SECONDS` thì đổi token
    mới qua `POST /auth/refresh` và ghi cookie mới vào phản hồi.

    Token đã hết hạn thì không làm mới (người dùng bị chuyển về trang đăng nhập như cũ).
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        if request.url.path.startswith(("/static", "/login", "/logout", "/health")):
            return response
        token = get_session_token(request)
        if not token:
            return response
        seconds_left = token_seconds_left(token)
        if seconds_left is None or not 0 < seconds_left < settings.SESSION_REFRESH_BEFORE_SECONDS:
            return response
        new_token = await run_in_threadpool(_refresh_token, token)
        if new_token:
            set_session_cookie(response, new_token)
        return response
