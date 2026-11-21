"""ABEST WMS - Kiểm thử Unit: Quản lý Transaction mỗi request.

Quy định:
- Một transaction mỗi request: commit khi thành công, rollback khi lỗi.
- Kiểm tra: một request ghi 2 bước mà bước 2 lỗi thì bước 1 bị rollback,
  không để lại dòng nào trong CSDL.
"""

import uuid

from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from server.app.core.database import SessionLocal, get_db
from server.app.core.exceptions import BusinessError
from server.app.core.responses import success_response
from server.app.main import app

dummy_tx_router = APIRouter(prefix="/test-transaction")


@dummy_tx_router.post("/two-step-success")
def two_step_success_endpoint(code1: str, code2: str, db: Session = Depends(get_db)) -> dict:
    """Request ghi 2 bước thành công."""
    db.execute(
        text(
            """
            INSERT INTO reason_codes (reason_code, reason_category, description, is_active)
            VALUES (:code, 'OTHER', 'Test Reason 1', TRUE);
            """
        ),
        {"code": code1},
    )

    db.execute(
        text(
            """
            INSERT INTO reason_codes (reason_code, reason_category, description, is_active)
            VALUES (:code, 'OTHER', 'Test Reason 2', TRUE);
            """
        ),
        {"code": code2},
    )

    return success_response(data={"message": "Created successfully"})


@dummy_tx_router.post("/two-step-failure")
def two_step_failure_endpoint(code1: str, db: Session = Depends(get_db)) -> dict:
    """Request ghi 2 bước mà bước 2 phát sinh lỗi -> bước 1 phải bị rollback hoàn toàn."""
    # Bước 1: Ghi thành công
    db.execute(
        text(
            """
            INSERT INTO reason_codes (reason_code, reason_category, description, is_active)
            VALUES (:code, 'OTHER', 'Test Reason Rollback', TRUE);
            """
        ),
        {"code": code1},
    )

    # Bước 2: Ném lỗi nghiệp vụ hoặc exception
    raise BusinessError(
        code="SIMULATED_STEP2_FAILURE",
        message="Mô phỏng lỗi ở bước 2 để kiểm tra transaction rollback",
        http_status=400,
    )


app.include_router(dummy_tx_router)
client = TestClient(app)


def test_transaction_two_step_rollback_on_error() -> None:
    """Khẳng định khi bước 2 gặp lỗi, bước 1 bị rollback và không để lại dòng nào trong DB."""
    test_code = f"ROLLBACK_TEST_{uuid.uuid4().hex[:8]}"

    # Gọi endpoint ghi 2 bước mà bước 2 thất bại
    response = client.post(f"/test-transaction/two-step-failure?code1={test_code}")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "SIMULATED_STEP2_FAILURE"

    # Kiểm tra trực tiếp trong DB bằng session độc lập: Bản ghi bước 1 không được phép tồn tại
    verify_session: Session = SessionLocal()
    try:
        row = verify_session.execute(
            text("SELECT COUNT(*) FROM reason_codes WHERE reason_code = :code;"),
            {"code": test_code},
        ).scalar()
        assert row == 0, f"Bản ghi {test_code} từ bước 1 chưa bị rollback!"
    finally:
        verify_session.close()


def test_transaction_commits_when_successful() -> None:
    """Khẳng định khi request không có lỗi, transaction được commit thành công."""
    code1 = f"TX_OK_1_{uuid.uuid4().hex[:8]}"
    code2 = f"TX_OK_2_{uuid.uuid4().hex[:8]}"

    response = client.post(f"/test-transaction/two-step-success?code1={code1}&code2={code2}")
    assert response.status_code == 200

    verify_session: Session = SessionLocal()
    try:
        count = verify_session.execute(
            text("SELECT COUNT(*) FROM reason_codes WHERE reason_code IN (:c1, :c2);"),
            {"c1": code1, "c2": code2},
        ).scalar()
        assert count == 2, "Cả 2 bản ghi không được commit đầy đủ vào CSDL!"
    finally:
        # Dọn dẹp dữ liệu test
        verify_session.execute(
            text("DELETE FROM reason_codes WHERE reason_code IN (:c1, :c2);"),
            {"c1": code1, "c2": code2},
        )
        verify_session.commit()
        verify_session.close()
