"""ABEST WMS - ENUMs dùng chung, sinh tự động từ PostgreSQL pg_enum.

DO NOT EDIT MANUALLY - Chạy `python scripts/gen_enums.py` để cập nhật.
"""

from enum import Enum


class ActorGroupType(str, Enum):
    """PostgreSQL ENUM `actor_group_type`."""

    THUC_THI = "THUC_THI"
    DIEU_HANH = "DIEU_HANH"
    LANH_DAO = "LANH_DAO"
    HE_THONG = "HE_THONG"


class ApprovalObjectType(str, Enum):
    """PostgreSQL ENUM `approval_object_type`."""

    GRN_DISCREPANCY = "GRN_DISCREPANCY"
    CYCLE_COUNT_DIFF = "CYCLE_COUNT_DIFF"
    STOCK_ADJUSTMENT = "STOCK_ADJUSTMENT"
    STOCK_SCRAP = "STOCK_SCRAP"
    OVERTIME_REQUEST = "OVERTIME_REQUEST"


class ApprovalStatusType(str, Enum):
    """PostgreSQL ENUM `approval_status_type`."""

    PENDING_D1 = "PENDING_D1"
    PENDING_D2 = "PENDING_D2"
    PENDING_D3 = "PENDING_D3"
    NEED_INFO = "NEED_INFO"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


class ApprovalTierType(str, Enum):
    """PostgreSQL ENUM `approval_tier_type`."""

    AUTO_TOLERANCE_Z = "AUTO_TOLERANCE_Z"
    D1_THUKHO = "D1_THUKHO"
    D2_QUANLY = "D2_QUANLY"
    D3_BGD = "D3_BGD"


class AuthProviderType(str, Enum):
    """PostgreSQL ENUM `auth_provider_type`."""

    SSO_LDAP = "SSO_LDAP"
    LOCAL_SEASONAL = "LOCAL_SEASONAL"


class GiDocType(str, Enum):
    """PostgreSQL ENUM `gi_doc_type`."""

    SO_SHIPMENT = "SO_SHIPMENT"
    INTER_WH_TRANSFER = "INTER_WH_TRANSFER"
    SUPPLIER_RETURN = "SUPPLIER_RETURN"
    CUSTOMER_RETURN_BACK = "CUSTOMER_RETURN_BACK"


class GrnStatusType(str, Enum):
    """PostgreSQL ENUM `grn_status_type`."""

    DRAFT = "DRAFT"
    COUNTING = "COUNTING"
    PENDING_D1 = "PENDING_D1"
    PENDING_D2 = "PENDING_D2"
    PENDING_D3 = "PENDING_D3"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"
    SYNCED_ERP = "SYNCED_ERP"


class LocationStatusType(str, Enum):
    """PostgreSQL ENUM `location_status_type`."""

    EMPTY = "EMPTY"
    PARTIAL = "PARTIAL"
    FULL = "FULL"
    COUNTING_LOCKED = "COUNTING_LOCKED"
    MAINTENANCE_LOCKED = "MAINTENANCE_LOCKED"
    DAMAGED_HOLD = "DAMAGED_HOLD"


class OrderStatusType(str, Enum):
    """PostgreSQL ENUM `order_status_type`."""

    NEW = "NEW"
    PICKING = "PICKING"
    PICKED = "PICKED"
    PACKING = "PACKING"
    WAITING_WAYBILL = "WAITING_WAYBILL"
    READY_TO_SHIP = "READY_TO_SHIP"
    SHIPPED = "SHIPPED"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    PARTIAL_DELIVERED = "PARTIAL_DELIVERED"
    DELIVERY_FAILED = "DELIVERY_FAILED"
    ON_HOLD = "ON_HOLD"
    CANCELLED = "CANCELLED"


class PalletStatusType(str, Enum):
    """PostgreSQL ENUM `pallet_status_type`."""

    RECEIVING = "RECEIVING"
    QUARANTINE_HOLD = "QUARANTINE_HOLD"
    DAMAGED_HOLD = "DAMAGED_HOLD"
    STAGED = "STAGED"
    PUTAWAY_IN_PROGRESS = "PUTAWAY_IN_PROGRESS"
    STORED = "STORED"
    EMPTY = "EMPTY"
    REJECTED_PENDING_RETURN = "REJECTED_PENDING_RETURN"


class PickModeType(str, Enum):
    """PostgreSQL ENUM `pick_mode_type`."""

    SINGLE_ORDER = "SINGLE_ORDER"
    BATCH = "BATCH"
    WAVE = "WAVE"


class PickingRuleType(str, Enum):
    """PostgreSQL ENUM `picking_rule_type`."""

    FEFO = "FEFO"
    FIFO = "FIFO"


class PoStatusType(str, Enum):
    """PostgreSQL ENUM `po_status_type`."""

    PENDING = "PENDING"
    RECEIVING = "RECEIVING"
    PARTIAL_RECEIVED = "PARTIAL_RECEIVED"
    FULLY_RECEIVED = "FULLY_RECEIVED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class PostApprovalExecStatus(str, Enum):
    """PostgreSQL ENUM `post_approval_exec_status`."""

    NOT_APPLICABLE = "NOT_APPLICABLE"
    WAITING_EXECUTION = "WAITING_EXECUTION"
    WAITING_SCRAP_EXECUTION = "WAITING_SCRAP_EXECUTION"
    EXECUTED_INVENTORY = "EXECUTED_INVENTORY"
    SCRAP_EXECUTED = "SCRAP_EXECUTED"
    SYNCED_ERP = "SYNCED_ERP"
    FAILED_SYNC = "FAILED_SYNC"


class SyncErrorCategory(str, Enum):
    """PostgreSQL ENUM `sync_error_category`."""

    NONE = "NONE"
    BUSINESS_ERROR = "BUSINESS_ERROR"
    TECHNICAL_ERROR = "TECHNICAL_ERROR"


class TaskPriorityType(str, Enum):
    """PostgreSQL ENUM `task_priority_type`."""

    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class TaskStatusType(str, Enum):
    """PostgreSQL ENUM `task_status_type`."""

    UNASSIGNED = "UNASSIGNED"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED_OFFLINE = "PAUSED_OFFLINE"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class TaskType(str, Enum):
    """PostgreSQL ENUM `task_type`."""

    RECEIVING = "RECEIVING"
    PUTAWAY = "PUTAWAY"
    PICKING = "PICKING"
    PACKING = "PACKING"
    CYCLE_COUNT = "CYCLE_COUNT"
    RECOUNT = "RECOUNT"
    RETURN_PICKING = "RETURN_PICKING"
    INTERNAL_MOVE = "INTERNAL_MOVE"
    RETURN_TO_SHELF = "RETURN_TO_SHELF"
    SCRAP_EXECUTION = "SCRAP_EXECUTION"


class UserStatusType(str, Enum):
    """PostgreSQL ENUM `user_status_type`."""

    ACTIVE = "ACTIVE"
    LOCKED = "LOCKED"
    INACTIVE = "INACTIVE"
    EXPIRED = "EXPIRED"


class WorkStageType(str, Enum):
    """PostgreSQL ENUM `work_stage_type`."""

    NHAN_HANG = "NHAN_HANG"
    CAT_HANG = "CAT_HANG"
    SOAN_HANG = "SOAN_HANG"
    DONG_GOI_XUAT = "DONG_GOI_XUAT"
    KIEM_KE = "KIEM_KE"
    QUAN_LY_CHUNG = "QUAN_LY_CHUNG"
