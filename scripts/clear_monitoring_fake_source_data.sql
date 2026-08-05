-- v13: clear fake source monitoring data only.

BEGIN;
DELETE FROM tb_emc_mdul_mntly_rcd WHERE bms_id = 'FAKE-BMS-9001';
DELETE FROM tb_emc_btrrck_mntly_rcd WHERE bms_id = 'FAKE-BMS-9001';
COMMIT;
