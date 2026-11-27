"""ABEST WMS - Pydantic Schemas cho Phân hệ Nhập kho (Inbound)."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CreateGrnRequest(BaseModel):
    """Dữ liệu tạo mới phiếu nhập kho GRN."""

    po_id: uuid.UUID | None = None
    asn_id: uuid.UUID | None = None
    is_blind_receipt: bool | None = None


class GrnLineCountRequest(BaseModel):
    """Dữ liệu ghi nhận một dòng kiểm đếm GRN."""

    po_line_id: uuid.UUID | None = None
    sku_id: uuid.UUID
    lot_id: uuid.UUID | None = None
    lot_number: str | None = None
    manufacture_date: date | None = None
    expiry_date: date | None = None
    uom_code: str = Field(min_length=1)
    qty_actual: Decimal
    qty_damaged: Decimal = Decimal("0.000")
    serial_numbers: list[str] | None = None
    reason_code: str | None = None
    damage_photo_urls: list[str] = Field(default_factory=list)
    notes: str | None = None
    version_no: int = Field(ge=1)


class SubmitGrnRequest(BaseModel):
    """Dữ liệu nộp phiếu nhập kho GRN."""

    version_no: int = Field(ge=1)


class RecountLineItem(BaseModel):
    """Dòng cập nhật số lượng khi đếm lại GRN."""

    grn_line_id: uuid.UUID
    qty_actual: Decimal
    qty_damaged: Decimal = Decimal("0.000")


class RecountGrnRequest(BaseModel):
    """Dữ liệu đếm lại GRN."""

    version_no: int = Field(ge=1)
    lines: list[RecountLineItem] = Field(min_length=1)


class CompleteGrnRequest(BaseModel):
    """Dữ liệu hoàn tất phiếu nhập kho GRN."""

    version_no: int = Field(ge=1)


class PutawaySuggestRequest(BaseModel):
    """Yêu cầu gợi ý vị trí cất hàng cho pallet."""

    pallet_id: uuid.UUID


class PutawayLineItem(BaseModel):
    """Chi tiết dòng hàng khi cất một phần pallet."""

    sku_id: uuid.UUID
    lot_id: uuid.UUID | None = None
    serial_number: str | None = None
    qty: Decimal


class PutawayConfirmRequest(BaseModel):
    """Xác nhận cất pallet vào vị trí."""

    location_id: uuid.UUID
    scanned_pallet_code: str | None = None
    scanned_location_barcode: str | None = None
    lines: list[PutawayLineItem] | None = None
    version_no: int = Field(ge=1)


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
