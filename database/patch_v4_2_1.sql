-- =============================================================================
-- WMS DATABASE PATCH v4.1 -> v4.2.1  (v4.2 + 4 bản vá F1..F4 bên dưới)
-- Áp dụng LÊN TRÊN wms_database_schema_v4_1.sql (PostgreSQL 15+, đã chạy thử trên 16)
-- Cách chạy:  psql -d <db> -v ON_ERROR_STOP=1 -f wms_database_patch_v4_2.sql
--   (KHÔNG dùng psql -1/--single-transaction vì PHẦN A thêm giá trị ENUM phải commit trước PHẦN B)
--
-- Nội dung vá (ký hiệu P# = mục trong bản rà soát):
--  P1  Kiểm kê: thêm REJECTED/ADJUSTED, đóng phiếu & mở khóa đúng thời điểm
--  P2  Phê duyệt: tự leo thang khi quá SLA, SUPERSEDED, đồng bộ trạng thái, chặn trùng request
--  P3  Phân luồng duyệt: hàm fn_resolve_approval_tier (force_review bỏ qua Z, Z-GRN tùy chọn)
--  P4  Hàm tồn kho v2: có from/to location, khóa lạc quan, sổ cái ghi delta từng bucket, cập nhật vị trí
--  P5  Trigger PO: kiểm tra từng dòng, gộp nhiều grn_line cùng po_line, chặn nhận dư
--  P6  Bảng mới: inventory_allocations, package_lines, return_order_lines, grn_count_attempts
--  P7  Liên kết: GRN reject -> xuất trả NCC, chuyển kho -> ASN kho nhận, RMA reject -> GI trả khách
--  P8  Ràng buộc nhỏ: FK thiếu, CHECK, sổ cái/audit bất biến, lỗi trigger DELETE của packages
--  P9  Đóng băng đơn xuất khi ERP đổi/hủy đang chờ Quản lý chốt (erp_change_pending = TRUE)
--  P10 Xử lý yêu cầu đổi/hủy từ ERP theo giai đoạn của đơn: tự chấp nhận / Quản lý quyết / tự từ chối,
--      luôn phản hồi lại ERP (bảng order_change_requests + 3 hàm fn_receive_erp_order_change, fn_decide_order_change)
--      Quy tắc mặc định (giả định thiết kế, đổi được): chỉ hỗ trợ HỦY ĐƠN; đổi số lượng/địa chỉ bị từ chối OUT_OF_SCOPE;
--      đơn đã lên xe (package đã quét hoặc GI LOADED/GI_CONFIRMED) tự từ chối; đơn SHIPPED trở đi tự từ chối + cảnh báo.
--  Bản vá v4.2.1 so với v4.2 (đã chạy thử 2 lần liên tiếp không lỗi, trên PostgreSQL 16):
--  F1  Chạy lại được nhiều lần (idempotent): thêm DROP CONSTRAINT IF EXISTS cho chk_approval_action / chk_actor_required;
--      bước đổi APPROVED -> ADJUSTED của dòng kiểm kê chỉ chạy ĐÚNG 1 LẦN (lần chạy lại không làm hỏng dòng
--      APPROVED hợp lệ theo nghĩa mới = đã duyệt, chưa ghi tồn)
--  F2  fn_refresh_location_status: hàng không gắn pallet tính mỗi (SKU, lô) là 1 đơn vị chiếm chỗ -> % đầy không còn 0%
--  F3  fn_transfer_inventory: sửa chú thích sai (hàng ALLOCATED chuyển sang staging VẪN giữ bucket ALLOCATED)
--  F4  Duyệt hết hạn (EXPIRED): đánh dấu grns.approval_expired_at và cycle_count_lines.approval_expired_at
--      (xóa dấu khi có yêu cầu duyệt mới) để màn hình lọc được hồ sơ chờ xử lý thủ công
-- Giả định về dữ liệu (ghi rõ để app tuân theo):
--  * approval_requests.object_id = grn_id | count_line_id | adjustment_id | ot_id theo object_type
--  * Dòng kiểm kê kết thúc khi status IN (AUTO_APPROVED_Z, ADJUSTED, REJECTED).
--    APPROVED = đã duyệt nhưng CHƯA ghi tồn; app ghi tồn xong mới chuyển ADJUSTED.
-- =============================================================================

-- ============================ PHẦN A: ENUM (autocommit) ======================
ALTER TYPE approval_status_type ADD VALUE IF NOT EXISTS 'SUPERSEDED';             -- request cũ bị thay khi đếm lại
ALTER TYPE pallet_status_type   ADD VALUE IF NOT EXISTS 'REJECTED_PENDING_RETURN'; -- GRN bị từ chối, chờ trả NCC
ALTER TYPE gi_doc_type          ADD VALUE IF NOT EXISTS 'CUSTOMER_RETURN_BACK';    -- trả lại khách khi RMA bị REJECT

-- ============================ PHẦN B: SCHEMA & LOGIC =========================
BEGIN;

-- ---------- B0. Cấu hình mới ----------
ALTER TABLE warehouse_configs
    ADD COLUMN IF NOT EXISTS grn_tolerance_apply BOOLEAN NOT NULL DEFAULT FALSE,        -- Z có áp dụng cho lệch GRN không (mặc định KHÔNG: Z là dung sai kiểm kê)
    ADD COLUMN IF NOT EXISTS over_receipt_tolerance_pct NUMERIC(5,2) NOT NULL DEFAULT 0; -- % nhận dư tối đa so với PO

-- [F4] Dấu hiệu hồ sơ duyệt đã HẾT HẠN, chờ xử lý thủ công (NULL = không hết hạn)
ALTER TABLE grns              ADD COLUMN IF NOT EXISTS approval_expired_at TIMESTAMPTZ;
ALTER TABLE cycle_count_lines ADD COLUMN IF NOT EXISTS approval_expired_at TIMESTAMPTZ;

-- ---------- B1. Vị trí: tính lại trạng thái & % đầy từ tồn thực tế ----------
CREATE OR REPLACE FUNCTION fn_refresh_location_status(p_location_id UUID)
RETURNS VOID AS $$
DECLARE
    v_has     BOOLEAN;
    v_pallets INT;
    v_max     INT;
    v_old_pct NUMERIC(5,2);
    v_pct     NUMERIC(5,2);
BEGIN
    SELECT max_pallets, current_capacity_pct INTO v_max, v_old_pct
    FROM locations WHERE location_id = p_location_id;
    IF NOT FOUND THEN RETURN; END IF;

    SELECT COALESCE(SUM(qty_available + qty_allocated + qty_counting + qty_locked + qty_damaged), 0) > 0,
           -- [F2] hàng có pallet: đếm theo pallet; hàng không gắn pallet: mỗi (SKU, lô) tính 1 đơn vị chiếm chỗ
           COUNT(DISTINCT COALESCE(pallet_id::TEXT, 'SKU:' || sku_id::TEXT || ':' || COALESCE(lot_id::TEXT, '')))
               FILTER (WHERE qty_available + qty_allocated + qty_counting + qty_locked + qty_damaged > 0)
    INTO v_has, v_pallets
    FROM inventory_balances WHERE location_id = p_location_id;

    v_pct := CASE
        WHEN NOT v_has THEN 0
        WHEN v_max IS NOT NULL AND v_max > 0 THEN LEAST(100, ROUND(100.0 * v_pallets / v_max, 2))
        ELSE v_old_pct
    END;

    UPDATE locations
    SET current_capacity_pct = v_pct,
        status = CASE
            WHEN status IN ('COUNTING_LOCKED', 'MAINTENANCE_LOCKED', 'DAMAGED_HOLD') THEN status  -- không tự gỡ khóa
            WHEN NOT v_has THEN 'EMPTY'::location_status_type
            WHEN v_pct >= 100 THEN 'FULL'::location_status_type
            ELSE 'PARTIAL'::location_status_type
        END
    WHERE location_id = p_location_id;
END;
$$ LANGUAGE plpgsql;

-- ---------- B2. Sổ cái: delta từng bucket + danh sách tx_type đầy đủ + bất biến ----------
ALTER TABLE inventory_transactions
    ADD COLUMN IF NOT EXISTS qty_delta_available NUMERIC(18,3) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS qty_delta_allocated NUMERIC(18,3) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS qty_delta_counting  NUMERIC(18,3) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS qty_delta_locked    NUMERIC(18,3) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS qty_delta_damaged   NUMERIC(18,3) NOT NULL DEFAULT 0;

ALTER TABLE inventory_transactions DROP CONSTRAINT IF EXISTS chk_tx_type;
ALTER TABLE inventory_transactions ADD CONSTRAINT chk_tx_type CHECK (tx_type IN (
    'RECEIVE','PUTAWAY','ALLOCATE','DEALLOCATE','PICK','PICK_TO_STAGING','RETURN_TO_SHELF','SHIP_GI',
    'INTERNAL_MOVE','LOCK_COUNT','CYCLE_COUNT','ADJUSTMENT','SCRAP','RETURN_IN','RETURN_BACK',
    'RELEASE_QUARANTINE','PALLET_SPLIT')) NOT VALID;   -- NOT VALID: không quét dữ liệu cũ, chỉ kiểm dòng mới

CREATE OR REPLACE FUNCTION fn_block_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'BAN_GHI_BAT_BIEN: Bảng % không cho phép % (chỉ INSERT). Dùng bút toán đảo để sửa.', TG_TABLE_NAME, TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_immutable_inventory_tx ON inventory_transactions;
CREATE TRIGGER trg_immutable_inventory_tx BEFORE UPDATE OR DELETE ON inventory_transactions
    FOR EACH ROW EXECUTE FUNCTION fn_block_mutation();
DROP TRIGGER IF EXISTS trg_immutable_audit_logs ON audit_logs;
CREATE TRIGGER trg_immutable_audit_logs BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION fn_block_mutation();

-- ---------- B3. Hàm tồn kho v2 ----------
DROP FUNCTION IF EXISTS fn_apply_inventory_movement(UUID,UUID,UUID,UUID,UUID,VARCHAR,VARCHAR,NUMERIC,NUMERIC,NUMERIC,NUMERIC,NUMERIC,VARCHAR,UUID,UUID);

CREATE OR REPLACE FUNCTION fn_apply_inventory_movement(
    p_warehouse_id UUID, p_location_id UUID, p_sku_id UUID, p_lot_id UUID, p_pallet_id UUID,
    p_serial_number VARCHAR, p_tx_type VARCHAR,
    p_delta_available NUMERIC, p_delta_allocated NUMERIC, p_delta_counting NUMERIC,
    p_delta_locked NUMERIC, p_delta_damaged NUMERIC,
    p_ref_doc_type VARCHAR, p_ref_doc_id UUID, p_performed_by UUID,
    p_counterpart_location_id UUID DEFAULT NULL,   -- vị trí đối ứng (nguồn nếu nhập, đích nếu xuất)
    p_expected_version INT DEFAULT NULL            -- khóa lạc quan (inventory_balances.version_no)
) RETURNS UUID AS $$
DECLARE
    v_unit_cost  NUMERIC(18,4);
    v_loc_status location_status_type;
    v_tx_id      UUID;
    v_net        NUMERIC(18,3);
    v_bal_id     UUID;
    v_ver        INT;
BEGIN
    SELECT status INTO v_loc_status FROM locations WHERE location_id = p_location_id;
    IF v_loc_status = 'MAINTENANCE_LOCKED' THEN
        RAISE EXCEPTION 'VI_TRI_BI_KHOA_BAO_TRI: Vị trí (%) đang khóa bảo trì, không thể thực hiện giao dịch (%).', p_location_id, p_tx_type;
    END IF;
    IF v_loc_status = 'COUNTING_LOCKED' AND p_tx_type NOT IN ('LOCK_COUNT', 'CYCLE_COUNT') THEN
        RAISE EXCEPTION 'VI_TRI_DANG_KIEM_KE: Vị trí (%) đang khóa kiểm kê, chặn giao dịch (%).', p_location_id, p_tx_type;
    END IF;

    SELECT unit_cost INTO v_unit_cost FROM skus WHERE sku_id = p_sku_id;

    SELECT balance_id, version_no INTO v_bal_id, v_ver
    FROM inventory_balances
    WHERE warehouse_id = p_warehouse_id AND location_id = p_location_id AND sku_id = p_sku_id
      AND lot_id        IS NOT DISTINCT FROM p_lot_id
      AND pallet_id     IS NOT DISTINCT FROM p_pallet_id
      AND serial_number IS NOT DISTINCT FROM p_serial_number
    FOR UPDATE;

    IF FOUND THEN
        IF p_expected_version IS NOT NULL AND v_ver <> p_expected_version THEN
            RAISE EXCEPTION 'XUNG_DOT_PHIEN_BAN: Tồn kho (%) đã thay đổi (phiên bản % ≠ %).', v_bal_id, v_ver, p_expected_version;
        END IF;
        UPDATE inventory_balances SET
            qty_available = qty_available + p_delta_available,
            qty_allocated = qty_allocated + p_delta_allocated,
            qty_counting  = qty_counting  + p_delta_counting,
            qty_locked    = qty_locked    + p_delta_locked,
            qty_damaged   = qty_damaged   + p_delta_damaged,
            version_no    = version_no + 1,
            updated_at    = NOW()
        WHERE balance_id = v_bal_id;       -- CHECK (>= 0) chặn âm
    ELSE
        IF LEAST(p_delta_available, p_delta_allocated, p_delta_counting, p_delta_locked, p_delta_damaged) < 0 THEN
            RAISE EXCEPTION 'TON_KHO_KHONG_TON_TAI: Không có dòng tồn để trừ (vị trí %, sku %, lô %).', p_location_id, p_sku_id, p_lot_id;
        END IF;
        INSERT INTO inventory_balances (warehouse_id, location_id, sku_id, lot_id, pallet_id, serial_number,
                                        qty_available, qty_allocated, qty_counting, qty_locked, qty_damaged)
        VALUES (p_warehouse_id, p_location_id, p_sku_id, p_lot_id, p_pallet_id, p_serial_number,
                p_delta_available, p_delta_allocated, p_delta_counting, p_delta_locked, p_delta_damaged)
        ON CONFLICT (warehouse_id, location_id, sku_id, lot_id, pallet_id, serial_number)   -- chống race 2 giao dịch cùng tạo
        DO UPDATE SET
            qty_available = inventory_balances.qty_available + EXCLUDED.qty_available,
            qty_allocated = inventory_balances.qty_allocated + EXCLUDED.qty_allocated,
            qty_counting  = inventory_balances.qty_counting  + EXCLUDED.qty_counting,
            qty_locked    = inventory_balances.qty_locked    + EXCLUDED.qty_locked,
            qty_damaged   = inventory_balances.qty_damaged   + EXCLUDED.qty_damaged,
            version_no    = inventory_balances.version_no + 1,
            updated_at    = NOW();
    END IF;

    v_net := p_delta_available + p_delta_allocated + p_delta_counting + p_delta_locked + p_delta_damaged;

    INSERT INTO inventory_transactions (
        warehouse_id, tx_type, sku_id, lot_id, pallet_id, serial_number,
        from_location_id, to_location_id, qty_change,
        qty_delta_available, qty_delta_allocated, qty_delta_counting, qty_delta_locked, qty_delta_damaged,
        unit_cost_snapshot, ref_doc_type, ref_doc_id, performed_by
    ) VALUES (
        p_warehouse_id, p_tx_type, p_sku_id, p_lot_id, p_pallet_id, p_serial_number,
        CASE WHEN v_net < 0 THEN p_location_id ELSE p_counterpart_location_id END,
        CASE WHEN v_net < 0 THEN p_counterpart_location_id ELSE p_location_id END,
        v_net,
        p_delta_available, p_delta_allocated, p_delta_counting, p_delta_locked, p_delta_damaged,
        COALESCE(v_unit_cost, 0), p_ref_doc_type, p_ref_doc_id, p_performed_by
    ) RETURNING tx_id INTO v_tx_id;

    PERFORM fn_refresh_location_status(p_location_id);
    RETURN v_tx_id;
END;
$$ LANGUAGE plpgsql;

-- Chuyển hàng 2 chân (cất hàng, chuyển nội bộ, đưa hàng đã soạn ra khu staging) - atomic trong 1 giao dịch DB
CREATE OR REPLACE FUNCTION fn_transfer_inventory(
    p_warehouse_id UUID, p_from_location_id UUID, p_to_location_id UUID,
    p_sku_id UUID, p_lot_id UUID, p_pallet_id UUID, p_serial_number VARCHAR,
    p_qty NUMERIC, p_tx_type VARCHAR,
    p_ref_doc_type VARCHAR, p_ref_doc_id UUID, p_performed_by UUID,
    p_bucket VARCHAR DEFAULT 'AVAILABLE'   -- AVAILABLE | ALLOCATED | LOCKED | DAMAGED
) RETURNS UUID AS $$
DECLARE
    v_a NUMERIC := 0; v_l NUMERIC := 0; v_k NUMERIC := 0; v_d NUMERIC := 0;
BEGIN
    IF p_qty <= 0 THEN RAISE EXCEPTION 'SO_LUONG_PHAI_DUONG'; END IF;
    IF p_from_location_id = p_to_location_id THEN RAISE EXCEPTION 'VI_TRI_NGUON_TRUNG_DICH'; END IF;
    CASE p_bucket
        WHEN 'AVAILABLE' THEN v_a := p_qty;
        WHEN 'ALLOCATED' THEN v_l := p_qty;
        WHEN 'LOCKED'    THEN v_k := p_qty;
        WHEN 'DAMAGED'   THEN v_d := p_qty;
        ELSE RAISE EXCEPTION 'BUCKET_KHONG_HOP_LE: %', p_bucket;
    END CASE;

    PERFORM fn_apply_inventory_movement(p_warehouse_id, p_from_location_id, p_sku_id, p_lot_id, p_pallet_id, p_serial_number,
        p_tx_type, -v_a, -v_l, 0, -v_k, -v_d, p_ref_doc_type, p_ref_doc_id, p_performed_by, p_to_location_id);
    -- [F3] Mọi bucket giữ nguyên khi chuyển: hàng đã soạn (ALLOCATED) sang khu staging VẪN là ALLOCATED, tiếp tục giữ cho đơn
    RETURN fn_apply_inventory_movement(p_warehouse_id, p_to_location_id, p_sku_id, p_lot_id, p_pallet_id, p_serial_number,
        p_tx_type, v_a, v_l, 0, v_k, v_d, p_ref_doc_type, p_ref_doc_id, p_performed_by, p_from_location_id);
END;
$$ LANGUAGE plpgsql;

-- ---------- B4. Kiểm kê: REJECTED / ADJUSTED, đóng phiếu đúng lúc ----------
DROP TRIGGER IF EXISTS trg_auto_close_cycle_count_sheet ON cycle_count_lines;

ALTER TABLE cycle_count_lines ADD COLUMN IF NOT EXISTS pallet_id UUID REFERENCES pallets(pallet_id);  -- đếm tới mức pallet
-- dữ liệu cũ: 'APPROVED' từng mang nghĩa "đã xong" -> ADJUSTED
-- [F1] CHỈ chạy đúng 1 lần: nếu ràng buộc hiện tại đã có 'ADJUSTED' thì patch đã được áp dụng trước đó,
--      khi ấy 'APPROVED' mang nghĩa mới (đã duyệt, chưa ghi tồn) và KHÔNG được đổi.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conname = 'chk_count_line_status'
                     AND conrelid = 'cycle_count_lines'::regclass
                     AND pg_get_constraintdef(oid) LIKE '%ADJUSTED%') THEN
        UPDATE cycle_count_lines SET status = 'ADJUSTED' WHERE status = 'APPROVED';
    END IF;
