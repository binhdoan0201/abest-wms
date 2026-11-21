"""ABEST WMS - Hạ tầng Bảo mật, Mật khẩu Bcrypt và JSON Web Token (JWT)."""

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from server.app.core.config import get_settings
from server.app.core.exceptions import BusinessError

settings = get_settings()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Xác thực mật khẩu người dùng với hash bcrypt."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def hash_password(password: str) -> str:
    """Băm mật khẩu bằng thuật toán bcrypt với salt chuẩn."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Sinh JWT token HS256 có thời hạn (mặc định 8 giờ)."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Giải mã và xác thực chữ ký JWT.

    Ném BusinessError nếu token hết hạn hoặc không hợp lệ.
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError as e:
        raise BusinessError(
            code="AUTH_TOKEN_EXPIRED",
            message="Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại",
            http_status=401,
        ) from e
    except jwt.PyJWTError as e:
        raise BusinessError(
            code="AUTH_INVALID_TOKEN",
            message="Token xác thực không hợp lệ",
            http_status=401,
        ) from e
