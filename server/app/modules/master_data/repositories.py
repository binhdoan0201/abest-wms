"""ABEST WMS - Repositories cho Phân hệ Dữ liệu nguồn (Master Data)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.app.modules.master_data.models import Location, Sku, Warehouse, Zone


class MasterDataRepository:
    """Repository truy vấn các bảng danh mục nguồn."""

    @staticmethod
    def get_warehouse_by_id(db: Session, warehouse_id: uuid.UUID) -> Warehouse | None:
        return db.scalar(select(Warehouse).where(Warehouse.warehouse_id == warehouse_id))

    @staticmethod
    def list_warehouses(db: Session) -> list[Warehouse]:
        return list(db.scalars(select(Warehouse).where(Warehouse.is_active.is_(True))).all())

    @staticmethod
    def list_zones(db: Session, warehouse_id: uuid.UUID) -> list[Zone]:
        return list(
            db.scalars(
                select(Zone).where(Zone.warehouse_id == warehouse_id, Zone.is_active.is_(True))
            ).all()
        )

    @staticmethod
    def list_locations(db: Session, warehouse_id: uuid.UUID) -> list[Location]:
        return list(
            db.scalars(
                select(Location).where(
                    Location.warehouse_id == warehouse_id, Location.is_active == True  # noqa: E712
                )
            ).all()
        )

    @staticmethod
    def list_skus(db: Session) -> list[Sku]:
        return list(db.scalars(select(Sku).where(Sku.is_active == True)).all())  # noqa: E712
