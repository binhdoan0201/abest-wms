"""ABEST WMS - Bộ định tuyến API (Routers) cho Phân hệ Xác thực."""

from typing import Any

from fastapi import APIRouter, Depends, Request

from server.app.core.database import DbSession, get_db
from server.app.core.rbac import UserContext, get_current_user
from server.app.core.responses import success_response
from server.app.modules.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
)
from server.app.modules.auth.services import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", summary="Đăng nhập tài khoản và nhận JWT token")
def login(
    req: LoginRequest,
    request: Request,
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    """Endpoint đăng nhập công khai."""
    client_ip = request.client.host if request.client else None
    result = AuthService.login(db, req, client_ip=client_ip)
    return success_response(data=result.model_dump())


@router.get("/me", summary="Lấy thông tin người dùng và danh sách quyền hạn")
def get_me(
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    """Endpoint kiểm tra thông tin phiên làm việc và danh mục quyền đã cấp."""
    result = AuthService.get_me(db, user_ctx)
    return success_response(data=result.model_dump())


@router.post("/refresh", summary="Làm mới phiên: đổi token còn hạn lấy token mới 8 giờ")
def refresh_token(
    request: Request,
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    """Token phải còn hạn; tài khoản bị khóa sau khi đăng nhập thì không gia hạn (403)."""
    client_ip = request.client.host if request.client else None
    result = AuthService.refresh(db, user_ctx, client_ip=client_ip)
    return success_response(data=result.model_dump())


@router.post("/change-password", summary="Đổi mật khẩu người dùng")
def change_password(
    req: ChangePasswordRequest,
    request: Request,
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    """Endpoint đổi mật khẩu (bắt buộc khi must_change_password = true)."""
    client_ip = request.client.host if request.client else None
    result = AuthService.change_password(
        db,
        user_ctx.user_id,
        req,
        client_ip=client_ip,
    )
    return success_response(data=result.model_dump())
