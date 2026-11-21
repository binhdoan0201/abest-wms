"""Quản lý phiên đăng nhập và Cookie HttpOnly cho Web Client."""

from fastapi import Request, Response

from client.app.core.config import get_client_settings

settings = get_client_settings()


def set_session_cookie(response: Response, token: str) -> None:
    """Thiết lập cookie phiên an toàn HttpOnly, SameSite=Lax chứa token JWT."""
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.SESSION_MAX_AGE_SECONDS,
        httponly=settings.SESSION_COOKIE_HTTPONLY,
        samesite=settings.SESSION_COOKIE_SAMESITE,  # type: ignore[arg-type]
        secure=settings.SESSION_COOKIE_SECURE,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    """Xóa cookie phiên khi đăng xuất."""
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        httponly=settings.SESSION_COOKIE_HTTPONLY,
        samesite=settings.SESSION_COOKIE_SAMESITE,  # type: ignore[arg-type]
        secure=settings.SESSION_COOKIE_SECURE,
    )


def get_session_token(request: Request) -> str | None:
    """Trích xuất token JWT từ cookie phiên của request."""
    return request.cookies.get(settings.SESSION_COOKIE_NAME)
