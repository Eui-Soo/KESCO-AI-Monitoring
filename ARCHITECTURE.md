# KERI Digital Twin - 아키텍처

## 개요
Pydantic V2 + dependency-injector 기반의 현대적인 FastAPI 애플리케이션입니다.
중앙 집중식 설정과 로깅 시스템으로 확장성과 유지보수성을 극대화했습니다.

## 프로젝트 구조

```
KERI-DigitalTwin/
├── main.py                  # FastAPI 앱 진입점
├── .env                     # 환경 설정 (프로덕션)
├── .env.dev                 # 환경 설정 (개발)
└── core/
    ├── setting/             # Pydantic V2 설정
    │   ├── settings.py      # Settings 모델
    │   └── README.md        # 설정 가이드
    ├── log/                 # 로깅 시스템
    │   ├── config.py        # setup_logging 함수
    │   ├── __init__.py
    │   └── README.md        # 로깅 가이드
    └── container/           # DI 컨테이너
        ├── container.py     # 싱글톤 관리
        ├── __init__.py
        └── README.md        # DI 컨테이너 가이드
```

## 핵심 컴포넌트

### 1. Settings (Pydantic V2)
**파일**: `core/setting/settings.py`

모든 애플리케이션 설정을 중앙화합니다:
- **Application 설정**: app_name, app_version, server_host, server_port, debug
- **Logging 설정**: log_backup_days, log_format 등
- **자동 검증**: ge/le, pattern, 커스텀 검증자
- **타입 안정성**: Literal, Path 사용

```python
settings = container.settings()  # Singleton
print(settings.app_name)
print(settings.server_port)
```

### 2. Logger (중앙 집중식 로깅)
**파일**: `core/log/config.py`

설정 기반의 로깅 시스템:
- **파일**: `log/app.log`
- **자동 로테이션**: 자정마다 파일 교체
- **자동 정리**: 설정된 일수 이상된 파일 자동 삭제
- **포맷**: `[YYYY-MM-DD HH:MM:SS] [LEVEL] message`

```python
logger = container.logger()  # Singleton
logger.info('메시지')
```

### 3. Container (DI 컨테이너)
**파일**: `core/container/container.py`

싱글톤 패턴으로 의존성 관리:
- **핵심 싱글톤**: Settings, Logger
- **향후 추가**: Database, Redis, Services 등
- **의존성 자동 주입**: `settings.provided.debug` 등

```python
from core.container import container

settings = container.settings()
logger = container.logger()
```

## 의존성 흐름

```
.env / .env.dev
       ↓
   Settings (Pydantic V2)
   ├── Application 설정
   ├── Logging 설정
   └── 검증 (Validators)
       ↓
   Logger (setup_logging)
       ↓
   main.py (FastAPI)
```

## 환경 설정

### .env (프로덕션)
```
APP_NAME=KERI-DigitalTwin
APP_VERSION=1.0.0
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
DEBUG=false
LOG_BACKUP_DAYS=60
```

### .env.dev (개발)
```
APP_NAME=KERI-DigitalTwin(Dev)
APP_VERSION=1.0.0
SERVER_HOST=127.0.0.1
SERVER_PORT=8000
DEBUG=true
LOG_BACKUP_DAYS=60
```

## FastAPI 앱

### 진입점: main.py
- **의존성 주입**: `container.settings()`, `container.logger()`
- **라이프사이클**: startup/shutdown hooks
- **Health Check**: GET `/health`
- **자동 문서**: Swagger UI, ReDoc

### 기본 엔드포인트
```python
@app.get('/health')
async def health_check():
    return {
        'status': 'healthy',
        'app': settings.app_name,
        'version': settings.app_version,
    }
```

## 로깅 시스템

### 파일 위치
- **현재 로그**: `log/app.log`
- **백업**: `log/app.log.2025-02-11` 등

### 로그 레벨
- **INFO**: 일반 정보 (기본)
- **WARNING**: 경고
- **ERROR**: 에러
- **DEBUG**: 디버그 정보 (DEBUG=true일 때만)

### 로그 예시
```
[2026-02-11 16:24:30] [INFO    ] ▶ KERI-DigitalTwin 시작 (v1.0.0)
[2026-02-11 16:24:31] [INFO    ] ◀ 종료
```

## 실행

### 프로덕션 실행
```bash
python main.py
```

### 개발 실행 (DEBUG=true)
```bash
cp .env.dev .env
python main.py
```

### 자동 리로드 (개발용)
```bash
uvicorn main:app --reload
```

## 서비스 추가 방법

### 1. 서비스 클래스 작성
```python
# service/my_service.py
class MyService:
    def __init__(self, settings: Settings):
        self.settings = settings
```

### 2. Container에 등록
```python
# core/container/container.py
my_service = providers.Singleton(
    MyService,
    settings=settings,
)
```

### 3. 사용
```python
service = container.my_service()
```

## 검증 예시

### Settings 검증 (자동)
```python
# 포트 범위 (1-65535)
server_port: int = Field(ge=1, le=65535)

# 버전 형식 (X.Y.Z)
app_version: str = Field(pattern=r'^\d+\.\d+\.\d+$')

# 로그 보관 기간 (1-3650일)
log_backup_days: int = Field(ge=1, le=3650)
```

## 코드 컨벤션

- **문자열**: 작은 따옴표 (`'`)
- **Docstring**: triple double quotes (`"""`)
- **속성명**: snake_case
- **의존성**: Settings 기반

## 주요 기술 스택

| 기술 | 목적 |
|------|------|
| **FastAPI** | 웹 프레임워크 |
| **Pydantic V2** | 데이터 검증 및 설정 관리 |
| **dependency-injector** | 의존성 주입 |
| **uvicorn** | ASGI 서버 |
| **python-logging** | 로깅 시스템 |

## 확장 가능성

이 아키텍처는 다음을 추가하기 쉽도록 설계되었습니다:

- **Database**: SQLAlchemy + db_service
- **Cache**: Redis + redis_service
- **Task Queue**: Celery + task_service
- **Authentication**: JWT + auth_service
- **Message Queue**: RabbitMQ + message_service

모두 Container에 `providers.Singleton()`으로 등록하면 됩니다.
