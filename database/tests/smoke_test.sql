-- =============================================================================
-- SMOKE TEST: schema v4.1 + patch v4.2.1  (chạy trên DB TRỐNG, sau khi nạp 2 file trên)
--   psql -d <db> -v ON_ERROR_STOP=1 -f wms_smoke_test_v4_2_1.sql
-- Mỗi bước dùng RAISE EXCEPTION nếu sai; chạy hết file không lỗi = PASS toàn bộ.
-- =============================================================================
CREATE OR REPLACE FUNCTION pg_temp.u(n INT) RETURNS UUID LANGUAGE sql IMMUTABLE AS
$$ SELECT ('00000000-0000-0000-0000-' || lpad(n::TEXT, 12, '0'))::UUID $$;

CREATE OR REPLACE FUNCTION pg_temp.expect_error(p_sql TEXT, p_like TEXT) RETURNS VOID AS $$
BEGIN
    BEGIN
        EXECUTE p_sql;
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM LIKE p_like THEN RETURN; END IF;
        RAISE EXCEPTION 'FAIL: lỗi khác mong đợi (% ): %', p_like, SQLERRM;
    END;
    RAISE EXCEPTION 'FAIL: đáng lẽ phải lỗi (%): %', p_like, p_sql;
END; $$ LANGUAGE plpgsql;

-- ---------- Dữ liệu mẫu ----------
INSERT INTO warehouses(warehouse_id,erp_warehouse_code,warehouse_name) VALUES (pg_temp.u(1),'W1','Kho 1');
INSERT INTO warehouse_configs(warehouse_id) VALUES (pg_temp.u(1));
INSERT INTO zones(zone_id,warehouse_id,zone_code,zone_name,zone_type) VALUES (pg_temp.u(2),pg_temp.u(1),'Z1','Z1','STORAGE');
INSERT INTO locations(location_id,warehouse_id,zone_id,location_code,barcode,max_pallets) VALUES
 (pg_temp.u(11),pg_temp.u(1),pg_temp.u(2),'L1','L1',2),(pg_temp.u(12),pg_temp.u(1),pg_temp.u(2),'L2','L2',2);
INSERT INTO skus(sku_id,sku_code,sku_name,base_uom,unit_cost) VALUES (pg_temp.u(21),'S1','S1','PCS',100000);
INSERT INTO roles(role_id,role_code,role_name,actor_group) VALUES
 (pg_temp.u(31),'nv-nhan','nv','THUC_THI'),(pg_temp.u(32),'thukho','tk','DIEU_HANH'),(pg_temp.u(33),'quanly','ql','DIEU_HANH');
INSERT INTO users(user_id,username,full_name,primary_role_id,primary_warehouse_id) VALUES
 (pg_temp.u(41),'nv1','nv1',pg_temp.u(31),pg_temp.u(1)),(pg_temp.u(42),'tk1','tk1',pg_temp.u(32),pg_temp.u(1)),(pg_temp.u(43),'ql1','ql1',pg_temp.u(33),pg_temp.u(1));
INSERT INTO customers(customer_id,erp_customer_code,customer_name) VALUES (pg_temp.u(51),'C1','C1');
INSERT INTO suppliers(supplier_id,erp_supplier_code,supplier_name) VALUES (pg_temp.u(52),'N1','N1');

-- ---------- T1-T5: tồn kho, sổ cái ----------
DO $$ DECLARE v NUMERIC; ver INT; pct1 NUMERIC; pct2 NUMERIC; BEGIN
    PERFORM fn_apply_inventory_movement(pg_temp.u(1),pg_temp.u(11),pg_temp.u(21),NULL,NULL,NULL,'RECEIVE',10,0,0,0,0,'GRN',gen_random_uuid(),pg_temp.u(41));
    PERFORM fn_apply_inventory_movement(pg_temp.u(1),pg_temp.u(11),pg_temp.u(21),NULL,NULL,NULL,'RECEIVE',5,0,0,0,0,'GRN',gen_random_uuid(),pg_temp.u(41));
    SELECT qty_available, version_no INTO v, ver FROM inventory_balances;
    IF v <> 15 OR ver <> 2 THEN RAISE EXCEPTION 'FAIL T1: tồn=% ver=%', v, ver; END IF;
    PERFORM fn_transfer_inventory(pg_temp.u(1),pg_temp.u(11),pg_temp.u(12),pg_temp.u(21),NULL,NULL,NULL,4,'PUTAWAY','PALLET',gen_random_uuid(),pg_temp.u(41));
    SELECT qty_available INTO v FROM inventory_balances WHERE location_id = pg_temp.u(11);
    IF v <> 11 THEN RAISE EXCEPTION 'FAIL T2: L1=%', v; END IF;
    SELECT current_capacity_pct INTO pct1 FROM locations WHERE location_id = pg_temp.u(11);
    IF pct1 <> 50 THEN RAISE EXCEPTION 'FAIL F2: % đầy (kỳ vọng 50)', pct1; END IF;
    RAISE NOTICE 'PASS T1-T2, F2 (tồn kho, chuyển hàng, phần trăm đầy với hàng không pallet)';