END $$;
ALTER TABLE cycle_count_lines DROP CONSTRAINT IF EXISTS chk_count_line_status;
ALTER TABLE cycle_count_lines ADD CONSTRAINT chk_count_line_status CHECK (status IN (
    'PENDING','COUNTED','RECOUNTING','AUTO_APPROVED_Z','PENDING_D1','PENDING_D2','PENDING_D3',
    'APPROVED','ADJUSTED','REJECTED'));

CREATE OR REPLACE FUNCTION fn_auto_close_cycle_count_sheet()
RETURNS TRIGGER AS $$
DECLARE
    v_unfinished INT;
    v_loc        UUID;
BEGIN
    IF NEW.status IN ('AUTO_APPROVED_Z', 'ADJUSTED', 'REJECTED') AND OLD.status IS DISTINCT FROM NEW.status THEN
        SELECT COUNT(*) INTO v_unfinished
        FROM cycle_count_lines
        WHERE count_sheet_id = NEW.count_sheet_id
          AND status NOT IN ('AUTO_APPROVED_Z', 'ADJUSTED', 'REJECTED');

        IF v_unfinished = 0 THEN
            UPDATE cycle_count_sheets
            SET status = 'CLOSED', closed_at = NOW(), version_no = version_no + 1
            WHERE count_sheet_id = NEW.count_sheet_id AND status <> 'CLOSED';

            FOR v_loc IN
                SELECT DISTINCT ccl.location_id
                FROM cycle_count_lines ccl
                JOIN locations l ON l.location_id = ccl.location_id AND l.status = 'COUNTING_LOCKED'
                WHERE ccl.count_sheet_id = NEW.count_sheet_id
                  AND NOT EXISTS (   -- vị trí còn bị phiếu khác giữ khóa thì không mở
                      SELECT 1 FROM cycle_count_lines o
                      WHERE o.location_id = ccl.location_id
                        AND o.count_sheet_id <> NEW.count_sheet_id
                        AND o.status NOT IN ('AUTO_APPROVED_Z', 'ADJUSTED', 'REJECTED'))
            LOOP
                UPDATE locations SET status = 'PARTIAL', lock_reason = NULL, locked_by = NULL, locked_at = NULL
                WHERE location_id = v_loc;
                PERFORM fn_refresh_location_status(v_loc);   -- tính lại EMPTY/PARTIAL/FULL từ tồn thật
            END LOOP;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_auto_close_cycle_count_sheet
