"""ABEST WMS - Pydantic Schemas cho Phân hệ Phê duyệt (Approvals)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ApproveDecisionRequest(BaseModel):
    """Yêu cầu phê duyệt hồ sơ."""

    recommendation_or_reason: str | None = None
    reauth_method: Literal["PASSWORD", "BIOMETRIC"] | None = None
    reauth_password: str | None = None
    version_no: int = Field(ge=1)


class RejectDecisionRequest(BaseModel):
    """Yêu cầu từ chối hồ sơ kèm lý do."""

    rejection_reason: str = Field(min_length=1)
    version_no: int = Field(ge=1)


class RequestInfoDecisionRequest(BaseModel):
    """Yêu cầu bổ sung thêm thông tin/chứng từ hoặc đếm lại."""

    info_required_note: str = Field(min_length=1)
    request_recount: bool = False
    version_no: int = Field(ge=1)


class EscalateTierRequest(BaseModel):
    """Thủ kho (D1) chủ động chuyển hồ sơ lên cấp trên (D2)."""

    recommendation_or_reason: str | None = None
    version_no: int = Field(ge=1)


class StockAdjustmentProposalCreate(BaseModel):
    """Đề xuất điều chỉnh tồn hoặc hủy hàng (TK-4.3, TK-5.3)."""

    adjustment_type: Literal["ADJUSTMENT", "SCRAP"]
    location_id: uuid.UUID
    sku_id: uuid.UUID
    lot_id: uuid.UUID | None = None
    source_pallet_id: uuid.UUID | None = None
    damaged_pallet_id: uuid.UUID | None = None
    qty_adjustment: Decimal
    reason_code: str = Field(min_length=1)
    proposal_photo_urls: list[str] | None = None


class ApprovalHistoryItem(BaseModel):
    """Một dòng lịch sử thao tác trên hồ sơ duyệt."""

    history_id: uuid.UUID
    tier: str
    actor_user_id: uuid.UUID | None = None
    delegated_from_user_id: uuid.UUID | None = None
    action: str
    recommendation_or_reason: str | None = None
    reauth_method: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApprovalResponse(BaseModel):
    """Phản hồi thông tin hồ sơ phê duyệt."""

    approval_id: uuid.UUID
    warehouse_id: uuid.UUID
    object_type: str
    object_id: uuid.UUID
    proposer_user_id: uuid.UUID
    current_tier: str
    status: str
    execution_status: str
    discrepancy_value_amount: Decimal
    locked_by_viewer_id: uuid.UUID | None = None
    locked_at: datetime | None = None
    sla_due_at: datetime | None = None
    final_decided_by: uuid.UUID | None = None
    final_decided_at: datetime | None = None
    version_no: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApprovalDetailResponse(ApprovalResponse):
    """Chi tiết hồ sơ phê duyệt kèm toàn bộ lịch sử."""

    histories: list[ApprovalHistoryItem] = []


class EscalateExpiredResponse(BaseModel):
    """Kết quả chạy leo thang SLA các hồ sơ quá hạn."""

    escalated_count: int