END $$;
SELECT pg_temp.expect_error($$SELECT fn_apply_inventory_movement(pg_temp.u(1),pg_temp.u(11),pg_temp.u(21),NULL,NULL,NULL,'PICK',-100,0,0,0,0,'SO',gen_random_uuid(),pg_temp.u(41))$$, '%inventory_balances_qty_available_check%');
SELECT pg_temp.expect_error($$UPDATE inventory_transactions SET qty_change = 0$$, 'BAN_GHI_BAT_BIEN%');
INSERT INTO audit_logs(action_code,entity_name) VALUES ('TEST','smoke');   -- cần có 1 dòng thì trigger mới kích hoạt
SELECT pg_temp.expect_error($$DELETE FROM audit_logs$$, 'BAN_GHI_BAT_BIEN%');

-- ---------- T6: phân luồng cấp duyệt ----------
DO $$ DECLARE r TEXT; BEGIN
    SELECT concat_ws(',',
        fn_resolve_approval_tier(pg_temp.u(1),'GRN_DISCREPANCY',100000,0.5,pg_temp.u(41),false),
        fn_resolve_approval_tier(pg_temp.u(1),'CYCLE_COUNT_DIFF',100000,0.5,pg_temp.u(41),false),
        fn_resolve_approval_tier(pg_temp.u(1),'CYCLE_COUNT_DIFF',3000000,5,pg_temp.u(41),false),
        fn_resolve_approval_tier(pg_temp.u(1),'CYCLE_COUNT_DIFF',3000000,5,pg_temp.u(42),false),
        fn_resolve_approval_tier(pg_temp.u(1),'CYCLE_COUNT_DIFF',30000000,5,pg_temp.u(41),false),
        fn_resolve_approval_tier(pg_temp.u(1),'CYCLE_COUNT_DIFF',3000000,5,pg_temp.u(43),false),
        fn_resolve_approval_tier(pg_temp.u(1),'CYCLE_COUNT_DIFF',100,0.1,pg_temp.u(41),true),
        fn_resolve_approval_tier(pg_temp.u(1),'OVERTIME_REQUEST',1,1,pg_temp.u(41),false)) INTO r;
    IF r <> 'D1_THUKHO,AUTO_TOLERANCE_Z,D1_THUKHO,D2_QUANLY,D3_BGD,D3_BGD,D1_THUKHO,D2_QUANLY' THEN
        RAISE EXCEPTION 'FAIL T6: %', r; END IF;
    RAISE NOTICE 'PASS T6 (8 ca phân luồng cấp duyệt)';
END $$;

-- ---------- T7-T8: ERP đổi/hủy đơn ----------
DO $$ DECLARE req UUID; st TEXT; n INT; BEGIN
    INSERT INTO outbound_orders(order_id,erp_order_number,warehouse_id,customer_id,cutoff_time) VALUES (pg_temp.u(101),'SO1',pg_temp.u(1),pg_temp.u(51),now()+interval '1 day');
    PERFORM fn_receive_erp_order_change(pg_temp.u(101),'CANCEL_ORDER','{}'::jsonb,pg_temp.u(43));
    SELECT status INTO st FROM outbound_orders WHERE order_id = pg_temp.u(101);
    SELECT count(*) INTO n FROM integration_sync_logs WHERE status = 'PENDING';
    IF st <> 'CANCELLED' OR n <> 1 THEN RAISE EXCEPTION 'FAIL T7: % / % log', st, n; END IF;

    INSERT INTO outbound_orders(order_id,erp_order_number,warehouse_id,customer_id,cutoff_time,status) VALUES (pg_temp.u(102),'SO2',pg_temp.u(1),pg_temp.u(51),now()+interval '1 day','PICKING');
    INSERT INTO outbound_order_lines(order_line_id,order_id,sku_id,qty_ordered,qty_allocated,qty_picked) VALUES (pg_temp.u(201),pg_temp.u(102),pg_temp.u(21),3,3,3);
    INSERT INTO pick_sessions(pick_session_id,warehouse_id,picker_user_id) VALUES (pg_temp.u(301),pg_temp.u(1),pg_temp.u(41));
    INSERT INTO pick_lines(pick_session_id,order_line_id,source_location_id,qty_to_pick,qty_picked) VALUES (pg_temp.u(301),pg_temp.u(201),pg_temp.u(11),3,3);
    req := fn_receive_erp_order_change(pg_temp.u(102),'CANCEL_ORDER','{}'::jsonb,pg_temp.u(43));
    BEGIN
        UPDATE outbound_orders SET status = 'PICKED' WHERE order_id = pg_temp.u(102);
        RAISE EXCEPTION 'FAIL T8: đơn đóng băng vẫn đổi được trạng thái';
    EXCEPTION WHEN OTHERS THEN IF SQLERRM LIKE 'FAIL%' THEN RAISE; END IF; END;
    PERFORM fn_decide_order_change(req,'ACCEPT',pg_temp.u(43),'ok');
    SELECT status INTO st FROM outbound_orders WHERE order_id = pg_temp.u(102);
    SELECT count(*) INTO n FROM tasks WHERE task_type = 'RETURN_PICKING';
    IF st <> 'CANCELLED' OR n <> 1 THEN RAISE EXCEPTION 'FAIL T8: % / % task', st, n; END IF;
    RAISE NOTICE 'PASS T7-T8 (hủy đơn tự chấp nhận; đóng băng + Quản lý chốt + task trả hàng)';