AFTER UPDATE OF status ON cycle_count_lines
FOR EACH ROW EXECUTE FUNCTION fn_auto_close_cycle_count_sheet();

-- ---------- B5. Phê duyệt ----------
-- 5a. Cho phép bước hệ thống (không có người) trong lịch sử duyệt
ALTER TABLE approval_histories ALTER COLUMN actor_user_id DROP NOT NULL;
ALTER TABLE approval_histories DROP CONSTRAINT IF EXISTS approval_histories_action_check;
ALTER TABLE approval_histories DROP CONSTRAINT IF EXISTS chk_approval_action;
ALTER TABLE approval_histories ADD CONSTRAINT chk_approval_action CHECK (action IN (
    'APPROVE','REJECT','REQUEST_RECOUNT','ESCALATE_NEXT_TIER','RETURN_FOR_INFO','RESUBMIT_INFO',
    'AUTO_ESCALATE_SLA','AUTO_EXPIRE_SLA','SUPERSEDED_BY_RECOUNT'));
ALTER TABLE approval_histories DROP CONSTRAINT IF EXISTS chk_actor_required;
ALTER TABLE approval_histories ADD CONSTRAINT chk_actor_required CHECK (
    actor_user_id IS NOT NULL OR action IN ('AUTO_ESCALATE_SLA','AUTO_EXPIRE_SLA','SUPERSEDED_BY_RECOUNT'));

-- 5b. Mỗi đối tượng chỉ có 1 request đang mở
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_open_approval_per_object
ON approval_requests (object_type, object_id)
WHERE status IN ('PENDING_D1','PENDING_D2','PENDING_D3','NEED_INFO');

-- 5c. Hàm phân luồng cấp duyệt (1 nguồn sự thật cho sơ đồ 5)
CREATE OR REPLACE FUNCTION fn_resolve_approval_tier(
    p_warehouse_id UUID, p_object_type approval_object_type,
    p_amount NUMERIC, p_percent NUMERIC, p_proposer_id UUID,
    p_force_review BOOLEAN DEFAULT FALSE   -- TRUE: lệch hạn dùng / blind receipt / hàng hư -> không được tự duyệt theo Z
) RETURNS approval_tier_type AS $$
DECLARE
    c       warehouse_configs%ROWTYPE;
    v_role  TEXT;
    v_amt   NUMERIC := ABS(COALESCE(p_amount, 0));
    v_pct   NUMERIC := ABS(COALESCE(p_percent, 0));
    v_in_z  BOOLEAN;
BEGIN
    SELECT * INTO c FROM warehouse_configs WHERE warehouse_id = p_warehouse_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'THIEU_CAU_HINH_KHO: %', p_warehouse_id; END IF;

    IF p_object_type = 'OVERTIME_REQUEST' THEN RETURN 'D2_QUANLY'; END IF;   -- tăng ca vào thẳng D2

    SELECT r.role_code INTO v_role FROM users u JOIN roles r ON r.role_id = u.primary_role_id WHERE u.user_id = p_proposer_id;

    IF NOT p_force_review AND (p_object_type <> 'GRN_DISCREPANCY' OR c.grn_tolerance_apply) THEN
        v_in_z := CASE c.tolerance_z_mode
            WHEN 'AMOUNT_ONLY'  THEN v_amt <= c.tolerance_z_amount
            WHEN 'PERCENT_ONLY' THEN v_pct <= c.tolerance_z_percent
            ELSE (v_amt <= c.tolerance_z_amount AND v_pct <= c.tolerance_z_percent)
        END;
        IF v_in_z THEN RETURN 'AUTO_TOLERANCE_Z'; END IF;
    END IF;

    IF v_role LIKE 'nv-%' AND v_amt <= c.threshold_x_d1_amount THEN RETURN 'D1_THUKHO'; END IF;
    IF v_role IS DISTINCT FROM 'quanly' AND v_role IS DISTINCT FROM 'bgd' AND v_amt <= c.threshold_y_d2_amount THEN
        RETURN 'D2_QUANLY';
    END IF;
    RETURN 'D3_BGD';
