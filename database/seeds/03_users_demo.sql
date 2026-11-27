-- =============================================================================
-- SEED 03: TÀI KHOẢN NGƯỜI DÙNG DEMO (9 VAI TRÒ)
-- Mật khẩu chung: Demo@123456
-- Hash bcrypt được sinh bởi scripts/make_password_hash.py
-- Chạy lại được (Idempotent với ON CONFLICT)
-- =============================================================================

INSERT INTO users (
    user_id,
    username,
    full_name,
    email,
    phone,
    auth_provider,
    password_hash,
    must_change_password,
    primary_warehouse_id,
    primary_role_id,
    primary_stage,
    status,
    is_seasonal,
    is_safety_checked
)
SELECT
    u.user_id,
    u.username,
    u.full_name,
    u.email,
    u.phone,
    'LOCAL_SEASONAL'::auth_provider_type,
    -- Hash sinh bởi scripts/make_password_hash.py cho mật khẩu 'Demo@123456'
    '$2b$12$Nsx9/JxFWBH8w2zStP0lZeMKQ1v8gass2BGZ4858VQnjL/tbpr5x2',
    FALSE,
    'a0000000-0000-0000-0000-000000000001'::uuid,
    r.role_id,
    u.primary_stage::work_stage_type,
    'ACTIVE'::user_status_type,
    FALSE,
    TRUE
FROM (VALUES
    ('c0000000-0000-0000-0000-000000000001'::uuid, 'nv_nhan', 'Trần Văn Nhận', 'nv_nhan@abest-wms.local', '0901000001', 'nv-nhan', 'NHAN_HANG'),
    ('c0000000-0000-0000-0000-000000000002'::uuid, 'nv_cat', 'Lê Văn Cất', 'nv_cat@abest-wms.local', '0901000002', 'nv-cat', 'CAT_HANG'),
    ('c0000000-0000-0000-0000-000000000003'::uuid, 'nv_soan', 'Phạm Văn Soạn', 'nv_soan@abest-wms.local', '0901000003', 'nv-soan', 'SOAN_HANG'),
    ('c0000000-0000-0000-0000-000000000004'::uuid, 'nv_dongoi', 'Hoàng Thị Gói', 'nv_dongoi@abest-wms.local', '0901000004', 'nv-dongoi', 'DONG_GOI_XUAT'),
    ('c0000000-0000-0000-0000-000000000005'::uuid, 'nv_kiemke', 'Võ Văn Kê', 'nv_kiemke@abest-wms.local', '0901000005', 'nv-kiemke', 'KIEM_KE'),
    ('c0000000-0000-0000-0000-000000000006'::uuid, 'thukho', 'Đỗ Thủ Kho', 'thukho@abest-wms.local', '0901000006', 'thukho', 'QUAN_LY_CHUNG'),
    ('c0000000-0000-0000-0000-000000000007'::uuid, 'quanly', 'Nguyễn Văn Quản Lý', 'quanly@abest-wms.local', '0901000007', 'quanly', 'QUAN_LY_CHUNG'),
    ('c0000000-0000-0000-0000-000000000008'::uuid, 'bgd', 'Phan Giám Đốc', 'bgd@abest-wms.local', '0901000008', 'bgd', 'QUAN_LY_CHUNG'),
    ('c0000000-0000-0000-0000-000000000009'::uuid, 'admin', 'Quản Trị Viên Hệ Thống', 'admin@abest-wms.local', '0901000009', 'admin', 'QUAN_LY_CHUNG')
) AS u(user_id, username, full_name, email, phone, role_code, primary_stage)
JOIN roles r ON r.role_code = u.role_code
ON CONFLICT (username) DO UPDATE SET
    full_name = EXCLUDED.full_name,
    password_hash = EXCLUDED.password_hash,
    primary_role_id = EXCLUDED.primary_role_id,
    primary_stage = EXCLUDED.primary_stage,
    status = EXCLUDED.status;
