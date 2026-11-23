"""ABEST WMS - Tầng Truy vấn CSDL (Repository) cho Phân hệ Nhiệm vụ (Tasks).

Ngoại lệ quy tắc 2.3 (đã thống nhất cùng Leader):
- c chỉ-đc cấu hình SLA & giới hạn task từ `warehouse_configs` (module `master_data`).
- c & khóa dòng `users` (`FOR UPDATE`) kèm join `roles` (module `auth`) để kiểm tra điu kiện
  nhận việc (kho, trạng thái ACTIVE, vai trò, khâu, an toàn thi vụ) và chống giao đồng thi.
"""

import json
import uuid
from typing import Any

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
        """Lấy thông tin nhiệm vụ theo task_id (có tùy chn khóa dòng for_update)."""
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
        """Lấy danh sách nhiệm vụ có lc theo kho, ngưi thực hiện, hàng đợi hoặc trạng thái."""
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
        """ếm số lượng task chưa hoàn tất (ASSIGNED, IN_PROGRESS, PAUSED_OFFLINE) của nhân viên."""
        stmt = select(func.count()).where(
            Task.warehouse_id == warehouse_id,
            Task.assigned_to == user_id,
            Task.status.in_(["ASSIGNED", "IN_PROGRESS", "PAUSED_OFFLINE"]),
        )
        return int(db.execute(stmt).scalar() or 0)

    @staticmethod
    def get_max_open_tasks(db: Session, warehouse_id: uuid.UUID) -> int:
        """c giới hạn task mở của mỗi nhân viên theo cấu hình kho (mặc định 3)."""
        row = db.execute(
            text("SELECT max_open_tasks_per_user FROM warehouse_configs WHERE warehouse_id = :w"),
            {"w": warehouse_id},
        ).fetchone()
        return int(row[0]) if row and row[0] is not None else 3

    @staticmethod
    def get_task_sla_minutes(db: Session, warehouse_id: uuid.UUID, task_type: str) -> int | None:
        """c thi gian SLA (phút) theo loại task từ `warehouse_configs.task_sla_minutes`."""
        row = db.execute(
            text("SELECT task_sla_minutes FROM warehouse_configs WHERE warehouse_id = :w"),
            {"w": warehouse_id},
        ).fetchone()
        if not row or row[0] is None:
            return None
        sla_map = row[0] if isinstance(row[0], dict) else json.loads(str(row[0]))
        minutes = sla_map.get(task_type)
        return int(minutes) if minutes is not None else None

    @staticmethod
    def lock_user_for_assignment(db: Session, user_id: uuid.UUID) -> dict[str, Any] | None:
        """Khóa dòng nhân viên (chống giao đồng thi) và trả v hồ sơ kiểm tra điu kiện nhận việc."""
        row = (
            db.execute(
                text(
                    """
                    SELECT
                        u.user_id,
                        u.primary_warehouse_id,
                        u.primary_stage::text AS primary_stage,
                        u.status::text AS status,
                        u.is_seasonal,
                        u.valid_from,
                        u.valid_until,
                        u.is_safety_checked,
                        r.role_code
                    FROM users u
                    JOIN roles r ON r.role_id = u.primary_role_id
                    WHERE u.user_id = :u
                    FOR UPDATE OF u
                    """
                ),
                {"u": user_id},
            )
            .mappings()
            .one_or_none()
        )
        return dict(row) if row is not None else None