END;
$$ LANGUAGE plpgsql STABLE;

-- 5d. Đồng bộ trạng thái đối tượng gốc + xử lý nhánh cuối (REJECTED / EXPIRED)
CREATE OR REPLACE FUNCTION fn_approval_mirror_status()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.status = NEW.status THEN RETURN NEW; END IF;

    IF NEW.object_type = 'GRN_DISCREPANCY' THEN
        IF NEW.status IN ('PENDING_D1','PENDING_D2','PENDING_D3','APPROVED','REJECTED') THEN
            UPDATE grns SET status = NEW.status::TEXT::grn_status_type, approval_expired_at = NULL, version_no = version_no + 1
            WHERE grn_id = NEW.object_id AND status NOT IN ('CLOSED','SYNCED_ERP');
        ELSIF NEW.status = 'EXPIRED' THEN   -- [F4] GRN giữ nguyên trạng thái chờ duyệt, chỉ đánh dấu hết hạn
            UPDATE grns SET approval_expired_at = NOW(), version_no = version_no + 1
            WHERE grn_id = NEW.object_id AND status NOT IN ('CLOSED','SYNCED_ERP');
        END IF;
        IF NEW.status = 'REJECTED' THEN
            UPDATE pallets SET status = 'REJECTED_PENDING_RETURN', version_no = version_no + 1
            WHERE source_grn_id = NEW.object_id AND status IN ('RECEIVING','QUARANTINE_HOLD');
        END IF;

    ELSIF NEW.object_type = 'CYCLE_COUNT_DIFF' THEN
        IF NEW.status IN ('PENDING_D1','PENDING_D2','PENDING_D3','APPROVED','REJECTED') THEN
            UPDATE cycle_count_lines SET status = NEW.status::TEXT, approval_expired_at = NULL
            WHERE count_line_id = NEW.object_id AND status NOT IN ('ADJUSTED','AUTO_APPROVED_Z');
        ELSIF NEW.status = 'EXPIRED' THEN   -- [F4]
            UPDATE cycle_count_lines SET approval_expired_at = NOW()
            WHERE count_line_id = NEW.object_id AND status NOT IN ('ADJUSTED','AUTO_APPROVED_Z');
        END IF;

    ELSIF NEW.object_type IN ('STOCK_ADJUSTMENT','STOCK_SCRAP') THEN
        UPDATE stock_adjustments SET
            status = NEW.status,
            execution_status = CASE
                WHEN NEW.status = 'APPROVED' THEN
                    CASE adjustment_type WHEN 'SCRAP' THEN 'WAITING_SCRAP_EXECUTION' ELSE 'WAITING_EXECUTION' END::post_approval_exec_status
                WHEN NEW.status IN ('REJECTED','EXPIRED','SUPERSEDED') THEN 'NOT_APPLICABLE'::post_approval_exec_status
                ELSE execution_status END,
            version_no = version_no + 1
        WHERE adjustment_id = NEW.object_id;

    ELSIF NEW.object_type = 'OVERTIME_REQUEST' THEN
        UPDATE overtime_requests SET approval_status = NEW.status WHERE ot_id = NEW.object_id;
    END IF;

    IF NEW.status = 'EXPIRED' THEN
        INSERT INTO alerts (warehouse_id, alert_type, severity, target_role_code, ref_object_type, ref_object_id)
        VALUES (NEW.warehouse_id, 'APPROVAL_EXPIRED', 'CRITICAL', 'quanly', 'APPROVAL', NEW.approval_id);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_approval_mirror_status ON approval_requests;
CREATE TRIGGER trg_approval_mirror_status
AFTER INSERT OR UPDATE OF status ON approval_requests
FOR EACH ROW EXECUTE FUNCTION fn_approval_mirror_status();

-- 5e. Quá SLA: D1 -> D2 -> D3 tự leo thang; quá SLA ở D3 mới EXPIRED (gọi bằng pg_cron/worker mỗi vài phút)
CREATE OR REPLACE FUNCTION fn_escalate_expired_approvals()
RETURNS INT AS $$
DECLARE
    r       RECORD;
    v_count INT := 0;
