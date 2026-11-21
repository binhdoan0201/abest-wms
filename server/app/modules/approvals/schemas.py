"""ABEST WMS - Pydantic Schemas cho Phân hệ Phê duyệt (Approvals)."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ApproveDecisionRequest(BaseModel):
    """Yêu cầu phê duyệt hồ sơ."""

    recommendation_or_reason: str | None = None
    reauth_method: str | None = None  # Bắt buộc nếu giá trị vượt ngưỡng reauth_min_amount
    version_no: int = 1


class RejectDecisionRequest(BaseModel):
    """Yêu cầu từ chối hồ sơ kèm lý do."""

    rejection_reason: str
    version_no: int = 1


class RequestInfoDecisionRequest(BaseModel):
    """Yêu cầu bổ sung thêm thông tin/chứng từ."""

    info_required_note: str
    version_no: int = 1


class ApprovalResponse(BaseModel):
    """Phản hồi thông tin hồ sơ phê duyệt."""

    approval_id: uuid.UUID
    warehouse_id: uuid.UUID
    object_type: str
    object_id: uuid.UUID
    current_tier: str
    status: str
    discrepancy_value_amount: Decimal
    version_no: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
