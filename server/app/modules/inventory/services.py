"""ABEST WMS - Tầng Nghiệp vụ (Service) cho Phân hệ Tồn kho.

Cung cấp apply_movement và transfer_inventory bọc các hàm CSDL fn_*
kèm cơ chế dịch lỗi chuẩn bằng translate_db_error.
"""

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from server.app.core.exceptions import translate_db_error
from server.app.modules.inventory.models import InventoryBalance
from server.app.modules.inventory.repositories import InventoryRepository
from server.app.modules.inventory.schemas import (
    BalanceItem,
    LotItem,
    PalletItem,
    TransactionItem,
)


def _balance_to_schema(b: InventoryBalance) -> BalanceItem:
    return BalanceItem(
        balance_id=b.balance_id,
        warehouse_id=b.warehouse_id,
        location_id=b.location_id,
        sku_id=b.sku_id,
        lot_id=b.lot_id,
        pallet_id=b.pallet_id,
        serial_number=b.serial_number,
        qty_available=str(b.qty_available),
        qty_allocated=str(b.qty_allocated),
        qty_counting=str(b.qty_counting),
        qty_locked=str(b.qty_locked),
        qty_damaged=str(b.qty_damaged),
        version_no=b.version_no,
    )


class InventoryService:
    """Service tồn kho cung cấp các hàm nghiệp vụ biến động tồn và tra cứu."""

    @staticmethod
    def apply_movement(
        db: Session,
        warehouse_id: uuid.UUID,
        location_id: uuid.UUID,
        sku_id: uuid.UUID,
        lot_id: uuid.UUID | None,
        pallet_id: uuid.UUID | None,
        serial_number: str | None,
        tx_type: str,
        delta_available: Decimal = Decimal("0"),
        delta_allocated: Decimal = Decimal("0"),
        delta_counting: Decimal = Decimal("0"),
        delta_locked: Decimal = Decimal("0"),
        delta_damaged: Decimal = Decimal("0"),
        ref_doc_type: str = "MANUAL",
        ref_doc_id: uuid.UUID = uuid.UUID("00000000-0000-0000-0000-000000000000"),
        performed_by: uuid.UUID = uuid.UUID("00000000-0000-0000-0000-000000000000"),
        counterpart_location_id: uuid.UUID | None = None,
        expected_version: int | None = None,
    ) -> uuid.UUID:
        """Thực hiện biến động tồn kho qua hàm CSDL fn_apply_inventory_movement."""
        try:
            return InventoryRepository.call_apply_inventory_movement(
                db=db,
                warehouse_id=warehouse_id,
                location_id=location_id,
                sku_id=sku_id,
                lot_id=lot_id,
                pallet_id=pallet_id,
                serial_number=serial_number,
                tx_type=tx_type,
                delta_available=delta_available,
                delta_allocated=delta_allocated,
                delta_counting=delta_counting,
                delta_locked=delta_locked,
                delta_damaged=delta_damaged,
                ref_doc_type=ref_doc_type,
                ref_doc_id=ref_doc_id,
                performed_by=performed_by,
                counterpart_location_id=counterpart_location_id,
                expected_version=expected_version,
            )
        except Exception as exc:
            raise translate_db_error(exc) from exc

    @staticmethod
    def transfer_inventory(
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
        """Thực hiện chuyển dịch tồn kho 2 chân qua hàm CSDL fn_transfer_inventory."""
        try:
            return InventoryRepository.call_transfer_inventory(
                db=db,
                warehouse_id=warehouse_id,
                from_location_id=from_location_id,
                to_location_id=to_location_id,
                sku_id=sku_id,
                lot_id=lot_id,
                pallet_id=pallet_id,
                serial_number=serial_number,
                qty=qty,
                tx_type=tx_type,
                ref_doc_type=ref_doc_type,
                ref_doc_id=ref_doc_id,
                performed_by=performed_by,
                bucket=bucket,
            )
        except Exception as exc:
            raise translate_db_error(exc) from exc

    @staticmethod
    def get_balances(
        db: Session,
        warehouse_id: uuid.UUID,
        sku_id: uuid.UUID | None = None,
        location_id: uuid.UUID | None = None,
        lot_id: uuid.UUID | None = None,
    ) -> list[BalanceItem]:
        """Lấy danh sách số dư tồn kho theo bộ lọc."""
        balances = InventoryRepository.get_balances(
            db=db,
            warehouse_id=warehouse_id,
            sku_id=sku_id,
            location_id=location_id,
            lot_id=lot_id,
        )
        return [_balance_to_schema(b) for b in balances]

    @staticmethod
    def get_transactions(
        db: Session,
        warehouse_id: uuid.UUID,
        sku_id: uuid.UUID | None = None,
        limit: int = 50,
    ) -> list[TransactionItem]:
        """Lấy danh sách sổ cái giao dịch tồn kho."""
        txs = InventoryRepository.get_transactions(
            db=db,
            warehouse_id=warehouse_id,
            sku_id=sku_id,
            limit=limit,
        )
        return [
            TransactionItem(
                tx_id=t.tx_id,
                warehouse_id=t.warehouse_id,
                tx_type=t.tx_type,
                sku_id=t.sku_id,
                lot_id=t.lot_id,
                pallet_id=t.pallet_id,
                from_location_id=t.from_location_id,
                to_location_id=t.to_location_id,
                qty_change=str(t.qty_change),
                ref_doc_type=t.ref_doc_type,
                ref_doc_id=t.ref_doc_id,
                performed_by=t.performed_by,
                performed_at=t.performed_at,
            )
            for t in txs
        ]

    @staticmethod
    def get_lots(db: Session, sku_id: uuid.UUID | None = None) -> list[LotItem]:
        """Lấy danh sách lô hàng."""
        lots = InventoryRepository.get_lots(db=db, sku_id=sku_id)
        return [
            LotItem(
                lot_id=lo.lot_id,
                sku_id=lo.sku_id,
                lot_number=lo.lot_number,
                manufacture_date=lo.manufacture_date,
                expiry_date=lo.expiry_date,
                is_priority_dispatch=lo.is_priority_dispatch,
            )
            for lo in lots
        ]

    @staticmethod
    def get_pallets(db: Session, warehouse_id: uuid.UUID) -> list[PalletItem]:
        """Lấy danh sách Pallet trong kho."""
        pallets = InventoryRepository.get_pallets(db=db, warehouse_id=warehouse_id)
        return [
            PalletItem(
                pallet_id=p.pallet_id,
                pallet_code=p.pallet_code,
                warehouse_id=p.warehouse_id,
                current_location_id=p.current_location_id,
                status=p.status,
                version_no=p.version_no,
            )
            for p in pallets
        ]

    @staticmethod
    def get_pallet_by_id(
        db: Session,
        pallet_id: uuid.UUID,
        warehouse_id: uuid.UUID,
    ) -> PalletItem | None:
        """Lấy chi tiết Pallet theo ID."""
        p = InventoryRepository.get_pallet_by_id(
            db=db, pallet_id=pallet_id, warehouse_id=warehouse_id
        )
        if not p:
            return None
        return PalletItem(
            pallet_id=p.pallet_id,
            pallet_code=p.pallet_code,
            warehouse_id=p.warehouse_id,
            current_location_id=p.current_location_id,
            status=p.status,
            version_no=p.version_no,
        )

    @staticmethod
    def get_location_stock(
        db: Session,
        location_id: uuid.UUID,
        warehouse_id: uuid.UUID,
    ) -> list[BalanceItem]:
        """Lấy danh sách số dư tồn kho tại một vị trí."""
        balances = InventoryRepository.get_location_stock(
            db=db,
            location_id=location_id,
            warehouse_id=warehouse_id,
        )
        return [_balance_to_schema(b) for b in balances]

    @staticmethod
    def has_stock(
        db: Session,
        warehouse_id: uuid.UUID | None = None,
        location_id: uuid.UUID | None = None,
        sku_id: uuid.UUID | None = None,
    ) -> bool:
        """Cho module khác hỏi còn tồn (mọi trạng thái) theo kho, vị trí hoặc SKU hay không.

        Dùng khi ngừng sử dụng danh mục (`master_data`): không cho ngừng kho, vị trí, SKU còn hàng.
        """
        return InventoryRepository.has_stock(
            db=db, warehouse_id=warehouse_id, location_id=location_id, sku_id=sku_id
        )


# Export các hàm công khai theo đúng quy định
apply_movement = InventoryService.apply_movement
transfer_inventory = InventoryService.transfer_inventory
has_stock = InventoryService.has_stock
