"""ABEST WMS - ORM Models cho Phân hệ Phê duyệt (Approvals)."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from server.app.core.database import Base


class ApprovalRequest(Base):
    """Mô hình ORM bảng `approval_requests`."""

    __tablename__ = "approval_requests"

    approval_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    object_type: Mapped[str] = mapped_column(String(16), nullable=False)
    object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    proposer_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    current_tier: Mapped[str] = mapped_column(String(16), nullable=False, default="D1_THUKHO")
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="PENDING")
    execution_status: Mapped[str] = mapped_column(
        String(23), nullable=False, default="NOT_EXECUTED"
    )
    discrepancy_value_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=0
    )
    locked_by_viewer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    final_decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    final_decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class ApprovalHistory(Base):
    """Mô hình ORM bảng `approval_histories`."""

    __tablename__ = "approval_histories"

    history_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    approval_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tier: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    delegated_from_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    recommendation_or_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reauth_method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class StockAdjustment(Base):
    """Mô hình ORM bảng `stock_adjustments`."""

    __tablename__ = "stock_adjustments"

    adjustment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    adjustment_type: Mapped[str] = mapped_column(String(30), nullable=False)
    location_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    sku_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    lot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_pallet_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    damaged_pallet_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    qty_adjustment: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    total_value_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(50), nullable=False)
    proposal_photo_urls: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    proposed_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    proposed_by_role: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="PENDING")
    execution_status: Mapped[str] = mapped_column(
        String(23), nullable=False, default="NOT_EXECUTED"
    )
    scrap_executed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    scrap_execution_photos: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    scrap_report_doc_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    scrap_executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
