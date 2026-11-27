"""ABEST WMS - Kiểm thử Unit & Integration cho Phân hệ Xác thực và Phân quyền (Auth & RBAC).

Quy định kiểm thử bắt buộc theo Mục 8 Quy trình dựng khung:
(a) 9 tài khoản seed đều đăng nhập được; /auth/me trả đúng role và danh sách quyền khác nhau.
(b) Test tham số hóa theo từng cặp (vai trò, quyền) trong role_permissions:
    endpoint thử trả 200 nếu có quyền và 403 FORBIDDEN nếu không; riêng admin bị chặn mọi quyền.
(c) Sai mật khẩu, token hỏng, token hết hạn đều trả đúng mã lỗi.
(d) Phạm vi kho: tạo kho thứ hai trong test, tài khoản của kho này không thấy dữ liệu của kho kia.
(e) audit_logs có dòng mới sau một hành động ghi.
(f) Đổi mật khẩu rồi đăng nhập bằng mật khẩu mới.
(g) make ci xanh.
(h) Đăng nhập thành công/thất bại đọc toàn bộ log: không chứa token, mật khẩu, Authorization.
"""

import io
import logging
import uuid
from collections.abc import Generator
from datetime import timedelta
from typing import Any

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from server.app.core.database import SessionLocal
from server.app.core.logging import JSONFormatter, SensitiveDataFilter
from server.app.core.rbac import (
    UserContext,
    enforce_warehouse_scope,
    get_current_user,
    require_permission,
)
from server.app.core.responses import success_response
from server.app.core.security import create_access_token
from server.app.main import app

# ---------------------------------------------------------------------------
# Router thử nghiệm CHỈ nằm trong thư mục test để kiểm tra phân quyền
# ---------------------------------------------------------------------------
dummy_rbac_router = APIRouter(prefix="/test-rbac", tags=["Test RBAC"])

ALL_PERMISSIONS = [
    "AD-1",
    "CAT-1",
    "DG-1",
    "KK-1",
    "NH-1",
    "NH-2",
    "NH-5",
    "QL-1.1",
    "QL-2.1",
    "QL-2.3",
    "QL-5.3",
    "QL-8.1",
    "QL-9.10",
    "SO-1",
    "TK-1.1",
    "TK-3.2",
    "TK-4.4",
]


def _build_perm_route(code: str) -> None:
    @dummy_rbac_router.get(f"/perm/{code}")
    def check_route(access_type: str = Depends(require_permission(code))) -> dict[str, Any]:
        return success_response(data={"permission": code, "access_type": access_type})


for perm_code in ALL_PERMISSIONS:
    _build_perm_route(perm_code)


@dummy_rbac_router.get("/warehouse/{warehouse_id}")
def check_warehouse_scope(
    warehouse_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
) -> dict[str, Any]:
    enforce_warehouse_scope(user, warehouse_id)
    return success_response(data={"warehouse_id": str(warehouse_id)})


