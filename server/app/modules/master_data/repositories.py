"""ABEST WMS - Repositories cho Phân hệ Dữ liệu nguồn (Master Data).

Truy vấn chung cho 10 bảng danh mục (lọc, tìm kiếm, sắp xếp, phân trang) và bảng
`warehouse_configs`. Chỉ truy cập bảng của module `master_data`.
"""

import uuid
from typing import Any

from sqlalchemy import ColumnElement, func, or_, select, text
from sqlalchemy.orm import InstrumentedAttribute, Session

from server.app.core.database import Base
from server.app.modules.master_data.models import (
    ItemCategory,
    Location,
    Sku,
    Warehouse,
    WarehouseConfig,
    Zone,
)


class MasterDataRepository:
    """Repository truy vấn các bảng danh mục nguồn."""

    @staticmethod
    def list_items(
        db: Session,
        model: type[Base],
        conditions: list[ColumnElement[bool]],
        search_columns: list[InstrumentedAttribute[Any]],
        q: str | None,
        order_by: ColumnElement[Any],
        page: int,
        page_size: int,
    ) -> tuple[list[Any], int]:
        """Danh sách có lọc, tìm kiếm không phân biệt hoa thường, sắp xếp và phân trang."""
        where = list(conditions)
        if q:
            pattern = f"%{q}%"
            where.append(or_(*[col.ilike(pattern) for col in search_columns]))

        total = db.execute(select(func.count()).select_from(model).where(*where)).scalar_one()
        stmt = (
            select(model)
            .where(*where)
            .order_by(order_by)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(db.execute(stmt).scalars().all()), int(total)

    @staticmethod
    def get_by_pk(
        db: Session,
        model: type[Base],
        pk_column: InstrumentedAttribute[Any],
        pk_value: Any,
        conditions: list[ColumnElement[bool]] | None = None,
        for_update: bool = False,
    ) -> Any | None:
        """Lấy một bản ghi theo khóa chính, kèm điều kiện phạm vi (kho) nếu có."""
        stmt = select(model).where(pk_column == pk_value, *(conditions or []))
        if for_update:
            stmt = stmt.with_for_update()
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def add(db: Session, obj: Base) -> None:
        """Thêm bản ghi mới và flush để lấy khóa chính, bắt lỗi ràng buộc ngay tại chỗ."""
        db.add(obj)
        db.flush()

    @staticmethod
    def flush(db: Session) -> None:
        """Flush thay đổi để ràng buộc CSDL (duy nhất, CHECK) được kiểm ngay."""
        db.flush()

    @staticmethod
    def zone_exists(db: Session, zone_id: uuid.UUID, warehouse_id: uuid.UUID) -> bool:
        """Zone có tồn tại trong kho chỉ định hay không."""
        stmt = select(Zone.zone_id).where(
            Zone.zone_id == zone_id, Zone.warehouse_id == warehouse_id
        )
        return db.execute(stmt).first() is not None

    @staticmethod
    def category_exists(db: Session, category_id: uuid.UUID) -> bool:
        """Nhóm hàng có tồn tại hay không."""
        stmt = select(ItemCategory.category_id).where(ItemCategory.category_id == category_id)
        return db.execute(stmt).first() is not None

    @staticmethod
    def sku_exists(db: Session, sku_id: uuid.UUID) -> bool:
        """SKU có tồn tại hay không."""
        return db.execute(select(Sku.sku_id).where(Sku.sku_id == sku_id)).first() is not None

    @staticmethod
    def count_active_locations_in_zone(db: Session, zone_id: uuid.UUID) -> int:
        """Đếm vị trí còn hoạt động trong một zone."""
        stmt = select(func.count()).where(Location.zone_id == zone_id, Location.is_active.is_(True))
        return int(db.execute(stmt).scalar_one())

    @staticmethod
    def get_warehouse(db: Session, warehouse_id: uuid.UUID) -> Warehouse | None:
        """Lấy kho theo khóa chính."""
        return db.get(Warehouse, warehouse_id)

    @staticmethod
    def get_config(
        db: Session, warehouse_id: uuid.UUID, for_update: bool = False
    ) -> WarehouseConfig | None:
        """Lấy dòng cấu hình của kho."""
        stmt = select(WarehouseConfig).where(WarehouseConfig.warehouse_id == warehouse_id)
        if for_update:
            stmt = stmt.with_for_update()
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def create_default_config(db: Session, warehouse_id: uuid.UUID) -> None:
        """Tạo dòng cấu hình mặc định bằng DEFAULT của CSDL (nguồn sự thật là schema.sql)."""
        db.execute(
            text(
                "INSERT INTO warehouse_configs (warehouse_id) VALUES (:w) "
                "ON CONFLICT (warehouse_id) DO NOTHING"
            ),
            {"w": warehouse_id},
        )
