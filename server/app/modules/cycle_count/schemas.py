"""ABEST WMS - Pydantic Schemas cho Phân hệ Kiểm kê (Cycle Count)."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CreateCycleCountRequest(BaseModel):
    """Yêu cầu tạo phiếu kiểm kê và khóa vị trí kiểm."""

    count_type: str = "PERIODIC"
    due_at: datetime
    location_ids: list[uuid.UUID] = Field(min_length=1)


class RecordCountRequest(BaseModel):
    """Ghi nhận số lượng đếm mù cho một dòng kiểm kê."""

    blind_counted_qty: Decimal
    same_counter_override_reason: str | None = None
    anomaly_type: str | None = None


class CycleCountResponse(BaseModel):
    """Phản hồi thông tin phiếu kiểm kê."""

    count_sheet_id: uuid.UUID
    sheet_number: str
    warehouse_id: uuid.UUID
    count_type: str
    status: str
    version_no: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
