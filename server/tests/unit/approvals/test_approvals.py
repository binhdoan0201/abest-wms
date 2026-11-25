"""Unit & DB integration tests cho module approvals (D-03, D-04, D-05)."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from server.app.core.database import SessionLocal
from server.app.core.exceptions import BusinessError
from server.app.core.rbac import UserContext
from server.app.main import app
from server.app.modules.approvals import (
    create_approval_request,
    mark_object_approval_executed,
    resubmit_approval_info,
    services,
    supersede_approval_for_recount,
    update_approval_execution_status,
)
from server.app.modules.approvals.schemas import (
    ApproveDecisionRequest,
    EscalateTierRequest,
    RequestInfoDecisionRequest,
    StockAdjustmentProposalCreate,
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
        permissions={},
    )
    return str(row["username"]), ctx


def _get_seed_location_sku_and_reason(
    db: Session, warehouse_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID, str]:
    loc_id = db.execute(
        text(
            """
            SELECT location_id FROM locations
            WHERE warehouse_id = :wh AND is_active = TRUE
            LIMIT 1
            """
        ),
        {"wh": warehouse_id},
    ).scalar_one()
    sku_id = db.execute(text("SELECT sku_id FROM skus WHERE is_active = TRUE LIMIT 1")).scalar_one()
    reason_code = db.execute(
        text("SELECT reason_code FROM reason_codes WHERE is_active = TRUE LIMIT 1")
    ).scalar_one()
    return loc_id, sku_id, str(reason_code)


def test_tier_resolution_escalate_d2_and_sod_violation() -> None:
    db = SessionLocal()
    try:
        _, nv_nhan = _get_user_by_role(db, "nv-nhan")
        _, thukho = _get_user_by_role(db, "thukho")
        _, quanly = _get_user_by_role(db, "quanly")
        assert nv_nhan.warehouse_id is not None
        assert thukho.warehouse_id is not None

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

        escalated = services.escalate_to_next_tier(
            db=db,
            user_ctx=thukho,
            approval_id=req_d1.approval_id,
            req=EscalateTierRequest(
                recommendation_or_reason="Chuyển Quản lý kho xem xét chênh lệch lô nhạy cảm",
                version_no=1,
            ),
        )
        assert escalated.current_tier == "D2_QUANLY"
        assert escalated.status == "PENDING_D2"
        assert escalated.version_no == 2

        approved_d2 = services.approve_request(
            db=db,
            user_ctx=quanly,
            approval_id=req_d1.approval_id,
            req=ApproveDecisionRequest(
                recommendation_or_reason="Quản lý đồng ý duyệt",
                version_no=2,
            ),
        )
        assert approved_d2.status == "APPROVED"

        req_sod = create_approval_request(
            db=db,
            warehouse_id=thukho.warehouse_id,
            object_type="STOCK_ADJUSTMENT",
            object_id=uuid.uuid4(),
            proposer_user_id=thukho.user_id,
            discrepancy_amount=Decimal("3000000"),
            force_review=True,
        )
        assert req_sod is not None
        assert req_sod.current_tier == "D2_QUANLY"

        with pytest.raises(BusinessError) as exc_info:
            services.approve_request(
                db=db,
                user_ctx=thukho,
                approval_id=req_sod.approval_id,
                req=ApproveDecisionRequest(version_no=1),
            )
        assert exc_info.value.code == "SOD_VIOLATION"
        assert exc_info.value.http_status == 403
    finally:
        db.rollback()
        db.close()


def test_approve_reauth_password_version_conflict_and_escalate() -> None:
    db = SessionLocal()
    try:
        _, nv_nhan = _get_user_by_role(db, "nv-nhan")
        _, quanly = _get_user_by_role(db, "quanly")
        assert nv_nhan.warehouse_id is not None

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
        assert req.current_tier == "D2_QUANLY"

        with pytest.raises(BusinessError) as exc_ver:
            services.approve_request(
                db=db,
                user_ctx=quanly,
                approval_id=req.approval_id,
                req=ApproveDecisionRequest(
                    reauth_method="PASSWORD",
                    reauth_password="Demo@123456",
                    version_no=99,
                ),
            )
        assert exc_ver.value.code == "VERSION_CONFLICT"

        with pytest.raises(BusinessError) as exc_reauth:
            services.approve_request(
                db=db,
                user_ctx=quanly,
                approval_id=req.approval_id,
                req=ApproveDecisionRequest(version_no=1),
            )
        assert exc_reauth.value.code == "REAUTH_REQUIRED"

        with pytest.raises(BusinessError) as exc_bad_pw:
            services.approve_request(
                db=db,
                user_ctx=quanly,
                approval_id=req.approval_id,
                req=ApproveDecisionRequest(
                    reauth_method="PASSWORD",
                    reauth_password="WrongPass@123",
                    version_no=1,
                ),
            )
        assert exc_bad_pw.value.code == "REAUTH_FAILED"

        approved = services.approve_request(
            db=db,
            user_ctx=quanly,
            approval_id=req.approval_id,
            req=ApproveDecisionRequest(
                recommendation_or_reason="Đã kiểm tra chứng từ",
                reauth_method="PASSWORD",
                reauth_password="Demo@123456",
                version_no=1,
            ),
        )
        assert approved.status == "APPROVED"
        assert approved.version_no == 2

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
    finally:
        db.rollback()
        db.close()


def test_stock_adjustment_and_scrap_post_approval_execution() -> None:
    db = SessionLocal()
    try:
        _, thukho = _get_user_by_role(db, "thukho")
        _, quanly = _get_user_by_role(db, "quanly")
        assert thukho.warehouse_id is not None
        loc_id, sku_id, reason_code = _get_seed_location_sku_and_reason(db, thukho.warehouse_id)

        adj_approval = services.propose_stock_adjustment(
            db=db,
            user_ctx=thukho,
            req=StockAdjustmentProposalCreate(
                adjustment_type="ADJUSTMENT",
                location_id=loc_id,
                sku_id=sku_id,
                qty_adjustment=Decimal("5.000"),
                reason_code=reason_code,
            ),
        )
        assert adj_approval.object_type == "STOCK_ADJUSTMENT"
        assert adj_approval.current_tier == "D2_QUANLY"

        with (
            patch(
                "server.app.modules.approvals.services.apply_movement",
                side_effect=BusinessError(
                    code="INVENTORY_INSUFFICIENT_QTY",
                    message="Tồn kho không đủ để điều chỉnh giảm",
                    http_status=409,
                ),
            ),
            pytest.raises(BusinessError),
        ):
            with db.begin_nested():
                services.approve_request(
                    db=db,
                    user_ctx=quanly,
                    approval_id=adj_approval.approval_id,
                    req=ApproveDecisionRequest(
                        reauth_method="PASSWORD",
                        reauth_password="Demo@123456",
                        version_no=1,
                    ),
                )

        db.refresh(adj_approval)
        assert adj_approval.status == "PENDING_D2"
        assert adj_approval.version_no == 1

        approved_adj = services.approve_request(
            db=db,
            user_ctx=quanly,
            approval_id=adj_approval.approval_id,
            req=ApproveDecisionRequest(
                reauth_method="PASSWORD",
                reauth_password="Demo@123456",
                version_no=1,
            ),
        )
        assert approved_adj.status == "APPROVED"
        assert approved_adj.execution_status == "EXECUTED_INVENTORY"

        sync_count = db.execute(
            text("SELECT COUNT(*) FROM integration_sync_logs WHERE doc_id = :doc_id"),
            {"doc_id": adj_approval.object_id},
        ).scalar_one()
        assert int(sync_count) == 1

        scrap_approval = services.propose_stock_adjustment(
            db=db,
            user_ctx=thukho,
            req=StockAdjustmentProposalCreate(
                adjustment_type="SCRAP",
                location_id=loc_id,
                sku_id=sku_id,
                qty_adjustment=Decimal("-2.000"),
                reason_code=reason_code,
            ),
        )
        approved_scrap = services.approve_request(
            db=db,
            user_ctx=quanly,
            approval_id=scrap_approval.approval_id,
            req=ApproveDecisionRequest(
                reauth_method="PASSWORD",
                reauth_password="Demo@123456",
                version_no=1,
            ),
        )
        assert approved_scrap.status == "APPROVED"
        assert approved_scrap.execution_status == "WAITING_SCRAP_EXECUTION"
    finally:
        db.rollback()
        db.close()


def test_lock_tier_guard_and_need_info_lifecycle() -> None:
    db = SessionLocal()
    try:
        _, nv_nhan = _get_user_by_role(db, "nv-nhan")
        _, thukho = _get_user_by_role(db, "thukho")
        _, quanly = _get_user_by_role(db, "quanly")
        assert nv_nhan.warehouse_id is not None

        req = create_approval_request(
            db=db,
            warehouse_id=nv_nhan.warehouse_id,
            object_type="GRN_DISCREPANCY",
            object_id=uuid.uuid4(),
            proposer_user_id=nv_nhan.user_id,
            discrepancy_amount=Decimal("1500000"),
            force_review=True,
        )
        assert req is not None
        assert req.current_tier == "D1_THUKHO"

        with pytest.raises(BusinessError) as exc_wrong_tier:
            services.get_approval_detail(
                db=db,
                user_ctx=quanly,
                approval_id=req.approval_id,
                acquire_lock=True,
            )
        assert exc_wrong_tier.value.http_status == 403
        assert req.locked_by_viewer_id is None

        detail_req, _ = services.get_approval_detail(
            db=db,
            user_ctx=thukho,
            approval_id=req.approval_id,
            acquire_lock=True,
        )
        assert detail_req.locked_by_viewer_id == thukho.user_id

        unlocked = services.unlock_approval(db=db, user_ctx=thukho, approval_id=req.approval_id)
        assert unlocked.locked_by_viewer_id is None

        info_req = services.request_more_info(
            db=db,
            user_ctx=thukho,
            approval_id=req.approval_id,
            req=RequestInfoDecisionRequest(
                info_required_note="Bổ sung ảnh biên bản giao nhận",
                request_recount=False,
                version_no=1,
            ),
        )
        assert info_req.status == "NEED_INFO"

        resubmitted = resubmit_approval_info(
            db=db,
            approval_id=req.approval_id,
            warehouse_id=nv_nhan.warehouse_id,
            actor_user_id=nv_nhan.user_id,
            note="Đã đính kèm biên bản có chữ ký tài xế",
        )
        assert resubmitted.status == "PENDING_D1"
        assert resubmitted.version_no == 3

        recount_req = services.request_more_info(
            db=db,
            user_ctx=thukho,
            approval_id=req.approval_id,
            req=RequestInfoDecisionRequest(
                info_required_note="Yêu cầu đếm lại lần 2",
                request_recount=True,
                version_no=3,
            ),
        )
        assert recount_req.status == "NEED_INFO"

        superseded = supersede_approval_for_recount(
            db=db,
            approval_id=req.approval_id,
            warehouse_id=nv_nhan.warehouse_id,
            actor_user_id=nv_nhan.user_id,
        )
        assert superseded.status == "SUPERSEDED"
    finally:
        db.rollback()
        db.close()


def test_approvals_endpoints_rbac() -> None:
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

    resp_ok = client.get(
        "/api/v1/approvals",
        headers={"Authorization": f"Bearer {thukho_token}"},
    )
    assert resp_ok.status_code == 200
    assert "data" in resp_ok.json()

    resp_forbidden = client.get(
        "/api/v1/approvals",
        headers={"Authorization": f"Bearer {worker_token}"},
    )
    assert resp_forbidden.status_code == 403

    resp_esc_forbidden = client.post(
        "/api/v1/approvals/escalate-expired",
        headers={"Authorization": f"Bearer {thukho_token}"},
    )
    assert resp_esc_forbidden.status_code == 403

    resp_esc_ok = client.post(
        "/api/v1/approvals/escalate-expired",
        headers={"Authorization": f"Bearer {quanly_token}"},
    )
    assert resp_esc_ok.status_code == 200
    assert "escalated_count" in resp_esc_ok.json()["data"]


def test_update_approval_execution_status_and_mark_executed() -> None:
    db = SessionLocal()
    try:
        _, nv_nhan = _get_user_by_role(db, "nv-nhan")
        _, thukho = _get_user_by_role(db, "thukho")
        grn_id = uuid.uuid4()

        req = create_approval_request(
            db=db,
            warehouse_id=nv_nhan.warehouse_id,
            object_type="GRN_DISCREPANCY",
            object_id=grn_id,
            proposer_user_id=nv_nhan.user_id,
            discrepancy_amount=Decimal("200000"),
            discrepancy_percent=Decimal("10"),
        )
        assert req is not None

        # Không được cập nhật execution_status khi chưa APPROVED
        with pytest.raises(BusinessError) as exc_not_approved:
            update_approval_execution_status(
                db=db,
                approval_id=req.approval_id,
                warehouse_id=nv_nhan.warehouse_id,
                actor_user_id=nv_nhan.user_id,
            )
        assert exc_not_approved.value.code == "INVALID_STATE"

        # Duyệt hồ sơ GRN_DISCREPANCY -> trạng thái APPROVED, execution_status = WAITING_EXECUTION
        thukho_ctx = UserContext(
            user_id=thukho.user_id,
            username=thukho.username,
            role_code="thukho",
            warehouse_id=thukho.warehouse_id,
            permissions=set(),
        )
        approved = services.approve_request(
            db=db,
            user_ctx=thukho_ctx,
            approval_id=req.approval_id,
            req=ApproveDecisionRequest(
                version_no=req.version_no,
                recommendation_or_reason="Duyệt chênh lệch nhận hàng để nhập tồn",
            ),
        )
        assert approved.status == "APPROVED"
        assert approved.execution_status == "WAITING_EXECUTION"

        # Phân hệ nguồn gọi mark_object_approval_executed sau khi ghi tồn kho
        executed = mark_object_approval_executed(
            db=db,
            warehouse_id=nv_nhan.warehouse_id,
            object_type="GRN_DISCREPANCY",
            object_id=grn_id,
            actor_user_id=nv_nhan.user_id,
            note="Đã ghi tồn kho hoàn tất GRN",
        )
        assert executed is not None
        assert executed.execution_status == "EXECUTED_INVENTORY"

        # Không cho phép đánh dấu EXECUTED_INVENTORY lần hai
        with pytest.raises(BusinessError) as exc_dup:
            update_approval_execution_status(
                db=db,
                approval_id=req.approval_id,
                warehouse_id=nv_nhan.warehouse_id,
                actor_user_id=nv_nhan.user_id,
                execution_status="EXECUTED_INVENTORY",
            )
        assert exc_dup.value.code == "INVALID_STATE"

        # Cho phép chuyển tiếp sang SYNCED_ERP sau khi đồng bộ ERP thành công
        synced = update_approval_execution_status(
            db=db,
            approval_id=req.approval_id,
            warehouse_id=nv_nhan.warehouse_id,
            actor_user_id=nv_nhan.user_id,
            execution_status="SYNCED_ERP",
        )
        assert synced.execution_status == "SYNCED_ERP"

        # Đối tượng tự duyệt dung sai Z (không có bản ghi approval_requests) trả về None
        none_res = mark_object_approval_executed(
            db=db,
            warehouse_id=nv_nhan.warehouse_id,
            object_type="CYCLE_COUNT_DIFF",
            object_id=uuid.uuid4(),
            actor_user_id=nv_nhan.user_id,
        )
        assert none_res is None
    finally:
        db.rollback()
        db.close()
