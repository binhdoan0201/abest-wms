"""ABEST WMS - Hạ tầng Ghi nhận Nhật ký Hoạt động (Audit Logging).

Quy định theo Mục 9.3 Chuẩn API:
Bắt buộc ghi audit_logs cho các hành động:
- Đăng nhập (LOGIN)
- Đổi mật khẩu (CHANGE_PASSWORD)
- Tạo, gửi, duyệt, từ chối chứng từ (CREATE_DOC, SUBMIT_DOC, APPROVE_DOC, REJECT_DOC)
- Biến động tồn (INVENTORY_MOVEMENT)
- Giao, nhận, hủy task (TASK_ASSIGN, TASK_ACCEPT, TASK_COMPLETE, TASK_CANCEL)
- Đổi hoặc hủy đơn từ ERP (ERP_ORDER_CHANGE)

Bảng audit_logs là bản ghi bất biến (chỉ cho phép INSERT, cấm UPDATE/DELETE bởi trigger CSDL).
"""

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def create_audit_log(
    db: Session,
    action_code: str,
    entity_name: str,
    actor_user_id: uuid.UUID | None = None,
    warehouse_id: uuid.UUID | None = None,
    entity_id: uuid.UUID | None = None,
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
    delegated_from_user_id: uuid.UUID | None = None,
    reauth_verified: bool = False,
    ip_address: str | None = None,
    device_id: uuid.UUID | None = None,
) -> int:
    """Ghi một dòng nhật ký kiểm toán bất biến vào bảng audit_logs."""
    import json

    stmt = text(
        """
        INSERT INTO audit_logs (
            warehouse_id, actor_user_id, delegated_from_user_id,
            action_code, entity_name, entity_id,
            old_values, new_values, reauth_verified,
            ip_address, device_id, created_at
        ) VALUES (
            :warehouse_id, :actor_user_id, :delegated_from_user_id,
            :action_code, :entity_name, :entity_id,
            :old_values, :new_values, :reauth_verified,
            :ip_address, :device_id, NOW()
        ) RETURNING audit_id;
        """
    )

    params = {
        "warehouse_id": warehouse_id,
        "actor_user_id": actor_user_id,
        "delegated_from_user_id": delegated_from_user_id,
        "action_code": action_code,
        "entity_name": entity_name,
        "entity_id": entity_id,
        "old_values": json.dumps(old_values) if old_values is not None else None,
        "new_values": json.dumps(new_values) if new_values is not None else None,
        "reauth_verified": reauth_verified,
        "ip_address": ip_address,
        "device_id": device_id,
    }

    result = db.execute(stmt, params)
    audit_id: int = result.scalar_one()
    return audit_id
