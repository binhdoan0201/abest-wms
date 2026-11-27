"""ABEST WMS - Repositories cho Phân hệ Tích hợp (Integrations).

Bảng của module: `integration_sync_logs` (vừa là nhật ký vừa là hàng đợi gửi đi kiểu outbox).
Gọi hàm DB `fn_receive_erp_order_change` (chuẩn API 4.4 giao cho integrations) và đọc kết quả
dòng `order_change_requests` mà hàm đó vừa tạo.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import ColumnElement, and_, func, or_, select, text
from sqlalchemy.orm import Session

from server.app.modules.integrations.models import IntegrationSyncLog

RETRYABLE_TECHNICAL = "FAILED_TECHNICAL"


class IntegrationRepository:
    """Repository nhật ký và hàng đợi tích hợp với hệ thống ngoài (ERP, TMS)."""

    @staticmethod
    def create_log(
        db: Session,
        external_system: str,
        direction: str,
        doc_type: str,
        doc_id: uuid.UUID | None = None,
        warehouse_id: uuid.UUID | None = None,
        business_payload: dict[str, Any] | None = None,
        technical_meta: dict[str, Any] | None = None,
        status: str = "PENDING",
    ) -> IntegrationSyncLog:
        """Ghi một dòng nhật ký (mặc định `PENDING`, chờ xử lý)."""
        log = IntegrationSyncLog(
            external_system=external_system,
            direction=direction,
            doc_type=doc_type,
            doc_id=doc_id,
            warehouse_id=warehouse_id,
            business_payload=business_payload,
            technical_meta=technical_meta,
            status=status,
        )
        db.add(log)
        db.flush()
        return log

    @staticmethod
    def get_log(
        db: Session, sync_id: uuid.UUID, for_update: bool = False
    ) -> IntegrationSyncLog | None:
        """Lấy một dòng nhật ký."""
        stmt = select(IntegrationSyncLog).where(IntegrationSyncLog.sync_id == sync_id)
        if for_update:
            stmt = stmt.with_for_update()
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_logs(
        db: Session,
        conditions: list[ColumnElement[bool]],
        page: int,
        page_size: int,
    ) -> tuple[list[IntegrationSyncLog], int]:
        """Danh sách nhật ký mới nhất trước, có phân trang."""
        total = db.execute(
            select(func.count()).select_from(IntegrationSyncLog).where(*conditions)
        ).scalar_one()
        stmt = (
            select(IntegrationSyncLog)
            .where(*conditions)
            .order_by(IntegrationSyncLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(db.execute(stmt).scalars().all()), int(total)

    @staticmethod
    def lock_processable(
        db: Session,
        inbound_doc_types: list[str],
        max_retries: int,
        limit: int,
        warehouse_id: uuid.UUID | None = None,
    ) -> list[IntegrationSyncLog]:
        """Khóa các dòng cần xử lý: gửi đi đang chờ, lỗi kỹ thuật còn lượt thử, nhận vào chờ
        module xử lý đã đăng ký. `SKIP LOCKED` để hai lần chạy song song không xử lý trùng."""
        stmt = (
            select(IntegrationSyncLog)
            .where(
                or_(
                    and_(
                        IntegrationSyncLog.direction == "OUTBOUND",
                        IntegrationSyncLog.status == "PENDING",
                    ),
                    and_(
                        IntegrationSyncLog.status == RETRYABLE_TECHNICAL,
                        IntegrationSyncLog.retry_count < max_retries,
                    ),
                    and_(
                        IntegrationSyncLog.direction == "INBOUND",
                        IntegrationSyncLog.status == "PENDING",
                        IntegrationSyncLog.doc_type.in_(inbound_doc_types),
                    ),
                )
            )
            .order_by(IntegrationSyncLog.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        if warehouse_id is not None:
            stmt = stmt.where(IntegrationSyncLog.warehouse_id == warehouse_id)
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def touch(log: IntegrationSyncLog) -> None:
        """Cập nhật mốc `updated_at`."""
        log.updated_at = datetime.now(timezone.utc)

    @staticmethod
    def receive_erp_order_change(
        db: Session,
        order_id: uuid.UUID,
        change_type: str,
        payload: dict[str, Any],
        actor_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Gọi `fn_receive_erp_order_change` và trả kết quả quyết định của dòng yêu cầu."""
        request_id = db.execute(
            text(
                "SELECT fn_receive_erp_order_change(:order_id, :change_type, "
                "CAST(:payload AS jsonb), :actor)"
            ),
            {
                "order_id": order_id,
                "change_type": change_type,
                "payload": _json(payload),
                "actor": actor_id,
            },
        ).scalar_one()
        row = (
            db.execute(
                text(
                    "SELECT request_id, warehouse_id, status, decision_path, reject_reason_code, "
                    "order_status_at_receipt::text AS order_status_at_receipt "
                    "FROM order_change_requests WHERE request_id = :id"
                ),
                {"id": request_id},
            )
            .mappings()
            .one()
        )
        return dict(row)


def _json(value: Any) -> str:
    import json

    return json.dumps(value, default=str, ensure_ascii=False)
