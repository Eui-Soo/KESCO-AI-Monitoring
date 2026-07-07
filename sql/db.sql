-- ============================================================
-- 개발/테스트용 확인 쿼리
-- ============================================================
-- 이 아래 쿼리들은 DB 상태를 빠르게 확인하기 위한 용도입니다.
-- 실제 운영 로직에서 직접 사용하는 SQL은 아니며,
-- psql 또는 DB Tool에서 복사해서 실행하면 됩니다.
-- ============================================================


-- ============================================================
-- 1. 전체 테이블 목록 확인
-- ============================================================

-- psql 접속 후 아래 명령어 실행
-- \dt


-- ============================================================
-- 2. 최근 AI 파이프라인 실행 이력 확인
-- ============================================================

SELECT
    id,
    ess_id,
    target_date,
    started_at,
    finished_at,
    status,
    battery_count,
    saved_score_count,
    deleted_preprocessed_count,
    raw_file_path,
    preprocessed_file_path,
    result_file_path,
    message,
    error_message
FROM pipeline_run_log
ORDER BY id DESC
LIMIT 10;


-- ============================================================
-- 3. 최근 AI 이상 점수 저장 결과 확인
-- ============================================================

SELECT
    id,
    rack_idx,
    date,
    inserted,
    updated
FROM anomaly_score
ORDER BY id DESC
LIMIT 20;


-- ============================================================
-- 4. 특정 날짜 AI 이상 점수 확인
-- ============================================================

SELECT
    id,
    rack_idx,
    date,
    sc_c1,
    sc_c2,
    sc_c3,
    sc_c4,
    sc_c5,
    inserted
FROM anomaly_score
WHERE date = '2026-05-27'
ORDER BY inserted DESC, rack_idx
LIMIT 20;


-- ============================================================
-- 5. 최근 실행 이력 중 empty 상태 확인
-- ============================================================

SELECT
    id,
    ess_id,
    target_date,
    status,
    battery_count,
    saved_score_count,
    message,
    error_message,
    started_at,
    finished_at
FROM pipeline_run_log
WHERE status = 'empty'
ORDER BY id DESC
LIMIT 10;


-- ============================================================
-- 6. 최근 실행 이력 중 error 상태 확인
-- ============================================================

SELECT
    id,
    ess_id,
    target_date,
    status,
    battery_count,
    saved_score_count,
    message,
    error_message,
    started_at,
    finished_at
FROM pipeline_run_log
WHERE status = 'error'
ORDER BY id DESC
LIMIT 10;


-- ============================================================
-- 7. 개발용 battery 원본 데이터 확인
-- ============================================================

SELECT
    id,
    total_racks,
    index,
    cv_1,
    cv_2,
    cv_3,
    cv_4,
    cv_5,
    date,
    inserted,
    updated
FROM battery
ORDER BY inserted DESC
LIMIT 20;


-- ============================================================
-- 8. 특정 날짜 개발용 battery 데이터 건수 확인
-- ============================================================

SELECT
    date,
    COUNT(*) AS row_count
FROM battery
GROUP BY date
ORDER BY date DESC;


-- ============================================================
-- 9. monitoring_battery_sample 샘플 데이터 확인
-- ============================================================

SELECT
    id,
    ess_id,
    site_id,
    bank_no,
    rack_no,
    string_no,
    module_no,
    measured_at,
    cv_1,
    cv_2,
    cv_3,
    temperature,
    current_a,
    voltage_v,
    soc
FROM monitoring_battery_sample
ORDER BY measured_at, rack_no
LIMIT 20;


-- ============================================================
-- 10. monitoring_battery_sample 날짜별 데이터 건수 확인
-- ============================================================

SELECT
    DATE(measured_at) AS measured_date,
    ess_id,
    COUNT(*) AS row_count
FROM monitoring_battery_sample
GROUP BY DATE(measured_at), ess_id
ORDER BY measured_date DESC, ess_id;


-- ============================================================
-- 11. anomaly_score 전체 삭제
-- ============================================================
-- 주의:
-- 개발 중 테스트 데이터를 초기화할 때만 사용하세요.
-- 실제 운영 환경에서는 사용하면 안 됩니다.

-- DELETE FROM anomaly_score;


-- ============================================================
-- 12. pipeline_run_log 전체 삭제
-- ============================================================
-- 주의:
-- 개발 중 테스트 실행 이력을 초기화할 때만 사용하세요.
-- 실제 운영 환경에서는 사용하면 안 됩니다.

-- DELETE FROM pipeline_run_log;


-- ============================================================
-- 13. anomaly_score + pipeline_run_log 테스트 데이터 초기화
-- ============================================================
-- 주의:
-- 개발 중 전체 테스트 결과를 초기화할 때만 사용하세요.
-- 실제 운영 환경에서는 사용하면 안 됩니다.

-- DELETE FROM anomaly_score;
-- DELETE FROM pipeline_run_log;


-- ============================================================
-- 14. 테이블별 row 개수 확인
-- ============================================================

SELECT
    'battery' AS table_name,
    COUNT(*) AS row_count
FROM battery

UNION ALL

SELECT
    'monitoring_battery_sample' AS table_name,
    COUNT(*) AS row_count
FROM monitoring_battery_sample

UNION ALL

SELECT
    'anomaly_score' AS table_name,
    COUNT(*) AS row_count
FROM anomaly_score

UNION ALL

SELECT
    'pipeline_run_log' AS table_name,
    COUNT(*) AS row_count
FROM pipeline_run_log;

