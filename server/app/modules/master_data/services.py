"""ABEST WMS - Services cho Phân hệ Dữ liệu nguồn (Master Data)."""

import uuid

from sqlalchemy.orm import Session

from server.app.core.exceptions import BusinessError
from server.app.modules.master_data.models import Warehouse
from server.app.modules.master_data.repositories import MasterDataRepository


class MasterDataService:
    """Service điều phối nghiệp vụ danh mục nguồn."""

    @staticmethod
    def get_warehouse(db: Session, warehouse_id: uuid.UUID) -> Warehouse:
        wh = MasterDataRepository.get_warehouse_by_id(db, warehouse_id)
        if not wh:
            raise BusinessError(code="NOT_FOUND", message="Không tìm thấy kho", http_status=404)
        return wh
