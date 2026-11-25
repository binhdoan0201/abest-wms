"""ABEST WMS - Pydantic Schemas cho Phân hệ Xuất kho (Outbound)."""

import uuid
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class AllocateOrderRequest(BaseModel):
    """Yêu cầu cấp phát tồn kho FEFO/FIFO cho đơn xuất."""

    strategy: Literal["FEFO", "FIFO"] | None = Field(
        default=None,
        description="Chiến lược cấp phát: FEFO hoặc FIFO (mặc định theo cấu hình kho)",
        examples=["FEFO"],
    )
    version_no: int | None = Field(
        default=None,
        ge=1,
        description="Khóa lạc quan phiên bản hiện tại của đơn xuất kho",
        examples=[1],
    )


class CreatePickSessionRequest(BaseModel):
    """Tạo phiên soạn hàng từ một hoặc nhiều đơn xuất."""

    order_ids: list[uuid.UUID] = Field(
        min_length=1,
        description="Danh sách ID đơn xuất kho đã cấp phát tồn kho",
    )
    picker_user_id: uuid.UUID | None = Field(
        default=None,
        description="ID nhân viên soạn hàng (nv-soan) được phân công",
    )
    pick_mode: Literal["SINGLE_ORDER", "BATCH", "WAVE"] = Field(
        default="SINGLE_ORDER",
        description="Chế độ soạn hàng: SINGLE_ORDER, BATCH hoặc WAVE",
        examples=["SINGLE_ORDER"],
    )
    shift_id: uuid.UUID | None = Field(
        default=None,
        description="ID ca làm việc hiện tại",
    )


class ConfirmPickLineRequest(BaseModel):
    """Xác nhận soạn một dòng hàng."""

    actual_lot_id: uuid.UUID | None = Field(
        default=None,
        description="ID lô thực tế lấy (nếu thay đổi so với lô gợi ý)",
    )
    qty_picked: Decimal = Field(
        gt=Decimal("0"),
        description="Số lượng thực tế lấy được (nếu thiếu phải báo exception)",
        examples=["10.000"],
    )
    target_tote_barcode: str | None = Field(
        default=None,
        max_length=50,
        description="Mã vạch rổ/tote chứa hàng soạn",
        examples=["TOTE-001"],
    )
    staged_location_id: uuid.UUID | None = Field(
        default=None,
        description="ID vị trí tập kết STAGING đích",
    )
    serial_numbers: list[str] = Field(
        default_factory=list,
        description="Danh sách số serial đã quét",
    )
    version_no: int | None = Field(
        default=None,
        ge=1,
        description="Khóa lạc quan phiên bản hiện tại của phiên soạn hàng",
        examples=[1],
    )


class PickLineExceptionRequest(BaseModel):
    """Báo cáo ngoại lệ khi lấy hàng (thiếu, hư hỏng, sai lô)."""

    exception_reason: str = Field(
        min_length=1,
        max_length=50,
        description="Mã lý do ngoại lệ hợp lệ trong danh mục reason_codes",
        examples=["SHORT_STOCK"],
    )
    exception_type: Literal["EXCEPTION_SHORT", "EXCEPTION_DAMAGED", "EXCEPTION_WRONG_LOT"] = Field(
        default="EXCEPTION_SHORT",
        description="Loại ngoại lệ soạn hàng",
        examples=["EXCEPTION_SHORT"],
    )
    qty_actual: Decimal = Field(
        default=Decimal("0.000"),
        ge=Decimal("0"),
        description="Số lượng thực tế lấy được tại kệ",
        examples=["2.000"],
    )
    version_no: int | None = Field(
        default=None,
        ge=1,
        description="Khóa lạc quan phiên bản hiện tại của phiên soạn hàng",
        examples=[1],
    )


class PackageLineInput(BaseModel):
    """Chi tiết từng mặt hàng đóng vào kiện."""

    order_line_id: uuid.UUID
    sku_id: uuid.UUID
    lot_id: uuid.UUID | None = None
    qty: Decimal = Field(gt=Decimal("0"), examples=["5.000"])
    serial_numbers: list[str] = Field(default_factory=list)


class CreatePackageRequest(BaseModel):
    """Đóng gói: tạo kiện hàng và danh sách dòng kiện."""

    box_type_id: uuid.UUID | None = None
    pick_session_id: uuid.UUID | None = None
    weight_kg: Decimal = Field(default=Decimal("0.100"), gt=Decimal("0"), examples=["2.500"])
    length_cm: Decimal | None = Field(default=None, gt=Decimal("0"), examples=["40.00"])
    width_cm: Decimal | None = Field(default=None, gt=Decimal("0"), examples=["30.00"])
    height_cm: Decimal | None = Field(default=None, gt=Decimal("0"), examples=["20.00"])
    items: list[PackageLineInput] = Field(default_factory=list)
    version_no: int | None = Field(
        default=None,
        ge=1,
        description="Khóa lạc quan phiên bản hiện tại của đơn xuất kho",
        examples=[3],
    )


class CreateGoodsIssueRequest(BaseModel):
    """Lập phiếu xuất kho GI."""

    order_id: uuid.UUID
    vehicle_id: uuid.UUID | None = None
    tms_waybill_code: str | None = Field(default=None, max_length=100, examples=["WB-2026-0001"])
    version_no: int | None = Field(
        default=None,
        ge=1,
        description="Khóa lạc quan phiên bản hiện tại của đơn xuất kho",
        examples=[4],
    )


class ConfirmGoodsIssueRequest(BaseModel):
    """Xác nhận bàn giao vận chuyển và trừ tồn kho."""

    driver_signature_data: str | None = Field(
        default=None,
        description="Dữ liệu chữ ký điện tử của tài xế",
        examples=["data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."],
    )
    handover_photo_urls: list[str] = Field(
        default_factory=list,
        description="Danh sách URL ảnh chụp bàn giao hàng lên xe",
    )
    version_no: int | None = Field(
        default=None,
        ge=1,
        description="Khóa lạc quan phiên bản hiện tại của phiếu xuất kho GI",
        examples=[1],
    )


class DecideOrderChangeRequest(BaseModel):
    """Quản lý chốt yêu cầu đổi/hủy đơn từ ERP."""

    decision: Literal["ACCEPT", "REJECT"] = Field(
        ...,
        description="Quyết định của Quản lý kho: ACCEPT hoặc REJECT",
        examples=["ACCEPT"],
    )
    reject_reason_code: str | None = Field(default=None, max_length=50)
    reject_note: str | None = Field(default=None, max_length=500)


class OutboundActionResponse(BaseModel):
    """Cấu trúc dữ liệu phản hồi linh hoạt cho các nghiệp vụ Outbound."""

    payload: dict[str, Any]
