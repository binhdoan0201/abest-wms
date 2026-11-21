"""ABEST WMS - Tầng Nghiệp vụ (Service) cho Phân hệ Nhiệm vụ (Tasks).

Triển khai bản tối thiểu chạy được cho các hàm:
- create_task
- assign_task
- accept_task
- reject_task
- complete_task
Kiểm tra luồng trạng thái hợp lệ và kiểm soát đồng thời qua version_no.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from server.app.core.audit import create_audit_log
from server.app.core.exceptions import BusinessError
from server.app.modules.tasks.models import Task
from server.app.modules.tasks.repositories import TaskRepository
from server.app.modules.tasks.schemas import (
    AcceptTaskRequest,
    AssignTaskRequest,
    CompleteTaskRequest,
    CreateTaskRequest,
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


class TaskService:
    """Service điều phối vòng đời nhiệm vụ trong kho."""

    # TODO (Chủ module D): Tự động giao task theo kỹ năng, chứng chỉ và tải công việc
    # TODO (Chủ module D): Cảnh báo và leo thang SLA tự động (sla_due_at)
    # TODO (Chủ module D): Điều chuyển task qua khu vực (reassign) giữa các nhân viên

    @staticmethod
    def create_task(
        db: Session,
        warehouse_id: uuid.UUID,
        creator_id: uuid.UUID,
        req: CreateTaskRequest,
    ) -> TaskResponse:
        """Tạo mới nhiệm vụ với trạng thái ban đầu UNASSIGNED."""
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
            version_no=1,
        )
        saved_task = TaskRepository.create_task(db, task)

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
    ) -> TaskResponse:
        """Giao nhiệm vụ cho nhân viên (chuyển sang ASSIGNED)."""
        task = TaskRepository.get_task_by_id(db, task_id)
        if not task:
            raise BusinessError(
                code="NOT_FOUND", message="Không tìm thấy nhiệm vụ", http_status=404
            )

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

        task.assigned_to = req.assigned_to
        task.assigned_by = assigner_id
        task.status = "ASSIGNED"
        task.rejection_reason = None
        task.version_no += 1

        create_audit_log(
            db,
            action_code="TASK_ASSIGN",
            entity_name="tasks",
            actor_user_id=assigner_id,
            warehouse_id=task.warehouse_id,
            entity_id=task.task_id,
            new_values={"assigned_to": str(req.assigned_to), "status": "ASSIGNED"},
        )
        return _task_to_schema(task)

    @staticmethod
    def accept_task(
        db: Session,
        task_id: uuid.UUID,
        worker_id: uuid.UUID,
        req: AcceptTaskRequest,
    ) -> TaskResponse:
        """Nhân viên nhận nhiệm vụ (chuyển sang IN_PROGRESS)."""
        task = TaskRepository.get_task_by_id(db, task_id)
        if not task:
            raise BusinessError(
                code="NOT_FOUND", message="Không tìm thấy nhiệm vụ", http_status=404
            )

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
    ) -> TaskResponse:
        """Nhân viên từ chối nhiệm vụ kèm lý do (chuyển sang REJECTED)."""
        task = TaskRepository.get_task_by_id(db, task_id)
        if not task:
            raise BusinessError(
                code="NOT_FOUND", message="Không tìm thấy nhiệm vụ", http_status=404
            )

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

        create_audit_log(
            db,
            action_code="TASK_CANCEL",
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
    ) -> TaskResponse:
        """Hoàn tất nhiệm vụ (chuyển sang COMPLETED, tiến độ 100%)."""
        task = TaskRepository.get_task_by_id(db, task_id)
        if not task:
            raise BusinessError(
                code="NOT_FOUND", message="Không tìm thấy nhiệm vụ", http_status=404
            )

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
    def get_tasks(
        db: Session,
        warehouse_id: uuid.UUID,
        worker_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[TaskResponse]:
        """Lấy danh sách nhiệm vụ."""
        tasks = TaskRepository.get_tasks(
            db=db,
            warehouse_id=warehouse_id,
            assigned_to=worker_id,
            status=status,
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
accept_task = TaskService.accept_task
reject_task = TaskService.reject_task
complete_task = TaskService.complete_task
