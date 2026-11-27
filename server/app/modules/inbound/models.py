"""ABEST WMS - ORM Models cho Phân hệ Nhập kho (Inbound)."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Computed, Date, DateTime, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column

from server.app.core.database import Base

GRN_STATUSES = (
    "DRAFT",
    "COUNTING",
    "PENDING_D1",
    "PENDING_D2",
    "PENDING_D3",
    "APPROVED",
    "REJECTED",
    "CLOSED",
    "SYNCED_ERP",
)

PO_STATUSES = (
    "PENDING",
    "RECEIVING",
    "PARTIAL_RECEIVED",
    "FULLY_RECEIVED",
    "CLOSED",
    "CANCELLED",
)


class PurchaseOrder(Base):
    """Mô hình ORM bảng `purchase_orders`."""

    __tablename__ = "purchase_orders"

    po_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    erp_po_number: Mapped[str] = mapped_column(String(100), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(
        PG_ENUM(*PO_STATUSES, name="po_status_type", create_type=False),
        nullable=False,
        default="PENDING",
    )
    expected_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class POLine(Base):
    """Mô hình ORM bảng `po_lines`."""

    __tablename__ = "po_lines"

    po_line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    po_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    sku_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    uom_code: Mapped[str] = mapped_column(String(30), nullable=False)
    qty_ordered: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    qty_received: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=0)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class Asn(Base):
    """Mô hình ORM bảng `asns`."""

    __tablename__ = "asns"

    asn_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    erp_asn_number: Mapped[str] = mapped_column(String(100), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    po_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    assigned_dock_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    assigned_zone_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    expected_arrival_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_arrival_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expected_pallets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="SCHEDULED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    source_outbound_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )


class Grn(Base):
    """Mô hình ORM bảng `grns`."""

    __tablename__ = "grns"

    grn_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    grn_number: Mapped[str] = mapped_column(String(100), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    po_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    asn_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    shift_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_blind_receipt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    received_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        PG_ENUM(*GRN_STATUSES, name="grn_status_type", create_type=False),
        nullable=False,
        default="RECEIVING",
    )
    has_discrepancy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    total_discrepancy_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=0.00
    )
    recount_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    erp_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    approval_expired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class GrnLine(Base):
    """Mô hình ORM bảng `grn_lines`."""

    __tablename__ = "grn_lines"

    grn_line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    grn_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    po_line_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    sku_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    lot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    pallet_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    damaged_pallet_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    uom_code: Mapped[str] = mapped_column(String(30), nullable=False)
    qty_expected: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=0)
    qty_actual: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=0)
    qty_damaged: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=0)
    qty_variance: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 3), Computed("qty_actual - qty_expected", persisted=True), nullable=True
    )
    variance_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    serial_numbers: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    is_quarantined: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reason_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    damage_photo_urls: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class GrnCountAttempt(Base):
    """Mô hình ORM bảng `grn_count_attempts` (bổ sung từ patch v4.2.1)."""

    __tablename__ = "grn_count_attempts"

    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    grn_line_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    counter_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    blind_counted_qty: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    counted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
