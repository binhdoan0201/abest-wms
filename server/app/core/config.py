"""Cấu hình ứng dụng ABEST WMS Server từ biến môi trường (.env)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    """Lớp quản lý cấu hình hệ thống."""

    # Môi trường
    ENV: str = "development"
    DEBUG: bool = True

    # CSDL PostgreSQL
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "abest_wms"
    DB_USER: str = "wms_admin"
    DB_PASSWORD: str = "wms_secret_pass"
    DATABASE_URL: str = "postgresql+psycopg://wms_admin:wms_secret_pass@localhost:5432/abest_wms"

    # Bảo mật & JWT
    SECRET_KEY: str = "change-this-in-production-dev-secret-key-32-chars-min"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 8

    # Server API
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    SERVER_API_URL: str = "http://localhost:8000/api/v1"

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Trả về singleton instance của cấu hình ứng dụng."""
    return Settings()
