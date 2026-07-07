"""DB package

이 패키지는 AI API 서버에서 사용하는 DB 서비스를 외부로 제공한다.

구성:
    - DBLocalService:
        우리 AI 서버 로컬 DB 접근 서비스

    - DBRemoteService:
        관제시스템 원격 DB 접근 서비스

    - Base:
        SQLAlchemy ORM 모델들이 상속받는 Base 클래스

외부 사용 예:
    from core.db import DBLocalService, DBRemoteService, Base
"""

from core.db.db_service import Base, DBLocalService
from core.db.db_remote_service import DBRemoteService


__all__ = [
    "Base",
    "DBLocalService",
    "DBRemoteService",
]