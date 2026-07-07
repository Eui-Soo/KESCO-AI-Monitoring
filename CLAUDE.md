# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

KERI Digital Twin은 ESS(배터리 에너지 저장 시스템)의 이상치를 탐지하는 FastAPI 기반 애플리케이션입니다. 매일 자정 원격 DB에서 배터리 데이터를 수집하여 Parquet 파일로 저장하고, AI 이상치 점수를 로컬 DB에 등록합니다.

### Key Technologies
- **Framework**: FastAPI + Uvicorn
- **Configuration**: Pydantic V2 (BaseSettings)
- **Dependency Injection**: dependency-injector (싱글톤 패턴)
- **ORM**: SQLAlchemy 2.0 async (asyncpg 드라이버)
- **Scheduler**: APScheduler (AsyncIOScheduler)
- **Data**: pandas + pyarrow (Parquet)

## Development Commands

```bash
# 실행
python main.py

# 개발 모드 (.env.dev를 .env로 복사 → DEBUG=true, DB_ECHO=true, 콘솔 로그 출력)
cp .env.dev .env
python main.py
```

## Architecture Overview

### 전체 의존성 흐름
```
.env / .env.dev
    ↓
Settings (Pydantic V2, core/setting/settings.py)
    ↓
Container (dependency_injector, core/container/container.py)
    ├── DBLocalService  ← 로컬 PostgreSQL (연결 풀)
    ├── DBRemoteService ← 원격 PostgreSQL (NullPool)
    ├── FileService     ← Parquet 저장
    ├── AIProcessingService ← 이상치 계산 (동기 함수를 ThreadPoolExecutor로 실행)
    └── SchedulerService ← 일일 파이프라인 오케스트레이션
    ↓
main.py (FastAPI lifespan)
    1. init_db() → 로컬 DB 테이블 생성 (create_all)
    2. scheduler.start() → 파이프라인 스케줄 등록
```

### 일일 파이프라인 (SchedulerService._process)
```
[1/3] DBRemoteService.find_battery_by_date()
          ↓ List[dict] (cv_1~20, index, date)
[2/3] FileService.save()
          ↓ files/YYYY-MM-DD/NN/Rack_NN.parquet
[3/3] AIProcessingService.process() → DBLocalService.save_anomaly_scores()
          ↓ anomaly_score 테이블 (sc_c1~sc_c20, Rack당 1행)
```

### DB 연결 전략
- **로컬 DB** (`DBLocalService`): asyncpg + 연결 풀 (pool_size=5, max_overflow=10)
- **원격 DB** (`DBRemoteService`): asyncpg + **NullPool** — 세션마다 연결/종료, 원격 부하 최소화

### 계층 구조 (Layer)
서비스는 직접 SQL을 쓰지 않고 `repo/` 계층에 위임합니다.
- `repo/battery_repo.py` → `DBRemoteService`에서 직접 import (순환 없음)
- `repo/anomaly_repo.py` → `DBLocalService.save_anomaly_scores()` **메서드 본문 안**에서 지연 import (순환 차단, 아래 참고)

### 동기 AI 함수와 비동기 프레임워크
`ai/ai_process.py`의 `ai_process()`는 CPU 연산이 있는 **동기 함수**입니다.
이를 async 이벤트 루프에서 직접 호출하면 FastAPI 전체가 블로킹됩니다.
`AIProcessingService`는 `run_in_executor`로 스레드에서 실행합니다.

```python
# service/ai_service.py
loop = asyncio.get_running_loop()
scores = await loop.run_in_executor(None, ai_process, data)
```

`ai_process()`를 구현할 때 `async def`로 바꾸지 말고 반드시 **일반 `def`**를 유지해야 합니다.

## Critical Gotchas

### `main.py`의 `import core.model` 필수
`main.py` 최상단의 `import core.model  # noqa: F401`을 절대 제거하지 말 것.
이 import가 없으면 `Base.metadata`에 `AnomalyScore` 모델이 등록되지 않아
`init_db()` 호출 시 `create_all()`이 아무 테이블도 생성하지 않습니다.

### 순환 임포트 주의
`core/db/__init__.py` → `db_service.py` → `repo/anomaly_repo.py` → `core/model/models.py` → `core/db` 순환 발생.
`DBLocalService.save_anomaly_scores()` 내부의 `AnomalyScoreRepository` import는 **반드시 메서드 본문 안에** 유지해야 합니다.

```python
# 올바른 패턴 (지연 import로 순환 차단)
async def save_anomaly_scores(self, scores):
    from repo.anomaly_repo import AnomalyScoreRepository  # ← 메서드 안에 있어야 함
    ...
```

### `models.py`의 `from __future__ import annotations` 필수
제거하면 SQLAlchemy `Mapped[date]`에서 `date` 타입과 필드명이 충돌하여
`TypeError: Parameters to generic types must be types` 발생.

## Environment Configuration

```
# 필수
APP_NAME=...
APP_VERSION=...
APP_HOST=0.0.0.0
APP_PORT=8000

# 로컬 DB (기본값: keri_dt / 실제 개발 환경: keri_digitaltwin)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=keri_digitaltwin
DB_USER=keri
DB_PASSWORD=keri

# 원격 DB
DB_REMOTE_HOST=...
DB_REMOTE_PORT=5432
DB_REMOTE_NAME=...
DB_REMOTE_USER=...
DB_REMOTE_PASSWORD=...

# 선택 (괄호 안은 기본값)
DEBUG=false
LOG_DIR=log
LOG_BACKUP_DAYS=60
FILES_DIR=files
DB_ECHO=false
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=1800   # 초 단위, 30분
```

- `.env.dev` → `.env` 순서로 읽음 (**.env가 우선** — 뒤에 오는 파일이 앞을 override)
- `case_sensitive=True`: 대문자 키만 인식

## Scheduler 설정

`service/schedule_service.py`에서 두 가지 trigger 블록이 있습니다.
- **date trigger** (즉시 1회 실행, **현재 활성**): 개발·테스트용
- **cron trigger** (프로덕션): `""" ... """` 주석 안에 있음, `hour=0, minute=0, second=30`

프로덕션 배포 시 date trigger를 제거하고 cron 블록을 활성화합니다.

## Code Style & Conventions

- **문자열**: 작은 따옴표 (`'`)
- **Docstring**: triple double quotes (`"""`)
- **환경변수/설정 필드**: 대문자 (`APP_NAME`, `DB_HOST`)
- **함수/메서드**: snake_case
- **로거**: 모든 모듈에서 `logging.getLogger('app')` 사용 (전역 `app` 로거 공유)
- `from __future__ import annotations`는 `models.py`에 필수 (위 주의사항 참고)

## Adding a New Service

1. `service/my_service.py` 작성
2. `core/container/container.py`에 등록:
   ```python
   my_service = providers.Singleton(MyService, settings=settings)
   ```
3. 필요한 곳에서 `container.my_service()` 호출

DB 접근이 필요하면 `repo/` 아래에 Repository 클래스를 만들어 서비스에서 주입받습니다.
