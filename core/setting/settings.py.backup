"""애플리케이션 설정

.env.dev / .env 파일의 환경변수를 읽어서
FastAPI 서버, DB, 파일 저장, 스케줄러 설정에 사용한다.

중요:
    DB 비밀번호에 특수문자가 포함될 수 있으므로
    DB URL 생성 시 quote_plus()로 인코딩한다.

하루 1회 자동 실행 시간 설정:
    SCHEDULE_HOUR=2
    SCHEDULE_MINUTE=30
    SCHEDULE_SECOND=0

위 예시는 매일 02:30:00에 AI 파이프라인을 실행한다.
"""

from functools import cached_property
from pathlib import Path
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 전체 설정"""

    # ============================================================
    # Application
    # ============================================================
    APP_NAME: str = "KESCO-DigitalTwin"
    APP_VERSION: str = "1.0.0"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = False

    # ============================================================
    # Logging
    # ============================================================
    LOG_BACKUP_DAYS: int = 60
    LOG_DIR: str = "log"

    # ============================================================
    # Files
    # ============================================================
    FILES_DIR: str = "files"

    # ============================================================
    # ESS
    # ============================================================
    DEFAULT_ESS_ID: str = "KESCO_ESS_001"

    # ============================================================
    # File retention
    # ============================================================
    PREPROCESSED_RETENTION_DAYS: int = 60

    # ============================================================
    # Scheduler
    # ============================================================
    # 하루에 한 번 실행할 시간
    # 예:
    #   SCHEDULE_HOUR=2
    #   SCHEDULE_MINUTE=30
    #   SCHEDULE_SECOND=0
    #   -> 매일 02:30:00 실행
    SCHEDULE_HOUR: int = 0
    SCHEDULE_MINUTE: int = 0
    SCHEDULE_SECOND: int = 30

    # 자동 실행 시 처리할 대상 날짜
    # 0  = 오늘 데이터 처리
    # -1 = 전날 데이터 처리
    TARGET_DATE_OFFSET_DAYS: int = -1

    # ============================================================
    # Database - AI 서버 로컬 결과 DB
    # ============================================================
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "kesco_digitaltwin"
    DB_USER: str = "kesco"
    DB_PASSWORD: str = "kesco"

    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_ECHO: bool = False

    # ============================================================
    # Remote Database - 관제시스템 원본 DB
    # ============================================================
    # 실제 접속 정보는 settings.py에 직접 쓰지 말고 .env.dev에 넣는다.
    DB_REMOTE_HOST: str = "localhost"
    DB_REMOTE_PORT: int = 5432
    DB_REMOTE_NAME: str = "kesco_digitaltwin"
    DB_REMOTE_USER: str = "kesco"
    DB_REMOTE_PASSWORD: str = "kesco"

    # ============================================================
    # Pydantic Settings
    # ============================================================
    model_config = SettingsConfigDict(
        env_file=(".env.dev", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # raw 원본 데이터 보관 기간
    RAW_RETENTION_DAYS: int = 10

    # 전처리 rolling 데이터 유지 기간
    ROLLING_PREPROCESS_DAYS: int = 7

    # AI 실행을 위한 최소 전처리 일수
    AI_MIN_PREPROCESS_DAYS: int = 7

    # AI 모델 루트 폴더
    AI_MODEL_ROOT: str = "model"
    
    
    FILES_DIR: str = "files"
    DEFAULT_ESS_ID: str = "KESCO_ESS_001"
    PREPROCESSED_RETENTION_DAYS: int = 60
    
    
    @cached_property
    def log_file(self) -> Path:
        """현재 로그 파일 경로"""

        return Path(self.LOG_DIR, "app.log")

    @cached_property
    def log_dir_path(self) -> Path:
        """로그 디렉토리 경로"""

        return Path(self.LOG_DIR)

    @cached_property
    def files_dir_path(self) -> Path:
        """Parquet 파일 저장 루트 디렉토리"""

        return Path(self.FILES_DIR)

    @cached_property
    def encoded_db_user(self) -> str:
        """로컬 DB 사용자명 URL 인코딩"""

        return quote_plus(self.DB_USER)

    @cached_property
    def encoded_db_password(self) -> str:
        """로컬 DB 비밀번호 URL 인코딩"""

        return quote_plus(self.DB_PASSWORD)

    @cached_property
    def encoded_remote_db_user(self) -> str:
        """원격 관제 DB 사용자명 URL 인코딩"""

        return quote_plus(self.DB_REMOTE_USER)

    @cached_property
    def encoded_remote_db_password(self) -> str:
        """원격 관제 DB 비밀번호 URL 인코딩"""

        return quote_plus(self.DB_REMOTE_PASSWORD)

    @cached_property
    def async_db_url(self) -> str:
        """AI 서버 로컬 결과 DB 접속 URL"""

        return (
            "postgresql+asyncpg://"
            f"{self.encoded_db_user}:{self.encoded_db_password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @cached_property
    def async_db_remote_url(self) -> str:
        """관제시스템 원본 DB 접속 URL"""

        return (
            "postgresql+asyncpg://"
            f"{self.encoded_remote_db_user}:{self.encoded_remote_db_password}"
            f"@{self.DB_REMOTE_HOST}:{self.DB_REMOTE_PORT}/{self.DB_REMOTE_NAME}"
        )

    def validate_schedule_time(self) -> None:
        """스케줄 시간 설정값 검증

        Settings 생성 시 자동 호출하지는 않는다.
        필요하면 main.py 또는 schedule_service.py에서 호출할 수 있다.
        """

        if not 0 <= self.SCHEDULE_HOUR <= 23:
            raise ValueError("SCHEDULE_HOUR must be between 0 and 23.")

        if not 0 <= self.SCHEDULE_MINUTE <= 59:
            raise ValueError("SCHEDULE_MINUTE must be between 0 and 59.")

        if not 0 <= self.SCHEDULE_SECOND <= 59:
            raise ValueError("SCHEDULE_SECOND must be between 0 and 59.")