END $$;

-- ---------- T9: phê duyệt, SLA, xác thực lại, nhánh REJECT ----------
DO $$ DECLARE s TEXT; t TEXT; ps TEXT; BEGIN
    INSERT INTO pallets(pallet_id,pallet_code,warehouse_id,status) VALUES (pg_temp.u(401),'P1',pg_temp.u(1),'QUARANTINE_HOLD');
    INSERT INTO grns(grn_id,grn_number,warehouse_id,received_by,status) VALUES (pg_temp.u(501),'GRN1',pg_temp.u(1),pg_temp.u(41),'PENDING_D1');
    UPDATE pallets SET source_grn_id = pg_temp.u(501) WHERE pallet_id = pg_temp.u(401);
    INSERT INTO approval_requests(approval_id,warehouse_id,object_type,object_id,proposer_user_id,current_tier,status,discrepancy_value_amount,sla_due_at)
        VALUES (pg_temp.u(601),pg_temp.u(1),'GRN_DISCREPANCY',pg_temp.u(501),pg_temp.u(41),'D1_THUKHO','PENDING_D1',20000000,now()-interval '1 hour');
    IF fn_escalate_expired_approvals() <> 1 THEN RAISE EXCEPTION 'FAIL T9: leo thang SLA'; END IF;
    SELECT status::TEXT INTO s FROM approval_requests WHERE approval_id = pg_temp.u(601);
    IF s <> 'PENDING_D2' THEN RAISE EXCEPTION 'FAIL T9: sau leo thang = %', s; END IF;
    BEGIN
        INSERT INTO approval_histories(approval_id,tier,actor_user_id,action) VALUES (pg_temp.u(601),'D2_QUANLY',pg_temp.u(43),'APPROVE');
        RAISE EXCEPTION 'FAIL T9: duyệt >= 10tr không cần xác thực lại';
    EXCEPTION WHEN OTHERS THEN IF SQLERRM LIKE 'FAIL%' THEN RAISE; END IF; END;
    INSERT INTO approval_histories(approval_id,tier,actor_user_id,action,reauth_method) VALUES (pg_temp.u(601),'D2_QUANLY',pg_temp.u(43),'APPROVE','PASSWORD');
    UPDATE approval_requests SET status = 'REJECTED', final_decided_by = pg_temp.u(43) WHERE approval_id = pg_temp.u(601);
    SELECT status::TEXT INTO t FROM grns WHERE grn_id = pg_temp.u(501);
    SELECT status::TEXT INTO ps FROM pallets WHERE pallet_id = pg_temp.u(401);
    IF t <> 'REJECTED' OR ps <> 'REJECTED_PENDING_RETURN' THEN RAISE EXCEPTION 'FAIL T9: GRN=% pallet=%', t, ps; END IF;
    RAISE NOTICE 'PASS T9 (leo thang SLA, xác thực lại, GRN bị từ chối -> pallet chờ trả NCC)';
END $$;
-- người lập không được tự duyệt (SoD)
SELECT pg_temp.expect_error($$UPDATE approval_requests SET final_decided_by = proposer_user_id WHERE approval_id = pg_temp.u(601)$$, '%');

