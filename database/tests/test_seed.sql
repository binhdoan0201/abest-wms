-- =============================================================================
-- KIỂM THỬ DỮ LIỆU SEED (TEST_SEED.SQL)
-- Kiểm tra:
-- 1. Đúng 9 vai trò
-- 2. Mỗi vai trò có đúng 1 user active
-- 3. Mỗi role_code có ít nhất 1 dòng role_permissions
-- 4. Đúng 1 kho
-- 5. Ít nhất 30 vị trí
-- 6. Ít nhất 10 SKU
-- =============================================================================

DO $$
DECLARE
    v_role_count INT;
    v_active_user_count INT;
    v_roles_without_perm INT;
    v_warehouse_count INT;
    v_location_count INT;
    v_sku_count INT;
    v_role RECORD;
BEGIN
    -- 1. Đúng 9 vai trò
    SELECT COUNT(*) INTO v_role_count FROM roles;
    IF v_role_count <> 9 THEN
        RAISE EXCEPTION 'TEST_SEED FAILED: Kỳ vọng đúng 9 vai trò, thực tế có % vai trò', v_role_count;
    END IF;

    -- 2. Mỗi vai trò có đúng 1 user active
    FOR v_role IN SELECT role_id, role_code FROM roles LOOP
        SELECT COUNT(*) INTO v_active_user_count
        FROM users
        WHERE primary_role_id = v_role.role_id AND status = 'ACTIVE';

        IF v_active_user_count <> 1 THEN
            RAISE EXCEPTION 'TEST_SEED FAILED: Vai trò % kỳ vọng đúng 1 user active, thực tế có % user',
                v_role.role_code, v_active_user_count;
        END IF;
    END LOOP;

    -- 3. Mỗi role_code có ít nhất 1 dòng role_permissions
    FOR v_role IN SELECT role_id, role_code FROM roles LOOP
        SELECT COUNT(*) INTO v_roles_without_perm
        FROM role_permissions
        WHERE role_id = v_role.role_id;

        IF v_roles_without_perm < 1 THEN
            RAISE EXCEPTION 'TEST_SEED FAILED: Vai trò % không có quyền nào trong role_permissions',
                v_role.role_code;
        END IF;
    END LOOP;

    -- 4. Đúng 1 kho
    SELECT COUNT(*) INTO v_warehouse_count FROM warehouses;
    IF v_warehouse_count <> 1 THEN
        RAISE EXCEPTION 'TEST_SEED FAILED: Kỳ vọng đúng 1 kho, thực tế có % kho', v_warehouse_count;
    END IF;

    -- 5. Ít nhất 30 vị trí
    SELECT COUNT(*) INTO v_location_count FROM locations;
    IF v_location_count < 30 THEN
        RAISE EXCEPTION 'TEST_SEED FAILED: Kỳ vọng ít nhất 30 vị trí, thực tế có % vị trí', v_location_count;
    END IF;

    -- 6. Ít nhất 10 SKU
    SELECT COUNT(*) INTO v_sku_count FROM skus;
    IF v_sku_count < 10 THEN
        RAISE EXCEPTION 'TEST_SEED FAILED: Kỳ vọng ít nhất 10 SKU, thực tế có % SKU', v_sku_count;
    END IF;

    RAISE NOTICE '============================================================';
    RAISE NOTICE 'TẤT CẢ KIỂM THỬ TEST_SEED THÀNH CÔNG!';
    RAISE NOTICE ' - Vai trò: %/9', v_role_count;
    RAISE NOTICE ' - User active theo vai trò: 1/1 cho 9 vai trò';
    RAISE NOTICE ' - Quyền theo vai trò: 100%% các vai trò có ít nhất 1 quyền';
    RAISE NOTICE ' - Kho: %/1', v_warehouse_count;
    RAISE NOTICE ' - Vị trí: % (kỳ vọng >= 30)', v_location_count;
    RAISE NOTICE ' - SKU: % (kỳ vọng >= 10)', v_sku_count;
    RAISE NOTICE '============================================================';
END $$;
