"""ABEST WMS - Server Application Main Entry Point."""

from fastapi import FastAPI

app = FastAPI(
    title="ABEST WMS Server API",
    version="0.1.0",
    description="Hệ thống quản lý kho ABEST WMS - Server API",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Kiểm tra trạng thái server."""
    return {"status": "ok", "service": "abest-wms-server"}
