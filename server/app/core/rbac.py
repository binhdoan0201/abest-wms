"""ABEST WMS - Hạ tầng Phân quyền RBAC, Kiểm tra Quyền và Phạm vi Kho."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Header
from sqlalchemy import text
from sqlalchemy.orm import Session

from server.app.core.database import get_db
from server.app.core.exceptions import BusinessError
from server.app.core.security import decode_access_token


@dataclass
class UserContext:
    """Thông tin ngữ cảnh người dùng đang đăng nhập."""

    user_id: uuid.UUID
    username: str
    role_code: str
    warehouse_id: uuid.UUID | None
    permissions: dict[str, str]  # permission_code -> access_type


def get_current_user(
    authorization: str | None = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> UserContext:
    """Dependency trích xuất và xác thực JWT token từ Authorization header."""
    if not authorization:
        raise BusinessError(
            code="AUTH_REQUIRED",
            message="Yêu cầu đăng nhập để truy cập tài nguyên",
            http_status=401,
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise BusinessError(
            code="AUTH_INVALID_TOKEN",
            message="Định dạng Authorization header phải là Bearer <token>",
            http_status=401,
        )

    token = parts[1]
    payload = decode_access_token(token)

    sub = payload.get("sub")
    role_code = payload.get("role_code")
    warehouse_id_str = payload.get("warehouse_id")
    username = payload.get("username", "")

    if not sub or not role_code:
        raise BusinessError(
            code="AUTH_INVALID_TOKEN",
            message="Token thiếu thông tin người dùng hoặc vai trò",
            http_status=401,
        )

    user_id = uuid.UUID(str(sub))
    warehouse_id = uuid.UUID(str(warehouse_id_str)) if warehouse_id_str else None

    # Tải danh sách quyền tương ứng với vai trò của người dùng từ CSDL
    stmt = text(
        """
        SELECT rp.permission_code, rp.access_type
        FROM roles r
        JOIN role_permissions rp ON r.role_id = rp.role_id
        WHERE r.role_code = :role_code;
        """
    )
    results = db.execute(stmt, {"role_code": role_code}).fetchall()
    permissions_dict: dict[str, str] = {row[0]: row[1] for row in results}

    return UserContext(
        user_id=user_id,
        username=username,
        role_code=role_code,
        warehouse_id=warehouse_id,
        permissions=permissions_dict,
    )


def require_permission(permission_code: str) -> Callable[..., str]:
    """Dependency factory yêu cầu người dùng phải có quyền `permission_code`.

    Quy định bảo mật đặc thù ABEST WMS:
    - Trả về `access_type` (V, X, V_OWN, X_OWN...).
    - Vai trò `admin` bị CHẶN tuyệt đối khỏi mọi quyền nghiệp vụ kho (chỉ được cấp AD-1...).
    - Nếu không có quyền, trả HTTP 403 FORBIDDEN.
    """

    def permission_checker(user: UserContext = Depends(get_current_user)) -> str:
        # Kiểm tra nguyên tắc tách biệt dữ liệu: Admin không được đọc hoặc ghi dữ liệu nghiệp vụ kho
        if user.role_code == "admin" and permission_code != "AD-1":
            raise BusinessError(
                code="FORBIDDEN",
                message=(
                    f"Vai trò Quản trị viên (admin) bị chặn thực hiện "
                    f"quyền nghiệp vụ `{permission_code}`"
                ),
                http_status=403,
                details={"permission_code": permission_code, "role_code": user.role_code},
            )

        if permission_code not in user.permissions:
            raise BusinessError(
                code="FORBIDDEN",
                message=f"Tài khoản không có quyền `{permission_code}` để thực hiện hành động này",
                http_status=403,
                details={"permission_code": permission_code, "role_code": user.role_code},
            )

        access_type = user.permissions[permission_code]
        return access_type

    return permission_checker


def enforce_warehouse_scope(user: UserContext, resource_warehouse_id: Any) -> None:
    """Helper đảm bảo người dùng chỉ được truy cập dữ liệu thuộc phạm vi kho của mình.

    Nếu khác kho, trả về 404 NOT_FOUND theo quy chuẩn bảo mật Mục 3 Chuẩn API
    (để tránh lộ sự tồn tại của dữ liệu kho khác).
    """
    if user.warehouse_id and resource_warehouse_id:
        if str(resource_warehouse_id) != str(user.warehouse_id):
            raise BusinessError(
                code="NOT_FOUND",
                message="Không tìm thấy đối tượng hoặc đối tượng thuộc kho khác",
                http_status=404,
            )


def enforce_owner_scope(access_type: str, user: UserContext, owner_user_id: Any) -> None:
    """Helper xử lý giới hạn quyền sở hữu X_OWN và V_OWN.

    Chỉ cho phép thao tác trên dữ liệu của chính mình.
    """
    if access_type in ("X_OWN", "V_OWN"):
        if str(owner_user_id) != str(user.user_id):
            raise BusinessError(
                code="FORBIDDEN",
                message="Bạn chỉ có quyền xem hoặc thao tác trên bản ghi của chính mình",
                http_status=403,
            )
