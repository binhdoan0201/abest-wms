-- =============================================================================
-- Migration 001: Khối lượng và thể tích đơn vị cho SKU
-- Issue #23, báo cáo docs/reports/r1-ra-soat-nghiep-vu.md mục 2.4
--
-- Tính theo đơn vị cơ sở skus.base_uom. Cho phép NULL vì dữ liệu ERP có thể chưa có;
-- gợi ý cất hàng (B-07) và đóng gói (C-05) bỏ qua kiểm tra tải khi giá trị là NULL.
-- Chạy lại nhiều lần không lỗi (idempotent).
-- =============================================================================
BEGIN;

ALTER TABLE skus
    ADD COLUMN IF NOT EXISTS unit_weight_kg NUMERIC(12, 4),
    ADD COLUMN IF NOT EXISTS unit_volume_m3 NUMERIC(12, 6);

ALTER TABLE skus DROP CONSTRAINT IF EXISTS chk_skus_unit_weight_nonneg;
ALTER TABLE skus ADD CONSTRAINT chk_skus_unit_weight_nonneg
    CHECK (unit_weight_kg IS NULL OR unit_weight_kg >= 0);

ALTER TABLE skus DROP CONSTRAINT IF EXISTS chk_skus_unit_volume_nonneg;
ALTER TABLE skus ADD CONSTRAINT chk_skus_unit_volume_nonneg
    CHECK (unit_volume_m3 IS NULL OR unit_volume_m3 >= 0);

COMMENT ON COLUMN skus.unit_weight_kg IS 'Khối lượng (kg) của 1 đơn vị base_uom';
COMMENT ON COLUMN skus.unit_volume_m3 IS 'Thể tích (m3) của 1 đơn vị base_uom';

COMMIT;
