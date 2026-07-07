# KESCO AI API Server 배포 및 실행 가이드

이 문서는 KESCO AI API Server를 새로운 PC 또는 개발 서버에서 실행하기 위한 설치 및 실행 절차를 정리한 문서입니다.

현재 기준은 **Windows 개발 PC + Anaconda 가상환경 + PostgreSQL + FastAPI 서버 실행** 구조입니다.

Docker 배포나 Linux 서버 배포는 추후 운영 환경이 확정된 뒤 별도 문서로 정리합니다.

---

## 1. 배포 대상

현재 배포 가이드는 아래 환경을 기준으로 합니다.

```text
OS: Windows 10 또는 Windows 11
Python: 3.8
가상환경: Anaconda 또는 Miniconda
DB: PostgreSQL 16
서버 프레임워크: FastAPI
실행 방식: python main.py
```

---

## 2. 전체 실행 구조

서버는 다음 흐름으로 실행됩니다.

```text
1. Python 가상환경 활성화
2. 필요한 패키지 설치
3. PostgreSQL DB 준비
4. .env 파일 설정
5. FastAPI 서버 실행
6. Swagger 접속
7. API 테스트
```

---

## 3. 사전 준비 프로그램

새 PC에서 서버를 실행하려면 아래 프로그램이 필요합니다.

### 3.1 Git

GitHub 저장소에서 코드를 내려받기 위해 필요합니다.

설치 확인:

```bat
git --version
```

정상 예시:

```text
git version 2.54.0.windows.1
```

---

### 3.2 Anaconda 또는 Miniconda

Python 가상환경을 만들기 위해 사용합니다.

설치 확인:

```bat
conda --version
```

---

### 3.3 PostgreSQL

AI 결과 DB와 개발용 테스트 DB로 사용합니다.

설치 확인:

```bat
"C:\Program Files\PostgreSQL\16\bin\psql.exe" --version
```

정상 예시:

```text
psql (PostgreSQL) 16.x
```

---

## 4. GitHub 저장소 받기

원하는 작업 폴더에서 아래 명령어를 실행합니다.

```bat
git clone https://github.com/Eui-Soo/KESCO-AI-API-Server.git
```

폴더 이동:

```bat
cd KESCO-AI-API-Server
```

현재 브랜치 확인:

```bat
git status
```

정상 예시:

```text
On branch main
Your branch is up to date with 'origin/main'.
nothing to commit, working tree clean
```

---

## 5. Python 가상환경 생성

Python 3.8 기준으로 가상환경을 생성합니다.

```bat
conda create -n kesco_api python=3.8 -y
```

가상환경 활성화:

```bat
conda activate kesco_api
```

정상적으로 활성화되면 터미널 앞에 아래처럼 표시됩니다.

```text
(kesco_api) C:\...
```

---

## 6. Python 패키지 설치

먼저 pip를 업데이트합니다.

```bat
python -m pip install --upgrade pip
```

API 서버 실행에 필요한 패키지를 설치합니다.

```bat
pip install -r requirements-api.txt
```

### 참고: requirements 파일 구분

이 프로젝트에는 requirements 파일이 여러 개 있습니다.

```text
requirements-api.txt
→ FastAPI 서버 실행에 필요한 최소 패키지

requirements-ai.txt
→ 실제 AI 모델 실행에 필요한 패키지

requirements.txt
→ 기존 전체 개발 환경 또는 통합 패키지
```

현재 API 서버 골격을 실행할 때는 `requirements-api.txt`를 우선 사용합니다.

실제 AI 모델을 연결할 때는 별도로 아래 명령을 실행합니다.

```bat
pip install -r requirements-ai.txt
```

---

## 7. PostgreSQL DB 준비

### 7.1 PostgreSQL 접속

관리자 계정으로 접속합니다.

```bat
"C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres
```

비밀번호는 PostgreSQL 설치 시 설정한 postgres 계정 비밀번호를 입력합니다.

---

### 7.2 사용자 및 DB 생성

psql 접속 후 아래 SQL을 실행합니다.

```sql
CREATE USER kesco WITH PASSWORD 'kesco';
CREATE DATABASE kesco_digitaltwin OWNER kesco;
GRANT ALL PRIVILEGES ON DATABASE kesco_digitaltwin TO kesco;
```

