"""Unit tests cho module approvals (D-03, D-04, D-05)."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from server.app.core.database import SessionLocal
from server.app.core.exceptions import BusinessError
from server.app.core.rbac import UserContext
from server.app.main import app
from server.app.modules.approvals import create_approval_request, services
from server.app.modules.approvals.schemas import (
    ApproveDecisionRequest,
    RejectDecisionRequest,
    RequestInfoDecisionRequest,
)

client = TestClient(app)


def _login(username: str) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "Demo@123456"},
    )
    assert resp.status_code == 200
    return str(resp.json()["data"]["access_token"])


def _get_user_by_role(db: Session, role_code: str) -> tuple[str, UserContext]:
    """Lấy username và UserContext từ tài khoản seed theo role_code."""
    row = (
        db.execute(
            text(
                """
                SELECT u.username, u.user_id, r.role_code, u.primary_warehouse_id
                FROM users u
                JOIN roles r ON r.role_id = u.primary_role_id
                WHERE r.role_code = :role_code AND u.status = 'ACTIVE'
                LIMIT 1
                """
            ),
            {"role_code": role_code},
        )
        .mappings()
        .one()
    )
    ctx = UserContext(
        user_id=row["user_id"],
        username=str(row["username"]),
        role_code=row["role_code"],
        warehouse_id=row["primary_warehouse_id"],
        permissions=set(),
    )
    return str(row["username"]), ctx


def test_tier_resolution_and_sod_violation() -> None:
    """Kiểm tra phân luồng tầng duyệt (Z, D1, D2, D3) và chặn SoD người lập tự duyệt."""
    db = SessionLocal()
    try:
        _, nv_nhan = _get_user_by_role(db, "nv-nhan")
        _, thukho = _get_user_by_role(db, "thukho")

        # 1. Trong dung sai Z (kiểm kê 100k <= 500k) -> trả None
        auto_z = create_approval_request(
            db=db,
            warehouse_id=nv_nhan.warehouse_id,
            object_type="CYCLE_COUNT_DIFF",
            object_id=uuid.uuid4(),
            proposer_user_id=nv_nhan.user_id,
            discrepancy_amount=Decimal("100000"),
            discrepancy_percent=Decimal("0.1"),
            force_review=False,
        )
        assert auto_z is None

        # 2. Lệch 2.000.000 <= X (5.000.000) do nv-nhan lập -> lên D1_THUKHO
        req_d1 = create_approval_request(
            db=db,
            warehouse_id=nv_nhan.warehouse_id,
            object_type="GRN_DISCREPANCY",
            object_id=uuid.uuid4(),
            proposer_user_id=nv_nhan.user_id,
            discrepancy_amount=Decimal("2000000"),
            force_review=True,
        )
        assert req_d1 is not None
        assert req_d1.current_tier == "D1_THUKHO"
        assert req_d1.status == "PENDING_D1"

        # 3. Thủ kho lập phiếu 3.000.000 -> bỏ qua D1, lên thẳng D2_QUANLY
        req_d2 = create_approval_request(
            db=db,
            warehouse_id=thukho.warehouse_id,
            object_type="STOCK_ADJUSTMENT",
            object_id=uuid.uuid4(),
            proposer_user_id=thukho.user_id,
            discrepancy_amount=Decimal("3000000"),
            force_review=True,
        )
        assert req_d2 is not None
        assert req_d2.current_tier == "D2_QUANLY"

        # 4. Vi phạm SoD: chính người lập duyệt phiếu của mình -> 403 SOD_VIOLATION
        with pytest.raises(BusinessError) as exc_info:
            services.approve_request(
                db=db,
                user_ctx=thukho,
                approval_id=req_d2.approval_id,
                req=ApproveDecisionRequest(version_no=1),
            )
        assert exc_info.value.code == "SOD_VIOLATION"
        assert exc_info.value.http_status == 403
    finally:
        db.rollback()
        db.close()


def test_approve_reauth_version_conflict_and_escalate() -> None:
    """Kiểm tra xác thực lại (>=10tr), xung đột version_no (409) và leo thang SLA."""
    db = SessionLocal()
    try:
        _, nv_nhan = _get_user_by_role(db, "nv-nhan")
        _, thukho = _get_user_by_role(db, "thukho")
        _, quanly = _get_user_by_role(db, "quanly")

        # Tạo phiếu 12.000.000 (> ngưỡng X=5tr và >= ngưỡng xác thực lại 10tr)
        req = create_approval_request(
            db=db,
            warehouse_id=nv_nhan.warehouse_id,
            object_type="GRN_DISCREPANCY",
            object_id=uuid.uuid4(),
            proposer_user_id=nv_nhan.user_id,
            discrepancy_amount=Decimal("12000000"),
            force_review=True,
        )
        assert req is not None
        # Vượt ngưỡng X nên DB xếp thẳng vào D2_QUANLY
        assert req.current_tier == "D2_QUANLY"

        # Sai version_no -> 409 VERSION_CONFLICT
        with pytest.raises(BusinessError) as exc_ver:
            services.approve_request(
                db=db,
                user_ctx=quanly,
                approval_id=req.approval_id,
                req=ApproveDecisionRequest(reauth_method="PASSWORD", version_no=99),
            )
        assert exc_ver.value.code == "VERSION_CONFLICT"
        assert exc_ver.value.http_status == 409

        # Thiếu reauth_method khi giá trị >= 10tr -> 403 REAUTH_REQUIRED
        with pytest.raises(BusinessError) as exc_reauth:
            services.approve_request(
                db=db,
                user_ctx=quanly,
                approval_id=req.approval_id,
                req=ApproveDecisionRequest(version_no=1),
            )
        assert exc_reauth.value.code == "REAUTH_REQUIRED"

        # Duyệt thành công khi có reauth_method
        approved = services.approve_request(
            db=db,
            user_ctx=quanly,
            approval_id=req.approval_id,
            req=ApproveDecisionRequest(
                recommendation_or_reason="Đã kiểm tra chứng từ",
                reauth_method="BIOMETRIC",
                version_no=1,
            ),
        )
        assert approved.status == "APPROVED"
        assert approved.version_no == 2

        # Tạo phiếu quá hạn SLA ở D1 và test leo thang
        overdue = create_approval_request(
            db=db,
            warehouse_id=nv_nhan.warehouse_id,
            object_type="GRN_DISCREPANCY",
            object_id=uuid.uuid4(),
            proposer_user_id=nv_nhan.user_id,
            discrepancy_amount=Decimal("1000000"),
            force_review=True,
        )
        assert overdue is not None
        overdue.sla_due_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.flush()

        escalated_count = services.escalate_expired_requests(db=db, user_ctx=quanly)
        assert escalated_count >= 1
        db.refresh(overdue)
        assert overdue.current_tier == "D2_QUANLY"
        assert overdue.status == "PENDING_D2"

        # Test reject & request_info trên phiếu khác
        req_reject = create_approval_request(
            db=db,
            warehouse_id=nv_nhan.warehouse_id,
            object_type="GRN_DISCREPANCY",
            object_id=uuid.uuid4(),
            proposer_user_id=nv_nhan.user_id,
            discrepancy_amount=Decimal("1500000"),
            force_review=True,
        )
        assert req_reject is not None
        info_req = services.request_more_info(
            db=db,
            user_ctx=thukho,
            approval_id=req_reject.approval_id,
            req=RequestInfoDecisionRequest(
                info_required_note="Đề nghị đếm lại lần 2",
                request_recount=True,
                version_no=1,
            ),
        )
        assert info_req.status == "NEED_INFO"

        rejected = services.reject_request(
            db=db,
            user_ctx=thukho,
            approval_id=req_reject.approval_id,
            req=RejectDecisionRequest(
                rejection_reason="Không khớp biên bản giao nhận",
                version_no=2,
            ),
        )
        assert rejected.status == "REJECTED"
    finally:
        db.rollback()
        db.close()


def test_approvals_endpoints_rbac() -> None:
    """Thử endpoint với vai trò đúng (thukho, quanly) và vai trò sai (nv-nhan)."""
    db = SessionLocal()
    try:
        thukho_user, _ = _get_user_by_role(db, "thukho")
        quanly_user, _ = _get_user_by_role(db, "quanly")
        worker_user, _ = _get_user_by_role(db, "nv-nhan")
    finally:
        db.close()

    thukho_token = _login(thukho_user)
    quanly_token = _login(quanly_user)
    worker_token = _login(worker_user)

    # Vai trò đúng: thukho xem hàng chờ -> 200
    resp_ok = client.get(
        "/api/v1/approvals",
        headers={"Authorization": f"Bearer {thukho_token}"},
    )
    assert resp_ok.status_code == 200
    assert "data" in resp_ok.json()

    # Vai trò sai: nv-nhan xem hàng chờ -> 403 FORBIDDEN
    resp_forbidden = client.get(
        "/api/v1/approvals",
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert resp_forbidden.status_code == 403

    # Vai trò sai: thukho gọi escalate-expired (chỉ quanly được gọi) -> 403
    resp_esc_forbidden = client.post(
        "/api/v1/approvals/escalate-expired",
        headers={"Authorization": f"Bearer {thukho_token}"},
    )
    assert resp_esc_forbidden.status_code == 403

    # Vai trò đúng: quanly gọi escalate-expired -> 200
    resp_esc_ok = client.post(
        "/api/v1/approvals/escalate-expired",
        headers={"Authorization": f"Bearer {quanly_token}"},
    )
    assert resp_esc_ok.status_code == 200
    assert "escalated_count" in resp_esc_ok.json()["data"]
