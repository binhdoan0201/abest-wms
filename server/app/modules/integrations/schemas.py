"""ABEST WMS - Pydantic Schemas cho Phân hệ Tích hợp (Integrations)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ErpPurchaseOrderRequest(BaseModel):
    """ERP mock đẩy thông tin đơn đặt hàng PO."""

    po_number: str
    warehouse_id: uuid.UUID
    supplier_id: uuid.UUID
    expected_delivery_date: datetime
    lines: list[dict[str, Any]] = []


class ErpAsnRequest(BaseModel):
    """ERP mock đẩy thông tin thông báo giao hàng ASN."""

    asn_number: str
    warehouse_id: uuid.UUID
    po_id: uuid.UUID | None = None
    supplier_id: uuid.UUID
    expected_arrival_time: datetime
    lines: list[dict[str, Any]] = []


class ErpOutboundOrderRequest(BaseModel):
    """ERP mock đẩy thông tin đơn bán hàng SO/Outbound Order."""

    order_number: str
    warehouse_id: uuid.UUID
    customer_id: uuid.UUID
    order_type: str = "B2C"
    lines: list[dict[str, Any]] = []


class ErpOrderChangeRequest(BaseModel):
    """ERP mock đổi hoặc hủy đơn bán hàng."""

    change_type: str  # CANCEL, MODIFY_QTY, CHANGE_ADDRESS
    change_reason: str
    payload: dict[str, Any] = {}


class SyncLogResponse(BaseModel):
    """Phản hồi thông tin nhật ký đồng bộ."""

    sync_id: uuid.UUID
    warehouse_id: uuid.UUID | None
    external_system: str
    direction: str
    doc_type: str
    doc_id: uuid.UUID | None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
