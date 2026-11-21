"""ABEST WMS - ORM Models cho Phân hệ Kiểm kê (Cycle Count)."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from server.app.core.database import Base


class CycleCountSheet(Base):
    """Mô hình ORM bảng `cycle_count_sheets`."""

    __tablename__ = "cycle_count_sheets"

    count_sheet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sheet_number: Mapped[str] = mapped_column(String(100), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    count_type: Mapped[str] = mapped_column(String(30), nullable=False, default="LOCATION")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="OPEN")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class CycleCountLine(Base):
    """Mô hình ORM bảng `cycle_count_lines`."""

    __tablename__ = "cycle_count_lines"

    count_line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    count_sheet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    location_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    sku_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    lot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    system_qty_snapshot: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False, default=0)
    final_counted_qty: Mapped[Decimal | None] = mapped_column(Numeric(18, 3), nullable=True)
    variance_qty: Mapped[Decimal | None] = mapped_column(Numeric(18, 3), nullable=True)
    variance_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    variance_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    recount_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    anomaly_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    approval_expired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pallet_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class CycleCountAttempt(Base):
    """Mô hình ORM bảng `cycle_count_attempts`."""

    __tablename__ = "cycle_count_attempts"

    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    count_line_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    counter_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    blind_counted_qty: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    same_counter_override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    counted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
