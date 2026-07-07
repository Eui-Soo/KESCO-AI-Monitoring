# KESCO AI API Server 테스트 가이드

이 문서는 KESCO AI API Server의 주요 기능이 정상 동작하는지 확인하기 위한 테스트 절차를 정리한 문서입니다.

테스트 목적은 다음과 같습니다.

1. FastAPI 서버가 정상 실행되는지 확인한다.
2. Swagger 문서가 정상 표시되는지 확인한다.
3. AI 파이프라인 수동 실행이 정상 동작하는지 확인한다.
4. AI 결과가 DB에 저장되는지 확인한다.
5. Parquet 파일이 정상 생성되는지 확인한다.
6. pipeline_run_log 실행 이력이 정상 저장되는지 확인한다.
7. 데이터가 0건일 때 empty 처리가 정상 동작하는지 확인한다.

---

## 1. 테스트 전 준비사항

### 1.1 Python 가상환경 활성화

```bat
conda activate kesco_api
```

### 1.2 프로젝트 폴더 이동

```bat
cd "C:\Users\euiso\OneDrive\바탕 화면\KERI-DigitalTwin-main"
```

### 1.3 PostgreSQL 실행 확인

PostgreSQL 서비스가 실행 중이어야 합니다.

접속 확인:

```bat
"C:\Program Files\PostgreSQL\16\bin\psql.exe" -U kesco -d kesco_digitaltwin
```

비밀번호 입력 후 정상 접속되면 아래처럼 표시됩니다.

```text
kesco_digitaltwin=>
```

테이블 확인:

```sql
\dt
```

정상적으로는 아래 테이블들이 보여야 합니다.

```text
anomaly_score
battery
monitoring_battery_sample
pipeline_run_log
```

---

## 2. 서버 실행 테스트

프로젝트 루트에서 아래 명령어를 실행합니다.

```bat
python main.py
```

정상 실행 시 터미널에 아래와 비슷한 로그가 출력됩니다.

