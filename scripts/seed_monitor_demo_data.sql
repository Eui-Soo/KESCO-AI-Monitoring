-- KESCO Monitor demo data seed v12
-- 목적: /monitor 화면 개발/시연용 가짜 AI 결과 데이터를 local DB에 추가한다.
-- 안전장치: bms_id는 DEMO-BMS-% 형식, pipeline_run_log.code_version은 demo-monitor-seed-v12 로 기록한다.
-- 삭제: scripts/clear_monitor_demo_data.sql 실행

BEGIN;

DO $$
DECLARE
    v_target_date date := current_date - 1;
    v_started_at timestamp := now() - interval '2 hours';
    v_finished_at timestamp := now() - interval '1 hour 55 minutes';
    v_prediction_time timestamp := now() - interval '5 minutes';
    v_run_id bigint;
    v_site_no integer;
    v_site_idx integer;
    v_module_no integer;
    v_score_base numeric;
    v_cell_scores numeric[];
    v_levels text[];
    v_max_score numeric;
    v_avg_score numeric;
    v_max_level text;
BEGIN
    -- 기존 demo seed 데이터 중복 방지
    DELETE FROM anomaly_score
    WHERE bms_id LIKE 'DEMO-BMS-%';

    DELETE FROM pipeline_run_log
    WHERE code_version = 'demo-monitor-seed-v12'
       OR bms_id LIKE 'DEMO-BMS-%';

    -- 6개 demo 사이트 생성: 9001~9006
    FOR v_site_idx IN 1..6 LOOP
        v_site_no := 9000 + v_site_idx;

        INSERT INTO pipeline_run_log (
            ess_id,
            site_no,
            bms_id,
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
            error_message,
            model_name,
            model_version,
            model_maker,
            model_root,
            fold_count,
            preprocess_version,
            code_version,
            inserted,
            updated
        ) VALUES (
            'DEMO-ESS-' || lpad(v_site_idx::text, 2, '0'),
            v_site_no,
            'DEMO-BMS-' || lpad(v_site_idx::text, 2, '0'),
            v_target_date,
            v_started_at - (v_site_idx || ' minutes')::interval,
            v_finished_at - (v_site_idx || ' minutes')::interval,
            'success',
            12,
            12,
            0,
            'files/raw/demo/' || v_site_no || '/' || v_target_date || '/battery_raw.parquet',
            'files/preprocess/demo/' || v_site_no || '/' || v_target_date || '/battery_preprocessed.parquet',
            'files/result/demo/' || v_site_no || '/' || v_target_date || '/anomaly_scores.parquet',
            'demo monitor seed data',
            NULL,
            'CNN-LSTM Ensemble Demo',
            'demo-v12',
            'Robovolt',
            'models/demo',
            10,
            'preprocess-demo-v1',
            'demo-monitor-seed-v12',
            now(),
            now()
        ) RETURNING id INTO v_run_id;

        -- 각 사이트별 12개 module 결과 생성
        FOR v_module_no IN 1..12 LOOP
            -- 사이트별 위험도 기본값. 9001/9002는 위험, 9003/9004는 주의, 9005는 정상, 9006은 데이터 확인용 낮은 점수.
            v_score_base := CASE v_site_idx
                WHEN 1 THEN 0.88
                WHEN 2 THEN 0.79
                WHEN 3 THEN 0.63
                WHEN 4 THEN 0.48
                WHEN 5 THEN 0.28
                ELSE 0.18
            END;

            -- module 번호에 따라 약간의 편차 부여
            v_cell_scores := ARRAY[
                LEAST(0.99, GREATEST(0.01, v_score_base - 0.22 + v_module_no * 0.006)),
                LEAST(0.99, GREATEST(0.01, v_score_base - 0.18 + v_module_no * 0.005)),
                LEAST(0.99, GREATEST(0.01, v_score_base - 0.12 + v_module_no * 0.004)),
                LEAST(0.99, GREATEST(0.01, v_score_base - 0.09 + v_module_no * 0.003)),
                LEAST(0.99, GREATEST(0.01, v_score_base - 0.06 + v_module_no * 0.004)),
                LEAST(0.99, GREATEST(0.01, v_score_base - 0.03 + v_module_no * 0.002)),
                LEAST(0.99, GREATEST(0.01, CASE WHEN v_site_idx IN (1,2) AND v_module_no IN (5,8) THEN v_score_base + 0.09 ELSE v_score_base + 0.02 END)),
                LEAST(0.99, GREATEST(0.01, v_score_base - 0.14 + v_module_no * 0.004)),
                LEAST(0.99, GREATEST(0.01, v_score_base - 0.19 + v_module_no * 0.005)),
                LEAST(0.99, GREATEST(0.01, v_score_base - 0.16 + v_module_no * 0.003)),
                LEAST(0.99, GREATEST(0.01, v_score_base - 0.10 + v_module_no * 0.002)),
                LEAST(0.99, GREATEST(0.01, CASE WHEN v_site_idx = 1 AND v_module_no = 5 THEN 0.96 ELSE v_score_base - 0.02 END)),
                LEAST(0.99, GREATEST(0.01, v_score_base - 0.20 + v_module_no * 0.003)),
                LEAST(0.99, GREATEST(0.01, v_score_base - 0.15 + v_module_no * 0.002)),
                LEAST(0.99, GREATEST(0.01, v_score_base - 0.11 + v_module_no * 0.003)),
                LEAST(0.99, GREATEST(0.01, v_score_base - 0.17 + v_module_no * 0.004)),
                LEAST(0.99, GREATEST(0.01, v_score_base - 0.21 + v_module_no * 0.002)),
                LEAST(0.99, GREATEST(0.01, v_score_base - 0.13 + v_module_no * 0.003)),
                LEAST(0.99, GREATEST(0.01, CASE WHEN v_site_idx = 3 AND v_module_no = 7 THEN 0.74 ELSE v_score_base - 0.08 END)),
                LEAST(0.99, GREATEST(0.01, v_score_base - 0.23 + v_module_no * 0.004))
            ];

            SELECT max(x), avg(x)
            INTO v_max_score, v_avg_score
            FROM unnest(v_cell_scores) AS x;

            v_max_level := CASE
                WHEN v_max_score >= 0.80 THEN 'abnormal'
                WHEN v_max_score >= 0.40 THEN 'warning'
                ELSE 'normal'
            END;

            v_levels := ARRAY(
                SELECT CASE
                    WHEN x >= 0.80 THEN 'abnormal'
                    WHEN x >= 0.40 THEN 'warning'
                    ELSE 'normal'
                END
                FROM unnest(v_cell_scores) AS x
            );

            INSERT INTO anomaly_score (
                pipeline_run_id,
                site_no,
                bms_id,
                target_date,
                serial_number,
                sensing_datetime,
                prediction_time,
                bank_no,
                rack_no,
                string_no,
                module_no,
                cell_1_score, cell_2_score, cell_3_score, cell_4_score, cell_5_score,
                cell_6_score, cell_7_score, cell_8_score, cell_9_score, cell_10_score,
                cell_11_score, cell_12_score, cell_13_score, cell_14_score, cell_15_score,
                cell_16_score, cell_17_score, cell_18_score, cell_19_score, cell_20_score,
                cell_1_level, cell_2_level, cell_3_level, cell_4_level, cell_5_level,
                cell_6_level, cell_7_level, cell_8_level, cell_9_level, cell_10_level,
                cell_11_level, cell_12_level, cell_13_level, cell_14_level, cell_15_level,
                cell_16_level, cell_17_level, cell_18_level, cell_19_level, cell_20_level,
                max_score,
                max_level,
                average_score,
                inserted,
                updated
            ) VALUES (
                v_run_id,
                v_site_no,
                'DEMO-BMS-' || lpad(v_site_idx::text, 2, '0'),
                v_target_date,
                'DEMO-SN-' || v_site_no || '-' || lpad(v_module_no::text, 2, '0'),
                v_prediction_time - (v_module_no || ' minutes')::interval,
                v_prediction_time - (v_module_no || ' minutes')::interval,
                1,
                ((v_module_no - 1) / 4) + 1,
                (((v_module_no - 1) % 4) / 2) + 1,
                v_module_no,
                v_cell_scores[1], v_cell_scores[2], v_cell_scores[3], v_cell_scores[4], v_cell_scores[5],
                v_cell_scores[6], v_cell_scores[7], v_cell_scores[8], v_cell_scores[9], v_cell_scores[10],
                v_cell_scores[11], v_cell_scores[12], v_cell_scores[13], v_cell_scores[14], v_cell_scores[15],
                v_cell_scores[16], v_cell_scores[17], v_cell_scores[18], v_cell_scores[19], v_cell_scores[20],
                v_levels[1], v_levels[2], v_levels[3], v_levels[4], v_levels[5],
                v_levels[6], v_levels[7], v_levels[8], v_levels[9], v_levels[10],
                v_levels[11], v_levels[12], v_levels[13], v_levels[14], v_levels[15],
                v_levels[16], v_levels[17], v_levels[18], v_levels[19], v_levels[20],
                round(v_max_score, 4),
                v_max_level,
                round(v_avg_score, 4),
                now(),
                now()
            );
        END LOOP;
    END LOOP;
END $$;

COMMIT;

-- 확인용
SELECT
    site_no,
    bms_id,
    COUNT(*) AS score_rows,
    ROUND(MAX(max_score)::numeric, 4) AS max_score,
    MAX(max_level) AS max_level,
    MAX(prediction_time) AS latest_prediction_time
FROM anomaly_score
WHERE bms_id LIKE 'DEMO-BMS-%'
GROUP BY site_no, bms_id
ORDER BY site_no;
