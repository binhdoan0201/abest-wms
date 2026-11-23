"""ABEST WMS - Pydantic Schemas cho Phân hệ Quản lý Nhiệm vụ (Tasks)."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CreateTaskRequest(BaseModel):
    """Dữ liệu yêu cầu tạo nhiệm vụ."""

    task_type: str = Field(..., description="Loại task: RECEIVING, PUTAWAY, PICKING, PACKING...")
    stage: str = Field(..., description="Công đoạn: NHAN_HANG, CAT_HANG, SOAN_HANG...")
    ref_doc_type: str = Field(..., description="Loại chứng từ: PO, ASN, SO, GRN...")
    ref_doc_id: uuid.UUID = Field(..., description="ID chứng từ tham chiếu")
    zone_id: uuid.UUID | None = None
    priority: str = Field("NORMAL", description="Độ ưu tiên: LOW, NORMAL, HIGH, URGENT")


class AssignTaskRequest(BaseModel):
    """Dữ liệu yêu cầu giao nhiệm vụ cho nhân viên."""

    assigned_to_user_id: uuid.UUID = Field(..., description="ID nhân viên được giao")
    version_no: int = Field(..., description="Phiên bản lạc quan hiện tại")


class ReassignTaskRequest(BaseModel):
    """Dữ liệu yêu cầu điều chuyển nhiệm vụ sang nhân viên khác."""

    new_assigned_to_user_id: uuid.UUID = Field(..., description="ID nhân viên nhận việc mới")
    reason: str | None = Field(None, description="Lý do điều chuyển")
    version_no: int = Field(..., description="Phiên bản lạc quan hiện tại")


class AcceptTaskRequest(BaseModel):
    """Dữ liệu yêu cầu tiếp nhận nhiệm vụ."""

    version_no: int = Field(..., description="Phiên bản lạc quan hiện tại")


class RejectTaskRequest(BaseModel):
    """Dữ liệu yêu cầu từ chối nhiệm vụ."""

    rejection_reason: str = Field(..., min_length=1, description="Lý do từ chối")
    version_no: int = Field(..., description="Phiên bản lạc quan hiện tại")


class CompleteTaskRequest(BaseModel):
    """Dữ liệu yêu cầu hoàn tất nhiệm vụ."""

    completed_qty: Decimal | None = None
    version_no: int = Field(..., description="Phiên bản lạc quan hiện tại")


class CancelTaskRequest(BaseModel):
    """Dữ liệu yêu cầu hủy nhiệm vụ."""

    cancel_reason: str | None = Field(None, description="Lý do hủy nhiệm vụ")
    version_no: int = Field(..., description="Phiên bản lạc quan hiện tại")


class TaskResponse(BaseModel):
    """Thông tin nhiệm vụ trả về."""

    model_config = ConfigDict(from_attributes=True)

    task_id: uuid.UUID
    warehouse_id: uuid.UUID
    task_type: str
    stage: str
    zone_id: uuid.UUID | None = None
    ref_doc_type: str
    ref_doc_id: uuid.UUID
    priority: str
    status: str
    assigned_to: uuid.UUID | None = None
    assigned_by: uuid.UUID | None = None
    sla_due_at: datetime | None = None
    progress_pct: str
    completed_qty: str
    rejection_reason: str | None = None
    version_no: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
