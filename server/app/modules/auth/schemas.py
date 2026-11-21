"""ABEST WMS - Pydantic Schemas cho Phân hệ Xác thực và Phân quyền (Auth & RBAC)."""

import uuid

from pydantic import BaseModel, Field


class PermissionItem(BaseModel):
    """Mục quyền hạn cụ thể của người dùng."""

    permission_code: str = Field(..., description="Mã quyền hạn, ví dụ: NH-1, TK-3.2, AD-1")
    access_type: str = Field(..., description="Kiểu truy cập: V, X, V_OWN, X_OWN")


class UserMeResponse(BaseModel):
    """Cấu trúc thông tin trả về của endpoint GET /auth/me."""

    user_id: uuid.UUID
    username: str
    full_name: str
    role_code: str
    warehouse_id: uuid.UUID | None = None
    must_change_password: bool = False
    permissions: list[PermissionItem] = Field(default_factory=list)


class LoginRequest(BaseModel):
    """Dữ liệu yêu cầu đăng nhập."""

    username: str = Field(..., min_length=1, description="Tên đăng nhập")
    password: str = Field(..., min_length=1, description="Mật khẩu người dùng")


class LoginResponseData(BaseModel):
    """Dữ liệu trả về khi đăng nhập thành công."""

    access_token: str
    token_type: str = "Bearer"
    expires_in_hours: int = 8
    user: UserMeResponse


class ChangePasswordRequest(BaseModel):
    """Dữ liệu yêu cầu đổi mật khẩu."""

    old_password: str = Field(..., min_length=1, description="Mật khẩu hiện tại")
    new_password: str = Field(..., min_length=6, description="Mật khẩu mới (tối thiểu 6 ký tự)")


class MessageResponse(BaseModel):
    """Thông báo phản hồi đơn giản."""

    message: str
