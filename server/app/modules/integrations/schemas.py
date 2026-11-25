"""ABEST WMS - Pydantic Schemas cho Phân hệ Tích hợp (Integrations).

ERP gửi **mã** (mã kho, mã NCC, mã khách, mã SKU), không gửi ID nội bộ của WMS.
`integrations` đổi mã sang ID qua `master_data.find_by_code` trước khi giao cho module xử lý.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _ErpModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _check_unique_lines(lines: list[Any]) -> None:
    numbers = [line.line_number for line in lines]
    if len(numbers) != len(set(numbers)):
        raise ValueError("line_number bị trùng")


class ErpPoLine(_ErpModel):
    """Dòng PO từ ERP."""

    line_number: int = Field(gt=0)
    sku_code: str = Field(min_length=1, max_length=100)
    uom_code: str = Field(min_length=1, max_length=30)
    qty_ordered: Decimal = Field(gt=0, max_digits=18, decimal_places=3)


class ErpPurchaseOrderPush(_ErpModel):
    """ERP đẩy đơn mua hàng (PO)."""

    erp_po_number: str = Field(min_length=1, max_length=100)
    warehouse_code: str = Field(min_length=1, max_length=50)
    supplier_code: str = Field(min_length=1, max_length=50)
    expected_date: date | None = None
    lines: list[ErpPoLine] = Field(min_length=1)

    @model_validator(mode="after")
    def _lines_unique(self) -> "ErpPurchaseOrderPush":
        _check_unique_lines(self.lines)
        return self


class ErpAsnPush(_ErpModel):
    """ERP đẩy thông báo giao hàng (ASN)."""

    erp_asn_number: str = Field(min_length=1, max_length=100)
    warehouse_code: str = Field(min_length=1, max_length=50)
    erp_po_number: str | None = Field(None, max_length=100)
    supplier_code: str | None = Field(None, max_length=50)
    expected_arrival_at: datetime
    expected_pallets: int | None = Field(None, ge=0)
    dock_location_code: str | None = Field(None, max_length=100)


class ErpOrderLine(_ErpModel):
    """Dòng đơn xuất từ ERP; số lượng theo đơn vị cơ sở của SKU."""

    line_number: int = Field(gt=0)
    sku_code: str = Field(min_length=1, max_length=100)
    qty_ordered: Decimal = Field(gt=0, max_digits=18, decimal_places=3)


class ErpOutboundOrderPush(_ErpModel):
    """ERP đẩy đơn xuất: bán hàng (SO), chuyển kho, trả NCC."""

    erp_order_number: str = Field(min_length=1, max_length=100)
    order_type: Literal["SO", "INTER_WH_TRANSFER", "SUPPLIER_RETURN"] = "SO"
    warehouse_code: str = Field(min_length=1, max_length=50)
    customer_code: str | None = Field(None, max_length=50)
    dest_warehouse_code: str | None = Field(None, max_length=50)
    supplier_code: str | None = Field(None, max_length=50)
    cutoff_time: datetime
    is_urgent: bool = False
    urgent_reason: str | None = None
    route_code: str | None = Field(None, max_length=50)
    lines: list[ErpOrderLine] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_party(self) -> "ErpOutboundOrderPush":
        _check_unique_lines(self.lines)
        required = {
            "SO": ("customer_code", self.customer_code),
            "INTER_WH_TRANSFER": ("dest_warehouse_code", self.dest_warehouse_code),
            "SUPPLIER_RETURN": ("supplier_code", self.supplier_code),
        }[self.order_type]
        if not required[1]:
            raise ValueError(f"order_type {self.order_type} bắt buộc có {required[0]}")
        return self


class ErpOrderChangePush(_ErpModel):
    """ERP đổi hoặc hủy đơn xuất (xử lý bởi `fn_receive_erp_order_change`)."""

    change_type: Literal["CANCEL_ORDER", "CHANGE_QTY", "CHANGE_ADDRESS"]
    payload: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None


class MockFailureConfig(_ErpModel):
    """Cấu hình lỗi giả lập cho ERP/TMS mock (chỉ dev)."""

    system: Literal["ERP", "TMS"]
    error_category: Literal["NONE", "BUSINESS_ERROR", "TECHNICAL_ERROR"]
    times: int = Field(1, ge=0, le=100)
