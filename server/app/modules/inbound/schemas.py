"""ABEST WMS - Pydantic Schemas cho Phân hệ Nhập kho (Inbound)."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CreateGrnRequest(BaseModel):
    """Dữ liệu tạo mới phiếu nhập kho GRN."""

    po_id: uuid.UUID | None = None
    asn_id: uuid.UUID | None = None
    is_blind_receipt: bool = True


class GrnLineCountRequest(BaseModel):
    """Dữ liệu ghi nhận một dòng kiểm đếm GRN."""

    po_line_id: uuid.UUID | None = None
    sku_id: uuid.UUID
    lot_id: uuid.UUID | None = None
    uom_code: str
    qty_actual: Decimal
    qty_damaged: Decimal = Decimal("0.000")
    serial_numbers: list[str] = Field(default_factory=list)
    reason_code: str | None = None
    version_no: int = 1


class PutawaySuggestRequest(BaseModel):
    """Yêu cầu gợi ý vị trí cất hàng cho pallet."""

    pallet_id: uuid.UUID


class PutawayConfirmRequest(BaseModel):
    """Xác nhận cất pallet vào vị trí."""

    location_id: uuid.UUID
    version_no: int = 1


class GrnResponse(BaseModel):
    """Phản hồi thông tin phiếu nhập kho."""

    grn_id: uuid.UUID
    grn_number: str
    warehouse_id: uuid.UUID
    status: str
    has_discrepancy: bool
    version_no: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
