"""ABEST WMS - Tầng Truy vấn CSDL (Repository) cho Phân hệ Tồn kho.

Toàn bộ các lời gọi hàm fn_apply_inventory_movement và fn_transfer_inventory
được đặt tập trung tại đây theo đúng Quy định 7.2.4 Chuẩn API.
"""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from server.app.modules.inventory.models import InventoryBalance, InventoryTransaction, Lot, Pallet


class InventoryRepository:
    """Repository thực thi truy vấn tồn kho và gọi hàm PL/pgSQL của CSDL."""

    @staticmethod
    def call_apply_inventory_movement(
        db: Session,
        warehouse_id: uuid.UUID,
        location_id: uuid.UUID,
        sku_id: uuid.UUID,
        lot_id: uuid.UUID | None,
        pallet_id: uuid.UUID | None,
        serial_number: str | None,
        tx_type: str,
        delta_available: Decimal,
        delta_allocated: Decimal,
        delta_counting: Decimal,
        delta_locked: Decimal,
        delta_damaged: Decimal,
        ref_doc_type: str,
        ref_doc_id: uuid.UUID,
        performed_by: uuid.UUID,
        counterpart_location_id: uuid.UUID | None = None,
        expected_version: int | None = None,
    ) -> uuid.UUID:
        """Gọi hàm CSDL fn_apply_inventory_movement."""
        stmt = text(
            """
            SELECT fn_apply_inventory_movement(
                :p_warehouse_id, :p_location_id, :p_sku_id, :p_lot_id, :p_pallet_id,
                :p_serial_number, :p_tx_type,
                :p_delta_available, :p_delta_allocated, :p_delta_counting,
                :p_delta_locked, :p_delta_damaged,
                :p_ref_doc_type, :p_ref_doc_id, :p_performed_by,
                :p_counterpart_location_id, :p_expected_version
            );
            """
        )
        params: dict[str, Any] = {
            "p_warehouse_id": warehouse_id,
            "p_location_id": location_id,
            "p_sku_id": sku_id,
            "p_lot_id": lot_id,
            "p_pallet_id": pallet_id,
            "p_serial_number": serial_number,
            "p_tx_type": tx_type,
            "p_delta_available": delta_available,
            "p_delta_allocated": delta_allocated,
            "p_delta_counting": delta_counting,
            "p_delta_locked": delta_locked,
            "p_delta_damaged": delta_damaged,
            "p_ref_doc_type": ref_doc_type,
            "p_ref_doc_id": ref_doc_id,
            "p_performed_by": performed_by,
            "p_counterpart_location_id": counterpart_location_id,
            "p_expected_version": expected_version,
        }
        result = db.execute(stmt, params)
        tx_id: uuid.UUID = result.scalar_one()
        return tx_id

    @staticmethod
    def call_transfer_inventory(
        db: Session,
        warehouse_id: uuid.UUID,
        from_location_id: uuid.UUID,
        to_location_id: uuid.UUID,
        sku_id: uuid.UUID,
        lot_id: uuid.UUID | None,
        pallet_id: uuid.UUID | None,
        serial_number: str | None,
        qty: Decimal,
        tx_type: str,
        ref_doc_type: str,
        ref_doc_id: uuid.UUID,
        performed_by: uuid.UUID,
        bucket: str = "AVAILABLE",
    ) -> uuid.UUID:
        """Gọi hàm CSDL fn_transfer_inventory."""
        stmt = text(
            """
            SELECT fn_transfer_inventory(
                :p_warehouse_id, :p_from_location_id, :p_to_location_id,
                :p_sku_id, :p_lot_id, :p_pallet_id, :p_serial_number,
                :p_qty, :p_tx_type,
                :p_ref_doc_type, :p_ref_doc_id, :p_performed_by,
                :p_bucket
            );
            """
        )
        params: dict[str, Any] = {
            "p_warehouse_id": warehouse_id,
            "p_from_location_id": from_location_id,
            "p_to_location_id": to_location_id,
            "p_sku_id": sku_id,
            "p_lot_id": lot_id,
            "p_pallet_id": pallet_id,
            "p_serial_number": serial_number,
            "p_qty": qty,
            "p_tx_type": tx_type,
            "p_ref_doc_type": ref_doc_type,
            "p_ref_doc_id": ref_doc_id,
            "p_performed_by": performed_by,
            "p_bucket": bucket,
        }
        result = db.execute(stmt, params)
        tx_id: uuid.UUID = result.scalar_one()
        return tx_id

    @staticmethod
    def get_balances(
        db: Session,
        warehouse_id: uuid.UUID,
        sku_id: uuid.UUID | None = None,
        location_id: uuid.UUID | None = None,
        lot_id: uuid.UUID | None = None,
    ) -> list[InventoryBalance]:
        """Truy vấn danh sách tồn kho theo bộ lọc."""
        stmt = select(InventoryBalance).where(InventoryBalance.warehouse_id == warehouse_id)
        if sku_id:
            stmt = stmt.where(InventoryBalance.sku_id == sku_id)
        if location_id:
            stmt = stmt.where(InventoryBalance.location_id == location_id)
        if lot_id:
            stmt = stmt.where(InventoryBalance.lot_id == lot_id)
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_transactions(
        db: Session,
        warehouse_id: uuid.UUID,
        sku_id: uuid.UUID | None = None,
        limit: int = 50,
    ) -> list[InventoryTransaction]:
        """Truy vấn sổ cái giao dịch tồn kho."""
        stmt = (
            select(InventoryTransaction)
            .where(InventoryTransaction.warehouse_id == warehouse_id)
            .order_by(InventoryTransaction.performed_at.desc())
            .limit(limit)
        )
        if sku_id:
            stmt = stmt.where(InventoryTransaction.sku_id == sku_id)
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_lots(db: Session, sku_id: uuid.UUID | None = None) -> list[Lot]:
        """Truy vấn danh sách lô hàng."""
        stmt = select(Lot).order_by(Lot.expiry_date.asc().nulls_last())
        if sku_id:
            stmt = stmt.where(Lot.sku_id == sku_id)
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_pallets(db: Session, warehouse_id: uuid.UUID) -> list[Pallet]:
        """Truy vấn danh sách Pallet trong kho."""
        stmt = (
            select(Pallet)
            .where(Pallet.warehouse_id == warehouse_id)
            .order_by(Pallet.created_at.desc())
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_pallet_by_id(
        db: Session,
        pallet_id: uuid.UUID,
        warehouse_id: uuid.UUID | None = None,
    ) -> Pallet | None:
        """Truy vấn chi tiết Pallet theo ID."""
        stmt = select(Pallet).where(Pallet.pallet_id == pallet_id)
        if warehouse_id:
            stmt = stmt.where(Pallet.warehouse_id == warehouse_id)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_location_stock(
        db: Session,
        location_id: uuid.UUID,
        warehouse_id: uuid.UUID | None = None,
    ) -> list[InventoryBalance]:
        """Truy vấn danh sách các dòng tồn tại một vị trí."""
        stmt = select(InventoryBalance).where(InventoryBalance.location_id == location_id)
        if warehouse_id:
            stmt = stmt.where(InventoryBalance.warehouse_id == warehouse_id)
        return list(db.execute(stmt).scalars().all())
