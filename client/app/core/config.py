"""Cấu hình ứng dụng ABEST WMS Client từ biến môi trường (.env)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent


class ClientSettings(BaseSettings):
    """Lớp quản lý cấu hình hệ thống phía Web Client."""

    ENV: str = "development"
    DEBUG: bool = True

    # Backend API Server
    SERVER_API_URL: str = "http://localhost:8000/api/v1"

    # Client Web Server
    CLIENT_HOST: str = "0.0.0.0"
    CLIENT_PORT: int = 3000
    ALLOWED_HOSTS: list[str] = [
        "localhost",
        "127.0.0.1",
        "localhost:3000",
        "127.0.0.1:3000",
        "localhost:8000",
        "127.0.0.1:8000",
        "testserver",
    ]

    # Quản trị phiên đăng nhập qua Cookie
    SESSION_COOKIE_NAME: str = "abest_session"
    SESSION_COOKIE_SECURE: bool = False  # Bật True khi chạy môi trường production HTTPS
    SESSION_COOKIE_SAMESITE: str = "lax"
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_MAX_AGE_SECONDS: int = 8 * 3600  # 8 giờ theo đúng thời hạn 1 ca làm việc

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_client_settings() -> ClientSettings:
    """Trả về singleton instance cấu hình Web Client."""
    return ClientSettings()