```text
▶ uvicorn 서버 실행 준비 중...
INFO:     Started server process
INFO:     Waiting for application startup.
======================================================================
🚀 KESCO-DigitalTwin 서버 시작
📌 Version : 1.0.0
🌐 Host    : 0.0.0.0
🔌 Port    : 8000
📄 Swagger : http://localhost:8000/docs
======================================================================
🗄️  로컬 DB 테이블 초기화 중...
✅ 로컬 DB 테이블 초기화 완료
⏰ 스케줄러 시작 중...
✅ 스케줄러 시작 완료
✅ 서버 준비 완료. 브라우저에서 Swagger를 열어 확인하세요.
👉 http://localhost:8000/docs
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

위 로그가 나오면 서버 실행은 정상입니다.

---

## 3. Swagger 접속 확인

브라우저에서 아래 주소로 접속합니다.

```text
http://localhost:8000/docs
```

Swagger 화면에서 아래 API 그룹이 보이면 정상입니다.

```text
Health
Anomaly Scores
Pipeline
```

---

## 4. Health API 테스트

Swagger에서 아래 API를 실행합니다.

```http
GET /api/v1/health
```

정상 응답 예시:

```json
{
  "status": "ok",
  "app_name": "KESCO-DigitalTwin",
  "app_version": "1.0.0",
  "message": "KESCO DigitalTwin AI API server is running."
}
```

확인 기준:

```text
status = ok
HTTP status code = 200
```

---

## 5. AI 파이프라인 수동 실행 테스트

Swagger에서 아래 API를 실행합니다.

```http
POST /api/v1/pipeline/run
```

이 API는 개발/테스트용입니다.
운영 환경에서는 스케줄러가 자동으로 실행합니다.

정상 응답 예시:

```json
{
  "status": "success",
  "run_id": 1,
  "target_date": "2026-05-27",
  "target_date_offset_days": -1,
  "ess_id": "KESCO_ESS_001",
  "battery_count": 4,
  "saved_score_count": 2,
  "deleted_preprocessed_count": 0,
  "raw_file_path": "files\\raw\\KESCO_ESS_001\\2026-05-27\\battery_raw.parquet",
  "preprocessed_file_path": "files\\preprocessed\\KESCO_ESS_001\\2026-05-27\\battery_preprocessed.parquet",
  "result_file_path": "files\\result\\KESCO_ESS_001\\2026-05-27\\anomaly_scores.parquet",
  "message": "AI pipeline completed successfully."
}
```

확인 기준:

```text
status = success
run_id 값 존재
battery_count > 0
saved_score_count > 0
raw_file_path 존재
preprocessed_file_path 존재
result_file_path 존재
```

---

## 6. 최신 AI 이상 점수 조회 테스트

Swagger에서 아래 API를 실행합니다.

```http
GET /api/v1/anomaly-scores/latest
```

정상 응답 예시:

```json
{
  "status": "success",
  "count": 2,
  "latest_date": "2026-05-27",
  "latest_inserted": "2026-05-28T11:07:58.207354",
  "message": "Latest AI anomaly scores retrieved successfully.",
  "results": [
    {
      "id": 1,
      "rack_idx": 1,
      "date": "2026-05-27",
      "score_max": 94.4,
      "score_avg": 44.87,
      "max_cell": "c10",
      "risk_level": "danger",
      "risk_label": "위험",
      "cell_scores": {
        "c1": 44.05,
        "c2": 84.11
      }
    }
  ]
}
```

확인 기준:

```text
status = success
count > 0
results 배열 존재
score_max 존재
score_avg 존재
risk_level 존재
risk_label 존재
cell_scores 존재
```

---

## 7. 날짜별 AI 이상 점수 조회 테스트

Swagger에서 아래 API를 실행합니다.

```http
GET /api/v1/anomaly-scores?date=2026-05-27
```

Swagger에서는 `date` 입력칸에 아래처럼 입력합니다.

```text
2026-05-27
```

정상 응답 예시:

```json
{
  "status": "success",
  "count": 2,
  "target_date": "2026-05-27",
  "latest_inserted": "2026-05-28T11:07:58.207354",
  "message": "AI anomaly scores by date retrieved successfully.",
  "results": []
}
```

확인 기준:

```text
status = success
target_date가 요청한 날짜와 동일
count > 0
results 배열 존재
```

참고:

같은 날짜에 AI 파이프라인을 여러 번 실행한 경우, 해당 날짜의 가장 최근 실행 결과만 반환합니다.

---

## 8. 최신 파이프라인 실행 이력 조회 테스트

Swagger에서 아래 API를 실행합니다.

```http
GET /api/v1/pipeline/runs/latest
```

정상 응답 예시:

```json
{
  "status": "success",
  "message": "Latest pipeline run retrieved successfully.",
  "result": {
    "id": 1,
    "ess_id": "KESCO_ESS_001",
    "target_date": "2026-05-27",
    "status": "success",
    "battery_count": 4,
    "saved_score_count": 2,
    "raw_file_path": "files\\raw\\KESCO_ESS_001\\2026-05-27\\battery_raw.parquet",
    "preprocessed_file_path": "files\\preprocessed\\KESCO_ESS_001\\2026-05-27\\battery_preprocessed.parquet",
    "result_file_path": "files\\result\\KESCO_ESS_001\\2026-05-27\\anomaly_scores.parquet"
  }
}
```

확인 기준:

```text
status = success
result.status = success 또는 empty 또는 error
result.target_date 존재
result.battery_count 존재
파일 경로 정보 존재
```

---

## 9. 최근 파이프라인 실행 이력 목록 조회 테스트

Swagger에서 아래 API를 실행합니다.

```http
GET /api/v1/pipeline/runs?limit=20
```

정상 응답 예시:

```json
{
  "status": "success",
  "count": 3,
  "message": "Recent pipeline runs retrieved successfully.",
  "results": [
    {
      "id": 3,
      "ess_id": "KESCO_ESS_001",
      "target_date": "2026-05-27",
      "status": "success"
    }
  ]
}
```

확인 기준:

```text
status = success
count 값 존재
results 배열 존재
최신 실행 이력이 위쪽에 표시
```

---

## 10. PostgreSQL DB 확인 테스트

서버 테스트 후 PostgreSQL에서 실제 데이터가 저장되었는지 확인합니다.

### 10.1 psql 접속

```bat
"C:\Program Files\PostgreSQL\16\bin\psql.exe" -U kesco -d kesco_digitaltwin
```

---

### 10.2 최근 anomaly_score 확인

```sql
SELECT id, rack_idx, date, inserted
FROM anomaly_score
ORDER BY id DESC
LIMIT 20;
```

확인 기준:

```text
pipeline/run 실행 후 row가 추가되어야 함
rack_idx 값이 존재해야 함
date 값이 target_date와 같아야 함
```

---

### 10.3 최근 pipeline_run_log 확인

```sql
SELECT 
    id,
    ess_id,
    target_date,
    status,
    battery_count,
    saved_score_count,
    deleted_preprocessed_count,
    raw_file_path,
    preprocessed_file_path,
    result_file_path
FROM pipeline_run_log
ORDER BY id DESC
LIMIT 10;
```

확인 기준:

```text
status = success 또는 empty 또는 error
battery_count 값 존재
saved_score_count 값 존재
파일 경로 저장 여부 확인
```

---

### 10.4 개발용 원본 데이터 확인

```sql
SELECT *
FROM battery
ORDER BY inserted DESC
LIMIT 20;
```

---

### 10.5 monitoring_battery_sample 확인

```sql
SELECT *
FROM monitoring_battery_sample
ORDER BY measured_at, rack_no
LIMIT 20;
```

---

## 11. Parquet 파일 생성 확인

AI 파이프라인 실행 후 터미널에서 아래 명령어를 실행합니다.

```bat
dir files /s
```

정상 구조 예시:

```text
files
├── raw
│   └── KESCO_ESS_001
│       └── 2026-05-27
│           ├── battery_raw.parquet
│           └── metadata.json
│
├── preprocessed
│   └── KESCO_ESS_001
│       └── 2026-05-27
│           ├── battery_preprocessed.parquet
│           └── metadata.json
│
└── result
    └── KESCO_ESS_001
        └── 2026-05-27
            ├── anomaly_scores.parquet
            └── metadata.json
