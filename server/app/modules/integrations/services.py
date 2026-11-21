"""ABEST WMS - Services cho Phân hệ Tích hợp (Integrations)."""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from server.app.modules.integrations.models import IntegrationSyncLog
from server.app.modules.integrations.repositories import IntegrationRepository


class IntegrationService:
    """Service điều phối nhận và đồng bộ dữ liệu với ERP/hệ thống ngoài."""

    @staticmethod
    def log_sync(
        db: Session,
        external_system: str,
        direction: str,
        doc_type: str,
        doc_id: uuid.UUID | None = None,
        warehouse_id: uuid.UUID | None = None,
        business_payload: dict[str, Any] | None = None,
        status: str = "SUCCESS",
    ) -> IntegrationSyncLog:
        return IntegrationRepository.create_log(
            db=db,
            external_system=external_system,
            direction=direction,
            doc_type=doc_type,
            doc_id=doc_id,
            warehouse_id=warehouse_id,
            business_payload=business_payload,
            status=status,
        )

    @staticmethod
    def get_logs(
        db: Session,
        warehouse_id: uuid.UUID | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[IntegrationSyncLog]:
        return IntegrationRepository.list_logs(
            db=db, warehouse_id=warehouse_id, status=status, limit=limit
        )
