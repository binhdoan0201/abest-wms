"""ABEST WMS - Client Application Main Entry Point."""

from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from client.app.core.api_client import ClientApiError
from client.app.core.auth_guard import NeedAuthException, get_optional_user, home_path
from client.app.core.config import get_client_settings
from client.app.core.middleware import CompactCsrfMiddleware
from client.app.modules.approvals import router as approvals_router
from client.app.modules.auth import router as auth_router
from client.app.modules.cycle_count import router as cycle_count_router
from client.app.modules.dashboard import router as dashboard_router
from client.app.modules.inbound import router as inbound_router
from client.app.modules.integrations import router as integrations_router
from client.app.modules.inventory import router as inventory_router
from client.app.modules.master_data import router as master_data_router
from client.app.modules.outbound import router as outbound_router
from client.app.modules.tasks import router as tasks_router

settings = get_client_settings()

APP_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"


def create_client_app() -> FastAPI:
    """Khởi tạo và cấu hình FastAPI Web Client."""
    app = FastAPI(
        title="ABEST WMS Client Web",
        version="0.1.0",
        description="Ứng dụng giao diện web cho ABEST WMS",
    )

    # 1. Cấu hình Jinja2 Templates & Static Files
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.state.templates = templates

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # 2. Đăng ký Middleware An ninh & CSRF bản gọn
    app.add_middleware(CompactCsrfMiddleware)

    # 3. Đăng ký Exception Handlers
    @app.exception_handler(NeedAuthException)
    def handle_need_auth(request: Request, exc: NeedAuthException) -> Response:
        """Chưa đăng nhập thì chuyển hướng 303 sang /login."""
        return RedirectResponse(url="/login", status_code=303)

    @app.exception_handler(ClientApiError)
    def handle_client_api_error(request: Request, exc: ClientApiError) -> Response:
        """Bắt lỗi từ Backend và render trang thông báo thân thiện."""
        tmpl: Jinja2Templates = request.app.state.templates
        if exc.http_status == 403:
            resp_403: Response = tmpl.TemplateResponse(
                request=request,
                name="_base/403.html",
                context={
                    "request": request,
                    "error_msg": exc.message,
                    "error_code": exc.code,
                },
                status_code=403,
            )
            return resp_403
        resp_err: Response = tmpl.TemplateResponse(
            request=request,
            name="_base/error.html",
            context={
                "request": request,
                "error_msg": exc.message,
                "error_code": exc.code,
            },
            status_code=exc.http_status if exc.http_status < 500 else 500,
        )
        return resp_err

    # 4. Đăng ký Routers của các Module
    app.include_router(auth_router)
    app.include_router(inventory_router)
    app.include_router(tasks_router)
    app.include_router(master_data_router)
    app.include_router(inbound_router)
    app.include_router(outbound_router)
    app.include_router(cycle_count_router)
    app.include_router(dashboard_router)
    app.include_router(approvals_router)
    app.include_router(integrations_router)

    # 5. Các tuyến điều hướng chung
    @app.get("/", response_class=HTMLResponse)
    def root_page(request: Request) -> Response:
        """Trang gốc: đã đăng nhập thì vào trang đầu theo vai trò, chưa thì sang /login."""
        user = get_optional_user(request)
        if not user:
            return RedirectResponse(url="/login", status_code=303)
        return RedirectResponse(url=home_path(user), status_code=303)

    @app.get("/health")
    def health_check() -> dict[str, str]:
        """Kiểm tra sức khỏe dịch vụ web client."""
        return {"status": "ok", "service": "abest-wms-client"}

    return app


app = create_client_app()
