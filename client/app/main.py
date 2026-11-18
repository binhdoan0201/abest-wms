"""ABEST WMS - Client Application Main Entry Point."""

from fastapi import FastAPI

app = FastAPI(
    title="ABEST WMS Client Web",
    version="0.1.0",
    description="Ứng dụng giao diện web cho ABEST WMS",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Kiểm tra trạng thái client web."""
    return {"status": "ok", "service": "abest-wms-client"}
