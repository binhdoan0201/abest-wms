-- =============================================================================
-- SEED 02: DỮ LIỆU DANH MỤC MASTER DATA DEMO
-- 1 Kho, 3 Zone, 30 Vị trí có barcode, 10 SKU (2 SKU có hạn dùng),
-- Box types, 3 Khách hàng, 3 Nhà cung cấp, Reason codes
-- Chạy lại được (Idempotent với ON CONFLICT)
-- =============================================================================

-- 1. Kho & Cấu hình kho (Warehouses & Warehouse Configs)
INSERT INTO warehouses (warehouse_id, erp_warehouse_code, warehouse_name, branch_code, address, is_active)
VALUES (
    'a0000000-0000-0000-0000-000000000001',
    'WH01',
    'Tổng Kho Miền Nam - ABEST WMS',
    'HCM',
    'Lô A1-2, Đường số 3, KCN Tân Bình, Tây Thạnh, Tân Phú, TP. HCM',
    TRUE
)
ON CONFLICT (erp_warehouse_code) DO UPDATE SET
    warehouse_name = EXCLUDED.warehouse_name,
    branch_code = EXCLUDED.branch_code,
    address = EXCLUDED.address;

INSERT INTO warehouse_configs (
    warehouse_id,
    threshold_x_d1_amount,
    threshold_y_d2_amount,
    tolerance_z_mode,
    tolerance_z_amount,
    tolerance_z_percent,
    reauth_min_amount,
    picking_rule
) VALUES (
    'a0000000-0000-0000-0000-000000000001',
    5000000.00,
    20000000.00,
    'BOTH_AND',
    500000.00,
    1.00,
    10000000.00,
    'FEFO'
)
ON CONFLICT (warehouse_id) DO NOTHING;

-- 2. Ba Khu vực (Zones: STORAGE, RECEIVING_DOCK, STAGING)
INSERT INTO zones (zone_id, warehouse_id, zone_code, zone_name, zone_type, is_active) VALUES
    ('a1000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'ZN-STORAGE', 'Khu vực Lưu trữ Kệ Tầng', 'STORAGE', TRUE),
    ('a1000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001', 'ZN-RECEIVE', 'Khu vực Cửa Nhận Dock', 'RECEIVING_DOCK', TRUE),
    ('a1000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001', 'ZN-STAGING', 'Khu vực Tập kết Soạn Đóng gói', 'STAGING', TRUE)
ON CONFLICT (warehouse_id, zone_code) DO UPDATE SET
    zone_name = EXCLUDED.zone_name,
    zone_type = EXCLUDED.zone_type;

-- 3. Ba mươi Vị trí lưu kho có Barcode (Locations)
INSERT INTO locations (warehouse_id, zone_id, location_code, barcode, aisle, rack, shelf_level, bin, max_pallets, max_weight_kg, status, is_active) VALUES
    -- 20 vị trí kệ tại ZN-STORAGE
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'LOC-A01-01', 'LOCA0101', 'A', '01', '01', '01', 2, 2000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'LOC-A01-02', 'LOCA0102', 'A', '01', '02', '01', 2, 2000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'LOC-A01-03', 'LOCA0103', 'A', '01', '03', '01', 2, 2000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'LOC-A01-04', 'LOCA0104', 'A', '01', '04', '01', 2, 2000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'LOC-A01-05', 'LOCA0105', 'A', '01', '05', '01', 2, 2000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'LOC-A01-06', 'LOCA0106', 'A', '01', '06', '01', 2, 2000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'LOC-A01-07', 'LOCA0107', 'A', '01', '07', '01', 2, 2000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'LOC-A01-08', 'LOCA0108', 'A', '01', '08', '01', 2, 2000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'LOC-A01-09', 'LOCA0109', 'A', '01', '09', '01', 2, 2000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'LOC-A01-10', 'LOCA0110', 'A', '01', '10', '01', 2, 2000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'LOC-A02-01', 'LOCA0201', 'A', '02', '01', '01', 2, 2000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'LOC-A02-02', 'LOCA0202', 'A', '02', '02', '01', 2, 2000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'LOC-A02-03', 'LOCA0203', 'A', '02', '03', '01', 2, 2000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'LOC-A02-04', 'LOCA0204', 'A', '02', '04', '01', 2, 2000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'LOC-A02-05', 'LOCA0205', 'A', '02', '05', '01', 2, 2000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'LOC-A02-06', 'LOCA0206', 'A', '02', '06', '01', 2, 2000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'LOC-A02-07', 'LOCA0207', 'A', '02', '07', '01', 2, 2000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'LOC-A02-08', 'LOCA0208', 'A', '02', '08', '01', 2, 2000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'LOC-A02-09', 'LOCA0209', 'A', '02', '09', '01', 2, 2000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'LOC-A02-10', 'LOCA0210', 'A', '02', '10', '01', 2, 2000.00, 'EMPTY', TRUE),

    -- 5 vị trí cửa nhận tại ZN-RECEIVE
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000002', 'LOC-RCV-01', 'LOCRCV01', 'RCV', '01', '01', '01', 4, 4000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000002', 'LOC-RCV-02', 'LOCRCV02', 'RCV', '01', '02', '01', 4, 4000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000002', 'LOC-RCV-03', 'LOCRCV03', 'RCV', '01', '03', '01', 4, 4000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000002', 'LOC-RCV-04', 'LOCRCV04', 'RCV', '01', '04', '01', 4, 4000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000002', 'LOC-RCV-05', 'LOCRCV05', 'RCV', '01', '05', '01', 4, 4000.00, 'EMPTY', TRUE),

    -- 5 vị trí tập kết xuất tại ZN-STAGING
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000003', 'LOC-STG-01', 'LOCSTG01', 'STG', '01', '01', '01', 4, 4000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000003', 'LOC-STG-02', 'LOCSTG02', 'STG', '01', '02', '01', 4, 4000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000003', 'LOC-STG-03', 'LOCSTG03', 'STG', '01', '03', '01', 4, 4000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000003', 'LOC-STG-04', 'LOCSTG04', 'STG', '01', '04', '01', 4, 4000.00, 'EMPTY', TRUE),
    ('a0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000003', 'LOC-STG-05', 'LOCSTG05', 'STG', '01', '05', '01', 4, 4000.00, 'EMPTY', TRUE)
ON CONFLICT (warehouse_id, location_code) DO NOTHING;

-- 4. Danh mục nhóm hàng (Item Categories)
INSERT INTO item_categories (category_id, category_code, category_name, min_receiving_shelf_life_days, shelf_life_violation_action) VALUES
    ('a2000000-0000-0000-0000-000000000001', 'CAT-FOOD', 'Thực phẩm & Đồ uống', 30, 'WARN'),
    ('a2000000-0000-0000-0000-000000000002', 'CAT-ELEC', 'Điện tử & Đồ gia dụng', 0, 'WARN')
ON CONFLICT (category_code) DO UPDATE SET
    category_name = EXCLUDED.category_name;

-- 5. Mười SKU (2 SKU có Hạn dùng & Theo dõi Lô)
INSERT INTO skus (sku_id, sku_code, sku_name, category_id, base_uom, unit_cost, min_stock_level, is_lot_tracked, is_expiry_tracked, is_serial_tracked, storage_requirement, is_active) VALUES
    -- 2 SKU có Hạn dùng & Theo dõi Lô (Phục vụ FEFO)
    ('a3000000-0000-0000-0000-000000000001', 'SKU-FOOD-001', 'Sữa tươi tiệt trùng nguyên chất 1L', 'a2000000-0000-0000-0000-000000000001', 'BOX', 32000.00, 50, TRUE, TRUE, FALSE, 'NORMAL', TRUE),
    ('a3000000-0000-0000-0000-000000000002', 'SKU-FOOD-002', 'Bánh mì sandwich bơ tỏi 250g', 'a2000000-0000-0000-0000-000000000001', 'PACK', 25000.00, 30, TRUE, TRUE, FALSE, 'NORMAL', TRUE),
    -- 8 SKU thông thường (FIFO)
    ('a3000000-0000-0000-0000-000000000003', 'SKU-ELEC-003', 'Bàn ủi hơi nước cầm tay 1200W', 'a2000000-0000-0000-0000-000000000002', 'PCS', 450000.00, 10, FALSE, FALSE, FALSE, 'NORMAL', TRUE),
    ('a3000000-0000-0000-0000-000000000004', 'SKU-ELEC-004', 'Ấm đun nước siêu tốc inox 1.8L', 'a2000000-0000-0000-0000-000000000002', 'PCS', 220000.00, 15, FALSE, FALSE, FALSE, 'NORMAL', TRUE),
    ('a3000000-0000-0000-0000-000000000005', 'SKU-ELEC-005', 'Quạt để bàn mini tích điện USB', 'a2000000-0000-0000-0000-000000000002', 'PCS', 180000.00, 20, FALSE, FALSE, FALSE, 'NORMAL', TRUE),
    ('a3000000-0000-0000-0000-000000000006', 'SKU-GEN-006', 'Hộp đựng thực phẩm thủy tinh 650ml', 'a2000000-0000-0000-0000-000000000002', 'PCS', 65000.00, 40, FALSE, FALSE, FALSE, 'NORMAL', TRUE),
    ('a3000000-0000-0000-0000-000000000007', 'SKU-GEN-007', 'Chảo chống dính đá hoa cương 26cm', 'a2000000-0000-0000-0000-000000000002', 'PCS', 195000.00, 15, FALSE, FALSE, FALSE, 'NORMAL', TRUE),
    ('a3000000-0000-0000-0000-000000000008', 'SKU-GEN-008', 'Bộ dao kéo nhà bếp 5 món thép không gỉ', 'a2000000-0000-0000-0000-000000000002', 'SET', 150000.00, 10, FALSE, FALSE, FALSE, 'NORMAL', TRUE),
    ('a3000000-0000-0000-0000-000000000009', 'SKU-GEN-009', 'Bình giữ nhiệt inox 304 dung tích 500ml', 'a2000000-0000-0000-0000-000000000002', 'PCS', 135000.00, 25, FALSE, FALSE, FALSE, 'NORMAL', TRUE),
    ('a3000000-0000-0000-0000-000000000010', 'SKU-GEN-010', 'Khăn lau sợi Microfiber 30x30cm', 'a2000000-0000-0000-0000-000000000002', 'PIECE', 15000.00, 100, FALSE, FALSE, FALSE, 'NORMAL', TRUE)
ON CONFLICT (sku_code) DO UPDATE SET
    sku_name = EXCLUDED.sku_name,
    unit_cost = EXCLUDED.unit_cost,
    is_lot_tracked = EXCLUDED.is_lot_tracked,
    is_expiry_tracked = EXCLUDED.is_expiry_tracked;

-- Barcode cho các SKU
INSERT INTO sku_barcodes (sku_id, barcode, uom_code, conversion_factor) VALUES
    ('a3000000-0000-0000-0000-000000000001', '893600001001', 'BOX', 1),
    ('a3000000-0000-0000-0000-000000000002', '893600001002', 'PACK', 1),
    ('a3000000-0000-0000-0000-000000000003', '893600001003', 'PCS', 1),
    ('a3000000-0000-0000-0000-000000000004', '893600001004', 'PCS', 1),
    ('a3000000-0000-0000-0000-000000000005', '893600001005', 'PCS', 1),
    ('a3000000-0000-0000-0000-000000000006', '893600001006', 'PCS', 1),
    ('a3000000-0000-0000-0000-000000000007', '893600001007', 'PCS', 1),
    ('a3000000-0000-0000-0000-000000000008', '893600001008', 'SET', 1),
    ('a3000000-0000-0000-0000-000000000009', '893600001009', 'PCS', 1),
    ('a3000000-0000-0000-0000-000000000010', '893600001010', 'PIECE', 1)
ON CONFLICT (barcode) DO NOTHING;

-- 6. Loại thùng đóng gói (Box types)
INSERT INTO box_types (box_type_id, box_code, box_name, length_cm, width_cm, height_cm, tare_weight_kg, max_weight_kg) VALUES
    ('a4000000-0000-0000-0000-000000000001', 'BOX-S', 'Thùng carton nhỏ (Size S)', 20.00, 15.00, 10.00, 0.150, 5.00),
    ('a4000000-0000-0000-0000-000000000002', 'BOX-M', 'Thùng carton vừa (Size M)', 35.00, 25.00, 20.00, 0.350, 15.00),
    ('a4000000-0000-0000-0000-000000000003', 'BOX-L', 'Thùng carton lớn (Size L)', 50.00, 40.00, 30.00, 0.600, 30.00)
ON CONFLICT (box_code) DO NOTHING;

-- 7. Ba Khách hàng (Customers)
INSERT INTO customers (customer_id, erp_customer_code, customer_name, shipping_address, phone, is_active) VALUES
    ('a5000000-0000-0000-0000-000000000001', 'CUST-001', 'Siêu thị VinMart Central', 'Tầng B1, TTTM Vincom Đồng Khởi, Q.1, TP. HCM', '02838221234', TRUE),
    ('a5000000-0000-0000-0000-000000000002', 'CUST-002', 'Chuỗi Cửa Hàng Bách Hóa Xanh Khu Tây', '128 Trần Não, P. An Khánh, TP. Thủ Đức, TP. HCM', '02839115678', TRUE),
    ('a5000000-0000-0000-0000-000000000003', 'CUST-003', 'Đại lý phân phối MegaMarket Bình Phú', 'Khu dân cư Bình Phú, P.11, Q.6, TP. HCM', '02837559999', TRUE)
ON CONFLICT (erp_customer_code) DO NOTHING;

-- 8. Ba Nhà cung cấp (Suppliers)
INSERT INTO suppliers (supplier_id, erp_supplier_code, supplier_name, contact_person, phone, email, is_active) VALUES
    ('a6000000-0000-0000-0000-000000000001', 'SUPP-001', 'Công ty Cổ phần Sữa Vinamilk', 'Nguyễn Văn Hùng', '02854155555', 'vinamilk-b2b@vinamilk.vn', TRUE),
    ('a6000000-0000-0000-0000-000000000002', 'SUPP-002', 'Tập đoàn Điện gia dụng Sunhouse', 'Trần Thị Mai', '02437366666', 'sales-wms@sunhouse.com.vn', TRUE),
    ('a6000000-0000-0000-0000-000000000003', 'SUPP-003', 'Công ty TNHH Quốc tế Unilever Việt Nam', 'Lê Quốc Bảo', '02854135678', 'order-support@unilever.com', TRUE)
ON CONFLICT (erp_supplier_code) DO NOTHING;

-- 9. Lý do nghiệp vụ / Ngoại lệ (Reason Codes)
INSERT INTO reason_codes (reason_code, reason_category, description, is_active) VALUES
    ('DAMAGED_TRANSIT', 'DAMAGED', 'Hàng hư hỏng, móp méo trong quá trình vận chuyển', TRUE),
    ('DISCREPANCY_SHORT', 'DISCREPANCY', 'Giao thiếu số lượng so với chứng từ PO/ASN', TRUE),
    ('DISCREPANCY_OVER', 'DISCREPANCY', 'Giao thừa số lượng so với chứng từ PO/ASN', TRUE),
    ('EXPIRED_LOT', 'SCRAP', 'Hàng cận hạn hoặc hết hạn sử dụng không đạt chuẩn nhập kho', TRUE),
    ('TASK_REJECT_BUSY', 'TASK_REJECT', 'Nhân viên đang thực hiện dở dang task khẩn khác', TRUE),
    ('PACKAGE_BROKEN_SEAL', 'PACKING_EXCEPTION', 'Bao bì rách niêm phong, cần kiểm tra lại', TRUE)
ON CONFLICT (reason_code) DO NOTHING;
