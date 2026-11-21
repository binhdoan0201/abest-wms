"""ABEST WMS - Repositories cho Phân hệ Tích hợp (Integrations)."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.app.modules.integrations.models import IntegrationSyncLog


class IntegrationRepository:
    """Repository quản lý nhật ký tích hợp với hệ thống ngoài (ERP, TMS...)."""

    @staticmethod
    def create_log(
        db: Session,
        external_system: str,
        direction: str,
        doc_type: str,
        doc_id: uuid.UUID | None = None,
        warehouse_id: uuid.UUID | None = None,
        business_payload: dict[str, Any] | None = None,
        status: str = "SUCCESS",
    ) -> IntegrationSyncLog:
        log = IntegrationSyncLog(
            external_system=external_system,
            direction=direction,
            doc_type=doc_type,
            doc_id=doc_id,
            warehouse_id=warehouse_id,
            business_payload=business_payload,
            status=status,
        )
        db.add(log)
        db.flush()
        return log

    @staticmethod
    def list_logs(
        db: Session,
        warehouse_id: uuid.UUID | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[IntegrationSyncLog]:
        query = select(IntegrationSyncLog).order_by(IntegrationSyncLog.created_at.desc())
        if warehouse_id:
            query = query.where(IntegrationSyncLog.warehouse_id == warehouse_id)
        if status:
            query = query.where(IntegrationSyncLog.status == status)
        return list(db.scalars(query.limit(limit)).all())