```

확인 기준:

```text
raw 폴더 생성
preprocessed 폴더 생성
result 폴더 생성
각 폴더에 parquet 파일 생성
각 폴더에 metadata.json 생성
```

---

## 12. 데이터 0건 empty 처리 테스트

데이터가 없는 날짜를 대상으로 파이프라인을 실행하면 `empty` 상태가 나와야 합니다.

### 12.1 `.env.dev` 임시 수정

테스트를 위해 `.env.dev`에서 아래 값을 임시로 변경합니다.

```env
TARGET_DATE_OFFSET_DAYS=-999
```

이렇게 하면 일반적으로 해당 날짜에 데이터가 없으므로 empty 테스트가 가능합니다.

---

### 12.2 서버 재실행

```bat
python main.py
```

---

### 12.3 Swagger에서 수동 실행

```http
POST /api/v1/pipeline/run
```

정상 empty 응답 예시:

```json
{
  "status": "empty",
  "run_id": 3,
  "target_date": "2023-09-02",
  "target_date_offset_days": -999,
  "ess_id": "KESCO_ESS_001",
  "battery_count": 0,
  "saved_score_count": 0,
  "deleted_preprocessed_count": 0,
  "raw_file_path": null,
  "preprocessed_file_path": null,
  "result_file_path": null,
  "message": "No battery data found for target date."
}
```

확인 기준:

```text
status = empty
battery_count = 0
saved_score_count = 0
raw_file_path = null
preprocessed_file_path = null
result_file_path = null
```

---

### 12.4 DB에서 empty 이력 확인

```sql
SELECT id, ess_id, target_date, status, battery_count, saved_score_count, message
FROM pipeline_run_log
ORDER BY id DESC
LIMIT 5;
```

확인 기준:

```text
status = empty
battery_count = 0
saved_score_count = 0
message = No battery data found for target date.
```

---

### 12.5 테스트 후 설정 복구

empty 테스트가 끝나면 `.env.dev` 값을 원래대로 복구합니다.

예:

```env
TARGET_DATE_OFFSET_DAYS=-1
```

또는 개발 상황에 맞게 기존 값으로 되돌립니다.

---

## 13. 테스트 중 자주 발생할 수 있는 문제

### 13.1 PostgreSQL 비밀번호 오류

증상:

```text
password authentication failed for user "kesco"
```

해결:

postgres 관리자 계정으로 접속 후 비밀번호를 다시 설정합니다.

```sql
ALTER USER kesco WITH PASSWORD 'kesco';
```

---

### 13.2 서버 포트 충돌

증상:

```text
Address already in use
```

원인:

이미 8000번 포트에서 서버가 실행 중일 수 있습니다.

해결:

기존 서버를 종료합니다.

```text
Ctrl + C
```

또는 `.env`에서 포트를 변경합니다.

```env
APP_PORT=8001
```

---

### 13.3 Parquet 저장 오류

증상:

```text
ImportError: Missing optional dependency 'pyarrow'
```

해결:

```bat
pip install pyarrow
```

또는 API 패키지를 다시 설치합니다.

```bat
pip install -r requirements-api.txt
```

---

### 13.4 Python 타입 문법 오류

증상:

```text
TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'
```

원인:

Python 3.8에서 `str | None` 문법을 사용했을 때 발생합니다.

해결:

```python
str | None
```

대신 아래처럼 사용합니다.

```python
Optional[str]
```

---

## 14. 테스트 완료 기준

아래 항목이 모두 확인되면 기본 기능 테스트가 완료된 것으로 봅니다.

```text
1. python main.py 서버 실행 성공
2. Swagger 접속 성공
3. GET /api/v1/health 성공
4. POST /api/v1/pipeline/run 성공
5. anomaly_score DB row 저장 확인
6. pipeline_run_log DB row 저장 확인
7. raw/preprocessed/result Parquet 파일 생성 확인
8. GET /api/v1/anomaly-scores/latest 성공
9. GET /api/v1/anomaly-scores?date=YYYY-MM-DD 성공
10. GET /api/v1/pipeline/runs/latest 성공
11. GET /api/v1/pipeline/runs 성공
12. 데이터 0건 empty 처리 확인
```

---

## 15. 테스트 후 정리

테스트 후 Git 상태를 확인합니다.

```bat
git status
```

`files/`, `.env`, `.env.dev`, `log/`가 Git 추적 대상에 올라오면 안 됩니다.

정상적으로는 코드와 문서 파일만 변경되어야 합니다.

예:

```text
modified:   README.md
modified:   TEST_GUIDE.md
modified:   service/schedule_service.py
```
