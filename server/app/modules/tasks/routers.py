"""ABEST WMS - Bộ định tuyến API (Routers) cho Phân hệ Nhiệm vụ (Tasks).

Khai báo các endpoint theo Mục 4.7 Chuẩn API:
- GET /tasks (nhân viên thực thi chỉ xem task của mình; thukho, quanly xem tất cả)
- GET /tasks/{id}
- POST /tasks (thukho, quanly)
- POST /tasks/{id}/assign (thukho, quanly)
- POST /tasks/{id}/accept (nhân viên được giao)
- POST /tasks/{id}/reject (nhân viên được giao)
- POST /tasks/{id}/complete (nhân viên được giao)
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query

from server.app.core.database import DbSession, get_db
from server.app.core.exceptions import BusinessError
from server.app.core.rbac import UserContext, get_current_user
from server.app.core.responses import success_response
from server.app.modules.tasks.schemas import (
    AcceptTaskRequest,
    AssignTaskRequest,
    CompleteTaskRequest,
    CreateTaskRequest,
    RejectTaskRequest,
)
from server.app.modules.tasks.services import TaskService

router = APIRouter(prefix="/tasks", tags=["Tasks"])

WORKER_ROLES = {"nv-nhan", "nv-cat", "nv-soan", "nv-dongoi", "nv-kiemke"}
SUPERVISOR_ROLES = {"thukho", "quanly"}


@router.get("", summary="Danh sách nhiệm vụ")
def get_tasks(
    scope: str = Query("all", description="Phạm vi: mine, queue, all"),
    status: str | None = Query(None, description="Lọc theo trạng thái"),
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    """Danh sách nhiệm vụ.

    Nhân viên thực thi chỉ thấy nhiệm vụ của mình.
    Thủ kho, Quản lý có thể xem tất cả trong kho.
    """
    if not user_ctx.warehouse_id:
        raise BusinessError(code="NOT_FOUND", message="Chưa gán kho", http_status=404)

    # Nhân viên thực thi luôn bị giới hạn chỉ thấy task của chính mình
    if user_ctx.role_code in WORKER_ROLES or scope == "mine":
        worker_filter: uuid.UUID | None = user_ctx.user_id
    elif user_ctx.role_code in SUPERVISOR_ROLES:
        worker_filter = None
    else:
        raise BusinessError(code="FORBIDDEN", message="Không có quyền truy cập", http_status=403)

    tasks = TaskService.get_tasks(
        db=db,
        warehouse_id=user_ctx.warehouse_id,
        worker_id=worker_filter,
        status=status,
    )
    return success_response(data=[t.model_dump() for t in tasks], total=len(tasks))


@router.get("/{task_id}", summary="Chi tiết nhiệm vụ")
def get_task_detail(
    task_id: uuid.UUID,
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    """Chi tiết một nhiệm vụ."""
    task = TaskService.get_task_by_id(db, task_id)
    if not user_ctx.warehouse_id or task.warehouse_id != user_ctx.warehouse_id:
        raise BusinessError(code="NOT_FOUND", message="Không tìm thấy nhiệm vụ", http_status=404)

    # Nhân viên thực thi chỉ được xem task được giao cho mình
    if user_ctx.role_code in WORKER_ROLES and task.assigned_to != user_ctx.user_id:
        raise BusinessError(
            code="FORBIDDEN", message="Không có quyền xem nhiệm vụ này", http_status=403
        )

    return success_response(data=task.model_dump())


@router.post("", summary="Tạo nhiệm vụ thủ công")
def create_task_endpoint(
    req: CreateTaskRequest,
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    """Tạo mới nhiệm vụ (Thủ kho, Quản lý)."""
    if user_ctx.role_code not in SUPERVISOR_ROLES:
        raise BusinessError(
            code="FORBIDDEN",
            message="Chỉ Thủ kho hoặc Quản lý mới được tạo nhiệm vụ thủ công",
            http_status=403,
        )

    if not user_ctx.warehouse_id:
        raise BusinessError(code="NOT_FOUND", message="Chưa gán kho", http_status=404)

    task = TaskService.create_task(
        db=db,
        warehouse_id=user_ctx.warehouse_id,
        creator_id=user_ctx.user_id,
        req=req,
    )
    return success_response(data=task.model_dump())


@router.post("/{task_id}/assign", summary="Giao nhiệm vụ cho nhân viên")
def assign_task_endpoint(
    task_id: uuid.UUID,
    req: AssignTaskRequest,
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    """Giao nhiệm vụ cho nhân viên (Thủ kho, Quản lý)."""
    if user_ctx.role_code not in SUPERVISOR_ROLES:
        raise BusinessError(
            code="FORBIDDEN", message="Không có quyền giao nhiệm vụ", http_status=403
        )

    task = TaskService.assign_task(
        db=db,
        task_id=task_id,
        assigner_id=user_ctx.user_id,
        req=req,
    )
    return success_response(data=task.model_dump())


@router.post("/{task_id}/accept", summary="Nhận nhiệm vụ")
def accept_task_endpoint(
    task_id: uuid.UUID,
    req: AcceptTaskRequest,
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    """Nhân viên nhận nhiệm vụ được giao."""
    task = TaskService.accept_task(
        db=db,
        task_id=task_id,
        worker_id=user_ctx.user_id,
        req=req,
    )
    return success_response(data=task.model_dump())


@router.post("/{task_id}/reject", summary="Từ chối nhiệm vụ")
def reject_task_endpoint(
    task_id: uuid.UUID,
    req: RejectTaskRequest,
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    """Nhân viên từ chối nhiệm vụ kèm lý do."""
    task = TaskService.reject_task(
        db=db,
        task_id=task_id,
        worker_id=user_ctx.user_id,
        req=req,
    )
    return success_response(data=task.model_dump())


@router.post("/{task_id}/complete", summary="Hoàn tất nhiệm vụ")
def complete_task_endpoint(
    task_id: uuid.UUID,
    req: CompleteTaskRequest,
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    """Nhân viên hoàn tất nhiệm vụ."""
    task = TaskService.complete_task(
        db=db,
        task_id=task_id,
        worker_id=user_ctx.user_id,
        req=req,
    )
    return success_response(data=task.model_dump())


@router.post("/{task_id}/reassign", summary="Điều chuyển nhiệm vụ sang nhân viên/khu vực khác")
def reassign_task_endpoint(
    task_id: uuid.UUID,
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    """Điều chuyển nhiệm vụ (TODO: chủ module hoàn thiện ở pha sau)."""
    raise BusinessError(
        code="NOT_IMPLEMENTED", message="Chức năng đang phát triển", http_status=501
    )


@router.post("/{task_id}/cancel", summary="Hủy nhiệm vụ")
def cancel_task_endpoint(
    task_id: uuid.UUID,
    user_ctx: UserContext = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict[str, Any]:
    """Hủy nhiệm vụ (TODO: chủ module hoàn thiện ở pha sau)."""
    raise BusinessError(
        code="NOT_IMPLEMENTED", message="Chức năng đang phát triển", http_status=501
    )
