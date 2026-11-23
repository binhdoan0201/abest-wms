"""ABEST WMS - Kiểm thử Phân hệ Nhiệm vụ (Tasks): assign, reassign, cancel (D-01, D-02).

Gồm hai nhóm:
- Kiểm thử service (có rollback sau mỗi bài, không để lại dữ liệu): giao, điu chuyển, hủy,
  khóa lạc quan `version_no`, giới hạn task mở (gồm PAUSED_OFFLINE), phạm vi kho, điu kiện nhân
  viên,
  tính `sla_due_at` và audit log (`TASK_REJECT`, `TASK_REASSIGN`, `TASK_CANCEL`).
- Kiểm thử endpoint: mỗi endpoint thử 1 vai trò đúng và 1 vai trò sai.
"""

import uuid
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from server.app.core.database import SessionLocal
from server.app.core.exceptions import BusinessError
from server.app.main import app
from server.app.modules.tasks.repositories import TaskRepository
from server.app.modules.tasks.schemas import (
    AcceptTaskRequest,
    AssignTaskRequest,
    CancelTaskRequest,
    CompleteTaskRequest,
    CreateTaskRequest,
    ReassignTaskRequest,
    RejectTaskRequest,
    TaskPriorityLiteral,
    TaskResponse,
    TaskTypeLiteral,
    WorkStageLiteral,
)
from server.app.modules.tasks.services import TaskService