-- ---------- T10: trigger PO ----------
DO $$ DECLARE q NUMERIC; st TEXT; BEGIN
    INSERT INTO purchase_orders(po_id,erp_po_number,warehouse_id,supplier_id) VALUES (pg_temp.u(701),'PO1',pg_temp.u(1),pg_temp.u(52));
    INSERT INTO po_lines(po_line_id,po_id,line_number,sku_id,uom_code,qty_ordered) VALUES (pg_temp.u(801),pg_temp.u(701),1,pg_temp.u(21),'PCS',10);
    INSERT INTO grns(grn_id,grn_number,warehouse_id,received_by,po_id,status) VALUES (pg_temp.u(502),'GRN2',pg_temp.u(1),pg_temp.u(41),pg_temp.u(701),'PENDING_D1');
    INSERT INTO grn_lines(grn_id,po_line_id,sku_id,uom_code,qty_actual,qty_damaged) VALUES (pg_temp.u(502),pg_temp.u(801),pg_temp.u(21),'PCS',6,1),(pg_temp.u(502),pg_temp.u(801),pg_temp.u(21),'PCS',2,0);
    UPDATE grns SET status = 'APPROVED' WHERE grn_id = pg_temp.u(502);
    SELECT qty_received INTO q FROM po_lines WHERE po_line_id = pg_temp.u(801);
    SELECT status::TEXT INTO st FROM purchase_orders WHERE po_id = pg_temp.u(701);
    IF q <> 7 OR st <> 'PARTIAL_RECEIVED' THEN RAISE EXCEPTION 'FAIL T10: nhận=% PO=%', q, st; END IF;
    RAISE NOTICE 'PASS T10 (PO gộp nhiều dòng GRN, trừ hàng hư, PARTIAL_RECEIVED)';
END $$;

-- ---------- T11 (F4): duyệt hết hạn ----------
DO $$ DECLARE a BOOLEAN; b BOOLEAN; c BOOLEAN; n INT; BEGIN
    INSERT INTO grns(grn_id,grn_number,warehouse_id,received_by,status) VALUES (pg_temp.u(511),'GRN9',pg_temp.u(1),pg_temp.u(41),'PENDING_D3');
    INSERT INTO approval_requests(approval_id,warehouse_id,object_type,object_id,proposer_user_id,current_tier,status,discrepancy_value_amount,sla_due_at)
        VALUES (pg_temp.u(611),pg_temp.u(1),'GRN_DISCREPANCY',pg_temp.u(511),pg_temp.u(41),'D3_BGD','PENDING_D3',30000000,now()-interval '1 hour');
    INSERT INTO cycle_count_sheets(count_sheet_id,sheet_number,warehouse_id,count_type,created_by,due_at) VALUES (pg_temp.u(901),'CC1',pg_temp.u(1),'PERIODIC',pg_temp.u(42),now()+interval '1 day');
    INSERT INTO cycle_count_lines(count_line_id,count_sheet_id,location_id,status) VALUES (pg_temp.u(902),pg_temp.u(901),pg_temp.u(11),'PENDING_D3');
    INSERT INTO approval_requests(approval_id,warehouse_id,object_type,object_id,proposer_user_id,current_tier,status,discrepancy_value_amount,sla_due_at)
        VALUES (pg_temp.u(612),pg_temp.u(1),'CYCLE_COUNT_DIFF',pg_temp.u(902),pg_temp.u(41),'D3_BGD','PENDING_D3',1000000,now()-interval '1 hour');
    IF fn_escalate_expired_approvals() <> 2 THEN RAISE EXCEPTION 'FAIL T11: số hồ sơ hết hạn'; END IF;
    SELECT approval_expired_at IS NOT NULL INTO a FROM grns WHERE grn_id = pg_temp.u(511);
    SELECT approval_expired_at IS NOT NULL INTO b FROM cycle_count_lines WHERE count_line_id = pg_temp.u(902);
    SELECT count(*) INTO n FROM alerts WHERE alert_type = 'APPROVAL_EXPIRED';
    IF NOT (a AND b) OR n <> 2 THEN RAISE EXCEPTION 'FAIL T11: dấu GRN=% dòng=% cảnh báo=%', a, b, n; END IF;
    INSERT INTO approval_requests(approval_id,warehouse_id,object_type,object_id,proposer_user_id,current_tier,status,discrepancy_value_amount)
        VALUES (pg_temp.u(613),pg_temp.u(1),'GRN_DISCREPANCY',pg_temp.u(511),pg_temp.u(41),'D1_THUKHO','PENDING_D1',1000000);
    SELECT approval_expired_at IS NOT NULL INTO c FROM grns WHERE grn_id = pg_temp.u(511);
    IF c THEN RAISE EXCEPTION 'FAIL T11: gửi duyệt lại nhưng dấu hết hạn chưa xóa'; END IF;
    RAISE NOTICE 'PASS T11 (duyệt hết hạn: đánh dấu, cảnh báo, xóa dấu khi gửi lại)';
END $$;

-- ---------- Tổng kết ----------
DO $$ BEGIN
    IF (SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public') < 62 THEN RAISE EXCEPTION 'FAIL: thiếu bảng'; END IF;
    RAISE NOTICE '=== TẤT CẢ BÀI KIỂM THỬ ĐẠT ===';
END $$;
