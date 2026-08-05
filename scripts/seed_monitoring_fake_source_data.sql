-- v13: insert fake source monitoring data for pipeline development.
-- Target DB: kesco_monitoring_fake or kesco_digitaltwin when using one DB for dev.
-- Data window: 2026-07-01 00:00:00 to 2026-07-07 23:55:00, 5 minute interval.
-- ASCII only to avoid Windows psql encoding issues.

BEGIN;

-- Re-seed safely.
DELETE FROM tb_emc_mdul_mntly_rcd WHERE bms_id = 'FAKE-BMS-9001';
DELETE FROM tb_emc_btrrck_mntly_rcd WHERE bms_id = 'FAKE-BMS-9001';

-- Rack records: 2 racks, 7 days, 5 minute interval.
INSERT INTO tb_emc_btrrck_mntly_rcd (
    site_no, bms_id, srvr_rcd_dt, dvc_rcd_dt, bms_no, dvc_no,
    soc, soh, dc_crnt, dvc_stts
)
SELECT
    9001 AS site_no,
    'FAKE-BMS-9001' AS bms_id,
    ts AS srvr_rcd_dt,
    ts AS dvc_rcd_dt,
    1 AS bms_no,
    rack_no AS dvc_no,
    ROUND((65 + 20 * SIN(EXTRACT(EPOCH FROM ts) / 86400.0) - rack_no)::numeric, 4) AS soc,
    ROUND((96.5 - rack_no * 0.3)::numeric, 4) AS soh,
    ROUND((CASE
        WHEN EXTRACT(HOUR FROM ts) BETWEEN 9 AND 17 THEN -38.0 - rack_no
        WHEN EXTRACT(HOUR FROM ts) BETWEEN 18 AND 22 THEN 32.0 + rack_no
        ELSE 0.0
    END)::numeric, 4) AS dc_crnt,
    CASE
        WHEN EXTRACT(HOUR FROM ts) BETWEEN 9 AND 17 THEN 1
        WHEN EXTRACT(HOUR FROM ts) BETWEEN 18 AND 22 THEN 2
        ELSE 3
    END AS dvc_stts
FROM generate_series(
    TIMESTAMP '2026-07-01 00:00:00',
    TIMESTAMP '2026-07-07 23:55:00',
    INTERVAL '5 minutes'
) AS ts
CROSS JOIN generate_series(1, 2) AS rack_no;

-- Module records: 12 modules, 20 cell voltages, 7 days, 5 minute interval.
INSERT INTO tb_emc_mdul_mntly_rcd (
    site_no, bms_id, srvr_rcd_dt, dvc_rcd_dt, bms_no, btrrck_no, dvc_no,
    cll_1_vltg, cll_2_vltg, cll_3_vltg, cll_4_vltg, cll_5_vltg,
    cll_6_vltg, cll_7_vltg, cll_8_vltg, cll_9_vltg, cll_10_vltg,
    cll_11_vltg, cll_12_vltg, cll_13_vltg, cll_14_vltg, cll_15_vltg,
    cll_16_vltg, cll_17_vltg, cll_18_vltg, cll_19_vltg, cll_20_vltg,
    mdul_tp_1, mdul_tp_2, mdul_tp_3
)
SELECT
    9001 AS site_no,
    'FAKE-BMS-9001' AS bms_id,
    ts AS srvr_rcd_dt,
    ts AS dvc_rcd_dt,
    1 AS bms_no,
    CASE WHEN module_no <= 6 THEN 1 ELSE 2 END AS btrrck_no,
    module_no AS dvc_no,
    ROUND((3.35 + base_delta + 0.001)::numeric, 4),
    ROUND((3.35 + base_delta + 0.002)::numeric, 4),
    ROUND((3.35 + base_delta + 0.003)::numeric, 4),
    ROUND((3.35 + base_delta + 0.004)::numeric, 4),
    ROUND((3.35 + base_delta + 0.005)::numeric, 4),
    ROUND((3.35 + base_delta + 0.006)::numeric, 4),
    ROUND((3.35 + base_delta + 0.007)::numeric, 4),
    ROUND((3.35 + base_delta + 0.008)::numeric, 4),
    ROUND((3.35 + base_delta + 0.009)::numeric, 4),
    ROUND((3.35 + base_delta + 0.010)::numeric, 4),
    ROUND((3.35 + base_delta + 0.011)::numeric, 4),
    ROUND((3.35 + base_delta + 0.012)::numeric, 4),
    ROUND((3.35 + base_delta + 0.013)::numeric, 4),
    ROUND((3.35 + base_delta + 0.014)::numeric, 4),
    ROUND((3.35 + base_delta + 0.015)::numeric, 4),
    ROUND((3.35 + base_delta + 0.016)::numeric, 4),
    ROUND((3.35 + base_delta + 0.017)::numeric, 4),
    ROUND((3.35 + base_delta + 0.018)::numeric, 4),
    ROUND((3.35 + base_delta + 0.019)::numeric, 4),
    ROUND((3.35 + base_delta + 0.020)::numeric, 4),
    ROUND((25.0 + module_no * 0.2 + temp_delta)::numeric, 4),
    ROUND((25.5 + module_no * 0.2 + temp_delta)::numeric, 4),
    ROUND((26.0 + module_no * 0.2 + temp_delta)::numeric, 4)
FROM generate_series(
    TIMESTAMP '2026-07-01 00:00:00',
    TIMESTAMP '2026-07-07 23:55:00',
    INTERVAL '5 minutes'
) AS ts
CROSS JOIN generate_series(1, 12) AS module_no
CROSS JOIN LATERAL (
    SELECT
        (module_no * 0.0007 + SIN(EXTRACT(EPOCH FROM ts) / 3600.0) * 0.004) AS base_delta,
        (SIN(EXTRACT(EPOCH FROM ts) / 7200.0) * 1.4) AS temp_delta
) AS calc;

COMMIT;

SELECT 'rack_rows' AS item, COUNT(*) AS count FROM tb_emc_btrrck_mntly_rcd WHERE bms_id = 'FAKE-BMS-9001'
UNION ALL
SELECT 'module_rows' AS item, COUNT(*) AS count FROM tb_emc_mdul_mntly_rcd WHERE bms_id = 'FAKE-BMS-9001';
