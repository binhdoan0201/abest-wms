"""ABEST WMS - Táº§ng Nghiá»‡p vá»¥ (Service) cho PhÃ¢n há»‡ Nhiá»‡m vá»¥ (Tasks).

Triá»ƒn khai Ä‘áº§y Ä‘á»§ cÃ¡c nghiá»‡p vá»¥ D-01, D-02:
- create_task (tá»± tÃ­nh `sla_due_at` theo cáº¥u hÃ¬nh `warehouse_configs.task_sla_minutes`)
- assign_task (kiá»ƒm tra pháº¡m vi kho, Ä‘iá»u kiá»‡n nhÃ¢n viÃªn, khÃ¢u lÃ m viá»‡c vÃ  giá»›i háº¡n task má»Ÿ)
- accept_task / reject_task / complete_task
- reassign_task (Ä‘iá»u chuyá»ƒn task sang nhÃ¢n viÃªn khÃ¡c, reset `started_at`)
- cancel_task (há»§y task chÆ°a hoÃ n táº¥t)
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from server.app.core.audit import create_audit_log
from server.app.core.exceptions import BusinessError, translate_db_error
from server.app.modules.tasks.models import Task
from server.app.modules.tasks.repositories import TaskRepository
from server.app.modules.tasks.schemas import (
    AcceptTaskRequest,
    AssignTaskRequest,
    CancelTaskRequest,
    CompleteTaskRequest,
    CreateTaskRequest,
    ReassignTaskRequest,
    RejectTaskRequest,
    TaskResponse,
)


def _task_to_schema(t: Task) -> TaskResponse:
    return TaskResponse(
        task_id=t.task_id,
        warehouse_id=t.warehouse_id,
        task_type=t.task_type,
        stage=t.stage,
        zone_id=t.zone_id,
        ref_doc_type=t.ref_doc_type,
        ref_doc_id=t.ref_doc_id,
        priority=t.priority,
        status=t.status,
        assigned_to=t.assigned_to,
        assigned_by=t.assigned_by,
        sla_due_at=t.sla_due_at,
        progress_pct=str(t.progress_pct),
        completed_qty=str(t.completed_qty),
        rejection_reason=t.rejection_reason,
        version_no=t.version_no,
        started_at=t.started_at,
        completed_at=t.completed_at,
        created_at=t.created_at,
    )


def _get_task_in_warehouse(
    db: Session,
    task_id: uuid.UUID,
    warehouse_id: uuid.UUID | None,
    for_update: bool = True,
) -> Task:
    """Láº¥y nhiá»‡m vá»¥ vÃ  xÃ¡c thá»±c thuá»™c Ä‘Ãºng kho cá»§a ngÆ°á»i thao tÃ¡c (quy táº¯c 5.4.1)."""
    task = TaskRepository.get_task_by_id(db, task_id, for_update=for_update)
    if not task or not warehouse_id or task.warehouse_id != warehouse_id:
        raise BusinessError(
            code="NOT_FOUND", message="KhÃ´ng tÃ¬m tháº¥y nhiá»‡m vá»¥", http_status=404
        )
    return task


def _check_assignee(db: Session, task: Task, user_id: uuid.UUID) -> None:
    """Kiá»ƒm tra ngÆ°á»i nháº­n viá»‡c: tá»“n táº¡i, cÃ¹ng kho, ACTIVE, Ä‘Ãºng vai trÃ²/khÃ¢u, an toÃ n thá»i vá»¥ vÃ  giá»›i háº¡n task má»Ÿ."""
    user_info = TaskRepository.lock_user_for_assignment(db, user_id)
    if user_info is None:
        raise BusinessError(
            code="NOT_FOUND",
            message="KhÃ´ng tÃ¬m tháº¥y nhÃ¢n viÃªn Ä‘Æ°á»£c giao",
            http_status=404,
        )

    if user_info["primary_warehouse_id"] != task.warehouse_id:
        raise BusinessError(
            code="FORBIDDEN",
            message="NhÃ¢n viÃªn khÃ´ng thuá»™c kho cá»§a nhiá»‡m vá»¥ nÃ y",
            http_status=403,
        )

    if user_info["status"] != "ACTIVE":
        raise BusinessError(
            code="INVALID_STATE",
            message="TÃ i khoáº£n nhÃ¢n viÃªn khÃ´ng á»Ÿ tráº¡ng thÃ¡i hoáº¡t Ä‘á»™ng (ACTIVE)",
            http_status=409,
        )

    role_code = str(user_info["role_code"] or "")
    is_executor = role_code.startswith("nv-")
    is_mgmt_general = task.stage == "QUAN_LY_CHUNG" and role_code in {"thukho", "quanly"}
    if not is_executor and not is_mgmt_general:
        raise BusinessError(
            code="FORBIDDEN",
            message="NgÆ°á»i Ä‘Æ°á»£c giao khÃ´ng cÃ³ vai trÃ² nhÃ¢n viÃªn thá»±c thi há»£p lá»‡",
            http_status=403,
        )

    if user_info["is_seasonal"]:
        if not user_info["is_safety_checked"]:
            raise BusinessError(
                code="FORBIDDEN",
                message="NhÃ¢n viÃªn thá»i vá»¥ chÆ°a hoÃ n táº¥t kiá»ƒm tra an toÃ n lao Ä‘á»™ng",
                http_status=403,
            )
        now = datetime.now(timezone.utc)
        valid_from = user_info["valid_from"]
        valid_until = user_info["valid_until"]
        if (valid_from is not None and now < valid_from) or (
            valid_until is not None and now > valid_until
        ):
            raise BusinessError(
                code="FORBIDDEN",
                message="Thá»i háº¡n lÃ m viá»‡c cá»§a nhÃ¢n viÃªn thá»i vá»¥ khÃ´ng há»£p lá»‡ hoáº·c Ä‘Ã£ háº¿t háº¡n",
                http_status=403,
            )

    if user_info["primary_stage"] != task.stage:
        raise BusinessError(
            code="TASKS_STAGE_MISMATCH",
            message="NhÃ¢n viÃªn khÃ´ng thuá»™c khÃ¢u lÃ m viá»‡c cá»§a nhiá»‡m vá»¥ nÃ y",
            http_status=409,
        )

    limit = TaskRepository.get_max_open_tasks(db, task.warehouse_id)
    if TaskRepository.count_open_tasks_for_user(db, user_id, task.warehouse_id) >= limit:
        raise BusinessError(
            code="TASKS_MAX_OPEN_EXCEEDED",
            message=f"NhÃ¢n viÃªn Ä‘ang giá»¯ tá»‘i Ä‘a {limit} nhiá»‡m vá»¥ má»Ÿ",
            http_status=409,
        )


class TaskService:
    """Service Ä‘iá»u phá»‘i vÃ²ng Ä‘á»i nhiá»‡m vá»¥ trong kho."""

    @staticmethod
    def create_task(
        db: Session,
        warehouse_id: uuid.UUID,
        creator_id: uuid.UUID,
        req: CreateTaskRequest,
    ) -> TaskResponse:
        """Táº¡o má»›i nhiá»‡m vá»¥ vá»›i tráº¡ng thÃ¡i ban Ä‘áº§u UNASSIGNED vÃ  tÃ­nh `sla_due_at`."""
        sla_minutes = TaskRepository.get_task_sla_minutes(db, warehouse_id, req.task_type)
        sla_due_at = (
            datetime.now(timezone.utc) + timedelta(minutes=sla_minutes)
            if sla_minutes is not None
            else None
        )

        task = Task(
            task_id=uuid.uuid4(),
            warehouse_id=warehouse_id,
            task_type=req.task_type,
            stage=req.stage,
            zone_id=req.zone_id,
            ref_doc_type=req.ref_doc_type,
            ref_doc_id=req.ref_doc_id,
            priority=req.priority,
            status="UNASSIGNED",
            sla_due_at=sla_due_at,
            version_no=1,
        )
        try:
            saved_task = TaskRepository.create_task(db, task)
        except IntegrityError as exc:
            raise translate_db_error(exc) from exc

        create_audit_log(
            db,
            action_code="TASK_CREATE",
            entity_name="tasks",
            actor_user_id=creator_id,
            warehouse_id=warehouse_id,
            entity_id=saved_task.task_id,
            new_values={"task_type": req.task_type, "status": "UNASSIGNED"},
        )
        return _task_to_schema(saved_task)

    @staticmethod
    def assign_task(
        db: Session,
        task_id: uuid.UUID,
        assigner_id: uuid.UUID,
        req: AssignTaskRequest,
        warehouse_id: uuid.UUID | None = None,
    ) -> TaskResponse:
        """Giao nhiá»‡m vá»¥ cho nhÃ¢n viÃªn (chuyá»ƒn sang ASSIGNED)."""
        task = _get_task_in_warehouse(db, task_id, warehouse_id, for_update=True)

        if req.version_no != task.version_no:
            raise BusinessError(
                code="VERSION_CONFLICT",
                message="Nhiá»‡m vá»¥ Ä‘Ã£ Ä‘Æ°á»£c cáº­p nháº­t bá»Ÿi thao tÃ¡c khÃ¡c",
                http_status=409,
                details={"current_version_no": task.version_no},
            )

        if task.status not in ("UNASSIGNED", "REJECTED"):
            raise BusinessError(
                code="INVALID_STATE",
                message=f"KhÃ´ng thá»ƒ giao nhiá»‡m vá»¥ Ä‘ang á»Ÿ tráº¡ng thÃ¡i `{task.status}`",
                http_status=409,
            )

        _check_assignee(db, task, req.assigned_to_user_id)

        task.assigned_to = req.assigned_to_user_id
        task.assigned_by = assigner_id
        task.status = "ASSIGNED"
        task.rejection_reason = None
        task.version_no += 1
        db.flush()

        create_audit_log(
            db,
            action_code="TASK_ASSIGN",
            entity_name="tasks",
            actor_user_id=assigner_id,
            warehouse_id=task.warehouse_id,
            entity_id=task.task_id,
            new_values={"assigned_to": str(req.assigned_to_user_id), "status": "ASSIGNED"},
        )
        return _task_to_schema(task)

    @staticmethod
    def accept_task(
        db: Session,
        task_id: uuid.UUID,
        worker_id: uuid.UUID,
        req: AcceptTaskRequest,
        warehouse_id: uuid.UUID | None = None,
    ) -> TaskResponse:
        """NhÃ¢n viÃªn nháº­n nhiá»‡m vá»¥ (chuyá»ƒn sang IN_PROGRESS)."""
        task = _get_task_in_warehouse(db, task_id, warehouse_id, for_update=True)

        if str(task.assigned_to) != str(worker_id):
            raise BusinessError(
                code="FORBIDDEN",
                message="Báº¡n khÃ´ng pháº£i nhÃ¢n viÃªn Ä‘Æ°á»£c giao nhiá»‡m vá»¥ nÃ y",
                http_status=403,
            )

        if req.version_no != task.version_no:
            raise BusinessError(
                code="VERSION_CONFLICT",
                message="Nhiá»‡m vá»¥ Ä‘Ã£ Ä‘Æ°á»£c cáº­p nháº­t bá»Ÿi thao tÃ¡c khÃ¡c",
                http_status=409,
                details={"current_version_no": task.version_no},
            )

        if task.status != "ASSIGNED":
            raise BusinessError(
                code="INVALID_STATE",
                message=(
                    f"Chá»‰ cÃ³ thá»ƒ nháº­n nhiá»‡m vá»¥ khi á»Ÿ tráº¡ng thÃ¡i ASSIGNED "
                    f"(hiá»‡n táº¡i: `{task.status}`)"
                ),
                http_status=409,
            )

        task.status = "IN_PROGRESS"
        task.started_at = datetime.now(timezone.utc)
        task.version_no += 1
        db.flush()

        create_audit_log(
            db,
            action_code="TASK_ACCEPT",
            entity_name="tasks",
            actor_user_id=worker_id,
            warehouse_id=task.warehouse_id,
            entity_id=task.task_id,
            new_values={"status": "IN_PROGRESS"},
        )
        return _task_to_schema(task)

    @staticmethod
    def reject_task(
        db: Session,
        task_id: uuid.UUID,
        worker_id: uuid.UUID,
        req: RejectTaskRequest,
        warehouse_id: uuid.UUID | None = None,
    ) -> TaskResponse:
        """NhÃ¢n viÃªn tá»« chá»‘i nhiá»‡m vá»¥ kÃ¨m lÃ½ do (chuyá»ƒn sang REJECTED)."""
        task = _get_task_in_warehouse(db, task_id, warehouse_id, for_update=True)

        if str(task.assigned_to) != str(worker_id):
            raise BusinessError(
                code="FORBIDDEN",
                message="Báº¡n khÃ´ng pháº£i nhÃ¢n viÃªn Ä‘Æ°á»£c giao nhiá»‡m vá»¥ nÃ y",
                http_status=403,
            )

        if req.version_no != task.version_no:
            raise BusinessError(
                code="VERSION_CONFLICT",
                message="Nhiá»‡m vá»¥ Ä‘Ã£ Ä‘Æ°á»£c cáº­p nháº­t bá»Ÿi thao tÃ¡c khÃ¡c",
                http_status=409,
                details={"current_version_no": task.version_no},
            )

        if task.status != "ASSIGNED":
            raise BusinessError(
                code="INVALID_STATE",
                message=(
                    f"Chá»‰ cÃ³ thá»ƒ tá»« chá»‘i nhiá»‡m vá»¥ khi á»Ÿ tráº¡ng thÃ¡i ASSIGNED "
                    f"(hiá»‡n táº¡i: `{task.status}`)"
                ),
                http_status=409,
            )

        task.status = "REJECTED"
        task.rejection_reason = req.rejection_reason
        task.version_no += 1
        db.flush()

        create_audit_log(
            db,
            action_code="TASK_REJECT",
            entity_name="tasks",
            actor_user_id=worker_id,
            warehouse_id=task.warehouse_id,
            entity_id=task.task_id,
            new_values={"status": "REJECTED", "reason": req.rejection_reason},
        )
        return _task_to_schema(task)

    @staticmethod
    def complete_task(
        db: Session,
        task_id: uuid.UUID,
        worker_id: uuid.UUID,
        req: CompleteTaskRequest,
        warehouse_id: uuid.UUID | None = None,
    ) -> TaskResponse:
        """HoÃ n táº¥t nhiá»‡m vá»¥ (chuyá»ƒn sang COMPLETED, tiáº¿n Ä‘á»™ 100%)."""
        task = _get_task_in_warehouse(db, task_id, warehouse_id, for_update=True)

        if str(task.assigned_to) != str(worker_id):
            raise BusinessError(
                code="FORBIDDEN",
                message="Báº¡n khÃ´ng pháº£i nhÃ¢n viÃªn Ä‘Æ°á»£c giao nhiá»‡m vá»¥ nÃ y",
                http_status=403,
            )

        if req.version_no != task.version_no:
            raise BusinessError(
                code="VERSION_CONFLICT",
                message="Nhiá»‡m vá»¥ Ä‘Ã£ Ä‘Æ°á»£c cáº­p nháº­t bá»Ÿi thao tÃ¡c khÃ¡c",
                http_status=409,
                details={"current_version_no": task.version_no},
            )

        if task.status != "IN_PROGRESS":
            raise BusinessError(
                code="INVALID_STATE",
                message=(
                    f"Chá»‰ cÃ³ thá»ƒ hoÃ n táº¥t nhiá»‡m vá»¥ khi á»Ÿ tráº¡ng thÃ¡i IN_PROGRESS "
                    f"(hiá»‡n táº¡i: `{task.status}`)"
                ),
                http_status=409,
            )

        task.status = "COMPLETED"
        task.completed_at = datetime.now(timezone.utc)
        task.progress_pct = Decimal("100.00")
        if req.completed_qty is not None:
            task.completed_qty = req.completed_qty
        task.version_no += 1
        db.flush()

        create_audit_log(
            db,
            action_code="TASK_COMPLETE",
            entity_name="tasks",
            actor_user_id=worker_id,
            warehouse_id=task.warehouse_id,
            entity_id=task.task_id,
            new_values={"status": "COMPLETED"},
        )
        return _task_to_schema(task)

    @staticmethod
    def reassign_task(
        db: Session,
        task_id: uuid.UUID,
        assigner_id: uuid.UUID,
        req: ReassignTaskRequest,
        warehouse_id: uuid.UUID | None = None,
    ) -> TaskResponse:
        """Äiá»u chuyá»ƒn nhiá»‡m vá»¥ sang nhÃ¢n viÃªn khÃ¡c."""
        task = _get_task_in_warehouse(db, task_id, warehouse_id, for_update=True)

        if req.version_no != task.version_no:
            raise BusinessError(
                code="VERSION_CONFLICT",
                message="Nhiá»‡m vá»¥ Ä‘Ã£ Ä‘Æ°á»£c cáº­p nháº­t bá»Ÿi thao tÃ¡c khÃ¡c",
                http_status=409,
                details={"current_version_no": task.version_no},
            )

        if task.status in ("COMPLETED", "CANCELLED"):
            raise BusinessError(
                code="INVALID_STATE",
                message=f"KhÃ´ng thá»ƒ Ä‘iá»u chuyá»ƒn nhiá»‡m vá»¥ Ä‘ang á»Ÿ tráº¡ng thÃ¡i `{task.status}`",
                http_status=409,
            )

        if task.assigned_to == req.new_assigned_to_user_id:
            raise BusinessError(
                code="INVALID_STATE",
                message="Nhiá»‡m vá»¥ Ä‘ang do chÃ­nh nhÃ¢n viÃªn nÃ y giá»¯",
                http_status=409,
            )

        _check_assignee(db, task, req.new_assigned_to_user_id)

        old_assignee = str(task.assigned_to) if task.assigned_to else None
        task.assigned_to = req.new_assigned_to_user_id
        task.assigned_by = assigner_id
        task.status = "ASSIGNED"
        task.started_at = None
        task.rejection_reason = None
        task.version_no += 1
        db.flush()

        create_audit_log(
            db,
            action_code="TASK_REASSIGN",
            entity_name="tasks",
            actor_user_id=assigner_id,
            warehouse_id=task.warehouse_id,
            entity_id=task.task_id,
            old_values={"assigned_to": old_assignee},
            new_values={
                "assigned_to": str(req.new_assigned_to_user_id),
                "status": "ASSIGNED",
                "reason": req.reason,
            },
        )
        return _task_to_schema(task)

    @staticmethod
    def cancel_task(
        db: Session,
        task_id: uuid.UUID,
        actor_id: uuid.UUID,
        req: CancelTaskRequest,
        warehouse_id: uuid.UUID | None = None,
    ) -> TaskResponse:
        """Há»§y nhiá»‡m vá»¥ chÆ°a hoÃ n táº¥t."""
        task = _get_task_in_warehouse(db, task_id, warehouse_id, for_update=True)

        if req.version_no != task.version_no:
            raise BusinessError(
                code="VERSION_CONFLICT",
                message="Nhiá»‡m vá»¥ Ä‘Ã£ Ä‘Æ°á»£c cáº­p nháº­t bá»Ÿi thao tÃ¡c khÃ¡c",
                http_status=409,
                details={"current_version_no": task.version_no},
            )

        if task.status in ("COMPLETED", "CANCELLED"):
            raise BusinessError(
                code="INVALID_STATE",
                message=f"KhÃ´ng thá»ƒ há»§y nhiá»‡m vá»¥ Ä‘ang á»Ÿ tráº¡ng thÃ¡i `{task.status}`",
                http_status=409,
            )

        task.status = "CANCELLED"
        task.version_no += 1
        db.flush()

        create_audit_log(
            db,
            action_code="TASK_CANCEL",
            entity_name="tasks",
            actor_user_id=actor_id,
            warehouse_id=task.warehouse_id,
            entity_id=task.task_id,
            new_values={"status": "CANCELLED", "reason": req.cancel_reason},
        )
        return _task_to_schema(task)

    @staticmethod
    def get_tasks(
        db: Session,
        warehouse_id: uuid.UUID,
        worker_id: uuid.UUID | None = None,
        status: str | None = None,
        queue_only: bool = False,
    ) -> list[TaskResponse]:
        """Láº¥y danh sÃ¡ch nhiá»‡m vá»¥."""
        tasks = TaskRepository.get_tasks(
            db=db,
            warehouse_id=warehouse_id,
            assigned_to=worker_id,
            status=status,
            queue_only=queue_only,
        )
        return [_task_to_schema(t) for t in tasks]

    @staticmethod
    def get_task_by_id(db: Session, task_id: uuid.UUID) -> TaskResponse:
        """Láº¥y chi tiáº¿t má»™t nhiá»‡m vá»¥."""
        task = TaskRepository.get_task_by_id(db, task_id)
        if not task:
            raise BusinessError(
                code="NOT_FOUND", message="KhÃ´ng tÃ¬m tháº¥y nhiá»‡m vá»¥", http_status=404
            )
        return _task_to_schema(task)


# Export cÃ¡c hÃ m cÃ´ng khai
create_task = TaskService.create_task
assign_task = TaskService.assign_task
accept_task = TaskService.accept_task
reject_task = TaskService.reject_task
complete_task = TaskService.complete_task
reassign_task = TaskService.reassign_task
cancel_task = TaskService.cancel_task
