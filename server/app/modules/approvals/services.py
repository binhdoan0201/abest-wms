"""ABEST WMS - Services cho Phân hệ Phê duyệt (Approvals)."""

import uuid

from sqlalchemy.orm import Session

from server.app.core.exceptions import BusinessError
from server.app.modules.approvals.models import ApprovalRequest
from server.app.modules.approvals.repositories import ApprovalsRepository


class ApprovalsService:
    """Service điều phối quy trình duyệt chênh lệch đa cấp D1/D2/D3 và leo thang SLA."""

    @staticmethod
    def get_approval(db: Session, approval_id: uuid.UUID) -> ApprovalRequest:
        approval = ApprovalsRepository.get_approval_by_id(db, approval_id)
        if not approval:
            raise BusinessError(
                code="NOT_FOUND", message="Không tìm thấy hồ sơ phê duyệt", http_status=404
            )
        return approval