client = TestClient(app)
BASE = "/api/v1/tasks"
PASSWORD = "Demo@123456"


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Session CSDL độc lập, luôn rollback để không để lại dữ liệu thử nghiệm."""
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _user_id(db: Session, username: str) -> uuid.UUID:
    value = db.execute(
        text("SELECT user_id FROM users WHERE username = :u"), {"u": username}
    ).scalar()
    assert value is not None, f"Không có tài khoản seed {username}"
    return uuid.UUID(str(value))


def _warehouse_id(db: Session) -> uuid.UUID:
    value = db.execute(text("SELECT warehouse_id FROM warehouses LIMIT 1")).scalar()
    assert value is not None
    return uuid.UUID(str(value))


def _new_task(
    db: Session,
    stage: WorkStageLiteral = "CAT_HANG",
    task_type: TaskTypeLiteral = "PUTAWAY",
    priority: TaskPriorityLiteral = "NORMAL",
) -> TaskResponse:
    """Tạo task UNASSIGNED bằng service (chưa commit)."""
    wh_id = _warehouse_id(db)
    return TaskService.create_task(
        db,
        warehouse_id=wh_id,
        creator_id=_user_id(db, "thukho"),
        req=CreateTaskRequest(
            task_type=task_type,
            stage=stage,
            ref_doc_type="GRN",
            ref_doc_id=uuid.uuid4(),
            priority=priority,
        ),
    )


def _assign(db: Session, task: TaskResponse, username: str) -> TaskResponse:
    return TaskService.assign_task(
        db,
        task_id=task.task_id,
        assigner_id=_user_id(db, "thukho"),
        req=AssignTaskRequest(
            assigned_to_user_id=_user_id(db, username), version_no=task.version_no
        ),
        warehouse_id=task.warehouse_id,
    )


def _audit_reason(db: Session, task_id: uuid.UUID, action_code: str) -> str | None:
    value = db.execute(
        text(
            "SELECT new_values->>'reason' FROM audit_logs "
            "WHERE entity_id = :i AND action_code = :a"
        ),
        {"i": task_id, "a": action_code},
    ).scalar()
    return None if value is None else str(value)


# ----------------------------------------------------------------------------
# assign & validation
# ----------------------------------------------------------------------------


def test_create_task_sets_sla_due_at(db_session: Session) -> None:
    task = _new_task(db_session, stage="CAT_HANG", task_type="PUTAWAY")
    assert task.sla_due_at is not None
    assert task.sla_due_at > task.created_at


def test_assign_success_bumps_version(db_session: Session) -> None:
    task = _new_task(db_session)
    assigned = _assign(db_session, task, "nv_cat")
    assert assigned.status == "ASSIGNED"
    assert assigned.assigned_to == _user_id(db_session, "nv_cat")
    assert assigned.version_no == task.version_no + 1


def test_assign_twice_is_invalid_state(db_session: Session) -> None:
    task = _assign(db_session, _new_task(db_session), "nv_cat")
    with pytest.raises(BusinessError) as exc:
        _assign(db_session, task, "nv_cat")
    assert exc.value.code == "INVALID_STATE"
    assert exc.value.http_status == 409


def test_assign_wrong_version_conflict(db_session: Session) -> None:
    task = _new_task(db_session)
    with pytest.raises(BusinessError) as exc:
        TaskService.assign_task(
            db_session,
            task_id=task.task_id,
            assigner_id=_user_id(db_session, "thukho"),
            req=AssignTaskRequest(
                assigned_to_user_id=_user_id(db_session, "nv_cat"), version_no=99
            ),
            warehouse_id=task.warehouse_id,
        )
    assert exc.value.code == "VERSION_CONFLICT"
    assert exc.value.http_status == 409
    assert exc.value.details["current_version_no"] == task.version_no


def test_assign_wrong_stage_is_rejected(db_session: Session) -> None:
    task = _new_task(db_session, stage="CAT_HANG")
    with pytest.raises(BusinessError) as exc:
        _assign(db_session, task, "nv_nhan")
    assert exc.value.code == "TASKS_STAGE_MISMATCH"
    assert exc.value.http_status == 409


def test_assign_unknown_user_not_found(db_session: Session) -> None:
    task = _new_task(db_session)
    with pytest.raises(BusinessError) as exc:
        TaskService.assign_task(
            db_session,
            task_id=task.task_id,
            assigner_id=_user_id(db_session, "thukho"),
            req=AssignTaskRequest(assigned_to_user_id=uuid.uuid4(), version_no=task.version_no),
            warehouse_id=task.warehouse_id,
        )
    assert exc.value.code == "NOT_FOUND"
    assert exc.value.http_status == 404


def test_assign_different_warehouse_task_not_found(db_session: Session) -> None:
    task = _new_task(db_session)
    with pytest.raises(BusinessError) as exc:
        TaskService.assign_task(
            db_session,
            task_id=task.task_id,
            assigner_id=_user_id(db_session, "thukho"),
            req=AssignTaskRequest(
                assigned_to_user_id=_user_id(db_session, "nv_cat"), version_no=task.version_no
            ),
            warehouse_id=uuid.uuid4(),
        )
    assert exc.value.code == "NOT_FOUND"
    assert exc.value.http_status == 404


def test_assign_inactive_or_unsafe_seasonal_user_rejected(db_session: Session) -> None:
    nv_cat_id = _user_id(db_session, "nv_cat")
    # 1. Nhân viên bị khóa (INACTIVE)
    db_session.execute(
        text("UPDATE users SET status = 'INACTIVE' WHERE user_id = :u"), {"u": nv_cat_id}
    )
    task1 = _new_task(db_session)
    with pytest.raises(BusinessError) as exc_inactive:
        _assign(db_session, task1, "nv_cat")
    assert exc_inactive.value.code == "INVALID_STATE"
    assert exc_inactive.value.http_status == 409

    # 2. Khôi phục ACTIVE nhưng đặt thi vụ chưa kiểm tra an toàn
    db_session.execute(
        text(
            "UPDATE users SET status = 'ACTIVE', is_seasonal = TRUE, valid_until = NOW() +
            INTERVAL '7 days', is_safety_checked = FALSE "
            "WHERE user_id = :u"
        ),
        {"u": nv_cat_id},
    )
    task2 = _new_task(db_session)
    with pytest.raises(BusinessError) as exc_safety:
        _assign(db_session, task2, "nv_cat")
    assert exc_safety.value.code == "FORBIDDEN"
    assert exc_safety.value.http_status == 403


def test_assign_exceeds_max_open_tasks_including_paused_offline(db_session: Session) -> None:
    limit = TaskRepository.get_max_open_tasks(db_session, _warehouse_id(db_session))
    assigned_list: list[TaskResponse] = []
    for _ in range(limit):
        assigned_list.append(
            _assign(db_session, _new_task(db_session, "KIEM_KE", "CYCLE_COUNT"), "nv_kiemke")
        )
    # ưa 1 task sang PAUSED_OFFLINE: vẫn phải tính là task mở
    db_session.execute(
        text("UPDATE tasks SET status = 'PAUSED_OFFLINE' WHERE task_id = :t"),
        {"t": assigned_list[0].task_id},
    )
    extra = _new_task(db_session, "KIEM_KE", "CYCLE_COUNT")
    with pytest.raises(BusinessError) as exc:
        _assign(db_session, extra, "nv_kiemke")
    assert exc.value.code == "TASKS_MAX_OPEN_EXCEEDED"
    assert exc.value.http_status == 409


# ----------------------------------------------------------------------------
# reassign & reject audit
# ----------------------------------------------------------------------------


def test_reassign_resets_started_at_and_logs_reason(db_session: Session) -> None:
    thukho_id = _user_id(db_session, "thukho")
    quanly_id = _user_id(db_session, "quanly")
    task = _assign(db_session, _new_task(db_session, "QUAN_LY_CHUNG", "INTERNAL_MOVE"), "thukho")
    started = TaskService.accept_task(
        db_session,
        task_id=task.task_id,
        worker_id=thukho_id,
        req=AcceptTaskRequest(version_no=task.version_no),
        warehouse_id=task.warehouse_id,
    )
    assert started.status == "IN_PROGRESS"
    assert started.started_at is not None

    moved = TaskService.reassign_task(
        db_session,
        task_id=task.task_id,
        assigner_id=thukho_id,
        req=ReassignTaskRequest(
            new_assigned_to_user_id=quanly_id, reason="ổi ca", version_no=started.version_no
        ),
        warehouse_id=task.warehouse_id,
    )
    assert moved.status == "ASSIGNED"
    assert moved.assigned_to == quanly_id
    assert moved.started_at is None
    assert moved.version_no == started.version_no + 1
    assert _audit_reason(db_session, task.task_id, "TASK_REASSIGN") == "ổi ca"


def test_reassign_to_same_user_is_rejected(db_session: Session) -> None:
    task = _assign(db_session, _new_task(db_session), "nv_cat")
    with pytest.raises(BusinessError) as exc:
        TaskService.reassign_task(
            db_session,
            task_id=task.task_id,
            assigner_id=_user_id(db_session, "thukho"),
            req=ReassignTaskRequest(
                new_assigned_to_user_id=_user_id(db_session, "nv_cat"),
                reason="Trùng ngưi",
                version_no=task.version_no,
            ),
            warehouse_id=task.warehouse_id,
        )
    assert exc.value.code == "INVALID_STATE"


def test_reassign_wrong_stage_is_rejected(db_session: Session) -> None:
    task = _assign(db_session, _new_task(db_session, "CAT_HANG"), "nv_cat")
    with pytest.raises(BusinessError) as exc:
        TaskService.reassign_task(
            db_session,
            task_id=task.task_id,
            assigner_id=_user_id(db_session, "thukho"),
            req=ReassignTaskRequest(
                new_assigned_to_user_id=_user_id(db_session, "nv_nhan"),
                reason="Sai khâu",
                version_no=task.version_no,
            ),
            warehouse_id=task.warehouse_id,
        )
    assert exc.value.code == "TASKS_STAGE_MISMATCH"


def test_reassign_wrong_version_conflict(db_session: Session) -> None:
    task = _assign(db_session, _new_task(db_session, "QUAN_LY_CHUNG", "INTERNAL_MOVE"), "thukho")
    with pytest.raises(BusinessError) as exc:
        TaskService.reassign_task(
            db_session,
            task_id=task.task_id,
            assigner_id=_user_id(db_session, "thukho"),
            req=ReassignTaskRequest(
                new_assigned_to_user_id=_user_id(db_session, "quanly"),
                reason="Lệch phiên bản",
                version_no=99,
            ),
            warehouse_id=task.warehouse_id,
        )
    assert exc.value.code == "VERSION_CONFLICT"


def test_reject_logs_task_reject_audit(db_session: Session) -> None:
    task = _assign(db_session, _new_task(db_session), "nv_cat")
    rejected = TaskService.reject_task(
        db_session,
        task_id=task.task_id,
        worker_id=_user_id(db_session, "nv_cat"),
        req=RejectTaskRequest(rejection_reason="Kệ đầy", version_no=task.version_no),
        warehouse_id=task.warehouse_id,
    )
    assert rejected.status == "REJECTED"
    assert _audit_reason(db_session, task.task_id, "TASK_REJECT") == "Kệ đầy"


# ----------------------------------------------------------------------------
# cancel
# ----------------------------------------------------------------------------


def test_cancel_logs_reason_without_touching_rejection_reason(db_session: Session) -> None:
    task = _assign(db_session, _new_task(db_session), "nv_cat")
    cancelled = TaskService.cancel_task(
        db_session,
        task_id=task.task_id,
        actor_id=_user_id(db_session, "thukho"),
        req=CancelTaskRequest(cancel_reason="Hủy đơn", version_no=task.version_no),
        warehouse_id=task.warehouse_id,
    )
    assert cancelled.status == "CANCELLED"
    assert cancelled.rejection_reason is None
    assert _audit_reason(db_session, task.task_id, "TASK_CANCEL") == "Hủy đơn"


def test_cancel_twice_is_invalid_state(db_session: Session) -> None:
    task = _new_task(db_session)
    cancelled = TaskService.cancel_task(
        db_session,
        task_id=task.task_id,
        actor_id=_user_id(db_session, "thukho"),
        req=CancelTaskRequest(cancel_reason="Hủy lần 1", version_no=task.version_no),
        warehouse_id=task.warehouse_id,
    )
    with pytest.raises(BusinessError) as exc:
        TaskService.cancel_task(
            db_session,
            task_id=task.task_id,
            actor_id=_user_id(db_session, "thukho"),
            req=CancelTaskRequest(cancel_reason="Hủy lần 2", version_no=cancelled.version_no),
            warehouse_id=task.warehouse_id,
        )
    assert exc.value.code == "INVALID_STATE"


def test_cancel_completed_task_is_invalid_state(db_session: Session) -> None:
    task = _assign(db_session, _new_task(db_session), "nv_cat")
    started = TaskService.accept_task(
        db_session,
        task_id=task.task_id,
        worker_id=_user_id(db_session, "nv_cat"),
        req=AcceptTaskRequest(version_no=task.version_no),
        warehouse_id=task.warehouse_id,
    )
    done = TaskService.complete_task(
        db_session,
        task_id=task.task_id,
        worker_id=_user_id(db_session, "nv_cat"),
        req=CompleteTaskRequest(version_no=started.version_no),
        warehouse_id=task.warehouse_id,
    )
    assert done.status == "COMPLETED"
    with pytest.raises(BusinessError) as exc:
        TaskService.cancel_task(
            db_session,
            task_id=task.task_id,
            actor_id=_user_id(db_session, "thukho"),
            req=CancelTaskRequest(cancel_reason="Hủy task đã xong", version_no=done.version_no),
            warehouse_id=task.warehouse_id,
        )
    assert exc.value.code == "INVALID_STATE"


def test_cancel_wrong_version_conflict(db_session: Session) -> None:
    task = _new_task(db_session)
    with pytest.raises(BusinessError) as exc:
        TaskService.cancel_task(
            db_session,
            task_id=task.task_id,
            actor_id=_user_id(db_session, "thukho"),
            req=CancelTaskRequest(cancel_reason="Sai version", version_no=99),
            warehouse_id=task.warehouse_id,
        )
    assert exc.value.code == "VERSION_CONFLICT"


# ----------------------------------------------------------------------------
# Endpoint: vai trò đúng và vai trò sai cho toàn bộ endpoint
# ----------------------------------------------------------------------------


def _login(username: str) -> tuple[dict[str, str], str]:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    assert res.status_code == 200, f"ăng nhập thất bại cho {username}"
    data = res.json()["data"]
    return {"Authorization": f"Bearer {data['access_token']}"}, str(data["user"]["user_id"])


def test_endpoints_full_lifecycle_and_rbac() -> None:
    """Thử đủ các endpoint của tasks với vai trò đúng (thukho, nv_cat) và vai trò sai (nv_nhan)."""
    thukho, thukho_id = _login("thukho")
    _, quanly_id = _login("quanly")
    nv_cat, nv_cat_id = _login("nv_cat")
    nv_nhan, _ = _login("nv_nhan")

    # 1. GET /tasks & POST /tasks: vai trò đúng (thukho) -> 200, vai trò sai (nv_nhan) -> 403
    assert client.get(BASE, headers=thukho).status_code == 200
    assert (
        client.post(
            BASE,
            headers=nv_nhan,
            json={
                "task_type": "PUTAWAY",
                "stage": "CAT_HANG",
                "ref_doc_type": "GRN",
                "ref_doc_id": str(uuid.uuid4()),
            },
        ).status_code
        == 403
    )

    created = client.post(
        BASE,
        headers=thukho,
        json={
            "task_type": "PUTAWAY",
            "stage": "CAT_HANG",
            "ref_doc_type": "GRN",
            "ref_doc_id": str(uuid.uuid4()),
            "priority": "HIGH",
        },
    )
    assert created.status_code == 200, created.text
    task = created.json()["data"]
    task_id = task["task_id"]
    version = task["version_no"]

    try:
        # 2. POST /assign: thukho -> 200
        res = client.post(
            f"{BASE}/{task_id}/assign",
            headers=thukho,
            json={"assigned_to_user_id": nv_cat_id, "version_no": version},
        )
        assert res.status_code == 200, res.text
        version = res.json()["data"]["version_no"]

        # 3. GET /{id}, POST /accept, POST /complete: vai trò sai (nv_nhan không được giao) -> 403
        assert client.get(f"{BASE}/{task_id}", headers=nv_nhan).status_code == 403
        assert (
            client.post(
                f"{BASE}/{task_id}/accept", headers=nv_nhan, json={"version_no": version}
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"{BASE}/{task_id}/reject",
                headers=nv_nhan,
                json={"rejection_reason": "Sai ngưi", "version_no": version},
            ).status_code
            == 403
        )

        # Vai trò đúng (nv_cat được giao): GET /{id}, POST /reject -> 200
        assert client.get(f"{BASE}/{task_id}", headers=nv_cat).status_code == 200
        res_rej = client.post(
            f"{BASE}/{task_id}/reject",
            headers=nv_cat,
            json={"rejection_reason": "Cần kiểm tra lại vị trí", "version_no": version},
        )
        assert res_rej.status_code == 200, res_rej.text
        version = res_rej.json()["data"]["version_no"]

        # 4. POST /reassign sang quanly (trên task QUAN_LY_CHUNG) và accept + complete trên task
        CAT_HANG
        res_re = client.post(
            f"{BASE}/{task_id}/assign",
            headers=thukho,
            json={"assigned_to_user_id": nv_cat_id, "version_no": version},
        )
        assert res_re.status_code == 200
        version = res_re.json()["data"]["version_no"]

        res_acc = client.post(
            f"{BASE}/{task_id}/accept", headers=nv_cat, json={"version_no": version}
        )
        assert res_acc.status_code == 200
        version = res_acc.json()["data"]["version_no"]

        # Vai trò sai (nv_nhan) gi complete -> 403; vai trò đúng (nv_cat) -> 200
        assert (
            client.post(
                f"{BASE}/{task_id}/complete", headers=nv_nhan, json={"version_no": version}
            ).status_code
            == 403
        )
        res_done = client.post(
            f"{BASE}/{task_id}/complete", headers=nv_cat, json={"version_no": version}
        )
        assert res_done.status_code == 200
    finally:
        # Tạo 1 task phụ để test reassign + cancel và dn sạch
        extra = client.post(
            BASE,
            headers=thukho,
            json={
                "task_type": "INTERNAL_MOVE",
                "stage": "QUAN_LY_CHUNG",
                "ref_doc_type": "GRN",
                "ref_doc_id": str(uuid.uuid4()),
            },
        ).json()["data"]
        ex_id = extra["task_id"]
        ex_ver = extra["version_no"]
        r1 = client.post(
            f"{BASE}/{ex_id}/assign",
            headers=thukho,
            json={"assigned_to_user_id": thukho_id, "version_no": ex_ver},
        ).json()["data"]
        r2 = client.post(
            f"{BASE}/{ex_id}/reassign",
            headers=thukho,
            json={
                "new_assigned_to_user_id": quanly_id,
                "reason": "Cân bằng tải",
                "version_no": r1["version_no"],
            },
        ).json()["data"]
        r3 = client.post(
            f"{BASE}/{ex_id}/cancel",
            headers=thukho,
            json={"cancel_reason": "Dn dữ liệu kiểm thử", "version_no": r2["version_no"]},
        )
        assert r3.status_code == 200


@pytest.mark.parametrize(
    ("action", "body"),
    [
        ("assign", {"assigned_to_user_id": str(uuid.uuid4()), "version_no": 1}),
        (
            "reassign",
            {"new_assigned_to_user_id": str(uuid.uuid4()), "reason": "x", "version_no": 1},
        ),
        ("cancel", {"cancel_reason": "x", "version_no": 1}),
    ],
)
def test_endpoints_forbidden_for_worker_role(action: str, body: dict[str, Any]) -> None:
    """nv_nhan (nhân viên thực thi) gi endpoint của quản lý phải bị 403."""
    headers, _ = _login("nv_nhan")
    res = client.post(f"{BASE}/{uuid.uuid4()}/{action}", headers=headers, json=body)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN"
