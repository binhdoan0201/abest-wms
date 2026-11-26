"""ABEST WMS - Tầng Nghiệp vụ (Service) cho Phân hệ Xác thực và Quản lý phiên."""

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from server.app.core.audit import create_audit_log
from server.app.core.exceptions import BusinessError
from server.app.core.rbac import UserContext
from server.app.core.security import create_access_token, hash_password, verify_password
from server.app.modules.auth.repositories import AuthRepository
from server.app.modules.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponseData,
    MessageResponse,
    PermissionItem,
    RefreshResponseData,
    UserMeResponse,
)

TOKEN_HOURS = 8


def _issue_token(user: Any) -> str:
    """JWT HS256 cho người dùng (dùng chung cho đăng nhập và làm mới phiên)."""
    payload = {
        "sub": str(user.user_id),
        "username": user.username,
        "role_code": user.role.role_code,
        "warehouse_id": str(user.primary_warehouse_id) if user.primary_warehouse_id else None,
    }
    return create_access_token(payload, expires_delta=timedelta(hours=TOKEN_HOURS))


class AuthService:
    """Service xử lý quy trình xác thực, cấp token và phân quyền."""

    @staticmethod
    def login(
        db: Session,
        login_data: LoginRequest,
        client_ip: str | None = None,
    ) -> LoginResponseData:
        """Thực hiện đăng nhập người dùng, kiểm tra mật khẩu và cấp JWT token 8 giờ."""
        user = AuthRepository.get_user_by_username(db, login_data.username)

        # Tránh tiết lộ tài khoản có tồn tại hay không
        if not user or not user.password_hash:
            raise BusinessError(
                code="AUTH_INVALID_CREDENTIALS",
                message="Tài khoản hoặc mật khẩu không chính xác",
                http_status=401,
            )

        if user.status != "ACTIVE":
            raise BusinessError(
                code="AUTH_ACCOUNT_LOCKED",
                message="Tài khoản hiện đang bị khóa hoặc ngưng hoạt động",
                http_status=403,
            )

        if not verify_password(login_data.password, user.password_hash):
            AuthRepository.increment_failed_login(db, user)
            create_audit_log(
                db,
                action_code="LOGIN_FAILED",
                entity_name="users",
                actor_user_id=user.user_id,
                warehouse_id=user.primary_warehouse_id,
                ip_address=client_ip,
            )
            raise BusinessError(
                code="AUTH_INVALID_CREDENTIALS",
                message="Tài khoản hoặc mật khẩu không chính xác",
                http_status=401,
            )

        # Đăng nhập thành công: ghi nhận thời gian và reset số lần sai
        AuthRepository.record_login_success(db, user)

        # Lấy danh sách quyền của vai trò
        perms = AuthRepository.get_permissions_by_role_id(db, user.primary_role_id)
        permission_items = [
            PermissionItem(permission_code=p.permission_code, access_type=p.access_type)
            for p in perms
        ]

        user_me = UserMeResponse(
            user_id=user.user_id,
            username=user.username,
            full_name=user.full_name,
            role_code=user.role.role_code,
            warehouse_id=user.primary_warehouse_id,
            must_change_password=user.must_change_password,
            permissions=permission_items,
        )

        # Sinh JWT HS256 với thời hạn 8 giờ theo đúng yêu cầu
        token = _issue_token(user)

        # Bắt buộc ghi audit log cho hành động LOGIN
        create_audit_log(
            db,
            action_code="LOGIN",
            entity_name="users",
            actor_user_id=user.user_id,
            warehouse_id=user.primary_warehouse_id,
            ip_address=client_ip,
        )

        return LoginResponseData(
            access_token=token,
            token_type="Bearer",
            expires_in_hours=8,
            user=user_me,
        )

    @staticmethod
    def refresh(
        db: Session, user_ctx: UserContext, client_ip: str | None = None
    ) -> RefreshResponseData:
        """Cấp token mới 8 giờ từ token còn hạn (A-03).

        Kiểm tra lại tài khoản: bị khóa hoặc ngưng hoạt động sau khi đăng nhập thì không gia hạn.
        Vai trò, kho lấy lại từ CSDL nên thay đổi phân quyền có hiệu lực ở lần làm mới kế tiếp.
        """
        user = AuthRepository.get_user_by_id(db, user_ctx.user_id)
        if not user:
            raise BusinessError(
                code="AUTH_INVALID_TOKEN",
                message="Tài khoản không còn tồn tại",
                http_status=401,
            )
        if user.status != "ACTIVE":
            raise BusinessError(
                code="AUTH_ACCOUNT_LOCKED",
                message="Tài khoản hiện đang bị khóa hoặc ngưng hoạt động",
                http_status=403,
            )
        token = _issue_token(user)
        create_audit_log(
            db,
            action_code="TOKEN_REFRESH",
            entity_name="users",
            actor_user_id=user.user_id,
            warehouse_id=user.primary_warehouse_id,
            ip_address=client_ip,
        )
        return RefreshResponseData(access_token=token, expires_in_hours=TOKEN_HOURS)

    @staticmethod
    def get_me(db: Session, user_ctx: UserContext) -> UserMeResponse:
        """Lấy thông tin người dùng hiện tại và danh sách quyền hạn chi tiết."""
        user = AuthRepository.get_user_by_id(db, user_ctx.user_id)
        if not user:
            raise BusinessError(
                code="NOT_FOUND",
                message="Không tìm thấy thông tin tài khoản người dùng",
                http_status=404,
            )

        perms = AuthRepository.get_permissions_by_role_id(db, user.primary_role_id)
        permission_items = [
            PermissionItem(permission_code=p.permission_code, access_type=p.access_type)
            for p in perms
        ]

        return UserMeResponse(
            user_id=user.user_id,
            username=user.username,
            full_name=user.full_name,
            role_code=user.role.role_code,
            warehouse_id=user.primary_warehouse_id,
            must_change_password=user.must_change_password,
            permissions=permission_items,
        )

    @staticmethod
    def change_password(
        db: Session,
        user_id: uuid.UUID,
        req: ChangePasswordRequest,
        client_ip: str | None = None,
    ) -> MessageResponse:
        """Đổi mật khẩu người dùng và ghi nhật ký kiểm toán."""
        user = AuthRepository.get_user_by_id(db, user_id)
        if not user or not user.password_hash:
            raise BusinessError(
                code="NOT_FOUND",
                message="Không tìm thấy tài khoản người dùng",
                http_status=404,
            )

        if not verify_password(req.old_password, user.password_hash):
            raise BusinessError(
                code="AUTH_INVALID_CREDENTIALS",
                message="Mật khẩu hiện tại không chính xác",
                http_status=401,
            )

        if req.old_password == req.new_password:
            raise BusinessError(
                code="AUTH_PASSWORD_UNCHANGED",
                message="Mật khẩu mới không được trùng với mật khẩu cũ",
                http_status=400,
            )

        new_hash = hash_password(req.new_password)
        AuthRepository.update_password(db, user, new_hash)

        # Bắt buộc ghi audit log
        create_audit_log(
            db,
            action_code="CHANGE_PASSWORD",
            entity_name="users",
            actor_user_id=user.user_id,
            warehouse_id=user.primary_warehouse_id,
            ip_address=client_ip,
        )

        return MessageResponse(message="Đổi mật khẩu thành công")