이미 사용자가 존재한다면 아래처럼 비밀번호만 다시 설정할 수 있습니다.

```sql
ALTER USER kesco WITH PASSWORD 'kesco';
```

종료:

```sql
\q
```

---

### 7.3 kesco 계정 접속 확인

```bat
"C:\Program Files\PostgreSQL\16\bin\psql.exe" -U kesco -d kesco_digitaltwin
```

비밀번호:

```text
kesco
```

정상 접속 시:

```text
kesco_digitaltwin=>
```

종료:

```sql
\q
```

---

## 8. 환경변수 파일 설정

`.env.example`을 참고하여 `.env` 또는 `.env.dev` 파일을 생성합니다.

개발 환경에서는 보통 `.env.dev`를 사용합니다.

```text
.env.dev
```

예시:

```env
# Application
APP_NAME=KESCO-DigitalTwin
APP_VERSION=1.0.0
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=false

# Logging
LOG_DIR=log
LOG_BACKUP_DAYS=60

# Files
FILES_DIR=files

# ESS
DEFAULT_ESS_ID=KESCO_ESS_001

# File retention
PREPROCESSED_RETENTION_DAYS=60

# Scheduler
SCHEDULE_HOUR=0
SCHEDULE_MINUTE=0
SCHEDULE_SECOND=30
TARGET_DATE_OFFSET_DAYS=-1

# Database - AI result DB
DB_HOST=localhost
DB_PORT=5432
DB_NAME=kesco_digitaltwin
DB_USER=kesco
DB_PASSWORD=kesco
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=1800
DB_ECHO=false

# Remote Database - monitoring system source DB
# 개발 중에는 로컬 DB를 관제시스템 DB처럼 사용
DB_REMOTE_HOST=localhost
DB_REMOTE_PORT=5432
DB_REMOTE_NAME=kesco_digitaltwin
DB_REMOTE_USER=kesco
DB_REMOTE_PASSWORD=kesco
```

주의:

```text
.env
.env.dev
```

이 파일들은 GitHub에 올리면 안 됩니다.

---

## 9. 서버 실행

프로젝트 루트에서 아래 명령어를 실행합니다.

```bat
python main.py
```

정상 실행 예시:

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

---

## 10. Swagger 접속

브라우저에서 아래 주소로 접속합니다.

```text
http://localhost:8000/docs
```

정상적으로 접속되면 API 문서 화면이 표시됩니다.

API 그룹:

```text
Health
Anomaly Scores
Pipeline
```

---

## 11. DB 테이블 자동 생성 확인

서버가 정상 실행되면 SQLAlchemy가 필요한 테이블을 자동 생성합니다.

psql 접속:

```bat
"C:\Program Files\PostgreSQL\16\bin\psql.exe" -U kesco -d kesco_digitaltwin
```

테이블 확인:

```sql
\dt
```

정상 예시:

```text
anomaly_score
battery
monitoring_battery_sample
pipeline_run_log
```

---

## 12. 기본 API 테스트

### 12.1 Health Check

```http
GET /api/v1/health
```

정상 기준:

```text
status = ok
HTTP 200
```

---

### 12.2 AI 파이프라인 수동 실행

```http
POST /api/v1/pipeline/run
```

정상 기준:

```text
status = success
run_id 값 존재
battery_count > 0
saved_score_count > 0
```

데이터가 없는 날짜라면 정상적으로 아래처럼 나올 수 있습니다.

```text
status = empty
battery_count = 0
saved_score_count = 0
```

---

### 12.3 최신 AI 결과 조회

```http
GET /api/v1/anomaly-scores/latest
```

---

### 12.4 날짜별 AI 결과 조회

```http
GET /api/v1/anomaly-scores?date=2026-05-27
```

---

### 12.5 최신 파이프라인 실행 이력 조회

```http
GET /api/v1/pipeline/runs/latest
```

---

### 12.6 최근 파이프라인 실행 이력 목록 조회

```http
GET /api/v1/pipeline/runs?limit=20
```

---

## 13. Parquet 파일 저장 확인

파이프라인 실행 후 아래 명령어로 파일 생성 여부를 확인합니다.

```bat
dir files /s
```

정상 구조 예시:

