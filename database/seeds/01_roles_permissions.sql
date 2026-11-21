-- =============================================================================
-- SEED 01: VAI TRÒ, QUYỀN VÀ PHÂN QUYỀN (RBAC)
-- Tuân thủ Mục 5.3 Đặc tả và slide phân rã chức năng v3 (Slide 90-93)
-- Chạy lại được (Idempotent với ON CONFLICT)
-- =============================================================================

-- 1. Nạp 9 vai trò chuẩn
INSERT INTO roles (role_id, role_code, role_name, actor_group, default_channel) VALUES
    ('b1000000-0000-0000-0000-000000000001', 'nv-nhan', 'Nhân viên nhận hàng', 'THUC_THI', 'MOBILE'),
    ('b1000000-0000-0000-0000-000000000002', 'nv-cat', 'Nhân viên cất hàng', 'THUC_THI', 'MOBILE'),
    ('b1000000-0000-0000-0000-000000000003', 'nv-soan', 'Nhân viên soạn hàng', 'THUC_THI', 'MOBILE'),
    ('b1000000-0000-0000-0000-000000000004', 'nv-dongoi', 'Nhân viên đóng gói, xuất hàng', 'THUC_THI', 'MOBILE'),
    ('b1000000-0000-0000-0000-000000000005', 'nv-kiemke', 'Nhân viên kiểm kê', 'THUC_THI', 'MOBILE'),
    ('b1000000-0000-0000-0000-000000000006', 'thukho', 'Thủ kho / Trưởng ca', 'DIEU_HANH', 'MOBILE_WEB'),
    ('b1000000-0000-0000-0000-000000000007', 'quanly', 'Quản lý kho', 'DIEU_HANH', 'MOBILE_WEB'),
    ('b1000000-0000-0000-0000-000000000008', 'bgd', 'Ban giám đốc', 'LANH_DAO', 'WEB'),
    ('b1000000-0000-0000-0000-000000000009', 'admin', 'Quản trị hệ thống', 'HE_THONG', 'WEB')
ON CONFLICT (role_code) DO UPDATE SET
    role_name = EXCLUDED.role_name,
    actor_group = EXCLUDED.actor_group,
    default_channel = EXCLUDED.default_channel;

-- 2. Nạp danh mục chức năng / quyền (permissions)
INSERT INTO permissions (permission_code, feature_name, module_tab, channel) VALUES
    ('NH-1', 'Nhận hàng', 'VAN_HANH', 'MOBILE'),
    ('CAT-1', 'Cất hàng', 'VAN_HANH', 'MOBILE'),
    ('SO-1', 'Soạn hàng', 'VAN_HANH', 'MOBILE'),
    ('DG-1', 'Đóng gói, xuất kho', 'VAN_HANH', 'MOBILE'),
    ('KK-1', 'Kiểm kê', 'VAN_HANH', 'MOBILE'),
    ('TK-3.2', 'Duyệt chênh lệch nhận hàng & kiểm kê', 'NGOAI_LE_CAU_HINH', 'MOBILE_WEB'),
    ('TK-4.4', 'Duyệt điều chỉnh tồn, hủy hàng', 'NGOAI_LE_CAU_HINH', 'MOBILE_WEB'),
    ('QL-2.1', 'Theo dõi phiếu nhập xuất', 'VAN_HANH', 'MOBILE_WEB'),
    ('TK-1.1', 'Điều phối và phân công task', 'GIAM_SAT_NHAN_LUC', 'MOBILE_WEB'),
    ('QL-1.1', 'Tra cứu tồn kho', 'VAN_HANH', 'ALL'),
    ('QL-8.1', 'KPI, dashboard, báo cáo', 'GIAM_SAT_NHAN_LUC', 'WEB'),
    ('AD-1', 'Người dùng, phân quyền, danh mục, cấu hình', 'NGOAI_LE_CAU_HINH', 'WEB'),
    ('QL-9.10', 'Sự cố an toàn lao động', 'GIAM_SAT_NHAN_LUC', 'ALL'),
    ('QL-5.3', 'Khiếu nại, giao thất bại, trả nhà cung cấp', 'NGOAI_LE_CAU_HINH', 'WEB')
