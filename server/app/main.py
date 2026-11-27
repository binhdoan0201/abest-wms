"""ABEST WMS - Server Application Main Entry Point."""

import importlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from server.app.core.config import get_settings
from server.app.core.database import get_db
from server.app.core.exceptions import BusinessError, register_exception_handlers
from server.app.core.logging import setup_logging
from server.app.core.responses import RequestIdMiddleware, success_response

logger = logging.getLogger("server.main")
settings = get_settings()


def auto_discover_module_routers(api_router: APIRouter) -> None:
    """Tự động phát hiện và nạp router của mọi module trong app/modules/*/routers.py."""
    modules_dir = Path(__file__).resolve().parent / "modules"
    if not modules_dir.exists() or not modules_dir.is_dir():
        return

    for mod_path in sorted(modules_dir.iterdir()):
        if mod_path.is_dir() and (mod_path / "routers.py").exists():
            mod_name = mod_path.name
            try:
                module = importlib.import_module(f"server.app.modules.{mod_name}.routers")
                router = getattr(module, "router", None)
                if isinstance(router, APIRouter):
                    api_router.include_router(router)
                    logger.info("Đã nạp router cho module: %s", mod_name)
            except Exception as e:
                logger.warning("Không thể nạp router module %s: %s", mod_name, e)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201
    """Quản lý vòng đời khởi chạy và tắt của FastAPI server."""
    setup_logging(level="DEBUG" if settings.DEBUG else "INFO")
    logger.info("Khởi động ABEST WMS Server (Env: %s)", settings.ENV)
    yield
    logger.info("Dừng ABEST WMS Server")


def create_app() -> FastAPI:
    """Khởi tạo và cấu hình FastAPI application."""
    app = FastAPI(
        title="ABEST WMS Server API",
        version="0.1.0",
        description="Hệ thống quản lý kho ABEST WMS - Server API",
        lifespan=lifespan,
    )

    # Middleware
    app.add_middleware(RequestIdMiddleware)

    # Exception Handlers
    register_exception_handlers(app)

    # Health check handler
    def health_handler(db: Session = Depends(get_db)) -> dict[str, Any]:
        try:
            db.execute(text("SELECT 1"))
            return success_response(data={"status": "ok", "database": "connected"})
        except Exception as e:
            logger.error("Health check thất bại khi kết nối CSDL: %s", e)
            raise BusinessError(
                code="DATABASE_ERROR",
                message="Không thể kết nối cơ sở dữ liệu",
                http_status=503,
            ) from e

    # Endpoint /health tại root
    app.add_api_route("/health", health_handler, methods=["GET"], tags=["System"])

    # Router với tiền tố /api/v1
    api_v1_router = APIRouter(prefix="/api/v1")
    api_v1_router.add_api_route("/health", health_handler, methods=["GET"], tags=["System"])

    # Tự động nạp routers của các modules
    auto_discover_module_routers(api_v1_router)

    app.include_router(api_v1_router)

    return app


app = create_app()