```text
files/
├── raw/
│   └── KESCO_ESS_001/
│       └── 2026-05-27/
│           ├── battery_raw.parquet
│           └── metadata.json
│
├── preprocessed/
│   └── KESCO_ESS_001/
│       └── 2026-05-27/
│           ├── battery_preprocessed.parquet
│           └── metadata.json
│
└── result/
    └── KESCO_ESS_001/
        └── 2026-05-27/
            ├── anomaly_scores.parquet
            └── metadata.json
```

---

## 14. 실행 이력 DB 확인

psql에서 아래 쿼리를 실행합니다.

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

정상 기준:

```text
status = success, empty, error 중 하나
target_date 존재
battery_count 존재
saved_score_count 존재
```

---

## 15. 서버 종료

터미널에서 아래 키를 입력합니다.

```text
Ctrl + C
```

정상 종료 시 스케줄러와 DB 연결도 함께 종료됩니다.

---

## 16. 자주 발생하는 문제와 해결

### 16.1 PostgreSQL 비밀번호 오류

증상:

```text
password authentication failed for user "kesco"
```

해결:

postgres 관리자 계정으로 접속 후 비밀번호 재설정:

```sql
ALTER USER kesco WITH PASSWORD 'kesco';
```

---

### 16.2 8000번 포트 충돌

증상:

```text
Address already in use
```

해결:

기존 실행 중인 서버를 종료합니다.

```text
Ctrl + C
```

또는 `.env.dev`에서 포트를 변경합니다.

```env
APP_PORT=8001
```

---

### 16.3 pyarrow 오류

증상:

```text
ImportError: Missing optional dependency 'pyarrow'
```

해결:

```bat
pip install pyarrow
```

또는:

```bat
pip install -r requirements-api.txt
```

---

### 16.4 Python 타입 문법 오류

증상:

```text
TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'
```

원인:

Python 3.8 환경에서 `str | None` 문법을 사용했을 때 발생합니다.

해결:

```python
str | None
```

대신 아래처럼 작성합니다.

```python
Optional[str]
```

---

### 16.5 데이터 0건으로 empty가 나오는 경우

증상:

```json
{
  "status": "empty",
  "battery_count": 0
}
```

원인:

대상 날짜에 조회된 배터리 데이터가 없는 경우입니다.

확인할 것:

```text
TARGET_DATE_OFFSET_DAYS 설정값
battery 테이블 데이터 날짜
관제 DB 조회 조건
```

현재 개발 환경에서는 `.env.dev`의 `TARGET_DATE_OFFSET_DAYS` 값에 따라 조회 날짜가 달라집니다.

---

## 17. GitHub 반영 방법

수정 파일 확인:

```bat
git status
```

변경 파일 추가:

```bat
git add .
```

커밋:

```bat
git commit -m "Update deployment documentation"
```

푸시:

```bat
git push
```

주의:

아래 파일과 폴더는 GitHub에 올리지 않습니다.

```text
.env
.env.dev
files/
log/
__pycache__/
```

---

## 18. 현재 배포 단계의 한계

현재 배포 방식은 개발용 실행 방식입니다.

```text
python main.py
```

실제 운영 배포에서는 아래 사항을 추가 검토해야 합니다.

```text
1. Windows 서비스 등록 또는 Linux systemd 서비스 등록
2. 서버 자동 재시작 정책
3. 로그 파일 일자별 관리
4. DB 백업 정책
5. Parquet 파일 보관 정책
6. 방화벽 및 포트 정책
7. 실제 관제시스템 DB 접속 정보 적용
8. 실제 AI 모델 및 전처리 코드 연결
```

---

## 19. 향후 운영 배포 후보

운영 환경이 확정되면 아래 방식 중 하나를 선택할 수 있습니다.

### 19.1 Windows 직접 실행

```text
Anaconda 가상환경
python main.py
작업 스케줄러 또는 NSSM으로 서비스화
```

### 19.2 Linux 서버 실행

```text
Python venv
systemd 서비스
Nginx reverse proxy
PostgreSQL 연동
```

### 19.3 Docker 배포

```text
Dockerfile
docker-compose.yml
PostgreSQL container 또는 외부 DB 연결
```

현재 단계에서는 Windows 개발 PC 기준 실행 방식을 우선 사용합니다.
