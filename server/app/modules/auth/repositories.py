"""ABEST WMS - Tầng Truy vấn CSDL (Repository) cho Phân hệ Xác thực."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from server.app.modules.auth.models import RolePermission, User


class AuthRepository:
    """Repository quản lý truy vấn người dùng, vai trò và phân quyền."""

    @staticmethod
    def get_user_by_username(db: Session, username: str) -> User | None:
        """Tìm người dùng theo tên đăng nhập kèm thông tin vai trò."""
        stmt = select(User).options(joinedload(User.role)).where(User.username == username)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
        """Tìm người dùng theo user_id kèm thông tin vai trò."""
        stmt = select(User).options(joinedload(User.role)).where(User.user_id == user_id)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_permissions_by_role_id(db: Session, role_id: uuid.UUID) -> list[RolePermission]:
        """Lấy danh sách các quyền được gán cho vai trò."""
        stmt = (
            select(RolePermission)
            .where(RolePermission.role_id == role_id)
            .order_by(RolePermission.permission_code)
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def record_login_success(db: Session, user: User) -> None:
        """Ghi nhận đăng nhập thành công: xóa đếm lần sai và cập nhật thời gian."""
        user.failed_login_attempts = 0
        user.last_login_at = datetime.now(timezone.utc)

    @staticmethod
    def increment_failed_login(db: Session, user: User) -> None:
        """Tăng số lần đăng nhập sai."""
        user.failed_login_attempts += 1

    @staticmethod
    def update_password(db: Session, user: User, new_password_hash: str) -> None:
        """Cập nhật mật khẩu mới và gỡ cờ bắt buộc đổi mật khẩu."""
        user.password_hash = new_password_hash
        user.must_change_password = False
