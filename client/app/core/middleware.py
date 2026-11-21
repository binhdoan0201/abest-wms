"""Middleware an ninh và chống CSRF bản gọn cho Web Client."""

from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from client.app.core.config import get_client_settings

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
