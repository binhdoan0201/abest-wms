"""ABEST WMS - Tầng Truy vấn CSDL (Repository) cho Phân hệ Nhiệm vụ (Tasks)."""

import uuid

from sqlalchemy import func, select, text
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

    @staticmethod
    def get_max_open_tasks(db: Session, warehouse_id: uuid.UUID) -> int:
        """Đọc giới hạn task mở của mỗi nhân viên theo cấu hình kho (mặc định 3).

        Truy vấn chỉ đọc bảng `warehouse_configs` của module master_data.
        """
        row = db.execute(
            text("SELECT max_open_tasks_per_user FROM warehouse_configs WHERE warehouse_id = :w"),
            {"w": warehouse_id},
        ).fetchone()
        return int(row[0]) if row and row[0] is not None else 3

    @staticmethod
    def lock_user_and_get_stage(db: Session, user_id: uuid.UUID) -> str | None:
        """Khóa dòng nhân viên (chống giao đồng thời) và trả về khâu làm việc `primary_stage`.

        Truy vấn chỉ đọc bảng `users` của module auth; khóa dòng để hai lệnh giao
        đồng thời cho cùng một nhân viên được thực hiện tuần tự.
        """
        row = db.execute(
            text("SELECT primary_stage::text FROM users WHERE user_id = :u FOR UPDATE"),
            {"u": user_id},
        ).fetchone()
        return str(row[0]) if row and row[0] else None
