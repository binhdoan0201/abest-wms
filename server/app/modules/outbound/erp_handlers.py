"""ABEST WMS - Hàm nhận chứng từ ERP (SO) cho module Xuất kho (Outbound)."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from server.app.core.exceptions import BusinessError
from server.app.modules.master_data import get_sku
from server.app.modules.outbound.models import OutboundOrder, OutboundOrderLine
from server.app.modules.outbound.repositories import OutboundRepository

ALLOWED_ORDER_TYPES = {"SO", "INTER_WH_TRANSFER", "SUPPLIER_RETURN"}


def _err(msg: str) -> BusinessError:
    return BusinessError(code="VALIDATION_ERROR", message=msg, http_status=422)


def _uuid(val: Any, f: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError):
        raise _err(f"{f} không phải UUID hợp lệ") from None


def receive_outbound_order(db: Session, data: dict[str, Any], actor_id: uuid.UUID) -> uuid.UUID:
    """Tạo `outbound_orders` và `outbound_order_lines` từ dữ liệu đơn xuất của ERP."""
    erp_no = str(data.get("erp_order_number") or "").strip()
    if not erp_no:
        raise _err("Thiếu erp_order_number")
    if OutboundRepository.get_order_by_erp_number(db, erp_no) is not None:
        raise BusinessError(
            code="OUTBOUND_ORDER_DUPLICATE",
            message=f"Số đơn xuất {erp_no} đã tồn tại",
            http_status=409,
        )
    otype = str(data.get("order_type") or "SO").strip().upper()
    if otype not in ALLOWED_ORDER_TYPES:
        raise _err(f"Loại đơn {otype} không hợp lệ")
    whid = _uuid(data.get("warehouse_id"), "warehouse_id")
    cid = _uuid(data["customer_id"], "customer_id") if data.get("customer_id") else None
    dwid = (
        _uuid(data["dest_warehouse_id"], "dest_warehouse_id")
        if data.get("dest_warehouse_id")
        else None
    )
    sid = _uuid(data["supplier_id"], "supplier_id") if data.get("supplier_id") else None
    if otype == "SO" and cid is None:
        raise _err("SO bắt buộc có customer_id")
    if otype == "INTER_WH_TRANSFER" and dwid is None:
        raise _err("INTER_WH_TRANSFER bắt buộc có dest_warehouse_id")
    if otype == "SUPPLIER_RETURN" and sid is None:
        raise _err("SUPPLIER_RETURN bắt buộc có supplier_id")
    lines = data.get("lines") or []
    if not lines:
        raise _err("Đơn xuất phải có ít nhất 1 dòng hàng")
    craw = data.get("cutoff_time")
    try:
        cutoff = (
            datetime.fromisoformat(str(craw))
            if craw
            else datetime.now(timezone.utc) + timedelta(hours=24)
        )
    except ValueError:
        raise _err("cutoff_time không hợp lệ") from None
    order = OutboundOrder(
        erp_order_number=erp_no,
        order_type=otype,
        warehouse_id=whid,
        customer_id=cid,
        dest_warehouse_id=dwid,
        supplier_id=sid,
        status="NEW",
        is_urgent=bool(data.get("is_urgent", False)),
        urgent_reason=data.get("urgent_reason"),
        cutoff_time=cutoff,
        route_code=data.get("route_code"),
    )
    db.add(order)
    db.flush()
    seen: set[uuid.UUID] = set()
    for raw in lines:
        sku_id = _uuid(raw.get("sku_id"), "sku_id")
        if sku_id in seen:
            raise _err("Trùng sku_id trong đơn xuất")
        seen.add(sku_id)
        try:
            qty = Decimal(str(raw.get("qty_ordered")))
        except (InvalidOperation, ValueError):
            raise _err("qty_ordered không hợp lệ") from None
        if qty <= Decimal("0"):
            raise _err("qty_ordered phải > 0")
        get_sku(db, sku_id)
        db.add(OutboundOrderLine(order_id=order.order_id, sku_id=sku_id, qty_ordered=qty))
    db.flush()
    return order.order_id
