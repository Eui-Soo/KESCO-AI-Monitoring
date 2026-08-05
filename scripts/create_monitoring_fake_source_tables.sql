-- v13: create development source DB tables for monitoring pipeline
-- ASCII only to avoid Windows psql encoding issues.

BEGIN;

CREATE TABLE IF NOT EXISTS tb_emc_btrrck_mntly_rcd (
    id BIGSERIAL PRIMARY KEY,
    site_no INTEGER NOT NULL,
    bms_id VARCHAR(100) NOT NULL,
    srvr_rcd_dt TIMESTAMP NOT NULL,
    dvc_rcd_dt TIMESTAMP NOT NULL,
    bms_no INTEGER NOT NULL DEFAULT 1,
    dvc_no INTEGER NOT NULL,
    soc NUMERIC(10,4),
    soh NUMERIC(10,4),
    dc_crnt NUMERIC(12,4),
    dvc_stts INTEGER,
    inserted TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tb_emc_mdul_mntly_rcd (
    id BIGSERIAL PRIMARY KEY,
    site_no INTEGER NOT NULL,
    bms_id VARCHAR(100) NOT NULL,
    srvr_rcd_dt TIMESTAMP NOT NULL,
    dvc_rcd_dt TIMESTAMP NOT NULL,
    bms_no INTEGER NOT NULL DEFAULT 1,
    btrrck_no INTEGER NOT NULL,
    dvc_no INTEGER NOT NULL,
    cll_1_vltg NUMERIC(10,4),
    cll_2_vltg NUMERIC(10,4),
    cll_3_vltg NUMERIC(10,4),
    cll_4_vltg NUMERIC(10,4),
    cll_5_vltg NUMERIC(10,4),
    cll_6_vltg NUMERIC(10,4),
    cll_7_vltg NUMERIC(10,4),
    cll_8_vltg NUMERIC(10,4),
    cll_9_vltg NUMERIC(10,4),
    cll_10_vltg NUMERIC(10,4),
    cll_11_vltg NUMERIC(10,4),
    cll_12_vltg NUMERIC(10,4),
    cll_13_vltg NUMERIC(10,4),
    cll_14_vltg NUMERIC(10,4),
    cll_15_vltg NUMERIC(10,4),
    cll_16_vltg NUMERIC(10,4),
    cll_17_vltg NUMERIC(10,4),
    cll_18_vltg NUMERIC(10,4),
    cll_19_vltg NUMERIC(10,4),
    cll_20_vltg NUMERIC(10,4),
    mdul_tp_1 NUMERIC(10,4),
    mdul_tp_2 NUMERIC(10,4),
    mdul_tp_3 NUMERIC(10,4),
    inserted TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fake_rack_ai_join
ON tb_emc_btrrck_mntly_rcd (site_no, bms_id, dvc_no, srvr_rcd_dt);

CREATE INDEX IF NOT EXISTS idx_fake_module_ai_query
ON tb_emc_mdul_mntly_rcd (site_no, bms_id, srvr_rcd_dt, btrrck_no, dvc_no);

COMMIT;
