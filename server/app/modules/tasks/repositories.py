"""ABEST WMS - Tầng Truy vấn CSDL (Repository) cho Phân hệ Nhiệm vụ (Tasks)."""

import uuid

from sqlalchemy import select
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
    def get_task_by_id(db: Session, task_id: uuid.UUID) -> Task | None:
        """Lấy thông tin nhiệm vụ theo task_id."""
        stmt = select(Task).where(Task.task_id == task_id)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_tasks(
        db: Session,
        warehouse_id: uuid.UUID,
        assigned_to: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[Task]:
        """Lấy danh sách nhiệm vụ có lọc theo kho, người thực hiện hoặc trạng thái."""
        stmt = (
            select(Task).where(Task.warehouse_id == warehouse_id).order_by(Task.created_at.desc())
        )
        if assigned_to:
            stmt = stmt.where(Task.assigned_to == assigned_to)
        if status:
            stmt = stmt.where(Task.status == status)
        return list(db.execute(stmt).scalars().all())
