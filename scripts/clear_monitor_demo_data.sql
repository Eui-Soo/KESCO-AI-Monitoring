-- KESCO Monitor demo data clear v12
BEGIN;

DELETE FROM anomaly_score
WHERE bms_id LIKE 'DEMO-BMS-%';

DELETE FROM pipeline_run_log
WHERE code_version = 'demo-monitor-seed-v12'
   OR bms_id LIKE 'DEMO-BMS-%';

COMMIT;

SELECT
    (SELECT COUNT(*) FROM anomaly_score WHERE bms_id LIKE 'DEMO-BMS-%') AS demo_anomaly_score_count,
    (SELECT COUNT(*) FROM pipeline_run_log WHERE code_version = 'demo-monitor-seed-v12' OR bms_id LIKE 'DEMO-BMS-%') AS demo_pipeline_run_log_count;