BEGIN
    FOR r IN
        SELECT ar.approval_id, ar.status, ar.current_tier, wc.approval_sla_hours
        FROM approval_requests ar
        JOIN warehouse_configs wc ON wc.warehouse_id = ar.warehouse_id
        WHERE ar.status IN ('PENDING_D1','PENDING_D2','PENDING_D3')
          AND ar.sla_due_at IS NOT NULL AND ar.sla_due_at < NOW()
        FOR UPDATE OF ar SKIP LOCKED
    LOOP
        IF r.status = 'PENDING_D1' THEN
            UPDATE approval_requests SET status = 'PENDING_D2', current_tier = 'D2_QUANLY',
                sla_due_at = NOW() + COALESCE((r.approval_sla_hours->>'D2')::NUMERIC, 8) * INTERVAL '1 hour',
                locked_by_viewer_id = NULL, locked_at = NULL, version_no = version_no + 1
            WHERE approval_id = r.approval_id;
            INSERT INTO approval_histories (approval_id, tier, actor_user_id, action, recommendation_or_reason)
            VALUES (r.approval_id, r.current_tier, NULL, 'AUTO_ESCALATE_SLA', 'Quá SLA D1, tự leo thang lên D2');
        ELSIF r.status = 'PENDING_D2' THEN
            UPDATE approval_requests SET status = 'PENDING_D3', current_tier = 'D3_BGD',
                sla_due_at = NOW() + COALESCE((r.approval_sla_hours->>'D3')::NUMERIC, 24) * INTERVAL '1 hour',
                locked_by_viewer_id = NULL, locked_at = NULL, version_no = version_no + 1
            WHERE approval_id = r.approval_id;
            INSERT INTO approval_histories (approval_id, tier, actor_user_id, action, recommendation_or_reason)
            VALUES (r.approval_id, r.current_tier, NULL, 'AUTO_ESCALATE_SLA', 'Quá SLA D2, tự leo thang lên D3');
        ELSE
            UPDATE approval_requests SET status = 'EXPIRED', version_no = version_no + 1 WHERE approval_id = r.approval_id;
            INSERT INTO approval_histories (approval_id, tier, actor_user_id, action, recommendation_or_reason)
            VALUES (r.approval_id, r.current_tier, NULL, 'AUTO_EXPIRE_SLA', 'Quá SLA D3, hết hạn - cần xử lý thủ công');
        END IF;
        v_count := v_count + 1;
    END LOOP;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- 5f. Bắt buộc xác thực lại khi duyệt hồ sơ giá trị lớn ([Q#10])
CREATE OR REPLACE FUNCTION fn_enforce_reauth()
RETURNS TRIGGER AS $$
DECLARE
    v_amount NUMERIC; v_min NUMERIC;
BEGIN
    IF NEW.action = 'APPROVE' AND NEW.actor_user_id IS NOT NULL THEN
        SELECT ar.discrepancy_value_amount, wc.reauth_min_amount INTO v_amount, v_min
        FROM approval_requests ar JOIN warehouse_configs wc ON wc.warehouse_id = ar.warehouse_id
        WHERE ar.approval_id = NEW.approval_id;
        IF v_amount >= v_min AND NEW.reauth_method IS NULL THEN
            RAISE EXCEPTION 'THIEU_XAC_THUC_LAI: Hồ sơ giá trị % >= % cần xác thực sinh trắc học/mật khẩu.', v_amount, v_min;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_enforce_reauth ON approval_histories;
CREATE TRIGGER trg_enforce_reauth BEFORE INSERT ON approval_histories
FOR EACH ROW EXECUTE FUNCTION fn_enforce_reauth();

-- ---------- B6. Trigger PO (sửa) ----------
CREATE OR REPLACE FUNCTION fn_sync_po_on_grn_approved()
RETURNS TRIGGER AS $$
DECLARE
    v_tol   NUMERIC;
    v_open  INT;
    v_total NUMERIC;
BEGIN
    IF NEW.status = 'APPROVED' AND OLD.status IS DISTINCT FROM 'APPROVED' AND NEW.po_id IS NOT NULL THEN
        UPDATE po_lines pl
        SET qty_received = pl.qty_received + agg.recv, version_no = pl.version_no + 1
        FROM (SELECT po_line_id, SUM(GREATEST(0, qty_actual - qty_damaged)) AS recv
              FROM grn_lines WHERE grn_id = NEW.grn_id AND po_line_id IS NOT NULL
              GROUP BY po_line_id) agg                     -- gộp nhiều grn_line cùng po_line
        WHERE agg.po_line_id = pl.po_line_id;

        SELECT over_receipt_tolerance_pct INTO v_tol FROM warehouse_configs WHERE warehouse_id = NEW.warehouse_id;
        IF EXISTS (SELECT 1 FROM po_lines WHERE po_id = NEW.po_id
                   AND qty_received > qty_ordered * (1 + COALESCE(v_tol, 0) / 100)) THEN
            RAISE EXCEPTION 'NHAN_DU_VUOT_DUNG_SAI: GRN % làm số nhận vượt PO % (dung sai % %%).', NEW.grn_id, NEW.po_id, COALESCE(v_tol, 0);
        END IF;

        SELECT COUNT(*) FILTER (WHERE qty_received < qty_ordered), COALESCE(SUM(qty_received), 0)
        INTO v_open, v_total FROM po_lines WHERE po_id = NEW.po_id;      -- so sánh TỪNG dòng, không so tổng

        UPDATE purchase_orders SET
            status = CASE WHEN v_open = 0 THEN 'FULLY_RECEIVED'::po_status_type
                          WHEN v_total > 0 THEN 'PARTIAL_RECEIVED'::po_status_type
                          ELSE status END,
            version_no = version_no + 1
        WHERE po_id = NEW.po_id AND status NOT IN ('CLOSED', 'CANCELLED');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ---------- B7. Bảng mới ----------
-- 7a. Ghi rõ từng dòng đơn đã giữ hàng ở balance nào (để nhả khi hủy/soạn lệch)
CREATE TABLE IF NOT EXISTS inventory_allocations (
    allocation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_line_id UUID NOT NULL REFERENCES outbound_order_lines(order_line_id) ON DELETE CASCADE,
    balance_id    UUID NOT NULL REFERENCES inventory_balances(balance_id),
    lot_id        UUID REFERENCES lots(lot_id),
    qty_allocated NUMERIC(18,3) NOT NULL CHECK (qty_allocated > 0),
    qty_picked    NUMERIC(18,3) NOT NULL DEFAULT 0 CHECK (qty_picked >= 0),
    status        VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','PICKED','RELEASED')),
    version_no    INT NOT NULL DEFAULT 1,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_alloc_picked_le_allocated CHECK (qty_picked <= qty_allocated),
    UNIQUE (order_line_id, balance_id)
);
CREATE INDEX IF NOT EXISTS idx_alloc_balance ON inventory_allocations (balance_id) WHERE status = 'ACTIVE';

ALTER TABLE pick_lines
    ADD COLUMN IF NOT EXISTS allocation_id UUID REFERENCES inventory_allocations(allocation_id),
    ADD COLUMN IF NOT EXISTS staged_location_id UUID REFERENCES locations(location_id);   -- nơi hàng nằm sau PICK (khu STAGING/PACKING)

-- 7b. Nội dung từng kiện hàng
CREATE TABLE IF NOT EXISTS package_lines (
    package_line_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    package_id      UUID NOT NULL REFERENCES packages(package_id) ON DELETE CASCADE,
    order_line_id   UUID NOT NULL REFERENCES outbound_order_lines(order_line_id),
    sku_id          UUID NOT NULL REFERENCES skus(sku_id),
    lot_id          UUID REFERENCES lots(lot_id),
    qty             NUMERIC(18,3) NOT NULL CHECK (qty > 0),
    serial_numbers  TEXT[]
);
CREATE INDEX IF NOT EXISTS idx_package_lines_pkg ON package_lines (package_id);
CREATE INDEX IF NOT EXISTS idx_package_lines_lot ON package_lines (sku_id, lot_id);   -- truy vết thu hồi theo lô

CREATE OR REPLACE FUNCTION fn_sync_qty_packed()
RETURNS TRIGGER AS $$
DECLARE v_line UUID;
BEGIN
    IF TG_OP IN ('UPDATE','DELETE') THEN
        UPDATE outbound_order_lines SET qty_packed = COALESCE((SELECT SUM(qty) FROM package_lines WHERE order_line_id = OLD.order_line_id), 0)
        WHERE order_line_id = OLD.order_line_id;
    END IF;
    IF TG_OP IN ('INSERT','UPDATE') THEN
        UPDATE outbound_order_lines SET qty_packed = COALESCE((SELECT SUM(qty) FROM package_lines WHERE order_line_id = NEW.order_line_id), 0)
        WHERE order_line_id = NEW.order_line_id;
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sync_qty_packed ON package_lines;
CREATE TRIGGER trg_sync_qty_packed AFTER INSERT OR UPDATE OR DELETE ON package_lines
FOR EACH ROW EXECUTE FUNCTION fn_sync_qty_packed();

-- 7c. Dòng hàng trả (RMA)
CREATE TABLE IF NOT EXISTS return_order_lines (
    return_line_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    return_id      UUID NOT NULL REFERENCES return_orders_complaints(return_id) ON DELETE CASCADE,
    sku_id         UUID NOT NULL REFERENCES skus(sku_id),
    lot_id         UUID REFERENCES lots(lot_id),
    uom_code       VARCHAR(30) NOT NULL,
    qty_expected   NUMERIC(18,3) NOT NULL DEFAULT 0 CHECK (qty_expected >= 0),
    qty_received   NUMERIC(18,3) NOT NULL DEFAULT 0 CHECK (qty_received >= 0),
    qty_good       NUMERIC(18,3) NOT NULL DEFAULT 0 CHECK (qty_good >= 0),      -- RESTOCK
    qty_damaged    NUMERIC(18,3) NOT NULL DEFAULT 0 CHECK (qty_damaged >= 0),   -- DAMAGED_ZONE
    serial_numbers TEXT[],
    reason_code    VARCHAR(50) REFERENCES reason_codes(reason_code),
    CONSTRAINT chk_return_split CHECK (qty_good + qty_damaged <= qty_received)
);
CREATE INDEX IF NOT EXISTS idx_return_lines_return ON return_order_lines (return_id);

-- 7d. Lịch sử đếm lại của GRN (NH-5), tương tự cycle_count_attempts
CREATE TABLE IF NOT EXISTS grn_count_attempts (
    attempt_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    grn_line_id       UUID NOT NULL REFERENCES grn_lines(grn_line_id) ON DELETE CASCADE,
    attempt_no        INT NOT NULL CHECK (attempt_no >= 1),
    counter_user_id   UUID NOT NULL REFERENCES users(user_id),
    blind_counted_qty NUMERIC(18,3) NOT NULL,
    counted_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (grn_line_id, attempt_no)
);

-- ---------- B8. Liên kết giữa các luồng ----------
ALTER TABLE outbound_orders ADD COLUMN IF NOT EXISTS source_grn_id UUID REFERENCES grns(grn_id);       -- xuất trả NCC từ GRN bị REJECTED
ALTER TABLE asns ADD COLUMN IF NOT EXISTS source_outbound_order_id UUID REFERENCES outbound_orders(order_id); -- ASN kho nhận cho chuyển kho

ALTER TABLE outbound_orders DROP CONSTRAINT IF EXISTS outbound_orders_order_type_check;
ALTER TABLE outbound_orders DROP CONSTRAINT IF EXISTS chk_order_type;
ALTER TABLE outbound_orders ADD CONSTRAINT chk_order_type CHECK (
    order_type IN ('SO','INTER_WH_TRANSFER','SUPPLIER_RETURN','CUSTOMER_RETURN_BACK'));
ALTER TABLE outbound_orders DROP CONSTRAINT IF EXISTS chk_order_type_parties;
ALTER TABLE outbound_orders ADD CONSTRAINT chk_order_type_parties CHECK (
       (order_type = 'SO'                   AND customer_id IS NOT NULL)
    OR (order_type = 'CUSTOMER_RETURN_BACK' AND customer_id IS NOT NULL)
    OR (order_type = 'INTER_WH_TRANSFER'    AND dest_warehouse_id IS NOT NULL)
    OR (order_type = 'SUPPLIER_RETURN'      AND supplier_id IS NOT NULL)) NOT VALID;

CREATE OR REPLACE FUNCTION fn_check_gi_type_matches_order()
RETURNS TRIGGER AS $$
DECLARE v_order_type TEXT;
BEGIN
    SELECT order_type INTO v_order_type FROM outbound_orders WHERE order_id = NEW.order_id;
    IF v_order_type IS DISTINCT FROM (CASE NEW.gi_type::TEXT WHEN 'SO_SHIPMENT' THEN 'SO' ELSE NEW.gi_type::TEXT END) THEN
        RAISE EXCEPTION 'GI_SAI_LOAI: gi_type % không khớp order_type % của đơn %.', NEW.gi_type, v_order_type, NEW.order_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_check_gi_type ON goods_issues;
CREATE TRIGGER trg_check_gi_type BEFORE INSERT OR UPDATE OF gi_type, order_id ON goods_issues
FOR EACH ROW EXECUTE FUNCTION fn_check_gi_type_matches_order();

-- ---------- B9. FK thiếu & ràng buộc nhỏ ----------
ALTER TABLE pallets        DROP CONSTRAINT IF EXISTS fk_pallets_source_grn;
ALTER TABLE pallets        ADD CONSTRAINT fk_pallets_source_grn FOREIGN KEY (source_grn_id) REFERENCES grns(grn_id);
ALTER TABLE grns           DROP CONSTRAINT IF EXISTS fk_grns_shift;
ALTER TABLE grns           ADD CONSTRAINT fk_grns_shift FOREIGN KEY (shift_id) REFERENCES shifts(shift_id);
ALTER TABLE pick_sessions  DROP CONSTRAINT IF EXISTS fk_pick_sessions_shift;
ALTER TABLE pick_sessions  ADD CONSTRAINT fk_pick_sessions_shift FOREIGN KEY (shift_id) REFERENCES shifts(shift_id);

-- GI_CONFIRMED bắt buộc có confirmed_at (CHECK cũ lọt khi confirmed_at NULL)
ALTER TABLE goods_issues DROP CONSTRAINT IF EXISTS chk_driver_sig_before_gi;
ALTER TABLE goods_issues ADD CONSTRAINT chk_driver_sig_before_gi CHECK (
    status <> 'GI_CONFIRMED'
    OR (confirmed_at IS NOT NULL
        AND (gi_type = 'SUPPLIER_RETURN'
             OR (driver_signature_data IS NOT NULL AND driver_signed_at <= confirmed_at))));

-- Giao thất bại từ TMS có thể chưa có số RMA của ERP
ALTER TABLE return_orders_complaints ALTER COLUMN erp_rma_number DROP NOT NULL;
ALTER TABLE return_orders_complaints DROP CONSTRAINT IF EXISTS chk_rma_number_required;
ALTER TABLE return_orders_complaints ADD CONSTRAINT chk_rma_number_required CHECK (
    record_type = 'FAILED_DELIVERY' OR erp_rma_number IS NOT NULL);

-- Lỗi trigger cũ: nhánh DELETE truy cập NEW (không tồn tại)
CREATE OR REPLACE FUNCTION fn_sync_gi_package_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        IF NEW.gi_id IS NOT NULL THEN
            UPDATE goods_issues SET total_packages = (SELECT COUNT(*) FROM packages WHERE gi_id = NEW.gi_id)
            WHERE gi_id = NEW.gi_id;
        END IF;
    END IF;
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        IF OLD.gi_id IS NOT NULL THEN
            IF TG_OP = 'DELETE' THEN
                UPDATE goods_issues SET total_packages = (SELECT COUNT(*) FROM packages WHERE gi_id = OLD.gi_id)
                WHERE gi_id = OLD.gi_id;
            ELSIF OLD.gi_id IS DISTINCT FROM NEW.gi_id THEN
                UPDATE goods_issues SET total_packages = (SELECT COUNT(*) FROM packages WHERE gi_id = OLD.gi_id)
                WHERE gi_id = OLD.gi_id;
            END IF;
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ---------- B10. Đóng băng đơn khi ERP đổi/hủy đang chờ Quản lý chốt (P9) ----------
-- Quy ước: ERP chỉ bật erp_change_pending. Trong lúc cờ bật, đơn đứng yên tại bước hiện tại.
--   * "Giữ đơn": UPDATE outbound_orders SET erp_change_pending = FALSE  (đơn đi tiếp từ đúng trạng thái đang có)
--   * "Hủy":     UPDATE outbound_orders SET status = 'CANCELLED', erp_change_pending = FALSE  (cùng 1 câu lệnh)
-- Khi cờ bật, các hành động đẩy đơn tiến lên bị chặn: đổi trạng thái đơn, soạn thêm hàng, tạo thùng,
-- lên xe, lập/xác nhận GI. Hủy thùng/GI (CANCELLED) và nhả hàng vẫn được phép để Quản lý xử lý nhánh hủy.
CREATE OR REPLACE FUNCTION fn_order_is_frozen(p_order_id UUID)
RETURNS BOOLEAN AS $$
    SELECT COALESCE((SELECT erp_change_pending FROM outbound_orders WHERE order_id = p_order_id), FALSE);
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION fn_freeze_order_status()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.erp_change_pending AND NEW.erp_change_pending AND NEW.status IS DISTINCT FROM OLD.status THEN
        RAISE EXCEPTION 'DON_BI_DONG_BANG: Đơn % có yêu cầu đổi/hủy từ ERP đang chờ Quản lý chốt, không được đổi trạng thái (% -> %).',
            OLD.erp_order_number, OLD.status, NEW.status;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_freeze_order_status ON outbound_orders;
CREATE TRIGGER trg_freeze_order_status BEFORE UPDATE OF status ON outbound_orders
FOR EACH ROW EXECUTE FUNCTION fn_freeze_order_status();

CREATE OR REPLACE FUNCTION fn_freeze_gi()
RETURNS TRIGGER AS $$
BEGIN
    IF fn_order_is_frozen(NEW.order_id)
       AND NEW.status <> 'CANCELLED'
       AND (TG_OP = 'INSERT' OR NEW.status IS DISTINCT FROM OLD.status) THEN
        RAISE EXCEPTION 'DON_BI_DONG_BANG: Đơn % đang chờ Quản lý chốt thay đổi từ ERP, không được lập/xác nhận GI.', NEW.order_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_freeze_gi ON goods_issues;
CREATE TRIGGER trg_freeze_gi BEFORE INSERT OR UPDATE OF status ON goods_issues
FOR EACH ROW EXECUTE FUNCTION fn_freeze_gi();

CREATE OR REPLACE FUNCTION fn_freeze_packages()
RETURNS TRIGGER AS $$
BEGIN
    IF fn_order_is_frozen(NEW.order_id)
       AND (TG_OP = 'INSERT' OR (NEW.is_loaded_on_truck AND NOT OLD.is_loaded_on_truck)) THEN
        RAISE EXCEPTION 'DON_BI_DONG_BANG: Đơn % đang chờ Quản lý chốt thay đổi từ ERP, không được tạo thùng hoặc quét lên xe.', NEW.order_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_freeze_packages ON packages;
CREATE TRIGGER trg_freeze_packages BEFORE INSERT OR UPDATE OF is_loaded_on_truck ON packages
FOR EACH ROW EXECUTE FUNCTION fn_freeze_packages();

CREATE OR REPLACE FUNCTION fn_freeze_pick_lines()
RETURNS TRIGGER AS $$
DECLARE v_order UUID;
BEGIN
    IF NEW.qty_picked > OLD.qty_picked THEN
        SELECT order_id INTO v_order FROM outbound_order_lines WHERE order_line_id = NEW.order_line_id;
        IF fn_order_is_frozen(v_order) THEN
            RAISE EXCEPTION 'DON_BI_DONG_BANG: Đơn % đang chờ Quản lý chốt thay đổi từ ERP, không được soạn thêm hàng.', v_order;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_freeze_pick_lines ON pick_lines;
CREATE TRIGGER trg_freeze_pick_lines BEFORE UPDATE OF qty_picked ON pick_lines
FOR EACH ROW EXECUTE FUNCTION fn_freeze_pick_lines();

-- Cảnh báo Quản lý ngay khi ERP bật cờ; nếu đơn đã rời kho thì đóng băng không còn tác dụng -> cảnh báo mức CRITICAL
CREATE OR REPLACE FUNCTION fn_alert_erp_change()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.erp_change_pending AND (TG_OP = 'INSERT' OR NOT OLD.erp_change_pending) THEN
        IF NEW.status IN ('SHIPPED','IN_TRANSIT','DELIVERED','PARTIAL_DELIVERED','DELIVERY_FAILED') THEN
            INSERT INTO alerts (warehouse_id, alert_type, severity, target_role_code, ref_object_type, ref_object_id)
            VALUES (NEW.warehouse_id, 'ERP_CHANGE_AFTER_SHIPPED', 'CRITICAL', 'quanly', 'OUTBOUND_ORDER', NEW.order_id);
        ELSE
            INSERT INTO alerts (warehouse_id, alert_type, severity, target_role_code, ref_object_type, ref_object_id)
            VALUES (NEW.warehouse_id, 'ERP_CHANGE_PENDING', 'WARNING', 'quanly', 'OUTBOUND_ORDER', NEW.order_id);
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_alert_erp_change ON outbound_orders;
CREATE TRIGGER trg_alert_erp_change AFTER INSERT OR UPDATE OF erp_change_pending ON outbound_orders
FOR EACH ROW EXECUTE FUNCTION fn_alert_erp_change();

-- ---------- B11. Yêu cầu đổi/hủy từ ERP: quy tắc theo giai đoạn đơn + phản hồi ERP (P10) ----------
INSERT INTO reason_codes (reason_code, reason_category, description) VALUES
    ('CHG_ALREADY_LOADED',    'ORDER_CANCEL', 'Từ chối hủy: hàng đã lên xe'),
    ('CHG_ALREADY_SHIPPED',   'ORDER_CANCEL', 'Từ chối hủy: đơn đã xuất kho (SHIPPED trở đi)'),
    ('CHG_ALREADY_CANCELLED', 'ORDER_CANCEL', 'Từ chối: đơn đã hủy trước đó'),
    ('CHG_OUT_OF_SCOPE',      'ORDER_CANCEL', 'Từ chối: kho chưa hỗ trợ loại thay đổi này (chỉ hỗ trợ hủy đơn)'),
    ('CHG_MANAGER_REJECT',    'ORDER_CANCEL', 'Quản lý kho từ chối yêu cầu hủy (kèm ghi chú)')
ON CONFLICT (reason_code) DO NOTHING;

CREATE TABLE IF NOT EXISTS order_change_requests (
    request_id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id                UUID NOT NULL REFERENCES outbound_orders(order_id),
    warehouse_id            UUID NOT NULL REFERENCES warehouses(warehouse_id),
    change_type             VARCHAR(20) NOT NULL CHECK (change_type IN ('CANCEL_ORDER','CHANGE_QTY','CHANGE_ADDRESS')),
    change_payload          JSONB,
    order_status_at_receipt order_status_type NOT NULL,         -- đơn đang ở đâu lúc nhận yêu cầu
    decision_path           VARCHAR(20) NOT NULL CHECK (decision_path IN ('AUTO_ACCEPT','MANAGER','AUTO_REJECT')),
    status                  VARCHAR(20) NOT NULL CHECK (status IN ('PENDING_MANAGER','ACCEPTED','REJECTED')),
    decided_by              UUID REFERENCES users(user_id),     -- NULL nếu hệ thống tự quyết
    decided_at              TIMESTAMPTZ,
    reject_reason_code      VARCHAR(50) REFERENCES reason_codes(reason_code),
    reject_note             TEXT,
    erp_notify_status       VARCHAR(10) NOT NULL DEFAULT 'NOT_YET' CHECK (erp_notify_status IN ('NOT_YET','PENDING','SENT','FAILED')),
    erp_notified_at         TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_chg_pending_path   CHECK (status <> 'PENDING_MANAGER' OR decision_path = 'MANAGER'),
    CONSTRAINT chk_chg_decided_at     CHECK (status = 'PENDING_MANAGER' OR decided_at IS NOT NULL),
    CONSTRAINT chk_chg_reject_reason  CHECK (status <> 'REJECTED' OR reject_reason_code IS NOT NULL),
    CONSTRAINT chk_chg_manager_actor  CHECK (decision_path <> 'MANAGER' OR status = 'PENDING_MANAGER' OR decided_by IS NOT NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_pending_change_per_order
    ON order_change_requests (order_id) WHERE status = 'PENDING_MANAGER';
CREATE INDEX IF NOT EXISTS idx_change_requests_order ON order_change_requests (order_id, created_at DESC);

-- Xếp hàng gửi phản hồi về ERP (worker tích hợp đọc integration_sync_logs status = PENDING)
CREATE OR REPLACE FUNCTION fn_enqueue_erp_change_reply(p_request_id UUID)
RETURNS VOID AS $$
DECLARE r order_change_requests%ROWTYPE; v_erp_no VARCHAR;
BEGIN
    SELECT * INTO r FROM order_change_requests WHERE request_id = p_request_id;
    SELECT erp_order_number INTO v_erp_no FROM outbound_orders WHERE order_id = r.order_id;
    INSERT INTO integration_sync_logs (warehouse_id, external_system, direction, doc_type, doc_id, business_payload, status)
    VALUES (r.warehouse_id, 'ERP', 'OUTBOUND', 'SO', r.order_id,
            jsonb_build_object('erp_order_number', v_erp_no, 'request_id', r.request_id, 'change_type', r.change_type,
                               'result', r.status, 'reason_code', r.reject_reason_code, 'note', r.reject_note),
            'PENDING');
    UPDATE order_change_requests SET erp_notify_status = 'PENDING' WHERE request_id = p_request_id;
END;
$$ LANGUAGE plpgsql;

-- Nhả phần hàng đã giữ nhưng chưa soạn (tx DEALLOCATE: allocated -> available); phần đã soạn để task trả hàng xử lý
CREATE OR REPLACE FUNCTION fn_release_order_allocations(p_order_id UUID, p_actor UUID)
RETURNS INT AS $$
DECLARE a RECORD; v_rem NUMERIC; v_n INT := 0;
BEGIN
    FOR a IN
        SELECT ia.allocation_id, ia.qty_allocated, ia.qty_picked, b.warehouse_id, b.location_id, b.sku_id, b.lot_id, b.pallet_id, b.serial_number
        FROM inventory_allocations ia
        JOIN inventory_balances b ON b.balance_id = ia.balance_id
        JOIN outbound_order_lines l ON l.order_line_id = ia.order_line_id
        WHERE l.order_id = p_order_id AND ia.status = 'ACTIVE'
    LOOP
        v_rem := a.qty_allocated - a.qty_picked;
        IF v_rem > 0 THEN
            PERFORM fn_apply_inventory_movement(a.warehouse_id, a.location_id, a.sku_id, a.lot_id, a.pallet_id, a.serial_number,
                'DEALLOCATE', v_rem, -v_rem, 0, 0, 0, 'SO', p_order_id, p_actor);
        END IF;
        IF a.qty_picked = 0 THEN
            UPDATE inventory_allocations SET status = 'RELEASED', updated_at = NOW(), version_no = version_no + 1
            WHERE allocation_id = a.allocation_id;
        ELSE
            UPDATE inventory_allocations SET qty_allocated = qty_picked, status = 'PICKED', updated_at = NOW(), version_no = version_no + 1
            WHERE allocation_id = a.allocation_id;
        END IF;
        v_n := v_n + 1;
    END LOOP;
    UPDATE outbound_order_lines SET qty_allocated = qty_picked WHERE order_id = p_order_id;
    RETURN v_n;
END;
$$ LANGUAGE plpgsql;

-- (1) ERP gửi yêu cầu -> kho phân luồng theo giai đoạn của đơn. p_actor = tài khoản dịch vụ tích hợp.
CREATE OR REPLACE FUNCTION fn_receive_erp_order_change(
    p_order_id UUID, p_change_type VARCHAR, p_payload JSONB, p_actor UUID
) RETURNS UUID AS $$
DECLARE
    o        outbound_orders%ROWTYPE;
    v_id     UUID;
    v_reason VARCHAR(50);
    v_loaded BOOLEAN;
BEGIN
    SELECT * INTO o FROM outbound_orders WHERE order_id = p_order_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'DON_KHONG_TON_TAI: %', p_order_id; END IF;
    IF EXISTS (SELECT 1 FROM order_change_requests WHERE order_id = p_order_id AND status = 'PENDING_MANAGER') THEN
        RAISE EXCEPTION 'DA_CO_YEU_CAU_DANG_CHO: Đơn % đã có yêu cầu đổi/hủy đang chờ Quản lý.', o.erp_order_number;
    END IF;

    v_loaded := EXISTS (SELECT 1 FROM packages WHERE order_id = p_order_id AND is_loaded_on_truck)
             OR EXISTS (SELECT 1 FROM goods_issues WHERE order_id = p_order_id AND status IN ('LOADED','GI_CONFIRMED'));

    v_reason := CASE
        WHEN o.status = 'CANCELLED' THEN 'CHG_ALREADY_CANCELLED'
        WHEN o.status IN ('SHIPPED','IN_TRANSIT','DELIVERED','PARTIAL_DELIVERED','DELIVERY_FAILED') THEN 'CHG_ALREADY_SHIPPED'
        WHEN p_change_type <> 'CANCEL_ORDER' THEN 'CHG_OUT_OF_SCOPE'
        WHEN o.status NOT IN ('NEW','ON_HOLD') AND v_loaded THEN 'CHG_ALREADY_LOADED'
    END;

    -- Nhánh 3: tự từ chối
    IF v_reason IS NOT NULL THEN
        INSERT INTO order_change_requests (order_id, warehouse_id, change_type, change_payload, order_status_at_receipt,
                                           decision_path, status, decided_at, reject_reason_code)
        VALUES (p_order_id, o.warehouse_id, p_change_type, p_payload, o.status, 'AUTO_REJECT', 'REJECTED', NOW(), v_reason)
        RETURNING request_id INTO v_id;
        IF v_reason = 'CHG_ALREADY_SHIPPED' THEN
            INSERT INTO alerts (warehouse_id, alert_type, severity, target_role_code, ref_object_type, ref_object_id)
            VALUES (o.warehouse_id, 'ERP_CHANGE_AFTER_SHIPPED', 'CRITICAL', 'quanly', 'OUTBOUND_ORDER', p_order_id);
        END IF;
        PERFORM fn_enqueue_erp_change_reply(v_id);
        RETURN v_id;
    END IF;

    -- Nhánh 1: chưa soạn -> tự chấp nhận hủy
    IF o.status IN ('NEW','ON_HOLD') THEN
        INSERT INTO order_change_requests (order_id, warehouse_id, change_type, change_payload, order_status_at_receipt,
                                           decision_path, status, decided_at)
        VALUES (p_order_id, o.warehouse_id, p_change_type, p_payload, o.status, 'AUTO_ACCEPT', 'ACCEPTED', NOW())
        RETURNING request_id INTO v_id;
        PERFORM fn_release_order_allocations(p_order_id, p_actor);
        UPDATE pick_sessions ps SET status = 'CANCELLED'          -- phiên chờ hàng (ON_HOLD_SHORTAGE) chỉ chứa đơn này
        WHERE ps.status IN ('OPEN','ON_HOLD_SHORTAGE')
          AND EXISTS (SELECT 1 FROM pick_lines pl JOIN outbound_order_lines l ON l.order_line_id = pl.order_line_id
                      WHERE pl.pick_session_id = ps.pick_session_id AND l.order_id = p_order_id)
          AND NOT EXISTS (SELECT 1 FROM pick_lines pl JOIN outbound_order_lines l ON l.order_line_id = pl.order_line_id
                          WHERE pl.pick_session_id = ps.pick_session_id AND l.order_id <> p_order_id);
        UPDATE outbound_orders SET status = 'CANCELLED', erp_change_pending = FALSE, erp_change_payload = NULL,
               version_no = version_no + 1, updated_at = NOW()
        WHERE order_id = p_order_id;
        PERFORM fn_enqueue_erp_change_reply(v_id);
        RETURN v_id;
    END IF;

    -- Nhánh 2: đang soạn / đóng gói / chờ xe -> đóng băng đơn, chờ Quản lý quyết
    INSERT INTO order_change_requests (order_id, warehouse_id, change_type, change_payload, order_status_at_receipt,
                                       decision_path, status)
    VALUES (p_order_id, o.warehouse_id, p_change_type, p_payload, o.status, 'MANAGER', 'PENDING_MANAGER')
    RETURNING request_id INTO v_id;
    UPDATE outbound_orders SET erp_change_pending = TRUE, erp_change_payload = p_payload, updated_at = NOW()
    WHERE order_id = p_order_id;                                   -- trigger fn_alert_erp_change báo Quản lý; đơn bị đóng băng
    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

-- (2) Quản lý quyết định cho các yêu cầu ở nhánh 2. ACCEPT = hủy; REJECT = giữ đơn (bắt buộc ghi lý do)
CREATE OR REPLACE FUNCTION fn_decide_order_change(
    p_request_id UUID, p_decision VARCHAR, p_manager_id UUID, p_note TEXT DEFAULT NULL
) RETURNS VOID AS $$
DECLARE
    r        order_change_requests%ROWTYPE;
    o        outbound_orders%ROWTYPE;
    v_role   TEXT;
    v_loaded BOOLEAN;
BEGIN
    SELECT ro.role_code INTO v_role FROM users u JOIN roles ro ON ro.role_id = u.primary_role_id WHERE u.user_id = p_manager_id;
    IF v_role IS NULL OR v_role NOT IN ('quanly','bgd') THEN
        RAISE EXCEPTION 'KHONG_DU_QUYEN: Chỉ Quản lý kho hoặc Ban giám đốc được chốt yêu cầu đổi/hủy từ ERP.';
    END IF;
    SELECT * INTO r FROM order_change_requests WHERE request_id = p_request_id FOR UPDATE;
    IF NOT FOUND OR r.status <> 'PENDING_MANAGER' THEN RAISE EXCEPTION 'YEU_CAU_KHONG_O_TRANG_THAI_CHO: %', p_request_id; END IF;
    SELECT * INTO o FROM outbound_orders WHERE order_id = r.order_id FOR UPDATE;

    IF p_decision = 'REJECT' THEN
        IF p_note IS NULL OR btrim(p_note) = '' THEN RAISE EXCEPTION 'THIEU_LY_DO: Từ chối yêu cầu của ERP bắt buộc ghi lý do.'; END IF;
        UPDATE order_change_requests SET status = 'REJECTED', decided_by = p_manager_id, decided_at = NOW(),
               reject_reason_code = 'CHG_MANAGER_REJECT', reject_note = p_note WHERE request_id = p_request_id;
        UPDATE outbound_orders SET erp_change_pending = FALSE, erp_change_payload = NULL, updated_at = NOW()
        WHERE order_id = r.order_id;                               -- mở băng, đơn đi tiếp từ trạng thái đang có

    ELSIF p_decision = 'ACCEPT' THEN
        v_loaded := EXISTS (SELECT 1 FROM packages WHERE order_id = r.order_id AND is_loaded_on_truck)
                 OR EXISTS (SELECT 1 FROM goods_issues WHERE order_id = r.order_id AND status IN ('LOADED','GI_CONFIRMED'));
        IF v_loaded THEN RAISE EXCEPTION 'DON_DA_LEN_XE: Không thể chấp nhận hủy, hàng đã lên xe.'; END IF;

        PERFORM fn_release_order_allocations(r.order_id, p_manager_id);
        UPDATE goods_issues SET status = 'CANCELLED' WHERE order_id = r.order_id AND status NOT IN ('GI_CONFIRMED','CANCELLED');
        IF EXISTS (SELECT 1 FROM pick_lines pl JOIN outbound_order_lines l ON l.order_line_id = pl.order_line_id
                   WHERE l.order_id = r.order_id AND pl.qty_picked > 0)
           OR EXISTS (SELECT 1 FROM packages WHERE order_id = r.order_id) THEN
            INSERT INTO tasks (warehouse_id, task_type, stage, ref_doc_type, ref_doc_id, priority, assigned_by)
            VALUES (r.warehouse_id, 'RETURN_PICKING', 'SOAN_HANG', 'SO', r.order_id, 'HIGH', p_manager_id);  -- đưa hàng đã soạn/đóng thùng về kệ
        END IF;
        UPDATE outbound_orders SET status = 'CANCELLED', erp_change_pending = FALSE, erp_change_payload = NULL,
               version_no = version_no + 1, updated_at = NOW() WHERE order_id = r.order_id;
        UPDATE order_change_requests SET status = 'ACCEPTED', decided_by = p_manager_id, decided_at = NOW(), reject_note = p_note
        WHERE request_id = p_request_id;
    ELSE
        RAISE EXCEPTION 'QUYET_DINH_KHONG_HOP_LE: % (chỉ ACCEPT hoặc REJECT)', p_decision;
    END IF;

    PERFORM fn_enqueue_erp_change_reply(p_request_id);
END;
$$ LANGUAGE plpgsql;

COMMIT;
