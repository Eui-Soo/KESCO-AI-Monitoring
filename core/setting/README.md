# Settings (Pydantic V2)

## 개요
Pydantic V2를 사용한 통합 설정 관리 시스템입니다.
모든 애플리케이션 설정을 중앙에서 관리하며, 자동 검증을 지원합니다.

## Pydantic V2 기능

### 1. 자동 검증 (Validators)
```python
server_port: int = Field(
    default=8000,
    ge=1,           # 최소값: 1
    le=65535,       # 최대값: 65535
)

log_backup_days: int = Field(
    default=60,
    ge=1,           # 최소값: 1
    le=3650,        # 최대값: 3650일 (약 10년)
)

app_version: str = Field(
    pattern=r'^\d+\.\d+\.\d+$',  # SemVer 패턴
)
```

### 2. 타입 힌팅
```python
from typing import Literal

log_rotation_when: Literal['midnight'] = Field(
    default='midnight',
)
```

### 3. 커스텀 검증자
```python
from pydantic import field_validator

@field_validator('app_version')
@classmethod
def validate_version(cls, v: str) -> str:
    """앱 버전 SemVer 검증"""
    parts = v.split('.')
    if len(parts) != 3:
        raise ValueError('X.Y.Z 형식이어야 합니다')
    return v
```

### 4. 필드 설명
```python
app_name: str = Field(
    default='KERI Digital Twin',
    description='애플리케이션 이름'
)
```

## 모델 API

### 로드
```python
from core.container import container

settings = container.settings()  # Singleton
```

### 변환
```python
# Dict로 변환
settings_dict = settings.model_dump()

# JSON으로 변환
settings_json = settings.model_dump_json(indent=2)

# 특정 필드만 추출
partial = settings.model_dump(include={'app_name', 'debug'})
```

### Schema
```python
schema = settings.model_json_schema()
# JSON Schema 생성 (OpenAPI 문서화 등에 사용)
```

## 환경 변수 설정

### .env 파일
```
# Application
APP_NAME=KERI-DigitalTwin
APP_VERSION=1.0.0
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
DEBUG=false

# Logging
LOG_BACKUP_DAYS=60
```

### 환경 변수로도 설정 가능
```bash
export APP_NAME="My App"
export SERVER_PORT=9000
python main.py
```

## 검증 오류 예시

```python
# 포트 범위 초과
Settings(server_port=99999)
# ValidationError: Input should be less than or equal to 65535

# 잘못된 버전 형식
Settings(app_version='1.0')
# ValidationError: Version must be X.Y.Z format
```

## 설정 필드 목록

### Application
- `app_name`: 애플리케이션 이름
- `app_version`: 버전 (SemVer: X.Y.Z)
- `server_host`: 서버 호스트 주소
- `server_port`: 서버 포트 (1-65535)
- `debug`: 디버그 모드

### Logging
- `log_backup_days`: 로그 보관 일수 (1-3650)
- `log_dir`: 로그 디렉토리
- `log_file`: 로그 파일 경로
- `log_format`: 로그 포맷 문자열
- `log_date_format`: 로그 날짜 포맷
- `log_rotation_when`: 로그 로테이션 시간 (midnight)
- `log_rotation_interval`: 로그 로테이션 간격 (일)

## Best Practices

1. **싱글톤 사용**
   ```python
   from core.container import container
   settings = container.settings()  # 항상 같은 인스턴스
   ```

2. **환경별 설정**
   ```bash
   # 개발 환경
   cp .env.dev .env

   # 프로덕션 환경
   cp .env.prod .env
   ```

3. **검증 활용**
   - 범위 검증 (ge, le, gt, lt)
   - 패턴 검증 (pattern)
   - 커스텀 검증자 (field_validator)

4. **타입 안정성**
   - Literal로 고정값 지정
   - Path로 경로 자동 관리
   - 정확한 타입 힌팅
