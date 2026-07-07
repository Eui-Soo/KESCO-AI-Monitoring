"""의존성 주입 컨테이너

FastAPI 서버에서 사용하는 주요 객체들을 한 곳에서 생성하고 관리한다.

관리 대상:
    - Settings
    - Logger
    - DBLocalService
    - DBRemoteService
    - FileService
    - AIProcessingService
    - SchedulerService
"""

from dependency_injector import containers, providers

from core.db import DBLocalService, DBRemoteService
from core.log import setup_logging
from core.setting import Settings
from service.ai_service import AIProcessingService
from service.file_service import FileService
from service.schedule_service import SchedulerService
from service.preprocess_service import PreprocessService

class Container(containers.DeclarativeContainer):
    """싱글톤 의존성 관리 컨테이너"""

    # ============================================================
    # Settings
    # ============================================================
    settings = providers.Singleton(Settings)

    # ============================================================
    # Logger
    # ============================================================
    logger = providers.Singleton(
        setup_logging,
        settings=settings,
    )

    # ============================================================
    # Local DB Service
    # ============================================================
    db_local_service = providers.Singleton(
        DBLocalService,
        settings=settings,
    )

    # ============================================================
    # Remote DB Service
    # ============================================================
    remote_db_service = providers.Singleton(
        DBRemoteService,
        settings=settings,
    )

    # ============================================================
    # File Service
    # ============================================================
    file_service = providers.Singleton(
        FileService,
        settings=settings,
    )

    # ============================================================
    # AI Processing Service
    # ============================================================
    ai_processing_service = providers.Singleton(
        AIProcessingService,
    )

    preprocess_service = providers.Singleton(PreprocessService)
    
    # ============================================================
    # Scheduler Service
    # ============================================================
    scheduler_service = providers.Singleton(
        SchedulerService,
        settings=settings,
        remote_db_service=remote_db_service,
        db_local_service=db_local_service,
        file_service=file_service,
        preprocess_service=preprocess_service,
        ai_processing_service=ai_processing_service,
    )


container = Container()