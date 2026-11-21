"""ABEST WMS - Repositories cho Phân hệ Xuất kho (Outbound)."""

import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from server.app.modules.outbound.models import GoodsIssue, OutboundOrder, PickSession


class OutboundRepository:
    """Repository truy vấn và thực thi các thao tác CSDL xuất kho."""

    @staticmethod
    def get_order_by_id(db: Session, order_id: uuid.UUID) -> OutboundOrder | None:
        return db.scalar(select(OutboundOrder).where(OutboundOrder.order_id == order_id))

    @staticmethod
    def get_pick_session_by_id(db: Session, session_id: uuid.UUID) -> PickSession | None:
        return db.scalar(select(PickSession).where(PickSession.pick_session_id == session_id))

    @staticmethod
    def get_gi_by_id(db: Session, gi_id: uuid.UUID) -> GoodsIssue | None:
        return db.scalar(select(GoodsIssue).where(GoodsIssue.gi_id == gi_id))

    @staticmethod
    def call_receive_erp_order_change(
        db: Session,
        order_id: uuid.UUID,
        change_type: str,
        change_payload_json: str,
    ) -> Any:
        """Gọi hàm PL/pgSQL fn_receive_erp_order_change xử lý đổi/hủy đơn từ ERP."""
        stmt = text(
            """
            SELECT * FROM fn_receive_erp_order_change(
                :p_order_id,
                :p_change_type,
                CAST(:p_change_payload AS jsonb)
            )
            """
        )
        return db.execute(
            stmt,
            {
                "p_order_id": order_id,
                "p_change_type": change_type,
                "p_change_payload": change_payload_json,
            },
        ).fetchone()

    @staticmethod
    def call_decide_order_change(
        db: Session,
        request_id: uuid.UUID,
        decided_by_user_id: uuid.UUID,
        decision: str,
        reject_reason_code: str | None = None,
        reject_note: str | None = None,
    ) -> Any:
        """Gọi hàm PL/pgSQL fn_decide_order_change để Quản lý chốt quyết định đổi đơn."""
        stmt = text(
            """
            SELECT * FROM fn_decide_order_change(
                :p_request_id,
                :p_decided_by,
                :p_decision,
                :p_reject_reason_code,
                :p_reject_note
            )
            """
        )
        return db.execute(
            stmt,
            {
                "p_request_id": request_id,
                "p_decided_by": decided_by_user_id,
                "p_decision": decision,
                "p_reject_reason_code": reject_reason_code,
                "p_reject_note": reject_note,
            },
        ).fetchone()
