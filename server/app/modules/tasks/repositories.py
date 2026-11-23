"""ABEST WMS - Tầng Truy vấn CSDL (Repository) cho Phân hệ Nhiệm vụ (Tasks)."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from server.app.modules.tasks.models import Task


class TaskRepository:
    """Repository quản lý các truy vấn và cập nhật bảng `tasks`."""

    @staticmethod
    def create_task(db: Session, task: Task) -> Task:
        """Tạo mới một nhiệm vụ trong CSDL."""
        db.add(task)
        db.flush()
        return task

    @staticmethod
    def get_task_by_id(db: Session, task_id: uuid.UUID, for_update: bool = False) -> Task | None:
        """Lấy thông tin nhiệm vụ theo task_id (có tùy chọn khóa dòng for_update)."""
        stmt = select(Task).where(Task.task_id == task_id)
        if for_update:
            stmt = stmt.with_for_update()
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_tasks(
        db: Session,
        warehouse_id: uuid.UUID,
        assigned_to: uuid.UUID | None = None,
        status: str | None = None,
        queue_only: bool = False,
    ) -> list[Task]:
        """Lấy danh sách nhiệm vụ có lọc theo kho, người thực hiện, hàng đợi hoặc trạng thái."""
        stmt = (
            select(Task).where(Task.warehouse_id == warehouse_id).order_by(Task.created_at.desc())
        )
        if queue_only:
            stmt = stmt.where(Task.status.in_(["UNASSIGNED", "REJECTED"]))
        elif assigned_to:
            stmt = stmt.where(Task.assigned_to == assigned_to)
        if status:
            stmt = stmt.where(Task.status == status)
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def count_open_tasks_for_user(db: Session, user_id: uuid.UUID, warehouse_id: uuid.UUID) -> int:
        """Đếm số lượng task chưa hoàn tất (ASSIGNED, IN_PROGRESS) của một nhân viên."""
        stmt = select(func.count()).where(
            Task.warehouse_id == warehouse_id,
            Task.assigned_to == user_id,
            Task.status.in_(["ASSIGNED", "IN_PROGRESS"]),
        )
        return int(db.execute(stmt).scalar() or 0)