ON CONFLICT (permission_code) DO UPDATE SET
    feature_name = EXCLUDED.feature_name,
    module_tab = EXCLUDED.module_tab,
    channel = EXCLUDED.channel;

-- 3. Nạp ma trận phân quyền (role_permissions)
-- Xóa quyền cũ nếu có để đảm bảo chạy lại đồng bộ đúng ma trận
DELETE FROM role_permissions;

INSERT INTO role_permissions (role_id, permission_code, access_type)
SELECT r.role_id, p.permission_code, p.access_type
FROM (VALUES
    -- nv-nhan
    ('nv-nhan', 'NH-1', 'X'),
    ('nv-nhan', 'QL-1.1', 'V'),
    ('nv-nhan', 'QL-9.10', 'X'),

    -- nv-cat
    ('nv-cat', 'CAT-1', 'X'),
    ('nv-cat', 'QL-1.1', 'V'),
    ('nv-cat', 'QL-9.10', 'X'),

    -- nv-soan
    ('nv-soan', 'SO-1', 'X'),
    ('nv-soan', 'QL-1.1', 'V'),
    ('nv-soan', 'QL-9.10', 'X'),

    -- nv-dongoi
    ('nv-dongoi', 'DG-1', 'X'),
    ('nv-dongoi', 'QL-1.1', 'V'),
    ('nv-dongoi', 'QL-9.10', 'X'),

    -- nv-kiemke (đếm mù: không có quyền xem tồn QL-1.1)
    ('nv-kiemke', 'KK-1', 'X'),
    ('nv-kiemke', 'QL-9.10', 'X'),

    -- thukho
    ('thukho', 'NH-1', 'V'),
    ('thukho', 'CAT-1', 'G'),
    ('thukho', 'SO-1', 'G'),
    ('thukho', 'DG-1', 'G'),
    ('thukho', 'KK-1', 'G'),
    ('thukho', 'TK-3.2', 'D1'),
    ('thukho', 'TK-4.4', 'E'),
    ('thukho', 'QL-2.1', 'V'),
    ('thukho', 'TK-1.1', 'G'),
    ('thukho', 'QL-1.1', 'V'),
    ('thukho', 'QL-8.1', 'V'),
    ('thukho', 'QL-9.10', 'X'),
    ('thukho', 'QL-5.3', 'V'),

    -- quanly
    ('quanly', 'NH-1', 'V'),
    ('quanly', 'CAT-1', 'V'),
    ('quanly', 'SO-1', 'V'),
    ('quanly', 'DG-1', 'V'),
    ('quanly', 'KK-1', 'V'),
    ('quanly', 'TK-3.2', 'D2'),
    ('quanly', 'TK-4.4', 'D2'),
    ('quanly', 'QL-2.1', 'V'),
    ('quanly', 'TK-1.1', 'G'),
    ('quanly', 'QL-1.1', 'V'),
    ('quanly', 'QL-8.1', 'V'),
    ('quanly', 'QL-9.10', 'X'),
    ('quanly', 'QL-5.3', 'X'),

    -- bgd
    ('bgd', 'TK-3.2', 'D3'),
    ('bgd', 'TK-4.4', 'D3'),
    ('bgd', 'QL-1.1', 'V'),
    ('bgd', 'QL-8.1', 'V'),
    ('bgd', 'QL-9.10', 'V'),

    -- admin (chỉ cấu hình quản trị hệ thống, không có quyền nghiệp vụ)
    ('admin', 'AD-1', 'X')
) AS p(role_code, permission_code, access_type)
JOIN roles r ON r.role_code = p.role_code
ON CONFLICT (role_id, permission_code) DO UPDATE SET
    access_type = EXCLUDED.access_type;
