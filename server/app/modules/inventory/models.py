"""ABEST WMS - ORM Models cho Phân hệ Tồn kho (Inventory)."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from server.app.core.database import Base
from server.app.shared.enums import PalletStatusType


class InventoryBalance(Base):
    """Mô hình ORM bảng `inventory_balances`."""

    __tablename__ = "inventory_balances"

    balance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    lot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    pallet_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    serial_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    qty_available: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=0)
    qty_allocated: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=0)
    qty_counting: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=0)
    qty_locked: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=0)
    qty_damaged: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=0)

    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )


class InventoryTransaction(Base):
    """Mô hình ORM bảng sổ cái bất biến `inventory_transactions`."""

    __tablename__ = "inventory_transactions"

    tx_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    tx_type: Mapped[str] = mapped_column(String(40), nullable=False)
    sku_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    lot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    pallet_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    serial_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    from_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    to_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    qty_change: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    unit_cost_snapshot: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    ref_doc_type: Mapped[str] = mapped_column(String(40), nullable=False)
    ref_doc_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    performed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )
    qty_delta_available: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=0)
    qty_delta_allocated: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=0)
    qty_delta_counting: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=0)
    qty_delta_locked: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=0)
    qty_delta_damaged: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=0)


class Lot(Base):
    """Mô hình ORM bảng `lots`."""

    __tablename__ = "lots"

    lot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    lot_number: Mapped[str] = mapped_column(String(100), nullable=False)
    manufacture_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    is_priority_dispatch: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )


class Pallet(Base):
    """Mô hình ORM bảng `pallets`."""

    __tablename__ = "pallets"

    pallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    pallet_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    parent_pallet_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    current_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    source_grn_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(
        ENUM(
            PalletStatusType,
            name="pallet_status_type",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default="RECEIVING",
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )


class InventoryAllocation(Base):
    """Mô hình ORM bảng `inventory_allocations` (bổ sung từ patch v4.2.1)."""

    __tablename__ = "inventory_allocations"

    allocation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    order_line_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    balance_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    lot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    qty_allocated: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    qty_picked: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )
