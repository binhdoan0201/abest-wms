-- =============================================================================
-- Seed 04: Khối lượng, thể tích SKU demo và mã vạch thùng để thử quy đổi đơn vị
-- Cần migration 001_sku_weight_volume.sql (Issue #22, #23)
-- Chạy lại nhiều lần không lỗi.
-- =============================================================================

UPDATE skus AS s SET
    unit_weight_kg = v.unit_weight_kg,
    unit_volume_m3 = v.unit_volume_m3
FROM (VALUES
    ('SKU-FOOD-001', 1.0500, 0.001100),
    ('SKU-FOOD-002', 0.2700, 0.000900),
    ('SKU-ELEC-003', 1.2000, 0.004500),
    ('SKU-ELEC-004', 1.1000, 0.004000),
    ('SKU-ELEC-005', 0.6000, 0.003000),
    ('SKU-GEN-006', 0.8000, 0.001500),
    ('SKU-GEN-007', 1.3000, 0.006000),
    ('SKU-GEN-008', 0.9000, 0.002500),
    ('SKU-GEN-009', 0.4000, 0.000900),
    ('SKU-GEN-010', 0.0500, 0.000300)
) AS v(sku_code, unit_weight_kg, unit_volume_m3)
WHERE s.sku_code = v.sku_code;

-- Thùng 12 hộp sữa: dùng để thử nhận hàng theo thùng và quy đổi về base_uom (BOX)
INSERT INTO sku_barcodes (sku_id, barcode, uom_code, conversion_factor) VALUES
    ('a3000000-0000-0000-0000-000000000001', '1893600001001', 'CTN', 12)
ON CONFLICT (barcode) DO NOTHING;
