"""ABEST WMS - Repositories cho Phân hệ Phê duyệt (Approvals)."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from server.app.modules.approvals.models import ApprovalHistory, ApprovalRequest


class ApprovalsRepository:
    """Repository truy vấn hồ sơ duyệt và gọi hàm CSDL giải quyết tầng duyệt."""

    @staticmethod
    def get_approval_by_id(db: Session, approval_id: uuid.UUID) -> ApprovalRequest | None:
        return db.scalar(select(ApprovalRequest).where(ApprovalRequest.approval_id == approval_id))

    @staticmethod
    def list_histories(db: Session, approval_id: uuid.UUID) -> list[ApprovalHistory]:
        return list(
            db.scalars(
                select(ApprovalHistory).where(ApprovalHistory.approval_id == approval_id)
            ).all()
        )

    @staticmethod
    def call_resolve_approval_tier(
        db: Session,
        warehouse_id: uuid.UUID,
        proposer_user_id: uuid.UUID,
        discrepancy_amount: Decimal,
        is_expiry_discrepancy: bool = False,
        is_unplanned_receipt: bool = False,
    ) -> Any:
        """Gọi hàm PL/pgSQL fn_resolve_approval_tier xác định tầng duyệt."""
        stmt = text(
            """
            SELECT * FROM fn_resolve_approval_tier(
                :p_warehouse_id,
                :p_proposer_user_id,
                :p_discrepancy_amount,
                :p_is_expiry_discrepancy,
                :p_is_unplanned_receipt
            )
            """
        )
        return db.execute(
            stmt,
            {
                "p_warehouse_id": warehouse_id,
                "p_proposer_user_id": proposer_user_id,
                "p_discrepancy_amount": discrepancy_amount,
                "p_is_expiry_discrepancy": is_expiry_discrepancy,
                "p_is_unplanned_receipt": is_unplanned_receipt,
            },
        ).fetchone()

    @staticmethod
    def call_escalate_expired_approvals(db: Session, warehouse_id: uuid.UUID) -> int:
        """Gọi hàm PL/pgSQL fn_escalate_expired_approvals leo thang hồ sơ duyệt quá hạn."""
        stmt = text("SELECT fn_escalate_expired_approvals(:p_warehouse_id) AS escalated_count")
        result = db.execute(stmt, {"p_warehouse_id": warehouse_id}).scalar()
        return int(result or 0)
