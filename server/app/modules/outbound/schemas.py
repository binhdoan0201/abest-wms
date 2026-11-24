"""ABEST WMS - Pydantic Schemas cho Phân hệ Xuất kho (Outbound)."""

import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class AllocateOrderRequest(BaseModel):
    """Yêu cầu cấp phát tồn kho FEFO/FIFO cho đơn xuất."""

    strategy: str | None = Field(default=None, description="FEFO hoặc FIFO (mặc định theo kho)")
    version_no: int | None = Field(default=None, description="Khóa lạc quan phiên bản đơn")


class CreatePickSessionRequest(BaseModel):
    """Tạo phiên soạn hàng từ một hoặc nhiều đơn xuất."""

    order_ids: list[uuid.UUID] = Field(min_length=1)
    picker_user_id: uuid.UUID | None = None
    pick_mode: str = Field(default="SINGLE_ORDER", description="SINGLE_ORDER, BATCH, WAVE")
    shift_id: uuid.UUID | None = None


class ConfirmPickLineRequest(BaseModel):
    """Xác nhận soạn một dòng hàng."""

    actual_lot_id: uuid.UUID | None = None
    qty_picked: Decimal = Field(gt=Decimal("0"))
    target_tote_barcode: str | None = None
    staged_location_id: uuid.UUID | None = None
    serial_numbers: list[str] = Field(default_factory=list)
    version_no: int | None = None


class PickLineExceptionRequest(BaseModel):
    """Báo cáo ngoại lệ khi lấy hàng (thiếu, hư hỏng, sai lô)."""

    exception_reason: str = Field(min_length=1, max_length=50)
    exception_type: str = Field(
        default="EXCEPTION_SHORT",
        description="EXCEPTION_SHORT, EXCEPTION_DAMAGED, EXCEPTION_WRONG_LOT",
    )
    qty_actual: Decimal = Field(default=Decimal("0.000"), ge=Decimal("0"))
    version_no: int | None = None


class PackageLineInput(BaseModel):
    """Chi tiết từng mặt hàng đóng vào kiện."""

    order_line_id: uuid.UUID
    sku_id: uuid.UUID
    lot_id: uuid.UUID | None = None
    qty: Decimal = Field(gt=Decimal("0"))
    serial_numbers: list[str] = Field(default_factory=list)


class CreatePackageRequest(BaseModel):
    """Đóng gói: tạo kiện hàng và danh sách dòng kiện."""

    box_type_id: uuid.UUID | None = None
    pick_session_id: uuid.UUID | None = None
    weight_kg: Decimal = Field(default=Decimal("0.100"), gt=Decimal("0"))
    length_cm: Decimal | None = None
    width_cm: Decimal | None = None
    height_cm: Decimal | None = None
    items: list[PackageLineInput] = Field(default_factory=list)
    version_no: int | None = None


class CreateGoodsIssueRequest(BaseModel):
    """Lập phiếu xuất kho GI."""

    order_id: uuid.UUID
    vehicle_id: uuid.UUID | None = None
    tms_waybill_code: str | None = None
    version_no: int | None = None


class ConfirmGoodsIssueRequest(BaseModel):
    """Xác nhận bàn giao vận chuyển và trừ tồn kho."""

    driver_signature_data: str | None = None
    handover_photo_urls: list[str] = Field(default_factory=list)
    version_no: int | None = None


class DecideOrderChangeRequest(BaseModel):
    """Quản lý chốt yêu cầu đổi/hủy đơn từ ERP."""

    decision: str = Field(description="ACCEPT hoặc REJECT")
    reject_reason_code: str | None = None
    reject_note: str | None = None


class OutboundActionResponse(BaseModel):
    """Cấu trúc dữ liệu phản hồi linh hoạt cho các nghiệp vụ Outbound."""

    payload: dict[str, Any]
