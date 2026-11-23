"""ABEST WMS - Kiểm thử Phân hệ Nhiệm vụ (Tasks): assign, reassign, cancel (D-01, D-02).

Gồm hai nhóm:
- Kiểm thử service (có rollback sau mỗi bài, không để lại dữ liệu): giao, điều chuyển, hủy,
  khóa lạc quan `version_no`, giới hạn task mở, kiểm tra khâu làm việc, audit log.
- Kiểm thử endpoint: mỗi endpoint thử 1 vai trò đúng (`thukho`) và 1 vai trò sai (`nv_nhan`).
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
    TaskResponse,
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


def _new_task(db: Session, stage: str = "CAT_HANG", task_type: str = "PUTAWAY") -> TaskResponse:
    """Tạo task UNASSIGNED bằng service (chưa commit)."""
    return TaskService.create_task(
        db,
        warehouse_id=_warehouse_id(db),
        creator_id=_user_id(db, "thukho"),
        req=CreateTaskRequest(
            task_type=task_type,
            stage=stage,
            ref_doc_type="GRN",
            ref_doc_id=uuid.uuid4(),
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
# assign
# ----------------------------------------------------------------------------


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
        )
    assert exc.value.code == "NOT_FOUND"
    assert exc.value.http_status == 404


def test_assign_exceeds_max_open_tasks(db_session: Session) -> None:
    limit = TaskRepository.get_max_open_tasks(db_session, _warehouse_id(db_session))
    for _ in range(limit):
        _assign(db_session, _new_task(db_session, "KIEM_KE", "CYCLE_COUNT"), "nv_kiemke")
    extra = _new_task(db_session, "KIEM_KE", "CYCLE_COUNT")
    with pytest.raises(BusinessError) as exc:
        _assign(db_session, extra, "nv_kiemke")
    assert exc.value.code == "TASKS_MAX_OPEN_EXCEEDED"
    assert exc.value.http_status == 409


# ----------------------------------------------------------------------------
# reassign
# ----------------------------------------------------------------------------


def test_reassign_resets_started_at_and_logs_reason(db_session: Session) -> None:
    thukho_id = _user_id(db_session, "thukho")
    quanly_id = _user_id(db_session, "quanly")
    # Hai tài khoản thukho và quanly cùng khâu QUAN_LY_CHUNG nên dùng để thử điều chuyển.
    task = _assign(db_session, _new_task(db_session, "QUAN_LY_CHUNG", "INTERNAL_MOVE"), "thukho")
    started = TaskService.accept_task(
        db_session,
        task_id=task.task_id,
        worker_id=thukho_id,
        req=AcceptTaskRequest(version_no=task.version_no),
    )
    assert started.status == "IN_PROGRESS"
    assert started.started_at is not None

    moved = TaskService.reassign_task(
        db_session,
        task_id=task.task_id,
        assigner_id=thukho_id,
        req=ReassignTaskRequest(
            new_assigned_to_user_id=quanly_id, reason="Đổi ca", version_no=started.version_no
        ),
    )
    assert moved.status == "ASSIGNED"
    assert moved.assigned_to == quanly_id
    assert moved.started_at is None
    assert moved.version_no == started.version_no + 1
    assert _audit_reason(db_session, task.task_id, "TASK_REASSIGN") == "Đổi ca"


def test_reassign_to_same_user_is_rejected(db_session: Session) -> None:
    task = _assign(db_session, _new_task(db_session), "nv_cat")
    with pytest.raises(BusinessError) as exc:
        TaskService.reassign_task(
            db_session,
            task_id=task.task_id,
            assigner_id=_user_id(db_session, "thukho"),
            req=ReassignTaskRequest(
                new_assigned_to_user_id=_user_id(db_session, "nv_cat"),
                version_no=task.version_no,
            ),
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
                version_no=task.version_no,
            ),
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
                new_assigned_to_user_id=_user_id(db_session, "quanly"), version_no=99
            ),
        )
    assert exc.value.code == "VERSION_CONFLICT"


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
        req=CancelTaskRequest(version_no=task.version_no),
    )
    with pytest.raises(BusinessError) as exc:
        TaskService.cancel_task(
            db_session,
            task_id=task.task_id,
            actor_id=_user_id(db_session, "thukho"),
            req=CancelTaskRequest(version_no=cancelled.version_no),
        )
    assert exc.value.code == "INVALID_STATE"


def test_cancel_completed_task_is_invalid_state(db_session: Session) -> None:
    task = _assign(db_session, _new_task(db_session), "nv_cat")
    started = TaskService.accept_task(
        db_session,
        task_id=task.task_id,
        worker_id=_user_id(db_session, "nv_cat"),
        req=AcceptTaskRequest(version_no=task.version_no),
    )
    done = TaskService.complete_task(
        db_session,
        task_id=task.task_id,
        worker_id=_user_id(db_session, "nv_cat"),
        req=CompleteTaskRequest(version_no=started.version_no),
    )
    assert done.status == "COMPLETED"
    with pytest.raises(BusinessError) as exc:
        TaskService.cancel_task(
            db_session,
            task_id=task.task_id,
            actor_id=_user_id(db_session, "thukho"),
            req=CancelTaskRequest(version_no=done.version_no),
        )
    assert exc.value.code == "INVALID_STATE"


def test_cancel_wrong_version_conflict(db_session: Session) -> None:
    task = _new_task(db_session)
    with pytest.raises(BusinessError) as exc:
        TaskService.cancel_task(
            db_session,
            task_id=task.task_id,
            actor_id=_user_id(db_session, "thukho"),
            req=CancelTaskRequest(version_no=99),
        )
    assert exc.value.code == "VERSION_CONFLICT"


# ----------------------------------------------------------------------------
# Endpoint: vai trò đúng (thukho) và vai trò sai (nv_nhan)
# ----------------------------------------------------------------------------


def _login(username: str) -> tuple[dict[str, str], str]:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    assert res.status_code == 200, f"Đăng nhập thất bại cho {username}"
    data = res.json()["data"]
    return {"Authorization": f"Bearer {data['access_token']}"}, str(data["user"]["user_id"])


def test_endpoints_assign_reassign_cancel_with_supervisor() -> None:
    """thukho gọi đủ assign, reassign, cancel và luôn hủy task ở cuối để không để lại dữ liệu."""
    thukho, thukho_id = _login("thukho")
    _, quanly_id = _login("quanly")
    created = client.post(
        BASE,
        headers=thukho,
        json={
            "task_type": "INTERNAL_MOVE",
            "stage": "QUAN_LY_CHUNG",
            "ref_doc_type": "GRN",
            "ref_doc_id": str(uuid.uuid4()),
        },
    )
    assert created.status_code == 200, created.text
    task = created.json()["data"]
    task_id = task["task_id"]
    version = task["version_no"]
    try:
        res = client.post(
            f"{BASE}/{task_id}/assign",
            headers=thukho,
            json={"assigned_to_user_id": thukho_id, "version_no": version},
        )
        assert res.status_code == 200, res.text
        assert res.json()["data"]["status"] == "ASSIGNED"
        version = res.json()["data"]["version_no"]

        res = client.post(
            f"{BASE}/{task_id}/reassign",
            headers=thukho,
            json={
                "new_assigned_to_user_id": quanly_id,
                "reason": "Cân bằng tải",
                "version_no": version,
            },
        )
        assert res.status_code == 200, res.text
        assert res.json()["data"]["assigned_to"] == quanly_id
        version = res.json()["data"]["version_no"]
    finally:
        res = client.post(
            f"{BASE}/{task_id}/cancel",
            headers=thukho,
            json={"cancel_reason": "Dọn dữ liệu kiểm thử", "version_no": version},
        )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["status"] == "CANCELLED"


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
    """nv_nhan (nhân viên thực thi) gọi endpoint của quản lý phải bị 403."""
    headers, _ = _login("nv_nhan")
    res = client.post(f"{BASE}/{uuid.uuid4()}/{action}", headers=headers, json=body)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN"
