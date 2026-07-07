# KESCO AI API Server (KESCO Digital Twin)

관제시스템에 연결되는 **ESS 배터리 이상치 탐지 AI 스케줄러 서버**입니다.

매일 정해진 시각에 관제시스템 DB에서 여러 ESS 사이트의 배터리 셀 전압 데이터를
자동으로 가져와, 전처리 후 STGCN 딥러닝 모델로 셀 단위 이상치 점수(0.00 ~ 1.00)를
계산하고, 그 결과를 AI 서버 자체 로컬 DB에 저장합니다.

---

## 목차

1. [이 프로젝트가 하는 일](#1-이-프로젝트가-하는-일)
2. [전체 구조 한눈에 보기](#2-전체-구조-한눈에-보기)
3. [핵심 개념 용어 정리](#3-핵심-개념-용어-정리)
4. [폴더 구조](#4-폴더-구조)
5. [매일 실행되는 파이프라인 9단계](#5-매일-실행되는-파이프라인-9단계)
6. [설치 및 실행 방법](#6-설치-및-실행-방법)
7. [환경 변수(.env) 설명](#7-환경-변수env-설명)
8. [API 목록](#8-api-목록)
9. [AI 모델 설명](#9-ai-모델-설명)
10. [자주 겪는 문제 (트러블슈팅)](#10-자주-겪는-문제-트러블슈팅)

---

## 1. 이 프로젝트가 하는 일

기존에 여러 개의 ESS(에너지 저장 장치) 사이트를 관리하는 **관제시스템**이 이미 있습니다.
이 프로젝트는 그 관제시스템 옆에 붙는 **별도의 AI 분석 서버**입니다.

동작을 한 문장으로 요약하면 다음과 같습니다.

> "관제시스템 DB에서 배터리 데이터를 읽어와 → AI로 이상치를 분석하고 → 결과를 우리 DB에 저장한다."

중요한 원칙 두 가지가 있습니다.

- **관제시스템 DB는 절대 수정하지 않습니다.** 오직 읽기(READ)만 합니다.
- **분석 결과는 관제 DB가 아니라 AI 서버 자체의 로컬 DB에 저장합니다.** 관제시스템은
  이 로컬 DB나 조회 API를 통해 결과를 가져갑니다.

---

## 2. 전체 구조 한눈에 보기

```
  ┌────────────────────┐        읽기 전용         ┌──────────────────────┐
  │   관제시스템 DB      │  ◀───────────────────   │   KESCO AI 서버       │
  │  (원격 PostgreSQL)  │   배터리 데이터 조회      │  (이 프로젝트)         │
  └────────────────────┘                          │                      │
                                                  │  1. 데이터 수집        │
                                                  │  2. 전처리            │
                                                  │  3. AI 이상치 분석     │
                                                  │  4. 결과 저장          │
                                                  │        │             │
                                                  │        ▼             │
                                                  │  ┌────────────────┐  │
                                                  │  │  로컬 결과 DB    │  │
                                                  │  │ (PostgreSQL)   │  │
                                                  │  └────────────────┘  │
                                                  └──────────────────────┘
```

핵심 기술 스택은 다음과 같습니다.

| 역할 | 사용 기술 |
|------|-----------|
| 웹 서버 프레임워크 | FastAPI + Uvicorn |
| 설정 관리 | Pydantic Settings (.env 파일 읽기) |
| 의존성 관리 | dependency-injector (싱글톤) |
| 데이터베이스 접근 | SQLAlchemy 2.0 (async) + asyncpg |
| 자동 실행(스케줄러) | APScheduler |
| 데이터 처리 | pandas + pyarrow (Parquet 파일) |
| AI 모델 | TensorFlow / Keras (STGCN 오토인코더) |

---

## 3. 핵심 개념 용어 정리

처음 보면 헷갈리는 용어를 먼저 정리합니다.

- **ESS**: Energy Storage System. 배터리 에너지 저장 장치입니다.
- **BMS**: Battery Management System. 배터리를 관리하는 장치이며, 데이터의 단위 식별자로 쓰입니다.
- **관제시스템 / 관제 DB / 원격 DB**: 이미 운영 중인 상위 시스템입니다. 원본 배터리 데이터가 여기 있습니다.
- **로컬 DB**: 이 AI 서버가 직접 관리하는 데이터베이스입니다. 분석 결과가 여기 저장됩니다.
- **파이프라인(Pipeline)**: "데이터 수집 → 전처리 → AI 분석 → 저장"으로 이어지는 일련의 처리 과정입니다.
- **이상치 점수(Anomaly Score)**: 배터리 셀이 얼마나 비정상적인지를 0.00 ~ 1.00 사이 숫자로 나타낸 값입니다.
- **셀(Cell)**: 배터리를 구성하는 가장 작은 단위입니다. 이 시스템은 셀 20개 각각을 분석합니다.
- **Parquet**: 표 형태 데이터를 효율적으로 저장하는 파일 형식입니다. 중간 데이터를 파일로 남겨둡니다.

이상치 점수에 따른 등급 기준은 다음과 같습니다.

| 점수 범위 | 등급 | 의미 |
|-----------|------|------|
| 0.00 이상 ~ 0.50 미만 | Normal | 정상 |
| 0.50 이상 ~ 0.70 미만 | Caution | 주의 |
| 0.70 이상 ~ 0.85 미만 | Warning | 경고 |
| 0.85 이상 ~ 1.00 이하 | Danger | 위험 |

---

## 4. 폴더 구조

```
kesco/
├── main.py                  # 프로그램 시작점 (FastAPI 앱)
├── .env                     # 환경 설정 파일 (실제 값)
├── .env.example             # 환경 설정 예시 파일
├── requirements.txt         # 필요한 파이썬 패키지 목록
│
├── core/                    # 핵심 공통 모듈
│   ├── setting/             # 설정 (Settings 클래스)
│   ├── log/                 # 로깅 설정
│   ├── container/           # 의존성 주입 컨테이너
│   ├── db/                  # DB 연결 서비스 (로컬 + 원격)
│   └── model/               # DB 테이블 정의 (SQLAlchemy 모델)
│
├── service/                 # 비즈니스 로직 (실제 일하는 계층)
│   ├── schedule_service.py  # 스케줄러 + 파이프라인 오케스트레이션 (가장 중요)
│   ├── preprocess_service.py# 데이터 전처리
│   ├── ai_service.py        # AI 실행 래퍼
│   └── file_service.py      # Parquet 파일 저장/정리
│
├── ai/
│   └── ai_process.py        # 실제 STGCN AI 추론 코드
│
├── repo/                    # DB 쿼리 담당 계층 (Repository)
│   ├── battery_repo.py      # 관제 DB 배터리 데이터 조회
│   ├── remote_site_repo.py  # 관제 DB 사이트/장치 조회
│   ├── site_repo.py         # 로컬 DB 사이트/장치 저장·조회
│   ├── anomaly_repo.py      # 로컬 DB 이상치 결과 저장·조회
│   └── pipeline_run_repo.py # 로컬 DB 실행 이력 저장·조회
│
├── router/                  # API 엔드포인트 정의
│   ├── health_router.py     # 서버 상태 확인
│   ├── site_router.py       # 사이트/장치 조회 및 동기화
│   ├── pipeline_router.py   # 파이프라인 수동 실행 및 이력 조회
│   └── anomaly_router.py    # AI 결과 조회
│
├── model_backup/            # AI 모델 가중치 파일 (LG, samsung × fold 10개)
├── files/                   # 중간 데이터 저장소 (raw / preprocess / result)
└── log/                     # 로그 파일
```

계층 흐름은 이렇게 이해하면 쉽습니다.

```
router (API 입구)  →  service (일 처리)  →  repo (DB 쿼리)  →  DB
```

---

## 5. 매일 실행되는 파이프라인 9단계

스케줄러는 매일 정해진 시각에 아래 과정을 **활성화된 모든 사이트/BMS마다** 반복 실행합니다.
(실행 전, 관제 DB의 사이트/장치 목록을 로컬 DB로 먼저 자동 동기화합니다.)

1. **실행 이력 시작 기록** — `pipeline_run_log` 테이블에 "시작" 기록을 남깁니다.
2. **관제 DB에서 하루치 데이터 조회** — 해당 날짜의 배터리 셀 전압 원본을 읽어옵니다.
3. **원본 저장 + 오래된 원본 정리** — `files/raw/`에 Parquet로 저장하고, 보관 기간(기본 10일)이 지난 것은 삭제합니다.
4. **전처리** — 데이터를 5분 간격 288개 지점으로 정리하고 셀 전압 컬럼 이름을 통일합니다.
5. **전처리 결과 저장 + 정리** — `files/preprocess/`에 저장하고, rolling 기간(기본 7일)이 지난 것은 삭제합니다.
6. **7일 게이트 확인** — 전처리된 데이터가 아직 7일치가 안 되면 `waiting_7days` 상태로 두고 AI는 건너뜁니다.
7. **AI 이상치 분석** — 7일치가 쌓였으면 최근 7일 데이터를 모아 STGCN 모델로 셀별 점수를 계산합니다.
8. **결과 저장** — 결과를 `files/result/` Parquet 파일과 로컬 DB `anomaly_score` 테이블에 저장합니다.
9. **실행 이력 마감** — `success` / `empty` / `error` 중 하나로 이력을 마무리합니다.

> **7일 게이트가 왜 있나요?** AI 모델이 정확히 예측하려면 최근 7일치 데이터가 필요하기 때문입니다.
> 처음 배포한 날에는 데이터가 부족하므로, 7일이 쌓일 때까지는 데이터만 모으고 분석은 미룹니다.

---

## 6. 설치 및 실행 방법

### 6.1. 사전 준비

- Python **3.9** (권장 — AI 라이브러리 버전 제약 때문에 3.8~3.9만 지원)
- PostgreSQL (로컬 결과 DB용)
- 관제시스템 DB 접속 정보 (호스트, 포트, 사용자, 비밀번호)

### 6.2. 패키지 설치

```bash
# 가상환경 생성 (권장)
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt
```

### 6.3. 환경 설정

```bash
# 예시 파일을 복사해서 실제 설정 파일을 만듭니다
cp .env.example .env

# .env 파일을 열어 DB 접속 정보 등을 실제 값으로 수정합니다
```

### 6.4. AI 모델 폴더 준비 (중요)

AI 추론 코드는 기본적으로 `model/` 폴더에서 모델 가중치를 찾습니다.
현재 저장소에는 가중치가 `model_backup/` 폴더에 들어 있으므로, 아래 중 하나를 선택합니다.

```bash
# 방법 1) 폴더 이름 변경 (가장 간단)
mv model_backup model

# 방법 2) 환경 변수로 위치 지정 (폴더는 그대로 두고 싶을 때)
export ESS_MODEL_ROOT=model_backup    # Windows: set ESS_MODEL_ROOT=model_backup
```

### 6.5. 서버 실행

```bash
python main.py
```

실행되면 브라우저에서 아래 주소로 접속할 수 있습니다.

- API 문서 (Swagger): `http://localhost:8000/docs`
- 서버 상태 확인: `http://localhost:8000/api/v1/health`

---

## 7. 환경 변수(.env) 설명

| 변수 이름 | 기본값 | 설명 |
|-----------|--------|------|
| `APP_NAME` | KESCO-DigitalTwin | 애플리케이션 이름 |
| `APP_VERSION` | 1.0.0 | 버전 |
| `APP_HOST` | 0.0.0.0 | 서버 바인딩 주소 |
| `APP_PORT` | 8000 | 서버 포트 |
| `DEBUG` | false | 디버그 모드 (개발 시 true) |
| `LOG_DIR` | log | 로그 저장 폴더 |
| `LOG_BACKUP_DAYS` | 60 | 로그 파일 보관 일수 |
| `FILES_DIR` | files | 중간 데이터 저장 폴더 |
| `SCHEDULE_HOUR` | 0 | 자동 실행 시각 (시) |
| `SCHEDULE_MINUTE` | 0 | 자동 실행 시각 (분) |
| `SCHEDULE_SECOND` | 30 | 자동 실행 시각 (초) |
| `TARGET_DATE_OFFSET_DAYS` | -1 | 분석 대상 날짜 (0=오늘, -1=어제) |
| `RAW_RETENTION_DAYS` | 10 | 원본 데이터 보관 일수 |
| `ROLLING_PREPROCESS_DAYS` | 7 | 전처리 데이터 rolling 보관 일수 |
| `AI_MIN_PREPROCESS_DAYS` | 7 | AI 실행에 필요한 최소 전처리 일수 |
| `AI_MODEL_ROOT` | model | AI 모델 루트 폴더 |
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | - | **로컬 결과 DB** 접속 정보 |
| `DB_REMOTE_HOST` / `DB_REMOTE_PORT` / `DB_REMOTE_NAME` / `DB_REMOTE_USER` / `DB_REMOTE_PASSWORD` | - | **관제 원격 DB** 접속 정보 |

> `SCHEDULE_HOUR=2`, `SCHEDULE_MINUTE=30`, `SCHEDULE_SECOND=0` 으로 설정하면 매일 새벽 02:30:00에 실행됩니다.

---

## 8. API 목록

서버 실행 후 `/docs`에서 직접 테스트할 수 있습니다.

### 상태 확인
- `GET /api/v1/health` — 서버가 살아있는지 확인

### 사이트 / 장치 (Sites)
- `GET  /api/v1/sites/remote` — 관제 DB의 사이트/장치 목록 직접 조회
- `GET  /api/v1/sites/device-type-summary` — 관제 DB 장치 유형 분포 조회
- `POST /api/v1/sites/sync` — 관제 DB 목록을 로컬 DB로 동기화
- `GET  /api/v1/sites` — 로컬 DB 사이트/장치 목록 조회
- `GET  /api/v1/sites/{site_no}` — 특정 사이트 상세 조회

### 파이프라인 (Pipeline)
- `POST /api/v1/pipeline/run` — AI 파이프라인 수동 실행 (개발/테스트/장애 대응용)
- `GET  /api/v1/pipeline/schedule` — 현재 자동 실행 스케줄 조회
- `GET  /api/v1/pipeline/runs/latest` — 가장 최근 실행 이력 조회
- `GET  /api/v1/pipeline/runs` — 최근 실행 이력 목록 조회

### AI 결과 (Anomaly Scores)
- `GET  /api/v1/anomaly-scores/latest` — 가장 최근 AI 결과 조회
- `GET  /api/v1/anomaly-scores?date=YYYY-MM-DD` — 특정 날짜 AI 결과 조회

---

## 9. AI 모델 설명

이 프로젝트의 AI는 **STGCN 오토인코더(Autoencoder)** 라는 딥러닝 모델을 사용합니다.

- **오토인코더**란: 정상 데이터를 학습해서 "정상이라면 이렇게 생겼을 것"을 재구성하는 모델입니다.
  실제 데이터가 재구성 결과와 많이 다르면(재구성 오차가 크면) "비정상"으로 판단합니다.
- **STGCN**이란: 시간(Temporal)과 셀 간의 연결 관계(Graph)를 함께 보는 신경망입니다.
  배터리 셀들은 서로 영향을 주고받으므로, 이 관계를 반영해 더 정확하게 분석합니다.

동작 방식을 단계별로 보면:

1. 데이터의 제조사(samsung / lg)를 감지합니다.
2. 해당 제조사의 학습된 모델 10개(fold1 ~ fold10)를 불러옵니다. (한 번 불러오면 캐싱)
3. 각 모델이 재구성 오차를 계산하고, 이를 이상치 점수(0 ~ 1)로 변환합니다.
4. 10개 모델의 점수를 **최댓값(max)으로 앙상블**하여 최종 점수를 만듭니다.
5. 셀 20개 각각의 점수와 등급(Normal/Caution/Warning/Danger), 그리고 최대·평균 점수를 산출합니다.

모델 파일 구조는 다음과 같습니다.

```
model/  (또는 model_backup/)
├── samsung/
│   ├── fold1/
│   │   ├── A.npy                    # 셀 간 연결 관계 행렬
│   │   ├── value_cols.json          # 사용하는 컬럼 목록
│   │   ├── train_norm_stats.npz     # 정규화 통계값
│   │   └── stgcn_..._fold1_...h5    # 학습된 가중치
│   └── ... fold10/
└── LG/
    └── ... fold10/
```

---

## 10. 자주 겪는 문제 (트러블슈팅)

**Q. AI 실행 시 `FileNotFoundError`가 납니다.**
A. 모델 폴더 경로 문제입니다. `model/` 폴더가 있는지 확인하거나, `ESS_MODEL_ROOT=model_backup`
환경 변수를 설정하세요. ([6.4 참고](#64-ai-모델-폴더-준비-중요))

**Q. 결과가 계속 `waiting_7days`로 나옵니다.**
A. 정상입니다. 전처리 데이터가 7일치 쌓여야 AI가 실행됩니다. 하루에 한 번씩 데이터가 쌓이므로
배포 후 7일이 지나야 실제 분석이 시작됩니다.

**Q. `TypeError`가 나거나 패키지 설치가 실패합니다.**
A. Python 버전을 확인하세요. AI 라이브러리(TensorFlow 2.5, numpy 1.19.5 등) 제약으로
**Python 3.8 ~ 3.9**에서만 정상 동작합니다.

**Q. 관제 DB 연결이 안 됩니다.**
A. `.env`의 `DB_REMOTE_*` 값을 확인하세요. `GET /api/v1/sites/remote`를 호출하면
관제 DB 연결이 정상인지 바로 확인할 수 있습니다.

**Q. 스케줄러를 기다리지 않고 지금 바로 테스트하고 싶어요.**
A. `POST /api/v1/pipeline/run`을 호출하면 파이프라인을 수동으로 1회 실행할 수 있습니다.
특정 날짜/사이트만 실행하려면 `?date=2026-07-05&site_no=1&bms_id=BMS001` 처럼 파라미터를 붙이세요.
