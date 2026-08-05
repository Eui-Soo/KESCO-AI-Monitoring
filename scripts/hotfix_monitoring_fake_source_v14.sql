-- ============================================================
-- v14 Hotfix - monitoring fake source schema compatibility
-- ============================================================
-- Purpose:
--   source-data-quality and pipeline queries expect rack column dc_vltg.
--   v13 fake source table missed that column.
--   This script safely adds/fills it.
--
-- Target DB:
--   kesco_monitoring_fake
-- ============================================================

BEGIN;

ALTER TABLE tb_emc_btrrck_mntly_rcd
    ADD COLUMN IF NOT EXISTS dc_vltg DOUBLE PRECISION;

UPDATE tb_emc_btrrck_mntly_rcd
SET dc_vltg = COALESCE(dc_vltg, 760.0 + (dvc_no * 0.8))
WHERE bms_id = 'FAKE-BMS-9001'
  AND dc_vltg IS NULL;

COMMIT;

SELECT
    COUNT(*) AS rack_rows,
    COUNT(dc_vltg) AS dc_vltg_filled_rows,
    MIN(dc_vltg) AS min_dc_vltg,
    MAX(dc_vltg) AS max_dc_vltg
FROM tb_emc_btrrck_mntly_rcd
WHERE bms_id = 'FAKE-BMS-9001';