app.include_router(dummy_rbac_router)
client = TestClient(app)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Cung cấp session CSDL độc lập có rollback sau mỗi bài test."""
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


SEED_ACCOUNTS = [
    ("admin", "admin"),
    ("bgd", "bgd"),
    ("nv_cat", "nv-cat"),
    ("nv_dongoi", "nv-dongoi"),
    ("nv_kiemke", "nv-kiemke"),
    ("nv_nhan", "nv-nhan"),
    ("nv_soan", "nv-soan"),
    ("quanly", "quanly"),
    ("thukho", "thukho"),
]


def test_all_9_seed_accounts_login_and_me() -> None:
    """(a) 9 tài khoản seed đều đăng nhập được; /auth/me trả đúng role và quyền."""
    role_permissions_seen: dict[str, set[str]] = {}

    for username, expected_role in SEED_ACCOUNTS:
        # 1. Đăng nhập
        login_res = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "Demo@123456"},
        )
        assert login_res.status_code == 200, f"Đăng nhập thất bại cho user {username}"
        login_data = login_res.json()["data"]

        token = login_data["access_token"]
        assert token and len(token) > 20
        assert login_data["token_type"] == "Bearer"
        assert login_data["expires_in_hours"] == 8
        assert login_data["user"]["role_code"] == expected_role

        # 2. Gọi /auth/me bằng token vừa nhận
        me_res = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_res.status_code == 200
        me_data = me_res.json()["data"]

        assert me_data["username"] == username
        assert me_data["role_code"] == expected_role
        assert "permissions" in me_data
        assert isinstance(me_data["permissions"], list)
        assert len(me_data["permissions"]) > 0

        perms = {p["permission_code"] for p in me_data["permissions"]}
        role_permissions_seen[expected_role] = perms

    # 3. Khẳng định các vai trò khác nhau có danh sách quyền khác nhau
    assert role_permissions_seen["admin"] == {"AD-1"}
    assert role_permissions_seen["nv-nhan"] != role_permissions_seen["nv-cat"]
    assert role_permissions_seen["nv-kiemke"] != role_permissions_seen["quanly"]
    assert len(role_permissions_seen["quanly"]) >= 10


def test_parameterized_role_permissions_matrix(db_session: Session) -> None:
    """(b) Test tham số hóa theo từng cặp (vai trò, quyền): 200 nếu có quyền, 403 nếu không.

    Riêng admin bị chặn mọi quyền nghiệp vụ kho (chỉ được phép AD-1).
    """
    # 1. Đọc ma trận phân quyền thực tế từ CSDL
    rows = db_session.execute(
        text(
            """
            SELECT r.role_code, rp.permission_code
            FROM roles r
            JOIN role_permissions rp ON r.role_id = rp.role_id;
            """
        )
    ).fetchall()

    role_perm_set = {(r[0], r[1]) for r in rows}

    # 2. Lấy token đăng nhập cho từng vai trò
    tokens: dict[str, str] = {}
    for username, role_code in SEED_ACCOUNTS:
        res = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "Demo@123456"},
        )
        assert res.status_code == 200
        tokens[role_code] = res.json()["data"]["access_token"]

    # 3. Kiểm tra từng cặp (role, permission)
    for _, role_code in SEED_ACCOUNTS:
        token = tokens[role_code]
        headers = {"Authorization": f"Bearer {token}"}

        for perm in ALL_PERMISSIONS:
            endpoint = f"/test-rbac/perm/{perm}"
            res = client.get(endpoint, headers=headers)

            if role_code == "admin":
                # Admin chỉ có quyền AD-1, bị chặn mọi quyền nghiệp vụ kho khác
                if perm == "AD-1":
                    assert res.status_code == 200, f"Admin phải truy cập được {perm}"
                else:
                    assert res.status_code == 403, f"Admin phải bị chặn quyền nghiệp vụ {perm}"
                    assert res.json()["error"]["code"] == "FORBIDDEN"
            else:
                has_permission = (role_code, perm) in role_perm_set
                if has_permission:
                    assert (
                        res.status_code == 200
                    ), f"Vai trò {role_code} có quyền {perm} nhưng bị từ chối"
                else:
                    assert (
                        res.status_code == 403
                    ), f"Vai trò {role_code} không có quyền {perm} nhưng lại truy cập được"
                    assert res.json()["error"]["code"] == "FORBIDDEN"


# Mã con là bước nghiệp vụ cùng dòng ma trận (slide 90) với mã cha, phải được cấp giống hệt.
CHILD_TO_PARENT_PERMISSION = {"NH-2": "NH-1", "NH-5": "NH-1", "QL-2.3": "QL-2.1"}


def test_child_permissions_mirror_parent_row(db_session: Session) -> None:
    """Mã con có đúng tập (vai trò, mức truy cập) như mã cha trong ma trận phân quyền."""
    rows = db_session.execute(
        text(
            "SELECT r.role_code, rp.permission_code, rp.access_type "
            "FROM roles r JOIN role_permissions rp ON r.role_id = rp.role_id"
        )
    ).fetchall()

    def grants(code: str) -> set[tuple[str, str]]:
        return {(r[0], r[2]) for r in rows if r[1] == code}

    for child, parent in CHILD_TO_PARENT_PERMISSION.items():
        assert grants(child), f"Mã {child} chưa được cấp cho vai trò nào"
        assert grants(child) == grants(parent), f"{child} lệch quyền so với {parent}"


def test_invalid_credentials_and_token_errors() -> None:
    """(c) Sai mật khẩu, token hỏng, token hết hạn đều trả đúng mã lỗi."""
    # 1. Sai mật khẩu
    wrong_pass_res = client.post(
        "/api/v1/auth/login",
        json={"username": "thukho", "password": "WrongPassword123"},
    )
    assert wrong_pass_res.status_code == 401
    assert wrong_pass_res.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"

    # 2. Token hỏng
    corrupt_res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer this-is-not-a-valid-jwt-token"},
    )
    assert corrupt_res.status_code == 401
    assert corrupt_res.json()["error"]["code"] == "AUTH_INVALID_TOKEN"

    # 3. Token hết hạn
    expired_token = create_access_token(
        {"sub": str(uuid.uuid4()), "role_code": "thukho", "username": "thukho"},
        expires_delta=timedelta(seconds=-30),
    )
    expired_res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert expired_res.status_code == 401
    assert expired_res.json()["error"]["code"] == "AUTH_TOKEN_EXPIRED"


def test_warehouse_scope_isolation(db_session: Session) -> None:
    """(d) Phạm vi kho: tạo kho thứ hai trong test, tài khoản kho này không thấy dữ liệu kho kia."""
    # 1. Tạo kho thứ hai WH02 trong CSDL
    wh2_id = uuid.uuid4()
    db_session.execute(
        text(
            """
            INSERT INTO warehouses (warehouse_id, erp_warehouse_code, warehouse_name, is_active)
            VALUES (:id, 'WH02_TEST', 'Kho Chi Nhánh 2 Test', TRUE);
            """
        ),
        {"id": wh2_id},
    )
    db_session.commit()

    try:
        # 2. Đăng nhập tài khoản thủ kho thuộc kho WH01 (seed)
        login_res = client.post(
            "/api/v1/auth/login",
            json={"username": "thukho", "password": "Demo@123456"},
        )
        token = login_res.json()["data"]["access_token"]
        wh1_id = login_res.json()["data"]["user"]["warehouse_id"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Truy cập tài nguyên kho WH01 của chính mình -> Thành công 200
        res_ok = client.get(f"/test-rbac/warehouse/{wh1_id}", headers=headers)
        assert res_ok.status_code == 200

        # 4. Truy cập tài nguyên kho WH02 của kho khác -> Bị chặn 404 NOT_FOUND
        res_fail = client.get(f"/test-rbac/warehouse/{wh2_id}", headers=headers)
        assert res_fail.status_code == 404
        assert res_fail.json()["error"]["code"] == "NOT_FOUND"
    finally:
        # Dọn dẹp kho WH02 sau bài test
        db_session.execute(
            text("DELETE FROM warehouses WHERE warehouse_id = :id;"),
            {"id": wh2_id},
        )
        db_session.commit()


def test_audit_logs_recorded(db_session: Session) -> None:
    """(e) audit_logs có dòng mới sau một hành động ghi."""
    # Đếm số lượng log trước khi đăng nhập
    count_before = db_session.execute(text("SELECT COUNT(*) FROM audit_logs;")).scalar() or 0

    # Thực hiện hành động đăng nhập
    res = client.post(
        "/api/v1/auth/login",
        json={"username": "nv_nhan", "password": "Demo@123456"},
    )
    assert res.status_code == 200

    # Đếm số lượng log sau khi đăng nhập
    count_after = db_session.execute(text("SELECT COUNT(*) FROM audit_logs;")).scalar() or 0
    assert count_after > count_before

    # Kiểm tra dòng audit log mới nhất có action_code = LOGIN
    latest_log = db_session.execute(
        text(
            """
            SELECT action_code, entity_name, actor_user_id
            FROM audit_logs
            ORDER BY audit_id DESC LIMIT 1;
            """
        )
    ).fetchone()
    assert latest_log is not None
    assert latest_log[0] == "LOGIN"
    assert latest_log[1] == "users"


def test_change_password_and_login_with_new_password() -> None:
    """(f) Đổi mật khẩu rồi đăng nhập bằng mật khẩu mới thành công."""
    target_user = "nv_cat"
    old_pass = "Demo@123456"
    new_pass = "Cat@NewSecurePass2026!"

    # 1. Đăng nhập bằng mật khẩu cũ để lấy token
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": target_user, "password": old_pass},
    )
    token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    try:
        # 2. Đổi mật khẩu
        change_res = client.post(
            "/api/v1/auth/change-password",
            json={"old_password": old_pass, "new_password": new_pass},
            headers=headers,
        )
        assert change_res.status_code == 200
        assert "thành công" in change_res.json()["data"]["message"]

        # 3. Đăng nhập bằng mật khẩu cũ phải THẤT BẠI (401)
        fail_res = client.post(
            "/api/v1/auth/login",
            json={"username": target_user, "password": old_pass},
        )
        assert fail_res.status_code == 401
        assert fail_res.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"

        # 4. Đăng nhập bằng mật khẩu mới phải THÀNH CÔNG (200)
        ok_res = client.post(
            "/api/v1/auth/login",
            json={"username": target_user, "password": new_pass},
        )
        assert ok_res.status_code == 200
        assert "access_token" in ok_res.json()["data"]

    finally:
        # Khôi phục lại mật khẩu ban đầu để không làm ảnh hưởng các bài test khác
        reset_token = client.post(
            "/api/v1/auth/login",
            json={"username": target_user, "password": new_pass},
        ).json()["data"]["access_token"]

        client.post(
            "/api/v1/auth/change-password",
            json={"old_password": new_pass, "new_password": old_pass},
            headers={"Authorization": f"Bearer {reset_token}"},
        )


def test_login_logging_masks_all_credentials() -> None:
    """(h) Đăng nhập thành công/thất bại đọc toàn bộ log: không chứa token, mật khẩu, header."""
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(SensitiveDataFilter())

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    test_pass = "SuperSecretPasswordToTestMask!"

    try:
        # Đăng nhập thất bại với mật khẩu nhạy cảm
        client.post(
            "/api/v1/auth/login",
            json={"username": "thukho", "password": test_pass},
        )

        # Đăng nhập thành công
        success_res = client.post(
            "/api/v1/auth/login",
            json={"username": "thukho", "password": "Demo@123456"},
        )
        token = success_res.json()["data"]["access_token"]

        # Gọi endpoint bảo vệ kèm Authorization header
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    finally:
        root_logger.removeHandler(handler)

    log_output = log_stream.getvalue()

    # Khẳng định tuyệt đối KHÔNG lộ mật khẩu, JWT token hay Bearer header trong toàn bộ log
    assert test_pass not in log_output
    assert "Demo@123456" not in log_output
    assert token not in log_output
    assert f"Bearer {token}" not in log_output
