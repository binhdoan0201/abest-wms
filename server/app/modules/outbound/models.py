"""ABEST WMS - ORM Models cho Phân hệ Xuất kho (Outbound)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column

from server.app.core.database import Base

ORDER_STATUSES = (
    "NEW",
    "PICKING",
    "PICKED",
    "PACKING",
    "WAITING_WAYBILL",
    "READY_TO_SHIP",
    "SHIPPED",
    "IN_TRANSIT",
    "DELIVERED",
    "PARTIAL_DELIVERED",
    "DELIVERY_FAILED",
    "ON_HOLD",
    "CANCELLED",
)


class OutboundOrder(Base):
    """Mô hình ORM bảng `outbound_orders`."""

    __tablename__ = "outbound_orders"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    erp_order_number: Mapped[str] = mapped_column(String(100), nullable=False)
    order_type: Mapped[str] = mapped_column(String(30), nullable=False, default="STANDARD")
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    dest_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(
        PG_ENUM(*ORDER_STATUSES, name="order_status_type", create_type=False),
        nullable=False,
        default="NEW",
    )
    is_urgent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    urgent_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cutoff_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    route_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    delay_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    erp_change_pending: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    erp_change_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    source_grn_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class OutboundOrderLine(Base):
    """Mô hình ORM bảng `outbound_order_lines`."""

    __tablename__ = "outbound_order_lines"

    order_line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    sku_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    qty_ordered: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    qty_allocated: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=0)
    qty_picked: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=0)
    qty_packed: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=0)
    qty_shipped: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=0)
    shortage_resolution: Mapped[str | None] = mapped_column(String(30), nullable=True)


class PickSession(Base):
    """Mô hình ORM bảng `pick_sessions`."""

    __tablename__ = "pick_sessions"

    pick_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    shift_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    pick_mode: Mapped[str] = mapped_column(String(12), nullable=False, default="DISCRETE")
    picker_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ASSIGNED")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class PickLine(Base):
    """Mô hình ORM bảng `pick_lines`."""

    __tablename__ = "pick_lines"

    pick_line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pick_session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    order_line_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_location_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    suggested_lot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    actual_lot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    serial_numbers: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    target_tote_barcode: Mapped[str | None] = mapped_column(String(100), nullable=True)
    qty_to_pick: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    qty_picked: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    exception_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    allocation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    staged_location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class Package(Base):
    """Mô hình ORM bảng `packages`."""

    __tablename__ = "packages"

    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    package_barcode: Mapped[str] = mapped_column(String(100), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    pick_session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    gi_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    box_type_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False, default=0)
    length_cm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    width_cm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    packed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    packed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_loaded_on_truck: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    loaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PackageLine(Base):
    """Mô hình ORM bảng `package_lines` (bổ sung từ patch v4.2.1)."""

    __tablename__ = "package_lines"

    package_line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    package_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    order_line_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    sku_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    lot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    serial_numbers: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)


class GoodsIssue(Base):
    """Mô hình ORM bảng `goods_issues`."""

    __tablename__ = "goods_issues"

    gi_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    gi_number: Mapped[str] = mapped_column(String(100), nullable=False)
    gi_type: Mapped[str] = mapped_column(String(20), nullable=False, default="STANDARD")
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    tms_waybill_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tms_waybill_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    total_packages: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    handover_photo_urls: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    driver_signature_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    driver_signed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class OrderChangeRequest(Base):
    """Mô hình ORM bảng `order_change_requests` (bổ sung từ patch v4.2.1)."""

    __tablename__ = "order_change_requests"

    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    change_type: Mapped[str] = mapped_column(String(20), nullable=False)
    change_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    order_status_at_receipt: Mapped[str] = mapped_column(String(17), nullable=False)
    decision_path: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reject_reason_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reject_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    erp_notify_status: Mapped[str] = mapped_column(String(10), nullable=False, default="PENDING")
    erp_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
