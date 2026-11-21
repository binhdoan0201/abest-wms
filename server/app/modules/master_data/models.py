"""ABEST WMS - ORM Models cho Phân hệ Dữ liệu nguồn (Master Data)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from server.app.core.database import Base


class Warehouse(Base):
    """Mô hình ORM bảng `warehouses`."""

    __tablename__ = "warehouses"

    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    erp_warehouse_code: Mapped[str] = mapped_column(String(50), nullable=False)
    warehouse_name: Mapped[str] = mapped_column(String(200), nullable=False)
    branch_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class WarehouseConfig(Base):
    """Mô hình ORM bảng `warehouse_configs`."""

    __tablename__ = "warehouse_configs"

    config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    threshold_x_d1_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=5000000
    )
    threshold_y_d2_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=20000000
    )
    tolerance_z_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="AMOUNT")
    tolerance_z_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=500000
    )
    tolerance_z_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=1.00
    )
    reauth_min_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=10000000
    )
    picking_rule: Mapped[str] = mapped_column(String(4), nullable=False, default="FEFO")
    putaway_rule_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    blind_receipt_policy: Mapped[str] = mapped_column(
        String(30), nullable=False, default="BLIND_MANDATORY"
    )
    missing_cert_policy: Mapped[str] = mapped_column(
        String(30), nullable=False, default="BLOCK_ASSIGNMENT"
    )
    counting_location_tx_policy: Mapped[str] = mapped_column(
        String(20), nullable=False, default="LOCK_LOCATION"
    )
    task_sla_minutes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    dashboard_refresh_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    idle_alert_minutes_n: Mapped[int | None] = mapped_column(Integer, nullable=True)
    offline_task_reclaim_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    escalation_minutes_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_open_tasks_per_user: Mapped[int | None] = mapped_column(Integer, nullable=True, default=3)
    max_recount_attempts: Mapped[int | None] = mapped_column(Integer, nullable=True, default=3)
    max_overtime_hours_month: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    allow_worker_view_own_kpi: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expiry_reminder_days_n: Mapped[int | None] = mapped_column(Integer, nullable=True, default=30)
    hr_integration_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="MANUAL")
    approval_sla_hours: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    min_headcount_per_stage: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    pre_shift_alert_hours: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    allow_same_counter_recount: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    grn_tolerance_apply: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    over_receipt_tolerance_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=0.00
    )


class Zone(Base):
    """Mô hình ORM bảng `zones`."""

    __tablename__ = "zones"

    zone_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    zone_code: Mapped[str] = mapped_column(String(50), nullable=False)
    zone_name: Mapped[str] = mapped_column(String(150), nullable=False)
    zone_type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Location(Base):
    """Mô hình ORM bảng `locations`."""

    __tablename__ = "locations"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    zone_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    location_code: Mapped[str] = mapped_column(String(100), nullable=False)
    barcode: Mapped[str] = mapped_column(String(100), nullable=False)
    aisle: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rack: Mapped[str | None] = mapped_column(String(20), nullable=True)
    shelf_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    max_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    max_volume_m3: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    max_pallets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_capacity_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=0.00
    )
    status: Mapped[str] = mapped_column(String(18), nullable=False, default="AVAILABLE")
    lock_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    locked_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ItemCategory(Base):
    """Mô hình ORM bảng `item_categories`."""

    __tablename__ = "item_categories"

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    category_code: Mapped[str] = mapped_column(String(50), nullable=False)
    category_name: Mapped[str] = mapped_column(String(150), nullable=False)
    min_receiving_shelf_life_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shelf_life_violation_action: Mapped[str] = mapped_column(
        String(20), nullable=False, default="WARN"
    )


class Sku(Base):
    """Mô hình ORM bảng `skus`."""

    __tablename__ = "skus"

    sku_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sku_code: Mapped[str] = mapped_column(String(100), nullable=False)
    sku_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    base_uom: Mapped[str] = mapped_column(String(30), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    min_stock_level: Mapped[Decimal | None] = mapped_column(Numeric(18, 3), nullable=True)
    is_lot_tracked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_expiry_tracked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_serial_tracked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    storage_requirement: Mapped[str | None] = mapped_column(String(50), nullable=True)
    erp_last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SkuBarcode(Base):
    """Mô hình ORM bảng `sku_barcodes`."""

    __tablename__ = "sku_barcodes"

    barcode_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    barcode: Mapped[str] = mapped_column(String(150), nullable=False)
    uom_code: Mapped[str] = mapped_column(String(30), nullable=False)
    conversion_factor: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, default=1.0000
    )


class Supplier(Base):
    """Mô hình ORM bảng `suppliers`."""

    __tablename__ = "suppliers"

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    erp_supplier_code: Mapped[str] = mapped_column(String(50), nullable=False)
    supplier_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Customer(Base):
    """Mô hình ORM bảng `customers`."""

    __tablename__ = "customers"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    erp_customer_code: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ReasonCode(Base):
    """Mô hình ORM bảng `reason_codes`."""

    __tablename__ = "reason_codes"

    reason_code_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reason_code: Mapped[str] = mapped_column(String(50), nullable=False)
    reason_name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class BoxType(Base):
    """Mô hình ORM bảng `box_types`."""

    __tablename__ = "box_types"

    box_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    box_code: Mapped[str] = mapped_column(String(50), nullable=False)
    box_name: Mapped[str] = mapped_column(String(100), nullable=False)
    max_weight_kg: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    volume_m3: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    length_cm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    width_cm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
