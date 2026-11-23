"""ABEST WMS - Táº§ng Truy váº¥n CSDL (Repository) cho PhÃ¢n há»‡ Nhiá»‡m vá»¥ (Tasks).

Ngoáº¡i lá»‡ quy táº¯c 2.3 (Ä‘Ã£ thá»‘ng nháº¥t cÃ¹ng Leader):
- Äá»c chá»‰-Ä‘á»c cáº¥u hÃ¬nh SLA & giá»›i háº¡n task tá»« `warehouse_configs` (module `master_data`).
- Äá»c & khÃ³a dÃ²ng `users` (`FOR UPDATE`) kÃ¨m join `roles` (module `auth`) Ä‘á»ƒ kiá»ƒm tra Ä‘iá»u kiá»‡n
  nháº­n viá»‡c (kho, tráº¡ng thÃ¡i ACTIVE, vai trÃ², khÃ¢u, an toÃ n thá»i vá»¥) vÃ  chá»‘ng giao Ä‘á»“ng thá»i.
"""

import json
import uuid
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from server.app.modules.tasks.models import Task


class TaskRepository:
    """Repository quáº£n lÃ½ cÃ¡c truy váº¥n vÃ  cáº­p nháº­t báº£ng `tasks`."""

    @staticmethod
    def create_task(db: Session, task: Task) -> Task:
        """Táº¡o má»›i má»™t nhiá»‡m vá»¥ trong CSDL."""
        db.add(task)
        db.flush()
        return task

    @staticmethod
    def get_task_by_id(db: Session, task_id: uuid.UUID, for_update: bool = False) -> Task | None:
        """Láº¥y thÃ´ng tin nhiá»‡m vá»¥ theo task_id (cÃ³ tÃ¹y chá»n khÃ³a dÃ²ng for_update)."""
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
        """Láº¥y danh sÃ¡ch nhiá»‡m vá»¥ cÃ³ lá»c theo kho, ngÆ°á»i thá»±c hiá»‡n, hÃ ng Ä‘á»£i hoáº·c tráº¡ng thÃ¡i."""
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
        """Äáº¿m sá»‘ lÆ°á»£ng task chÆ°a hoÃ n táº¥t (ASSIGNED, IN_PROGRESS, PAUSED_OFFLINE) cá»§a nhÃ¢n viÃªn."""
        stmt = select(func.count()).where(
            Task.warehouse_id == warehouse_id,
            Task.assigned_to == user_id,
            Task.status.in_(["ASSIGNED", "IN_PROGRESS", "PAUSED_OFFLINE"]),
        )
        return int(db.execute(stmt).scalar() or 0)

    @staticmethod
    def get_max_open_tasks(db: Session, warehouse_id: uuid.UUID) -> int:
        """Äá»c giá»›i háº¡n task má»Ÿ cá»§a má»—i nhÃ¢n viÃªn theo cáº¥u hÃ¬nh kho (máº·c Ä‘á»‹nh 3)."""
        row = db.execute(
            text("SELECT max_open_tasks_per_user FROM warehouse_configs WHERE warehouse_id = :w"),
            {"w": warehouse_id},
        ).fetchone()
        return int(row[0]) if row and row[0] is not None else 3

    @staticmethod
    def get_task_sla_minutes(db: Session, warehouse_id: uuid.UUID, task_type: str) -> int | None:
        """Äá»c thá»i gian SLA (phÃºt) theo loáº¡i task tá»« `warehouse_configs.task_sla_minutes`."""
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
        """KhÃ³a dÃ²ng nhÃ¢n viÃªn (chá»‘ng giao Ä‘á»“ng thá»i) vÃ  tráº£ vá» há»“ sÆ¡ kiá»ƒm tra Ä‘iá»u kiá»‡n nháº­n viá»‡c."""
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
