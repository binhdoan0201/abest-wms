"""ABEST WMS - Tầng Nghiệp vụ (Service) cho Phân hệ Nhiệm vụ (Tasks).

Triển khai đầy đủ các nghiệp vụ D-01, D-02:
- create_task (tự tính `sla_due_at`, hỗ trợ `auto_assign` giao ngay cho người ít việc nhất)
- assign_task / auto_assign_task / auto_assign_queue (giao tự động cùng khâu, can_receive_tasks)
- update_task_priority (đổi mức ưu tiên NORMAL / HIGH / URGENT, có audit log)
- accept_task / reject_task / complete_task
- reassign_task (điều chuyển task sang nhân viên khác, reset `started_at`)
- cancel_task (hủy task chưa hoàn tất)
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

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
    UpdateTaskPriorityRequest,
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
    warehouse_id: uuid.UUID,
    for_update: bool = True,
) -> Task:
    """Lấy nhiệm vụ và xác thực thuộc đúng kho của người thao tác (quy tắc 5.4.1)."""
    task = TaskRepository.get_task_by_id(db, task_id, for_update=for_update)
    if not task or task.warehouse_id != warehouse_id:
        raise BusinessError(code="NOT_FOUND", message="Không tìm thấy nhiệm vụ", http_status=404)
    return task


def _is_user_eligible_for_task(
    user_info: dict[str, Any],
    stage: str,
    now: datetime,
) -> bool:
    """Kiểm tra nhân viên đủ điều kiện nhận việc (tương thích `can_receive_tasks`)."""
    if user_info.get("status") != "ACTIVE":
        return False

    role_code = str(user_info.get("role_code") or "")
    is_executor = role_code.startswith("nv-")
    is_mgmt_general = stage == "QUAN_LY_CHUNG" and role_code in {"thukho", "quanly"}
    if not is_executor and not is_mgmt_general:
        return False

    if user_info.get("primary_stage") != stage:
        return False

    if user_info.get("is_seasonal"):
        if not user_info.get("is_safety_checked"):
            return False
        valid_from = user_info.get("valid_from")
        valid_until = user_info.get("valid_until")
        if (valid_from is not None and now < valid_from) or (
            valid_until is not None and now > valid_until
        ):
            return False

    return True


def _check_assignee(db: Session, task: Task, user_id: uuid.UUID) -> None:
    """Kiểm tra người nhận việc: tồn tại, cùng kho, ACTIVE, đúng vai trò/khâu, an toàn thời vụ và
    giới hạn task mở."""
    user_info = TaskRepository.lock_user_for_assignment(db, user_id)
    if user_info is None:
        raise BusinessError(
            code="NOT_FOUND",
            message="Không tìm thấy nhân viên được giao",
            http_status=404,
        )

    if user_info["primary_warehouse_id"] != task.warehouse_id:
        raise BusinessError(
            code="FORBIDDEN",
            message="Nhân viên không thuộc kho của nhiệm vụ này",
            http_status=403,
        )

    if user_info["status"] != "ACTIVE":
        raise BusinessError(
            code="INVALID_STATE",
            message="Tài khoản nhân viên không ở trạng thái hoạt động (ACTIVE)",
            http_status=409,
        )

    role_code = str(user_info["role_code"] or "")
    is_executor = role_code.startswith("nv-")
    is_mgmt_general = task.stage == "QUAN_LY_CHUNG" and role_code in {"thukho", "quanly"}
    if not is_executor and not is_mgmt_general:
        raise BusinessError(
            code="FORBIDDEN",
            message="Người được giao không có vai trò nhân viên thực thi hợp lệ",
            http_status=403,
        )

    if user_info["is_seasonal"]:
        if not user_info["is_safety_checked"]:
            raise BusinessError(
                code="FORBIDDEN",
                message="Nhân viên thời vụ chưa hoàn tất kiểm tra an toàn lao động",
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
                message="Thời hạn làm việc của nhân viên thời vụ không hợp lệ hoặc đã hết hạn",
                http_status=403,
            )

    if user_info["primary_stage"] != task.stage:
        raise BusinessError(
            code="TASKS_STAGE_MISMATCH",
            message="Nhân viên không thuộc khâu làm việc của nhiệm vụ này",
            http_status=409,
        )

    limit = TaskRepository.get_max_open_tasks(db, task.warehouse_id)
    if TaskRepository.count_open_tasks_for_user(db, user_id, task.warehouse_id) >= limit:
        raise BusinessError(
            code="TASKS_MAX_OPEN_EXCEEDED",
            message=f"Nhân viên đang giữ tối đa {limit} nhiệm vụ mở",
            http_status=409,
        )


def _try_auto_assign_single_task(
    db: Session,
    task: Task,
    assigner_id: uuid.UUID,
) -> bool:
    """Tìm nhân viên cùng khâu đang ít task mở nhất và có `can_receive_tasks = True` để giao."""
    if task.status not in ("UNASSIGNED", "REJECTED"):
        return False

    limit = TaskRepository.get_max_open_tasks(db, task.warehouse_id)
    candidates = TaskRepository.list_stage_candidates_for_auto_assign(
        db, task.warehouse_id, task.stage
    )
    now = datetime.now(timezone.utc)

    best_candidate: dict[str, Any] | None = None
    best_open_count = limit + 1

    for cand in candidates:
        if not _is_user_eligible_for_task(cand, task.stage, now):
            continue
        open_count = int(cand.get("open_tasks") or 0)
        if open_count >= limit:
            continue
        if open_count < best_open_count:
            best_open_count = open_count
            best_candidate = cand

    if best_candidate is None:
        return False

    chosen_user_id = uuid.UUID(str(best_candidate["user_id"]))
    task.assigned_to = chosen_user_id
    task.assigned_by = assigner_id
    task.status = "ASSIGNED"
    task.rejection_reason = None
    task.version_no += 1
    db.flush()

    create_audit_log(
        db,
        action_code="TASK_AUTO_ASSIGN",
        entity_name="tasks",
        actor_user_id=assigner_id,
        warehouse_id=task.warehouse_id,
        entity_id=task.task_id,
        new_values={
            "assigned_to": str(chosen_user_id),
            "status": "ASSIGNED",
            "open_tasks_before": best_open_count,
        },
    )
    return True


class TaskService:
    """Service điều phối vòng đời nhiệm vụ trong kho."""

    @staticmethod
    def create_task(
        db: Session,
        warehouse_id: uuid.UUID,
        creator_id: uuid.UUID,
        req: CreateTaskRequest,
        auto_assign: bool = False,
    ) -> TaskResponse:
        """Tạo mới nhiệm vụ (tự tính `sla_due_at`, tự giao nếu `auto_assign=True`)."""
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

        if auto_assign or getattr(req, "auto_assign", False):
            _try_auto_assign_single_task(db, saved_task, creator_id)

        return _task_to_schema(saved_task)

    @staticmethod
    def auto_assign_queue(
        db: Session,
        warehouse_id: uuid.UUID,
        assigner_id: uuid.UUID,
        stage: str | None = None,
    ) -> list[TaskResponse]:
        """Tự động giao nhiệm vụ đang chờ (UNASSIGNED/REJECTED) cho người ít việc nhất."""
        queue_tasks = TaskRepository.get_queue_tasks_for_auto_assign(
            db, warehouse_id=warehouse_id, stage=stage
        )
        assigned_tasks: list[TaskResponse] = []
        for task in queue_tasks:
            if _try_auto_assign_single_task(db, task, assigner_id):
                assigned_tasks.append(_task_to_schema(task))
        return assigned_tasks

    @staticmethod
    def update_task_priority(
        db: Session,
        task_id: uuid.UUID,
        actor_id: uuid.UUID,
        req: UpdateTaskPriorityRequest,
        warehouse_id: uuid.UUID,
    ) -> TaskResponse:
        """Đổi mức độ ưu tiên của nhiệm vụ (NORMAL / HIGH / URGENT) và ghi audit log."""
        task = _get_task_in_warehouse(db, task_id, warehouse_id, for_update=True)

        if req.version_no != task.version_no:
            raise BusinessError(
                code="VERSION_CONFLICT",
                message="Nhiệm vụ đã được cập nhật bởi thao tác khác",
                http_status=409,
                details={"current_version_no": task.version_no},
            )

        if task.status in ("COMPLETED", "CANCELLED"):
            raise BusinessError(
                code="INVALID_STATE",
                message=f"Không thể đổi độ ưu tiên nhiệm vụ đang ở trạng thái `{task.status}`",
                http_status=409,
            )

        old_priority = task.priority
        if old_priority == req.priority:
            return _task_to_schema(task)

        task.priority = req.priority
        task.version_no += 1
        db.flush()

        create_audit_log(
            db,
            action_code="TASK_UPDATE_PRIORITY",
            entity_name="tasks",
            actor_user_id=actor_id,
            warehouse_id=task.warehouse_id,
            entity_id=task.task_id,
            old_values={"priority": old_priority},
            new_values={"priority": req.priority},
        )
        return _task_to_schema(task)

    @staticmethod
    def assign_task(
        db: Session,
        task_id: uuid.UUID,
        assigner_id: uuid.UUID,
        req: AssignTaskRequest,
        warehouse_id: uuid.UUID,
    ) -> TaskResponse:
        """Giao nhiệm vụ cho nhân viên (chuyển sang ASSIGNED)."""
        task = _get_task_in_warehouse(db, task_id, warehouse_id, for_update=True)

        if req.version_no != task.version_no:
            raise BusinessError(
                code="VERSION_CONFLICT",
                message="Nhiệm vụ đã được cập nhật bởi thao tác khác",
                http_status=409,
                details={"current_version_no": task.version_no},
            )

        if task.status not in ("UNASSIGNED", "REJECTED"):
            raise BusinessError(
                code="INVALID_STATE",
                message=f"Không thể giao nhiệm vụ đang ở trạng thái `{task.status}`",
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
        warehouse_id: uuid.UUID,
    ) -> TaskResponse:
        """Nhân viên nhận nhiệm vụ (chuyển sang IN_PROGRESS)."""
        task = _get_task_in_warehouse(db, task_id, warehouse_id, for_update=True)

        if str(task.assigned_to) != str(worker_id):
            raise BusinessError(
                code="FORBIDDEN",
                message="Bạn không phải nhân viên được giao nhiệm vụ này",
                http_status=403,
            )

        if req.version_no != task.version_no:
            raise BusinessError(
                code="VERSION_CONFLICT",
                message="Nhiệm vụ đã được cập nhật bởi thao tác khác",
                http_status=409,
                details={"current_version_no": task.version_no},
            )

        if task.status != "ASSIGNED":
            raise BusinessError(
                code="INVALID_STATE",
                message=(
                    f"Chỉ có thể nhận nhiệm vụ khi ở trạng thái ASSIGNED "
                    f"(hiện tại: `{task.status}`)"
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
        warehouse_id: uuid.UUID,
    ) -> TaskResponse:
        """Nhân viên từ chối nhiệm vụ kèm lý do (chuyển sang REJECTED)."""
        task = _get_task_in_warehouse(db, task_id, warehouse_id, for_update=True)

        if str(task.assigned_to) != str(worker_id):
            raise BusinessError(
                code="FORBIDDEN",
                message="Bạn không phải nhân viên được giao nhiệm vụ này",
                http_status=403,
            )

        if req.version_no != task.version_no:
            raise BusinessError(
                code="VERSION_CONFLICT",
                message="Nhiệm vụ đã được cập nhật bởi thao tác khác",
                http_status=409,
                details={"current_version_no": task.version_no},
            )

        if task.status != "ASSIGNED":
            raise BusinessError(
                code="INVALID_STATE",
                message=(
                    f"Chỉ có thể từ chối nhiệm vụ khi ở trạng thái ASSIGNED "
                    f"(hiện tại: `{task.status}`)"
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
        warehouse_id: uuid.UUID,
    ) -> TaskResponse:
        """Hoàn tất nhiệm vụ (chuyển sang COMPLETED, tiến độ 100%)."""
        task = _get_task_in_warehouse(db, task_id, warehouse_id, for_update=True)

        if str(task.assigned_to) != str(worker_id):
            raise BusinessError(
                code="FORBIDDEN",
                message="Bạn không phải nhân viên được giao nhiệm vụ này",
                http_status=403,
            )

        if req.version_no != task.version_no:
            raise BusinessError(
                code="VERSION_CONFLICT",
                message="Nhiệm vụ đã được cập nhật bởi thao tác khác",
                http_status=409,
                details={"current_version_no": task.version_no},
            )

        if task.status != "IN_PROGRESS":
            raise BusinessError(
                code="INVALID_STATE",
                message=(
                    f"Chỉ có thể hoàn tất nhiệm vụ khi ở trạng thái IN_PROGRESS "
                    f"(hiện tại: `{task.status}`)"
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
        warehouse_id: uuid.UUID,
    ) -> TaskResponse:
        """Điều chuyển nhiệm vụ sang nhân viên khác."""
        task = _get_task_in_warehouse(db, task_id, warehouse_id, for_update=True)

        if req.version_no != task.version_no:
            raise BusinessError(
                code="VERSION_CONFLICT",
                message="Nhiệm vụ đã được cập nhật bởi thao tác khác",
                http_status=409,
                details={"current_version_no": task.version_no},
            )

        if task.status in ("COMPLETED", "CANCELLED"):
            raise BusinessError(
                code="INVALID_STATE",
                message=f"Không thể điều chuyển nhiệm vụ đang ở trạng thái `{task.status}`",
                http_status=409,
            )

        if task.assigned_to == req.new_assigned_to_user_id:
            raise BusinessError(
                code="INVALID_STATE",
                message="Nhiệm vụ đang do chính nhân viên này giữ",
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
        warehouse_id: uuid.UUID,
    ) -> TaskResponse:
        """Hủy nhiệm vụ chưa hoàn tất."""
        task = _get_task_in_warehouse(db, task_id, warehouse_id, for_update=True)

        if req.version_no != task.version_no:
            raise BusinessError(
                code="VERSION_CONFLICT",
                message="Nhiệm vụ đã được cập nhật bởi thao tác khác",
                http_status=409,
                details={"current_version_no": task.version_no},
            )

        if task.status in ("COMPLETED", "CANCELLED"):
            raise BusinessError(
                code="INVALID_STATE",
                message=f"Không thể hủy nhiệm vụ đang ở trạng thái `{task.status}`",
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
        """Lấy danh sách nhiệm vụ."""
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
        """Lấy chi tiết một nhiệm vụ."""
        task = TaskRepository.get_task_by_id(db, task_id)
        if not task:
            raise BusinessError(
                code="NOT_FOUND", message="Không tìm thấy nhiệm vụ", http_status=404
            )
        return _task_to_schema(task)


# Export các hàm công khai
create_task = TaskService.create_task
assign_task = TaskService.assign_task
auto_assign_queue = TaskService.auto_assign_queue
update_task_priority = TaskService.update_task_priority
accept_task = TaskService.accept_task
reject_task = TaskService.reject_task
complete_task = TaskService.complete_task
reassign_task = TaskService.reassign_task
cancel_task = TaskService.cancel_task
