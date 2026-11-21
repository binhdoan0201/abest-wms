"""ABEST WMS - Pydantic Schemas cho Phân hệ Xuất kho (Outbound)."""

import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class AllocateOrderRequest(BaseModel):
    """Yêu cầu cấp phát hàng cho đơn xuất theo quy tắc FEFO/FIFO."""

    picking_rule: str = "FEFO"


class CreatePickSessionRequest(BaseModel):
    """Yêu cầu tạo phiên lấy hàng."""

    order_ids: list[uuid.UUID]
    pick_mode: str = "DISCRETE"


class ConfirmPickLineRequest(BaseModel):
    """Xác nhận lấy hàng cho một dòng trong phiên pick."""

    actual_lot_id: uuid.UUID | None = None
    qty_picked: Decimal
    target_tote_barcode: str | None = None
    serial_numbers: list[str] = Field(default_factory=list)


class PickLineExceptionRequest(BaseModel):
    """Báo cáo ngoại lệ khi lấy hàng (thiếu, hư, sai lô)."""

    exception_reason: str
    qty_actual: Decimal = Decimal("0.000")


class CreatePackageRequest(BaseModel):
    """Đóng gói: tạo kiện và danh sách dòng kiện."""

    box_type_id: uuid.UUID | None = None
    weight_kg: Decimal = Decimal("0.000")
    items: list[dict[str, Any]] = Field(default_factory=list)


class CreateGoodsIssueRequest(BaseModel):
    """Lập phiếu xuất kho GI."""

    order_id: uuid.UUID
    vehicle_id: uuid.UUID | None = None
    total_packages: int = 1


class ConfirmGoodsIssueRequest(BaseModel):
    """Xác nhận giao hàng và trừ tồn kho."""

    driver_signature_data: str | None = None
    version_no: int = 1


class DecideOrderChangeRequest(BaseModel):
    """Quản lý chốt yêu cầu đổi/hủy đơn từ ERP."""

    decision: str  # ACCEPT hoặc REJECT
    reject_reason_code: str | None = None
    reject_note: str | None = None
