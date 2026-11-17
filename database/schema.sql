-- =============================================================================
-- HỆ QUẢN TRỊ CƠ SỞ DỮ LIỆU WMS (WAREHOUSE MANAGEMENT SYSTEM - MOBILE & WEB)
-- Phiên bản: v4.1 (Full Clean DDL - Đã vá toàn bộ 54 phát hiện F01..F54 & Chốt Q-1..Q-14)
-- Đối tượng: 17 tác nhân, 178 chức năng (bổ sung NH-5, DG-6, TK-5.10), 27 quy tắc [Q#]
-- Hệ quản trị mục tiêu: PostgreSQL 15+
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- PHẦN 1: KHAI BÁO CÁC KIỂU DỮ LIỆU ENUM (DANH MỤC CỐ ĐỊNH - 20 ENUMS)
-- =============================================================================

CREATE TYPE auth_provider_type AS ENUM ('SSO_LDAP', 'LOCAL_SEASONAL');
CREATE TYPE user_status_type AS ENUM ('ACTIVE', 'LOCKED', 'INACTIVE', 'EXPIRED');
CREATE TYPE actor_group_type AS ENUM ('THUC_THI', 'DIEU_HANH', 'LANH_DAO', 'HE_THONG');
CREATE TYPE work_stage_type AS ENUM ('NHAN_HANG', 'CAT_HANG', 'SOAN_HANG', 'DONG_GOI_XUAT', 'KIEM_KE', 'QUAN_LY_CHUNG');
CREATE TYPE location_status_type AS ENUM ('EMPTY', 'PARTIAL', 'FULL', 'COUNTING_LOCKED', 'MAINTENANCE_LOCKED', 'DAMAGED_HOLD');

-- [MỚI v4.1 - F24, F27] Máy trạng thái chuẩn cho Pallet (hỗ trợ cách ly hàng lệch/hư trước khi D1 duyệt)
CREATE TYPE pallet_status_type AS ENUM (
    'RECEIVING', 'QUARANTINE_HOLD', 'DAMAGED_HOLD',
    'STAGED', 'PUTAWAY_IN_PROGRESS', 'STORED', 'EMPTY'
);

CREATE TYPE picking_rule_type AS ENUM ('FEFO', 'FIFO');
CREATE TYPE pick_mode_type AS ENUM ('SINGLE_ORDER', 'BATCH', 'WAVE');

-- [CẬP NHẬT v4.1 - F02, F07, F19, F35] Phủ kín 10 loại Task cho mọi khâu thực thi
CREATE TYPE task_type AS ENUM (
    'RECEIVING', 'PUTAWAY', 'PICKING', 'PACKING',
    'CYCLE_COUNT', 'RECOUNT', 'RETURN_PICKING',
    'INTERNAL_MOVE', 'RETURN_TO_SHELF', 'SCRAP_EXECUTION'
);

CREATE TYPE task_priority_type AS ENUM ('NORMAL', 'HIGH', 'URGENT');
CREATE TYPE task_status_type AS ENUM ('UNASSIGNED', 'ASSIGNED', 'IN_PROGRESS', 'PAUSED_OFFLINE', 'COMPLETED', 'REJECTED', 'CANCELLED');
CREATE TYPE po_status_type AS ENUM ('PENDING', 'RECEIVING', 'PARTIAL_RECEIVED', 'FULLY_RECEIVED', 'CLOSED', 'CANCELLED');
CREATE TYPE grn_status_type AS ENUM ('DRAFT', 'COUNTING', 'PENDING_D1', 'PENDING_D2', 'PENDING_D3', 'APPROVED', 'REJECTED', 'CLOSED', 'SYNCED_ERP');

-- [CẬP NHẬT v4.1 - F33, F50, F51] Bổ sung WAITING_WAYBILL; WMS kết thúc trách nhiệm kho tại SHIPPED
CREATE TYPE order_status_type AS ENUM (
    'NEW', 'PICKING', 'PICKED', 'PACKING', 'WAITING_WAYBILL', 'READY_TO_SHIP', 'SHIPPED',
    'IN_TRANSIT', 'DELIVERED', 'PARTIAL_DELIVERED', 'DELIVERY_FAILED', 'ON_HOLD', 'CANCELLED'
);

-- [MỚI v4.1 - F39, F40] Phân loại chứng từ xuất kho GI (Đơn bán, Chuyển kho liên chi nhánh, Xuất trả NCC)
CREATE TYPE gi_doc_type AS ENUM ('SO_SHIPMENT', 'INTER_WH_TRANSFER', 'SUPPLIER_RETURN');

CREATE TYPE approval_tier_type AS ENUM ('AUTO_TOLERANCE_Z', 'D1_THUKHO', 'D2_QUANLY', 'D3_BGD');
CREATE TYPE approval_object_type AS ENUM ('GRN_DISCREPANCY', 'CYCLE_COUNT_DIFF', 'STOCK_ADJUSTMENT', 'STOCK_SCRAP', 'OVERTIME_REQUEST');
CREATE TYPE approval_status_type AS ENUM ('PENDING_D1', 'PENDING_D2', 'PENDING_D3', 'NEED_INFO', 'APPROVED', 'REJECTED', 'EXPIRED');

-- [MỚI v4.1 - F07, F42, F47] Tách bạch trạng thái Phê duyệt và trạng thái Thực thi/Đồng bộ ERP hậu phê duyệt
CREATE TYPE post_approval_exec_status AS ENUM (
    'NOT_APPLICABLE', 'WAITING_EXECUTION', 'WAITING_SCRAP_EXECUTION',
    'EXECUTED_INVENTORY', 'SCRAP_EXECUTED', 'SYNCED_ERP', 'FAILED_SYNC'
);

CREATE TYPE sync_error_category AS ENUM ('NONE', 'BUSINESS_ERROR', 'TECHNICAL_ERROR');

-- =============================================================================
-- PHẦN 2: QUẢN TRỊ KHO, DANH MỤC GỐC & THAM SỐ CẤU HÌNH [Q#1..Q#27]
-- =============================================================================

-- 1. Bảng Kho & Chi nhánh (AD-8, ER-1)
CREATE TABLE warehouses (
    warehouse_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    erp_warehouse_code VARCHAR(50) NOT NULL UNIQUE,
    warehouse_name VARCHAR(200) NOT NULL,
    branch_code VARCHAR(50),
    address TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Bảng Cấu hình Quy tắc Nghiệp vụ & Tham số Vận hành theo Kho (AD-5, AD-6, AD-9, [Q#1..Q#27])
-- [CẬP NHẬT v4.1 - F09, F16, F46] Bổ sung tolerance_z_mode, offline_task_reclaim_minutes & gán DEFAULT cho 8 quy tắc Q#
CREATE TABLE warehouse_configs (
    config_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    warehouse_id UUID NOT NULL UNIQUE REFERENCES warehouses(warehouse_id) ON DELETE CASCADE,
    -- Ngưỡng duyệt & dung sai ([Q#6], [Q#15], [Q#10])
    threshold_x_d1_amount NUMERIC(18, 2) NOT NULL DEFAULT 5000000.00,   -- [Q#6] Ngưỡng tối đa Thủ kho duyệt (D1)
    threshold_y_d2_amount NUMERIC(18, 2) NOT NULL DEFAULT 20000000.00,  -- [Q#6] Ngưỡng tối đa Quản lý kho duyệt (D2), vượt Y lên D3
    tolerance_z_mode VARCHAR(20) NOT NULL DEFAULT 'BOTH_AND'            -- [Q-5 / F09] AMOUNT_ONLY, PERCENT_ONLY, BOTH_AND
        CHECK (tolerance_z_mode IN ('AMOUNT_ONLY', 'PERCENT_ONLY', 'BOTH_AND')),
    tolerance_z_amount NUMERIC(18, 2) NOT NULL DEFAULT 500000.00,       -- [Q#15] Dung sai kiểm kê tự ghi nhận theo giá trị
    tolerance_z_percent NUMERIC(5, 2) NOT NULL DEFAULT 1.00,            -- [Q#15] Dung sai kiểm kê theo %
    reauth_min_amount NUMERIC(18, 2) NOT NULL DEFAULT 10000000.00,      -- [Q#10] Giá trị từ mức này phải xác thực sinh trắc học/mật khẩu
    -- Quy tắc kho (AD-5, [Q#8], [Q#19], [Q#26])
    picking_rule picking_rule_type NOT NULL DEFAULT 'FEFO',
    putaway_rule_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    blind_receipt_policy VARCHAR(30) NOT NULL DEFAULT 'WARN_HOLD_D1',   -- [Q#19] REJECT hoặc WARN_HOLD_D1
    missing_cert_policy VARCHAR(30) NOT NULL DEFAULT 'HARD_BLOCK',      -- [Q#8] HARD_BLOCK hoặc SOFT_OVERRIDE
    counting_location_tx_policy VARCHAR(20) NOT NULL DEFAULT 'BLOCK',   -- [Q#26] BLOCK hoặc QUEUE
    -- Tham số SLA & Vận hành (AD-6, [Q#1..Q#5], [Q#7], [Q#11..Q#16])
    task_sla_minutes JSONB NOT NULL DEFAULT '{"RECEIVING": 60, "PUTAWAY": 30, "PICKING": 45, "PACKING": 30, "CYCLE_COUNT": 60, "RECOUNT": 30, "RETURN_PICKING": 45, "INTERNAL_MOVE": 30, "RETURN_TO_SHELF": 30, "SCRAP_EXECUTION": 60}'::jsonb, -- [Q#1]
    dashboard_refresh_seconds INT NOT NULL DEFAULT 30,                  -- [Q#2]
    idle_alert_minutes_n INT DEFAULT 15,                                -- [Q#3] Số phút nhàn rỗi N (NULL = tắt cảnh báo)
    offline_task_reclaim_minutes INT NOT NULL DEFAULT 30,               -- [Q-10 / F16] Số phút mất kết nối tối đa trước khi thu hồi Task
    escalation_minutes_m INT DEFAULT 30,                                -- [Q#4] Số phút M leo thang cảnh báo
    max_open_tasks_per_user INT DEFAULT 3,                              -- [Q#5] Số task mở tối đa mỗi nhân viên
    max_recount_attempts INT DEFAULT 2,                                 -- [Q#7] Số lần đếm lại tối đa trước khi bắt buộc lên cấp trên
    max_overtime_hours_month NUMERIC(5, 2) DEFAULT 40.00,               -- [Q#9] Giới hạn giờ làm thêm
    allow_worker_view_own_kpi BOOLEAN NOT NULL DEFAULT FALSE,           -- [Q#11]
    expiry_reminder_days_n INT DEFAULT 7,                               -- [Q#12] Số ngày nhắc trước hết hạn chứng nhận/thời vụ/ủy quyền
    hr_integration_mode VARCHAR(30) NOT NULL DEFAULT 'HR_MASTER',       -- [Q#13] HR_MASTER: nhận lịch ca từ HR
    approval_sla_hours JSONB NOT NULL DEFAULT '{"D1": 4, "D2": 8, "D3": 24}'::jsonb, -- [Q#14]
    min_headcount_per_stage JSONB NOT NULL DEFAULT '{"NHAN_HANG": 1, "CAT_HANG": 1, "SOAN_HANG": 2, "DONG_GOI_XUAT": 1, "KIEM_KE": 1}'::jsonb, -- [Q#16]
    pre_shift_alert_hours NUMERIC(4, 1) DEFAULT 2.0,                    -- [Q#16]
    allow_same_counter_recount BOOLEAN NOT NULL DEFAULT FALSE,          -- [Q#18] Mặc định bắt buộc đổi người khi đếm lại
    updated_by UUID,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Bảng Khu vực (Zone) và Vị trí / Ô kệ / Cửa nhận (AD-3, TK-5.2, TK-5.6, QL-1.2)
CREATE TABLE zones (
    zone_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    warehouse_id UUID NOT NULL REFERENCES warehouses(warehouse_id) ON DELETE CASCADE,
    zone_code VARCHAR(50) NOT NULL,
    zone_name VARCHAR(150) NOT NULL,
    zone_type VARCHAR(50) NOT NULL, -- STORAGE, RECEIVING_DOCK, PACKING, DAMAGED, QUARANTINE, STAGING, COLD, HAZMAT
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (warehouse_id, zone_code)
);

CREATE TABLE locations (
    location_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    warehouse_id UUID NOT NULL REFERENCES warehouses(warehouse_id) ON DELETE CASCADE,
    zone_id UUID NOT NULL REFERENCES zones(zone_id),
    location_code VARCHAR(100) NOT NULL,
    barcode VARCHAR(100) NOT NULL,
    aisle VARCHAR(20),
    rack VARCHAR(20),
    shelf_level VARCHAR(20),
    bin VARCHAR(20),
    max_weight_kg NUMERIC(12, 2),
    max_volume_m3 NUMERIC(12, 4),
    max_pallets INT,
    current_capacity_pct NUMERIC(5, 2) NOT NULL DEFAULT 0 CHECK (current_capacity_pct >= 0 AND current_capacity_pct <= 100),
    status location_status_type NOT NULL DEFAULT 'EMPTY',
    lock_reason TEXT,
    locked_by UUID,
    locked_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (warehouse_id, location_code)
);

-- 4. Bảng Nhóm hàng, SKU & Quy cách đóng gói (ER-1, AD-5, [Q#19], [Q#21], [Q#27])
CREATE TABLE item_categories (
    category_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category_code VARCHAR(50) NOT NULL UNIQUE,
    category_name VARCHAR(150) NOT NULL,
    min_receiving_shelf_life_days INT DEFAULT 0, -- [CẬP NHẬT v4.1 - F47] Chuẩn hóa snake_case
    shelf_life_violation_action VARCHAR(20) NOT NULL DEFAULT 'WARN' -- WARN hoặc BLOCK
);

CREATE TABLE skus (
    sku_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sku_code VARCHAR(100) NOT NULL UNIQUE,
    sku_name VARCHAR(255) NOT NULL,
    category_id UUID REFERENCES item_categories(category_id),
    base_uom VARCHAR(30) NOT NULL,
    unit_cost NUMERIC(18, 4) NOT NULL DEFAULT 0 CHECK (unit_cost >= 0), -- [Q#27] Giá vốn từ ERP phục vụ tính chênh lệch/hủy hàng
    min_stock_level NUMERIC(18, 3) DEFAULT 0,                           -- QL-6.1 Cảnh báo tồn tối thiểu (SC-2.s2)
    is_lot_tracked BOOLEAN NOT NULL DEFAULT TRUE,                       -- [F28] Cờ cấu hình bắt buộc nhập Lô
    is_expiry_tracked BOOLEAN NOT NULL DEFAULT TRUE,                    -- [F28] Cờ cấu hình bắt buộc nhập Hạn dùng
    is_serial_tracked BOOLEAN NOT NULL DEFAULT FALSE,                   -- [F28] Cờ cấu hình bắt buộc quét Serial
    storage_requirement VARCHAR(50) DEFAULT 'NORMAL',                   -- NORMAL, COLD, HAZMAT
    erp_last_synced_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE sku_barcodes (
    barcode_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sku_id UUID NOT NULL REFERENCES skus(sku_id) ON DELETE CASCADE,
    barcode VARCHAR(150) NOT NULL UNIQUE,
    uom_code VARCHAR(30) NOT NULL,
    conversion_factor NUMERIC(12, 4) NOT NULL DEFAULT 1 CHECK (conversion_factor > 0)
);

-- 5. Bảng Đối tác: Nhà cung cấp & Khách hàng (Đồng bộ từ ERP - ER-1, [Q#20])
CREATE TABLE suppliers (
    supplier_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    erp_supplier_code VARCHAR(50) NOT NULL UNIQUE,
    supplier_name VARCHAR(255) NOT NULL,
    contact_person VARCHAR(150),
    phone VARCHAR(50),
    email VARCHAR(150),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE customers (
    customer_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    erp_customer_code VARCHAR(50) NOT NULL UNIQUE,
    customer_name VARCHAR(255) NOT NULL,
    shipping_address TEXT,
    phone VARCHAR(50),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

-- 6. Bảng Danh mục phụ trợ do WMS quản lý (AD-3)
CREATE TABLE reason_codes (
    reason_code VARCHAR(50) PRIMARY KEY,
    reason_category VARCHAR(50) NOT NULL, -- DAMAGED, DISCREPANCY, TASK_REJECT, ORDER_CANCEL, SCRAP, OVERRIDE, PACKING_EXCEPTION
    description VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE box_types (
    box_type_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    box_code VARCHAR(50) NOT NULL UNIQUE,
    box_name VARCHAR(100) NOT NULL,
    length_cm NUMERIC(8, 2) NOT NULL,
    width_cm NUMERIC(8, 2) NOT NULL,
    height_cm NUMERIC(8, 2) NOT NULL,
    tare_weight_kg NUMERIC(8, 3) NOT NULL DEFAULT 0,
    max_weight_kg NUMERIC(8, 2)
);

CREATE TABLE vehicles_drivers (
    vehicle_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    license_plate VARCHAR(30) NOT NULL UNIQUE,
    vehicle_type VARCHAR(50),
    driver_name VARCHAR(150) NOT NULL,
    driver_phone VARCHAR(30),
    carrier_name VARCHAR(150),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE label_templates (
    template_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_code VARCHAR(50) NOT NULL UNIQUE,
    template_name VARCHAR(150) NOT NULL,
    label_type VARCHAR(50) NOT NULL, -- PALLET, PACKAGE, WAYBILL, LOCATION, SKU
    zpl_content TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

-- =============================================================================
-- PHẦN 3: NGƯỜI DÙNG, PHÂN QUYỀN (RBAC), ỦY QUYỀN & THIẾT BỊ
-- =============================================================================

CREATE TABLE roles (
    role_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    role_code VARCHAR(50) NOT NULL UNIQUE, -- nv-nhan, nv-cat, nv-soan, nv-dongoi, nv-kiemke, thukho, quanly, bgd, admin
    role_name VARCHAR(150) NOT NULL,
    actor_group actor_group_type NOT NULL,
    default_channel VARCHAR(20) NOT NULL DEFAULT 'MOBILE' -- MOBILE, WEB, MOBILE_WEB
);

CREATE TABLE permissions (
    permission_code VARCHAR(50) PRIMARY KEY, -- Mã chức năng: NH-1..AD-12 (bao gồm NH-5, DG-6, TK-5.10)
    feature_name VARCHAR(200) NOT NULL,
    module_tab VARCHAR(50) NOT NULL,         -- VAN_HANH, GIAM_SAT_NHAN_LUC, NGOAI_LE_CAU_HINH
    channel VARCHAR(20) NOT NULL
);

CREATE TABLE role_permissions (
    role_id UUID NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
    permission_code VARCHAR(50) NOT NULL REFERENCES permissions(permission_code) ON DELETE CASCADE,
    access_type VARCHAR(20) NOT NULL, -- X, X_OWN, V, V_OWN, G, E, D1, D2, D3
    PRIMARY KEY (role_id, permission_code)
);

CREATE TABLE sso_group_mappings (
    mapping_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sso_group_name VARCHAR(150) NOT NULL UNIQUE,
    role_id UUID NOT NULL REFERENCES roles(role_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(100) NOT NULL UNIQUE,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(150) UNIQUE,
    phone VARCHAR(30),
    auth_provider auth_provider_type NOT NULL DEFAULT 'SSO_LDAP', -- [Q#24 / F21] Phân biệt SSO_LDAP vs LOCAL_SEASONAL
    password_hash TEXT,                                          -- Bắt buộc khi auth_provider = LOCAL_SEASONAL
    must_change_password BOOLEAN NOT NULL DEFAULT FALSE,         -- [F21] Bắt buộc đổi mật khẩu lần đầu cho tài khoản cục bộ
    failed_login_attempts INT NOT NULL DEFAULT 0,
    primary_warehouse_id UUID REFERENCES warehouses(warehouse_id),
    primary_role_id UUID NOT NULL REFERENCES roles(role_id),
    is_role_manual_override BOOLEAN NOT NULL DEFAULT FALSE,      -- AD-2 Ghi đè ánh xạ SSO
    primary_stage work_stage_type,
    status user_status_type NOT NULL DEFAULT 'ACTIVE',
    -- Quản lý thời vụ (QL-9.5a, QL-9.5b, SC-4)
    is_seasonal BOOLEAN NOT NULL DEFAULT FALSE,
    valid_from TIMESTAMPTZ,
    valid_until TIMESTAMPTZ,
    is_safety_checked BOOLEAN NOT NULL DEFAULT TRUE,             -- Thời vụ bắt buộc TRUE mới nhận được task (NV-DC-1, QL-9.5a)
    biometric_enabled BOOLEAN NOT NULL DEFAULT FALSE,            -- AD-9, [Q#10]
    dnd_start_time TIME,                                         -- QL-6.5 Giờ không làm phiền
    dnd_end_time TIME,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_seasonal_expiry CHECK (NOT is_seasonal OR valid_until IS NOT NULL),
    CONSTRAINT chk_local_auth_password CHECK (auth_provider <> 'LOCAL_SEASONAL' OR password_hash IS NOT NULL)
);

-- Bảng Ủy quyền duyệt khi vắng mặt dùng chung cho D1, D2, D3 (TK-4.4, QL-9.8, BG-6, SC-5)
CREATE TABLE approval_delegations (
    delegation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    warehouse_id UUID REFERENCES warehouses(warehouse_id),
    grantor_user_id UUID NOT NULL REFERENCES users(user_id),
    grantee_user_id UUID NOT NULL REFERENCES users(user_id),
    approval_tier approval_tier_type NOT NULL,
    allowed_object_types approval_object_type[] NOT NULL,
    max_limit_amount NUMERIC(18, 2),                             -- [CẬP NHẬT v4.1 - F47] Chuẩn hóa snake_case
    valid_from TIMESTAMPTZ NOT NULL,
    valid_until TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',                -- ACTIVE, REVOKED_EARLY, EXPIRED_AUTO
    revoked_at TIMESTAMPTZ,
    revoked_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_no_self_delegation CHECK (grantor_user_id <> grantee_user_id),
    CONSTRAINT chk_delegation_dates CHECK (valid_until > valid_from)
);

-- Bảng Thiết bị Mobile, Máy quét, Máy in & Token Push (AD-4, TB-1..5, TP-1..2)
CREATE TABLE devices (
    device_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    warehouse_id UUID NOT NULL REFERENCES warehouses(warehouse_id),
    device_serial VARCHAR(100) NOT NULL UNIQUE,
    device_type VARCHAR(30) NOT NULL, -- MOBILE_PDA, SCANNER_BT, RFID_READER, PRINTER
    device_name VARCHAR(150) NOT NULL,
    app_version VARCHAR(30),
    force_update_required BOOLEAN NOT NULL DEFAULT FALSE,
    remote_wipe_requested BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(30) NOT NULL DEFAULT 'ONLINE', -- ONLINE, OFFLINE, PAPER_OUT, ERROR, LOCKED
    fcm_apns_token TEXT,
    current_user_id UUID REFERENCES users(user_id),
    last_heartbeat_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- PHẦN 4: TỒN KHO, LÔ (LOT), PALLET & SỔ CÁI GIAO DỊCH (F01, F24, F27, F28, F35, F53)
-- =============================================================================

CREATE TABLE lots (
    lot_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sku_id UUID NOT NULL REFERENCES skus(sku_id),
    lot_number VARCHAR(100) NOT NULL,
    manufacture_date DATE,
    expiry_date DATE,
    supplier_id UUID REFERENCES suppliers(supplier_id),
    is_priority_dispatch BOOLEAN NOT NULL DEFAULT FALSE, -- [MỚI v4.1 - F35] Cờ ưu tiên xuất trước cho lô hàng cận date (QL-6.2.s4)
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (sku_id, lot_number)
);

-- [CẬP NHẬT v4.1 - F24, F27, F49, F53] Bổ sung parent_pallet_id (tách pallet hàng hư/cất lẻ), pallet_status_type và version_no
CREATE TABLE pallets (
    pallet_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pallet_code VARCHAR(100) NOT NULL UNIQUE,
    parent_pallet_id UUID REFERENCES pallets(pallet_id),
    warehouse_id UUID NOT NULL REFERENCES warehouses(warehouse_id),
    current_location_id UUID REFERENCES locations(location_id),
    source_grn_id UUID,
    status pallet_status_type NOT NULL DEFAULT 'RECEIVING',
    version_no INT NOT NULL DEFAULT 1,
    created_by UUID REFERENCES users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Bảng Tồn kho chi tiết 5 trạng thái (Thực thể Tồn_kho cốt lõi - F01, TK-5.8, QL-1.1..1.3, BG-1)
CREATE TABLE inventory_balances (
    balance_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    warehouse_id UUID NOT NULL REFERENCES warehouses(warehouse_id),
    location_id UUID NOT NULL REFERENCES locations(location_id),
    sku_id UUID NOT NULL REFERENCES skus(sku_id),
    lot_id UUID REFERENCES lots(lot_id),
    pallet_id UUID REFERENCES pallets(pallet_id),
    serial_number VARCHAR(100),
    qty_available NUMERIC(18, 3) NOT NULL DEFAULT 0 CHECK (qty_available >= 0),
    qty_allocated NUMERIC(18, 3) NOT NULL DEFAULT 0 CHECK (qty_allocated >= 0),
    qty_counting NUMERIC(18, 3) NOT NULL DEFAULT 0 CHECK (qty_counting >= 0),
    qty_locked NUMERIC(18, 3) NOT NULL DEFAULT 0 CHECK (qty_locked >= 0),
    qty_damaged NUMERIC(18, 3) NOT NULL DEFAULT 0 CHECK (qty_damaged >= 0),
    version_no INT NOT NULL DEFAULT 1, -- [MỚI v4.1 - F49] Khóa đồng thời Optimistic Locking
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE NULLS NOT DISTINCT (warehouse_id, location_id, sku_id, lot_id, pallet_id, serial_number)
);

-- Sổ cái Giao dịch Tồn kho bất biến (QL-1.4, F01, F28)
CREATE TABLE inventory_transactions (
    tx_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    warehouse_id UUID NOT NULL REFERENCES warehouses(warehouse_id),
    tx_type VARCHAR(40) NOT NULL, -- RECEIVE, PUTAWAY, ALLOCATE, PICK, RETURN_TO_SHELF, SHIP_GI, INTERNAL_MOVE, LOCK_COUNT, CYCLE_COUNT, ADJUSTMENT, SCRAP, RETURN_IN
    sku_id UUID NOT NULL REFERENCES skus(sku_id),
    lot_id UUID REFERENCES lots(lot_id),
    pallet_id UUID REFERENCES pallets(pallet_id),
    serial_number VARCHAR(100),   -- [MỚI v4.1 - F28] Truy vết Serial trên sổ cái
    from_location_id UUID REFERENCES locations(location_id),
    to_location_id UUID REFERENCES locations(location_id),
    qty_change NUMERIC(18, 3) NOT NULL,
    unit_cost_snapshot NUMERIC(18, 4) NOT NULL,
    ref_doc_type VARCHAR(40) NOT NULL, -- GRN, TASK, PICK_SESSION, SO, GI, CYCLE_COUNT, STOCK_ADJ, RMA
    ref_doc_id UUID NOT NULL,
    performed_by UUID NOT NULL REFERENCES users(user_id),
    performed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- PHẦN 5: NHẬP KHO (PO, ASN, GRN) & CẤT HÀNG (PUTAWAY) (F02, F03, F14, F23..F30)
-- =============================================================================

CREATE TABLE purchase_orders (
    po_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    erp_po_number VARCHAR(100) NOT NULL UNIQUE,
    warehouse_id UUID NOT NULL REFERENCES warehouses(warehouse_id),
    supplier_id UUID NOT NULL REFERENCES suppliers(supplier_id),
    status po_status_type NOT NULL DEFAULT 'PENDING',
    expected_date DATE,
    version_no INT NOT NULL DEFAULT 1, -- [MỚI v4.1 - F49]
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE po_lines (
    po_line_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    po_id UUID NOT NULL REFERENCES purchase_orders(po_id) ON DELETE CASCADE,
    line_number INT NOT NULL,
    sku_id UUID NOT NULL REFERENCES skus(sku_id),
    uom_code VARCHAR(30) NOT NULL,
    qty_ordered NUMERIC(18, 3) NOT NULL CHECK (qty_ordered > 0),
    qty_received NUMERIC(18, 3) NOT NULL DEFAULT 0 CHECK (qty_received >= 0),
    version_no INT NOT NULL DEFAULT 1, -- [MỚI v4.1 - F25, F49]
    UNIQUE (po_id, line_number)
);

CREATE TABLE asns (
    asn_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    erp_asn_number VARCHAR(100) NOT NULL UNIQUE,
    warehouse_id UUID NOT NULL REFERENCES warehouses(warehouse_id),
    po_id UUID REFERENCES purchase_orders(po_id),
    supplier_id UUID REFERENCES suppliers(supplier_id),
    assigned_dock_location_id UUID REFERENCES locations(location_id), -- TK-5.6 Gán cửa/khu nhận
    assigned_zone_id UUID REFERENCES zones(zone_id),
    expected_arrival_at TIMESTAMPTZ NOT NULL,
    actual_arrival_at TIMESTAMPTZ,
    expected_pallets INT,
    status VARCHAR(30) NOT NULL DEFAULT 'SCHEDULED', -- SCHEDULED, ARRIVED, RECEIVING, COMPLETED, CANCELLED
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- [CẬP NHẬT v4.1 - F14, F29, F30, F49] Tạo GRN ở đầu NH-1, mặc định đếm mù (is_blind_receipt = TRUE), lưu shift_id & started_at
CREATE TABLE grns (
    grn_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    grn_number VARCHAR(100) NOT NULL UNIQUE,
    warehouse_id UUID NOT NULL REFERENCES warehouses(warehouse_id),
    po_id UUID REFERENCES purchase_orders(po_id),
    asn_id UUID REFERENCES asns(asn_id),
    shift_id UUID,                                      -- [MỚI v4.1 - F30] Ca nhận hàng
    is_blind_receipt BOOLEAN NOT NULL DEFAULT TRUE,     -- [CẬP NHẬT v4.1 - Q-9 / F29] Mặc định nhận đếm mù
    received_by UUID NOT NULL REFERENCES users(user_id),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),      -- [MỚI v4.1 - F30] Thời điểm bắt đầu nhận
    status grn_status_type NOT NULL DEFAULT 'DRAFT',
    has_discrepancy BOOLEAN NOT NULL DEFAULT FALSE,
    total_discrepancy_amount NUMERIC(18, 2) NOT NULL DEFAULT 0, -- Tính theo unit_cost ERP (TK-3.2)
    recount_count INT NOT NULL DEFAULT 0,               -- [MỚI v4.1 - F23] Số lần đếm lại GRN (NH-5)
    version_no INT NOT NULL DEFAULT 1,                  -- [MỚI v4.1 - F49]
    closed_at TIMESTAMPTZ,
    erp_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE grn_lines (
    grn_line_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    grn_id UUID NOT NULL REFERENCES grns(grn_id) ON DELETE CASCADE,
    po_line_id UUID REFERENCES po_lines(po_line_id),
    sku_id UUID NOT NULL REFERENCES skus(sku_id),
    lot_id UUID REFERENCES lots(lot_id),
    pallet_id UUID REFERENCES pallets(pallet_id),
    damaged_pallet_id UUID REFERENCES pallets(pallet_id), -- [MỚI v4.1 - F24] Pallet tách riêng cho phần hàng hư
    uom_code VARCHAR(30) NOT NULL,
    qty_expected NUMERIC(18, 3) NOT NULL DEFAULT 0,       -- Ẩn trên UI khi grns.is_blind_receipt = TRUE
    qty_actual NUMERIC(18, 3) NOT NULL DEFAULT 0,
    qty_damaged NUMERIC(18, 3) NOT NULL DEFAULT 0,
    qty_variance NUMERIC(18, 3) GENERATED ALWAYS AS (qty_actual - qty_expected) STORED,
    variance_amount NUMERIC(18, 2) NOT NULL DEFAULT 0,
    serial_numbers TEXT[],                                -- [MỚI v4.1 - F28] Danh sách serial quét lúc nhận
    is_quarantined BOOLEAN NOT NULL DEFAULT FALSE,        -- [MỚI v4.1 - F24] Chặn sinh Task PUTAWAY khi đang chờ D1 duyệt lệch
    reason_code VARCHAR(50) REFERENCES reason_codes(reason_code),
    damage_photo_urls TEXT[],
    notes TEXT
);

-- =============================================================================
-- PHẦN 6: XUẤT KHO (SO, PICKING, PACKING, GI, VẬN ĐƠN TMS & HÀNG TRẢ RMA)
-- =============================================================================

CREATE TABLE outbound_orders (
    order_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    erp_order_number VARCHAR(100) NOT NULL UNIQUE,
    order_type VARCHAR(30) NOT NULL DEFAULT 'SO'
        CHECK (order_type IN ('SO', 'INTER_WH_TRANSFER', 'SUPPLIER_RETURN')), -- [Q-12 / F39, F40]
    warehouse_id UUID NOT NULL REFERENCES warehouses(warehouse_id),
    customer_id UUID REFERENCES customers(customer_id),
    supplier_id UUID REFERENCES suppliers(supplier_id),
    dest_warehouse_id UUID REFERENCES warehouses(warehouse_id),
    status order_status_type NOT NULL DEFAULT 'NEW', -- QL-3.1
    is_urgent BOOLEAN NOT NULL DEFAULT FALSE,        -- TK-5.4, QL-3.3 Đơn khẩn
    urgent_reason TEXT,
    cutoff_time TIMESTAMPTZ NOT NULL,                -- QL-3.2, QL-4.2 Giờ cắt xe
    route_code VARCHAR(50),
    delay_reason VARCHAR(50),                        -- SHORTAGE, NO_STAFF, NO_VEHICLE, PENDING_APPROVAL
    erp_change_pending BOOLEAN NOT NULL DEFAULT FALSE, -- [F17] ER-2.s2 chỉ bật cờ này; QL-5.1.s8 là nơi duy nhất chốt CANCELLED
    erp_change_payload JSONB,
    version_no INT NOT NULL DEFAULT 1,               -- [MỚI v4.1 - F49] Chống chọn trùng SO vào 2 phiên pick
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE outbound_order_lines (
    order_line_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID NOT NULL REFERENCES outbound_orders(order_id) ON DELETE CASCADE,
    sku_id UUID NOT NULL REFERENCES skus(sku_id),
    qty_ordered NUMERIC(18, 3) NOT NULL CHECK (qty_ordered > 0),
    qty_allocated NUMERIC(18, 3) NOT NULL DEFAULT 0,
    qty_picked NUMERIC(18, 3) NOT NULL DEFAULT 0,
    qty_packed NUMERIC(18, 3) NOT NULL DEFAULT 0,
    qty_shipped NUMERIC(18, 3) NOT NULL DEFAULT 0,
    shortage_resolution VARCHAR(30) -- WAIT_STOCK, PARTIAL_SHIP, REQUEST_ERP_CANCEL (QL-3.4 - F33)
);

-- Phiên Pick hàng (SH-1..SH-5 - F30, F31, F49)
CREATE TABLE pick_sessions (
    pick_session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    warehouse_id UUID NOT NULL REFERENCES warehouses(warehouse_id),
    shift_id UUID,                                              -- [MỚI v4.1 - F30]
    pick_mode pick_mode_type NOT NULL DEFAULT 'SINGLE_ORDER',   -- [Q#23]
    picker_user_id UUID NOT NULL REFERENCES users(user_id),     -- [CẬP NHẬT v4.1 - F30] Bắt buộc ghi nhận người soạn ngay khi mở phiên
    status VARCHAR(30) NOT NULL DEFAULT 'OPEN',                 -- OPEN, IN_PROGRESS, COMPLETED, ON_HOLD_SHORTAGE, CANCELLED
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),              -- [CẬP NHẬT v4.1 - F30]
    completed_at TIMESTAMPTZ,
    version_no INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE pick_lines (
    pick_line_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pick_session_id UUID NOT NULL REFERENCES pick_sessions(pick_session_id) ON DELETE CASCADE,
    order_line_id UUID NOT NULL REFERENCES outbound_order_lines(order_line_id),
    source_location_id UUID NOT NULL REFERENCES locations(location_id),
    suggested_lot_id UUID REFERENCES lots(lot_id),              -- Gợi ý theo is_priority_dispatch + FEFO/FIFO (SH-2, F35)
    actual_lot_id UUID REFERENCES lots(lot_id),
    serial_numbers TEXT[],                                      -- [MỚI v4.1 - F28]
    target_tote_barcode VARCHAR(100),
    qty_to_pick NUMERIC(18, 3) NOT NULL,
    qty_picked NUMERIC(18, 3) NOT NULL DEFAULT 0,
    status VARCHAR(30) NOT NULL DEFAULT 'PENDING',              -- PENDING, SKIPPED (SH-3), PICKED, EXCEPTION_SHORT, EXCEPTION_DAMAGED, EXCEPTION_WRONG_LOT (SH-4 - F31)
    exception_reason VARCHAR(50) REFERENCES reason_codes(reason_code)
);

-- Đóng gói, Vận đơn TMS & Phiếu xuất kho GI (DG-1..6, TM-1..5)
-- [CẬP NHẬT v4.1 - F13, F39, F40, F49, F51] Cắt bỏ hóa đơn bán hàng ERP & ePOD khách hàng; hỗ trợ xuất trả NCC & chuyển kho
CREATE TABLE goods_issues (
    gi_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    gi_number VARCHAR(100) NOT NULL UNIQUE,
    gi_type gi_doc_type NOT NULL DEFAULT 'SO_SHIPMENT',         -- [MỚI v4.1 - F39, F40]
    warehouse_id UUID NOT NULL REFERENCES warehouses(warehouse_id),
    order_id UUID NOT NULL REFERENCES outbound_orders(order_id),
    vehicle_id UUID REFERENCES vehicles_drivers(vehicle_id),
    tms_waybill_code VARCHAR(100),
    tms_waybill_status VARCHAR(30) DEFAULT 'PENDING',           -- PENDING, CREATED, CANCELLED (TM-5)
    total_packages INT NOT NULL DEFAULT 0,                      -- [MỚI v4.1 - F13] Hệ thống tự động đếm từ bảng packages
    handover_photo_urls TEXT[],
    driver_signature_data TEXT,                                 -- DG-4 Bắt buộc có chữ ký tài xế TRƯỚC khi xác nhận GI (với đơn qua TMS/Xe tải)
    driver_signed_at TIMESTAMPTZ,
    confirmed_by UUID REFERENCES users(user_id),
    confirmed_at TIMESTAMPTZ,
    status VARCHAR(30) NOT NULL DEFAULT 'PACKING',              -- PACKING, WAITING_WAYBILL, LOADED, GI_CONFIRMED, CANCELLED
    version_no INT NOT NULL DEFAULT 1,                          -- [MỚI v4.1 - F49] Chống bấm phát hành GI 2 lần
    CONSTRAINT chk_driver_sig_before_gi CHECK (
        status <> 'GI_CONFIRMED'
        OR gi_type = 'SUPPLIER_RETURN'
        OR (driver_signature_data IS NOT NULL AND driver_signed_at <= confirmed_at)
    )
);

-- [CẬP NHẬT v4.1 - F13] Cho phép gi_id NULL lúc đóng thùng tại DG-2, gán gi_id khi phát hành GI tại DG-5
CREATE TABLE packages (
    package_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    package_barcode VARCHAR(100) NOT NULL UNIQUE,
    order_id UUID NOT NULL REFERENCES outbound_orders(order_id) ON DELETE CASCADE,
    pick_session_id UUID REFERENCES pick_sessions(pick_session_id),
    gi_id UUID REFERENCES goods_issues(gi_id) ON DELETE SET NULL,
    box_type_id UUID REFERENCES box_types(box_type_id),
    weight_kg NUMERIC(10, 3) NOT NULL,
    length_cm NUMERIC(8, 2),
    width_cm NUMERIC(8, 2),
    height_cm NUMERIC(8, 2),
    packed_by UUID REFERENCES users(user_id),
    packed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_loaded_on_truck BOOLEAN NOT NULL DEFAULT FALSE,          -- DG-4 Quét kiện lên xe
    loaded_at TIMESTAMPTZ
);

-- Nhận Hàng trả (RMA) từ ERP/TMS (TK-5.5, QL-5.2, QL-5.4, ER-2.s3)
-- [CẬP NHẬT v4.1 - Q-8 / F38, F52] Bỏ xử lý khiếu nại thương mại (CUSTOMER_COMPLAINT, RESHIP, REDELIVER); chỉ nhận RMA từ ERP/TMS
CREATE TABLE return_orders_complaints (
    return_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    erp_rma_number VARCHAR(100) NOT NULL UNIQUE,
    warehouse_id UUID NOT NULL REFERENCES warehouses(warehouse_id),
    record_type VARCHAR(30) NOT NULL DEFAULT 'RMA_RETURN'
        CHECK (record_type IN ('RMA_RETURN', 'FAILED_DELIVERY')),
    related_order_id UUID REFERENCES outbound_orders(order_id),
    customer_id UUID REFERENCES customers(customer_id),
    issue_type VARCHAR(30) NOT NULL,                            -- SHORTAGE, DAMAGED, WRONG_ITEM, DELIVERY_FAILED
    inspection_photo_urls TEXT[],
    manager_decision VARCHAR(40)
        CHECK (manager_decision IS NULL OR manager_decision IN ('ACCEPT_RETURN', 'REJECT')),
    decision_reason TEXT,
    physical_disposition VARCHAR(30)
        CHECK (physical_disposition IS NULL OR physical_disposition IN ('RESTOCK', 'DAMAGED_ZONE')), -- TK-5.5
    return_pallet_id UUID REFERENCES pallets(pallet_id),        -- [MỚI v4.1 - F52] Pallet hàng trả để sinh Task PUTAWAY
    received_by UUID REFERENCES users(user_id),
    status VARCHAR(30) NOT NULL DEFAULT 'PENDING_RECEIPT',      -- PENDING_RECEIPT, INSPECTED, PUTAWAY_PENDING, CLOSED
    closed_at TIMESTAMPTZ,                                      -- [MỚI v4.1 - F52]
    version_no INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- PHẦN 7: KIỂM KÊ (CYCLE COUNT), ĐIỀU CHỈNH TỒN & LUỒNG DUYỆT D1 -> D2 -> D3
-- =============================================================================

CREATE TABLE cycle_count_sheets (
    count_sheet_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sheet_number VARCHAR(100) NOT NULL UNIQUE,
    warehouse_id UUID NOT NULL REFERENCES warehouses(warehouse_id),
    count_type VARCHAR(30) NOT NULL, -- PERIODIC, RANDOM, FULL, SHORTAGE_TRIGGERED (TK-3.6, SH-4.s2 - F32)
    created_by UUID NOT NULL REFERENCES users(user_id),
    due_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'OPEN', -- OPEN, COUNTING, PENDING_APPROVAL, COMPLETED, CLOSED (F43)
    closed_at TIMESTAMPTZ,
    version_no INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- [CẬP NHẬT v4.1 - F09, F10, F11, F12] Tự động chụp system_qty_snapshot khi khóa vị trí; tính cả variance_pct
CREATE TABLE cycle_count_lines (
    count_line_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    count_sheet_id UUID NOT NULL REFERENCES cycle_count_sheets(count_sheet_id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES locations(location_id),
    sku_id UUID REFERENCES skus(sku_id),
    lot_id UUID REFERENCES lots(lot_id),
    system_qty_snapshot NUMERIC(18, 3) NOT NULL DEFAULT 0, -- Chụp tại thời điểm tạo phiếu & khóa vị trí (F12); ẩn khi đếm mù (KK-2)
    final_counted_qty NUMERIC(18, 3),                      -- Luôn cập nhật từ lần đếm mới nhất (KK-2 hoặc KK-4 - F11)
    variance_qty NUMERIC(18, 3),
    variance_pct NUMERIC(8, 2),                            -- [MỚI v4.1 - F09] Tỷ lệ % lệch phục vụ so sánh ngưỡng kép Z
    variance_amount NUMERIC(18, 2),
    recount_count INT NOT NULL DEFAULT 0,
    anomaly_type VARCHAR(30) DEFAULT 'NONE',               -- NONE, EMPTY_LOCATION, UNKNOWN_ITEM (KK-3)
    status VARCHAR(30) NOT NULL DEFAULT 'PENDING'          -- PENDING, COUNTED, RECOUNTING, AUTO_APPROVED_Z, PENDING_D1, PENDING_D2, PENDING_D3, APPROVED
);

CREATE TABLE cycle_count_attempts (
    attempt_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    count_line_id UUID NOT NULL REFERENCES cycle_count_lines(count_line_id) ON DELETE CASCADE,
    attempt_no INT NOT NULL, -- 1 = Đếm lần đầu (KK-2), >=2 = Đếm lại mù (KK-4)
    counter_user_id UUID NOT NULL REFERENCES users(user_id),
    blind_counted_qty NUMERIC(18, 3) NOT NULL,
    same_counter_override_reason TEXT, -- [Q#18] Lý do nếu bắt buộc chọn lại người đếm cũ
    counted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (count_line_id, attempt_no)
);

-- Đề xuất Điều chỉnh tồn & Hủy hàng (TK-4.3, TK-5.3, TK-5.10, QL-6.2, QL-7.3, QL-7.4)
-- [CẬP NHẬT v4.1 - F07, F08, F47, F53] Bổ sung trạng thái chờ D2, tách pallet hàng hư và bước thực thi tiêu hủy TK-5.10
CREATE TABLE stock_adjustments (
    adjustment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    warehouse_id UUID NOT NULL REFERENCES warehouses(warehouse_id),
    adjustment_type VARCHAR(30) NOT NULL CHECK (adjustment_type IN ('ADJUSTMENT', 'SCRAP')),
    location_id UUID NOT NULL REFERENCES locations(location_id),
    sku_id UUID NOT NULL REFERENCES skus(sku_id),
    lot_id UUID REFERENCES lots(lot_id),
    source_pallet_id UUID REFERENCES pallets(pallet_id),
    damaged_pallet_id UUID REFERENCES pallets(pallet_id),       -- [MỚI v4.1 - F53] Pallet tách riêng chứa phần hàng hư
    qty_adjustment NUMERIC(18, 3) NOT NULL,
    total_value_amount NUMERIC(18, 2) NOT NULL,                 -- Tính theo unit_cost ERP
    reason_code VARCHAR(50) NOT NULL REFERENCES reason_codes(reason_code),
    proposal_photo_urls TEXT[],
    proposed_by UUID NOT NULL REFERENCES users(user_id),
    proposed_by_role VARCHAR(30) NOT NULL,                      -- THUKHO lập -> PENDING_D2; QUANLY lập hoặc > Y -> PENDING_D3 (F08)
    status approval_status_type NOT NULL DEFAULT 'PENDING_D2',
    execution_status post_approval_exec_status NOT NULL DEFAULT 'WAITING_EXECUTION', -- [MỚI v4.1 - F07, F47]
    -- Xác nhận tiêu hủy thực tế của Thủ kho tại chức năng TK-5.10 sau khi được duyệt (F07, QL-7.4)
    scrap_executed_by UUID REFERENCES users(user_id),
    scrap_execution_photos TEXT[],
    scrap_report_doc_url TEXT,
    scrap_executed_at TIMESTAMPTZ,
    version_no INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Chặn trùng đề xuất đang chờ cho cùng SKU và Vị trí (TK-4.3)
CREATE UNIQUE INDEX idx_unique_pending_adjustment
ON stock_adjustments (warehouse_id, location_id, sku_id, COALESCE(lot_id, '00000000-0000-0000-0000-000000000000'::uuid))
WHERE status IN ('PENDING_D1', 'PENDING_D2', 'PENDING_D3', 'NEED_INFO');

-- Bảng Trung tâm Phê duyệt Đa cấp D1 -> D2 -> D3 (TK-3.1..3.3, TK-4.1, QL-7.1..7.6, BG-3)
-- [CẬP NHẬT v4.1 - F03, F04, F05, F06, F22, F42, F47] Hợp nhất cả 4 loại hồ sơ kho & hỗ trợ leo thang D1 -> D2 -> D3 đầy đủ
CREATE TABLE approval_requests (
    approval_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    warehouse_id UUID NOT NULL REFERENCES warehouses(warehouse_id),
    object_type approval_object_type NOT NULL,
    object_id UUID NOT NULL,
    proposer_user_id UUID NOT NULL REFERENCES users(user_id),
    current_tier approval_tier_type NOT NULL,
    status approval_status_type NOT NULL,
    execution_status post_approval_exec_status NOT NULL DEFAULT 'WAITING_EXECUTION',
    discrepancy_value_amount NUMERIC(18, 2) NOT NULL DEFAULT 0,
    locked_by_viewer_id UUID REFERENCES users(user_id),         -- TK-3.1, QL-7.1, QL-7.6 Chặn mở trùng phiếu (F49)
    locked_at TIMESTAMPTZ,
    sla_due_at TIMESTAMPTZ,                                     -- [Q#14]
    final_decided_by UUID REFERENCES users(user_id),
    final_decided_at TIMESTAMPTZ,
    version_no INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- QUY TẮC BẤT BIẾN: Người đề xuất không bao giờ được tự duyệt đề xuất của chính mình
    CONSTRAINT chk_sod_no_self_approval CHECK (final_decided_by IS NULL OR final_decided_by <> proposer_user_id)
);

CREATE TABLE approval_histories (
    history_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    approval_id UUID NOT NULL REFERENCES approval_requests(approval_id) ON DELETE CASCADE,
    tier approval_tier_type NOT NULL,
    actor_user_id UUID NOT NULL REFERENCES users(user_id),
    delegated_from_user_id UUID REFERENCES users(user_id),      -- QL-7.6, QL-9.8 Ghi rõ duyệt thay cho ai
    action VARCHAR(30) NOT NULL
        CHECK (action IN ('APPROVE', 'REJECT', 'REQUEST_RECOUNT', 'ESCALATE_NEXT_TIER', 'RETURN_FOR_INFO', 'RESUBMIT_INFO')),
    recommendation_or_reason TEXT,
    reauth_method VARCHAR(30),                                  -- BIOMETRIC, PASSWORD ([Q#10] - F22)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- PHẦN 8: ĐIỀU PHỐI TASK, OFFLINE SYNC, NHÂN LỰC, CA LÀM VIỆC & AN TOÀN
-- =============================================================================

CREATE TABLE tasks (
    task_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    warehouse_id UUID NOT NULL REFERENCES warehouses(warehouse_id),
    task_type task_type NOT NULL,
    stage work_stage_type NOT NULL,
    zone_id UUID REFERENCES zones(zone_id),
    ref_doc_type VARCHAR(40) NOT NULL, -- GRN, PALLET, PICK_SESSION, SO, GI, CYCLE_COUNT, STOCK_ADJ, RMA
    ref_doc_id UUID NOT NULL,
    priority task_priority_type NOT NULL DEFAULT 'NORMAL',
    status task_status_type NOT NULL DEFAULT 'UNASSIGNED',
    assigned_to UUID REFERENCES users(user_id),
    assigned_by UUID REFERENCES users(user_id),
    sla_due_at TIMESTAMPTZ,
    progress_pct NUMERIC(5, 2) NOT NULL DEFAULT 0,
    completed_qty NUMERIC(18, 3) NOT NULL DEFAULT 0,
    rejection_reason TEXT,
    version_no INT NOT NULL DEFAULT 1, -- Chống xung đột giao task trùng (TK-1.1) & Offline sync (NV-DC-2 - F48, F49)
    started_at TIMESTAMPTZ,            -- [F15, F30] Ghi nhận ngay khi nhân viên bấm bắt đầu làm Task
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Hàng đợi đồng bộ Offline từ Mobile (NV-DC-2, [Q#25] - F16, F48)
CREATE TABLE offline_sync_batches (
    batch_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id),
    device_id UUID NOT NULL REFERENCES devices(device_id),
    offline_actions_json JSONB NOT NULL,
    conflict_actions_json JSONB,       -- Lưu nhật ký các thao tác bị loại do xung đột (task đã hủy/giao lại/đơn ERP hủy)
    sync_status VARCHAR(30) NOT NULL DEFAULT 'PROCESSED', -- PROCESSED, PARTIAL_CONFLICT, FAILED
    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Lịch ca (Đồng bộ từ HR theo [Q#13] = HR_MASTER), Điều động liên khâu & Bàn giao ca (NV-DC-3..5, TK-2.5, QL-9.1..9.4)
CREATE TABLE shifts (
    shift_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    warehouse_id UUID NOT NULL REFERENCES warehouses(warehouse_id),
    shift_code VARCHAR(30) NOT NULL,
    shift_name VARCHAR(100) NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    is_overnight BOOLEAN NOT NULL DEFAULT FALSE, -- Hỗ trợ ca qua nửa đêm
    UNIQUE (warehouse_id, shift_code)
);

CREATE TABLE shift_rosters (
    roster_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    warehouse_id UUID NOT NULL REFERENCES warehouses(warehouse_id),
    shift_date DATE NOT NULL,
    shift_id UUID NOT NULL REFERENCES shifts(shift_id),
    user_id UUID NOT NULL REFERENCES users(user_id),
    assigned_stage work_stage_type NOT NULL,
    attendance_status VARCHAR(30) NOT NULL DEFAULT 'SCHEDULED', -- SCHEDULED, PRESENT, LATE, ABSENT, ON_LEAVE (Đồng bộ từ HR - QL-9.1a)
    is_incident_shift_excluded BOOLEAN NOT NULL DEFAULT FALSE,  -- [Q#17] Đánh dấu ca sự cố loại khỏi so sánh KPI
    incident_exclusion_reason TEXT,
    UNIQUE (shift_date, shift_id, user_id)
);

-- Bảng lưu yêu cầu đổi ca (chỉ dùng khi hr_integration_mode = 'WMS_LOCAL', mặc định tắt theo Q-11 / F45)
CREATE TABLE shift_swap_requests (
    swap_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    requester_roster_id UUID NOT NULL REFERENCES shift_rosters(roster_id),
    target_user_id UUID REFERENCES users(user_id),
    reason TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING', -- PENDING, APPROVED, REJECTED
    decided_by UUID REFERENCES users(user_id),
    decision_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE overtime_requests (
    ot_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    warehouse_id UUID NOT NULL REFERENCES warehouses(warehouse_id),
    shift_date DATE NOT NULL,
    stage work_stage_type NOT NULL,
    requested_headcount INT NOT NULL,
    planned_hours NUMERIC(4, 2) NOT NULL,
    reason TEXT NOT NULL,
    proposed_by UUID NOT NULL REFERENCES users(user_id),
    approval_status approval_status_type NOT NULL DEFAULT 'PENDING_D2',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE overtime_participants (
    ot_id UUID NOT NULL REFERENCES overtime_requests(ot_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(user_id),
    worker_response VARCHAR(20) NOT NULL DEFAULT 'INVITED', -- INVITED, ACCEPTED, DECLINED (NV-DC-5)
    decline_reason TEXT,
    actual_hours_logged NUMERIC(4, 2),                      -- WMS chỉ ghi giờ thực tế để đẩy HR, không tính lương
    PRIMARY KEY (ot_id, user_id)
);

CREATE TABLE cross_stage_transfers (
    transfer_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    warehouse_id UUID NOT NULL REFERENCES warehouses(warehouse_id),
    user_id UUID NOT NULL REFERENCES users(user_id),
    from_stage work_stage_type NOT NULL,
    to_stage work_stage_type NOT NULL,
    proposed_by UUID REFERENCES users(user_id), -- TK-5.9 Thủ kho đề xuất
    approved_by UUID REFERENCES users(user_id), -- QL-9.3 Quản lý duyệt
    effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_until TIMESTAMPTZ NOT NULL,       -- Hết giờ tự trả về khâu cũ
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    worker_reject_reason TEXT
);

CREATE TABLE shift_handovers (
    handover_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    warehouse_id UUID NOT NULL REFERENCES warehouses(warehouse_id),
    shift_date DATE NOT NULL,
    from_shift_id UUID NOT NULL REFERENCES shifts(shift_id),
    from_supervisor_id UUID NOT NULL REFERENCES users(user_id),
    to_supervisor_id UUID NOT NULL REFERENCES users(user_id),
    unfinished_tasks_count INT NOT NULL DEFAULT 0,
    urgent_orders_count INT NOT NULL DEFAULT 0,
    locked_locations_count INT NOT NULL DEFAULT 0,
    pending_approvals_count INT NOT NULL DEFAULT 0,
    handover_notes TEXT,
    shift_report_summary JSONB,                 -- TK-2.6 Báo cáo ca
    acknowledged_at TIMESTAMPTZ,                -- TK-2.5 Trưởng ca sau xác nhận nhận ca
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Chứng nhận, Đào tạo, Hiệu suất & Sự cố An toàn (NV-DC-6..8, QL-9.6..9.10, BG-4)
CREATE TABLE user_certifications (
    user_cert_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    cert_type_code VARCHAR(50) NOT NULL, -- FORKLIFT, COLD_STORAGE, HAZMAT, STAGE_QUALIFICATION (QL-9.7b)
    issued_date DATE NOT NULL,
    expiry_date DATE,
    attachment_url TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'VALID', -- VALID, EXPIRED, REVOKED
    revoked_reason TEXT,
    revoked_by UUID REFERENCES users(user_id)
);

CREATE TABLE safety_incidents (
    incident_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    warehouse_id UUID NOT NULL REFERENCES warehouses(warehouse_id),
    incident_type VARCHAR(30) NOT NULL, -- ACCIDENT, NEAR_MISS (NV-DC-7, QL-9.10)
    severity VARCHAR(20) NOT NULL DEFAULT 'NORMAL', -- NORMAL, CRITICAL (Tự báo BG-4)
    occurred_at TIMESTAMPTZ NOT NULL,
    location_id UUID REFERENCES locations(location_id),
    reported_by UUID NOT NULL REFERENCES users(user_id),
    involved_user_ids UUID[],
    description TEXT NOT NULL,
    photo_urls TEXT[],
    bgd_acknowledged_by UUID REFERENCES users(user_id), -- BG-4
    bgd_acknowledged_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- PHẦN 9: CẢNH BÁO, THÔNG BÁO, ĐỒNG BỘ ERP/TMS & AUDIT LOG
-- =============================================================================

CREATE TABLE alerts (
    alert_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    warehouse_id UUID NOT NULL REFERENCES warehouses(warehouse_id),
    alert_type VARCHAR(50) NOT NULL, -- TASK_OVERDUE, WORKER_IDLE, ZONE_OVERLOAD, DEVICE_ERROR, LOW_STOCK (QL-6.1), EXPIRING_LOT (QL-6.2), ERP_RECON_DIFF, CRITICAL_INCIDENT
    severity VARCHAR(20) NOT NULL DEFAULT 'WARNING', -- INFO, WARNING, CRITICAL (Không được tắt tại QL-6.5)
    target_role_code VARCHAR(50) NOT NULL,
    ref_object_type VARCHAR(40),
    ref_object_id UUID,
    grouped_count INT NOT NULL DEFAULT 1, -- TK-2.3 Gộp nhiều cảnh báo cùng loại
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN', -- OPEN, ACKNOWLEDGED, SNOOZED, ESCALATED, CLOSED
    snoozed_until TIMESTAMPTZ,
    escalated_to_user_id UUID REFERENCES users(user_id), -- [Q#4] Leo thang lên Quản lý kho sau M phút
    resolution_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE notifications (
    notification_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    body TEXT NOT NULL,
    deep_link_route VARCHAR(200), -- Mở đúng màn hình (#/f/...) (NV-DC-9)
    push_status VARCHAR(20) NOT NULL DEFAULT 'PENDING', -- PENDING, SENT, DELIVERED, CLICKED, FAILED_FALLBACK_INBOX (TP-4, TP-5)
    is_read_in_app BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Chứng từ đồng bộ ERP/TMS & Phân tách Lỗi Nghiệp vụ vs Lỗi Kỹ thuật (TK-5.7, AD-12, ER-3..5)
CREATE TABLE integration_sync_logs (
    sync_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    warehouse_id UUID REFERENCES warehouses(warehouse_id),
    external_system VARCHAR(20) NOT NULL, -- ERP, TMS, SSO, HR
    direction VARCHAR(10) NOT NULL,       -- INBOUND, OUTBOUND
    doc_type VARCHAR(40) NOT NULL,        -- SKU, PO, SO, ASN, GRN, GI, ADJUSTMENT, SCRAP, WAYBILL, RECONCILIATION, RMA
    doc_id UUID,
    business_payload JSONB,               -- Chỉ Thủ kho (TK-5.7) được xem/sửa; ẩn với Admin (AD-12)
    technical_meta JSONB,                 -- [CẬP NHẬT v4.1 - F47] Chuẩn hóa snake_case
    error_category sync_error_category NOT NULL DEFAULT 'NONE',
    error_message TEXT,
    retry_count INT NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'SUCCESS', -- PENDING, SUCCESS, FAILED_BUSINESS, FAILED_TECHNICAL, RESOLVED
    resolved_by UUID REFERENCES users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Nhật ký Kiểm toán bất biến (Audit Log - Bắt buộc cho mọi thao tác từ chối, hủy, duyệt D1/D2/D3 - F41)
CREATE TABLE audit_logs (
    audit_id BIGSERIAL PRIMARY KEY,
    warehouse_id UUID,
    actor_user_id UUID REFERENCES users(user_id),
    delegated_from_user_id UUID REFERENCES users(user_id),
    action_code VARCHAR(50) NOT NULL, -- Mã chức năng thực hiện (VD: NH-1.s6, CT-1.s4, TK-3.2, TK-3.3, QL-7.5, BG-3)
    entity_name VARCHAR(50) NOT NULL,
    entity_id UUID,
    old_values JSONB,
    new_values JSONB,
    reauth_verified BOOLEAN NOT NULL DEFAULT FALSE,
    ip_address VARCHAR(45),
    device_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- PHẦN 10: HÀM NGHIỆP VỤ LÕI & TRIGGERS RÀNG BUỘC TỰ ĐỘNG (v4.1)
-- =============================================================================

-- 10.1. Hàm lõi cập nhật Tồn kho 5 trạng thái & ghi Sổ cái giao dịch bất biến (Khắc phục F01)
CREATE OR REPLACE FUNCTION fn_apply_inventory_movement(
    p_warehouse_id UUID,
    p_location_id UUID,
    p_sku_id UUID,
    p_lot_id UUID,
    p_pallet_id UUID,
    p_serial_number VARCHAR(100),
    p_tx_type VARCHAR(40),
    p_delta_available NUMERIC(18, 3),
    p_delta_allocated NUMERIC(18, 3),
    p_delta_counting NUMERIC(18, 3),
    p_delta_locked NUMERIC(18, 3),
    p_delta_damaged NUMERIC(18, 3),
    p_ref_doc_type VARCHAR(40),
    p_ref_doc_id UUID,
    p_performed_by UUID
) RETURNS UUID AS $$
DECLARE
    v_unit_cost NUMERIC(18, 4);
    v_loc_status location_status_type;
    v_tx_id UUID;
    v_net_qty_change NUMERIC(18, 3);
BEGIN
    -- [Khắc phục F37] Kiểm tra trạng thái khóa vị trí trước khi cho phép nhập/xuất/cất/soạn
    SELECT status INTO v_loc_status FROM locations WHERE location_id = p_location_id;
    IF v_loc_status = 'MAINTENANCE_LOCKED' THEN
        RAISE EXCEPTION 'VI_TRI_BI_KHOA_BAO_TRI: Vị trí (%) đang khóa bảo trì, không thể thực hiện giao dịch (%).',
            p_location_id, p_tx_type;
    END IF;
    IF v_loc_status = 'COUNTING_LOCKED' AND p_tx_type NOT IN ('LOCK_COUNT', 'CYCLE_COUNT') THEN
        RAISE EXCEPTION 'VI_TRI_DANG_KIEM_KE: Vị trí (%) đang khóa kiểm kê, chặn các giao dịch xuất/nhập/cất/soạn (%).',
            p_location_id, p_tx_type;
    END IF;

    SELECT unit_cost INTO v_unit_cost FROM skus WHERE sku_id = p_sku_id;

    INSERT INTO inventory_balances (
        warehouse_id, location_id, sku_id, lot_id, pallet_id, serial_number,
        qty_available, qty_allocated, qty_counting, qty_locked, qty_damaged, updated_at
    ) VALUES (
        p_warehouse_id, p_location_id, p_sku_id, p_lot_id, p_pallet_id, p_serial_number,
        GREATEST(0, p_delta_available), GREATEST(0, p_delta_allocated),
        GREATEST(0, p_delta_counting), GREATEST(0, p_delta_locked), GREATEST(0, p_delta_damaged), NOW()
    )
    ON CONFLICT (warehouse_id, location_id, sku_id, lot_id, pallet_id, serial_number)
    DO UPDATE SET
        qty_available = inventory_balances.qty_available + p_delta_available,
        qty_allocated = inventory_balances.qty_allocated + p_delta_allocated,
        qty_counting  = inventory_balances.qty_counting  + p_delta_counting,
        qty_locked    = inventory_balances.qty_locked    + p_delta_locked,
        qty_damaged   = inventory_balances.qty_damaged   + p_delta_damaged,
        version_no    = inventory_balances.version_no + 1,
        updated_at    = NOW();

    v_net_qty_change := p_delta_available + p_delta_allocated + p_delta_counting + p_delta_locked + p_delta_damaged;

    INSERT INTO inventory_transactions (
        warehouse_id, tx_type, sku_id, lot_id, pallet_id, serial_number,
        to_location_id, qty_change, unit_cost_snapshot, ref_doc_type, ref_doc_id, performed_by
    ) VALUES (
        p_warehouse_id, p_tx_type, p_sku_id, p_lot_id, p_pallet_id, p_serial_number,
        p_location_id, v_net_qty_change, COALESCE(v_unit_cost, 0), p_ref_doc_type, p_ref_doc_id, p_performed_by
    ) RETURNING tx_id INTO v_tx_id;

    RETURN v_tx_id;
END;
$$ LANGUAGE plpgsql;

-- 10.2. Trigger kiểm tra Tách quyền (SoD) ở MỌI CẤP DUYỆT D1, D2, D3 (Khắc phục F22, F44)
CREATE OR REPLACE FUNCTION fn_enforce_sod_all_tiers()
RETURNS TRIGGER AS $$
DECLARE
    v_proposer_id UUID;
BEGIN
    IF NEW.action IN ('APPROVE', 'REJECT') THEN
        SELECT proposer_user_id INTO v_proposer_id
        FROM approval_requests
        WHERE approval_id = NEW.approval_id;

        IF NEW.actor_user_id = v_proposer_id OR NEW.delegated_from_user_id = v_proposer_id THEN
            RAISE EXCEPTION 'VI_PHAM_TACH_QUYEN_SOD: Người lập đề xuất (%) không được phép phê duyệt hồ sơ của chính mình ở bất kỳ cấp nào (Tier: %).',
                v_proposer_id, NEW.tier;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_enforce_sod_all_tiers
BEFORE INSERT ON approval_histories
FOR EACH ROW EXECUTE FUNCTION fn_enforce_sod_all_tiers();

-- 10.3. Trigger tự động cộng dồn po_lines.qty_received & cập nhật trạng thái PO khi GRN được duyệt (Khắc phục F25)
CREATE OR REPLACE FUNCTION fn_sync_po_on_grn_approved()
RETURNS TRIGGER AS $$
DECLARE
    v_total_ordered NUMERIC(18, 3);
    v_total_received NUMERIC(18, 3);
BEGIN
    IF NEW.status = 'APPROVED' AND (OLD.status IS DISTINCT FROM 'APPROVED') AND NEW.po_id IS NOT NULL THEN
        UPDATE po_lines pl
        SET qty_received = pl.qty_received + GREATEST(0, gl.qty_actual - gl.qty_damaged),
            version_no = pl.version_no + 1
        FROM grn_lines gl
        WHERE gl.grn_id = NEW.grn_id AND gl.po_line_id = pl.po_line_id;

        SELECT SUM(qty_ordered), SUM(qty_received)
        INTO v_total_ordered, v_total_received
        FROM po_lines
        WHERE po_id = NEW.po_id;

        UPDATE purchase_orders
        SET status = CASE
                WHEN v_total_received >= v_total_ordered THEN 'FULLY_RECEIVED'::po_status_type
                WHEN v_total_received > 0 THEN 'PARTIAL_RECEIVED'::po_status_type
                ELSE status
            END,
            version_no = version_no + 1
        WHERE po_id = NEW.po_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_po_on_grn_approved
AFTER UPDATE OF status ON grns
FOR EACH ROW EXECUTE FUNCTION fn_sync_po_on_grn_approved();

-- 10.4. Trigger tự động đếm tổng số kiện (goods_issues.total_packages) từ bảng packages (Khắc phục F13)
CREATE OR REPLACE FUNCTION fn_sync_gi_package_count()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.gi_id IS NOT NULL THEN
        UPDATE goods_issues
        SET total_packages = (SELECT COUNT(*) FROM packages WHERE gi_id = NEW.gi_id)
        WHERE gi_id = NEW.gi_id;
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.gi_id IS NOT NULL AND OLD.gi_id IS DISTINCT FROM NEW.gi_id THEN
        UPDATE goods_issues
        SET total_packages = (SELECT COUNT(*) FROM packages WHERE gi_id = OLD.gi_id)
        WHERE gi_id = OLD.gi_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_gi_package_count
AFTER INSERT OR UPDATE OF gi_id OR DELETE ON packages
FOR EACH ROW EXECUTE FUNCTION fn_sync_gi_package_count();

-- 10.5. Trigger tự động đóng Phiếu kiểm kê & mở khóa Vị trí khi tất cả dòng kiểm kê đã hoàn tất (Khắc phục F43)
CREATE OR REPLACE FUNCTION fn_auto_close_cycle_count_sheet()
RETURNS TRIGGER AS $$
DECLARE
    v_unfinished_lines INT;
BEGIN
    IF NEW.status IN ('AUTO_APPROVED_Z', 'APPROVED') AND (OLD.status IS DISTINCT FROM NEW.status) THEN
        SELECT COUNT(*) INTO v_unfinished_lines
        FROM cycle_count_lines
        WHERE count_sheet_id = NEW.count_sheet_id
          AND status NOT IN ('AUTO_APPROVED_Z', 'APPROVED');

        IF v_unfinished_lines = 0 THEN
            UPDATE cycle_count_sheets
            SET status = 'CLOSED',
                closed_at = NOW(),
                version_no = version_no + 1
            WHERE count_sheet_id = NEW.count_sheet_id;

            UPDATE locations l
            SET status = CASE
                    WHEN l.current_capacity_pct = 0 THEN 'EMPTY'::location_status_type
                    WHEN l.current_capacity_pct >= 100 THEN 'FULL'::location_status_type
                    ELSE 'PARTIAL'::location_status_type
                END,
                lock_reason = NULL,
                locked_by = NULL,
                locked_at = NULL
            FROM cycle_count_lines ccl
            WHERE ccl.count_sheet_id = NEW.count_sheet_id
              AND ccl.location_id = l.location_id
              AND l.status = 'COUNTING_LOCKED';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_auto_close_cycle_count_sheet
AFTER UPDATE OF status ON cycle_count_lines
FOR EACH ROW EXECUTE FUNCTION fn_auto_close_cycle_count_sheet();

-- =============================================================================
-- PHẦN 11: CHỈ MỤC (INDEXES) TỐI ƯU HIỆU NĂNG TRUY VẤN THỜI GIAN THỰC
-- =============================================================================

CREATE INDEX idx_inv_balances_lookup ON inventory_balances (warehouse_id, sku_id, location_id);
CREATE INDEX idx_lots_fefo ON lots (sku_id, is_priority_dispatch DESC, expiry_date ASC NULLS LAST, received_at ASC);
CREATE INDEX idx_tasks_dispatch ON tasks (warehouse_id, status, stage, priority, sla_due_at);
CREATE INDEX idx_tasks_worker ON tasks (assigned_to, status);
CREATE INDEX idx_orders_status_cutoff ON outbound_orders (warehouse_id, status, is_urgent DESC, cutoff_time ASC);
CREATE INDEX idx_approvals_queue ON approval_requests (warehouse_id, status, current_tier, created_at ASC);
CREATE INDEX idx_sync_errors ON integration_sync_logs (status, error_category, external_system);
CREATE INDEX idx_audit_logs_entity ON audit_logs (entity_name, entity_id, created_at DESC);
