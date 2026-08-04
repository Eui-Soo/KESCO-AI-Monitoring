"""관제 원격 DB 서비스

이 파일은 원격 관제 DB에서 데이터를 읽기만 한다.

중요:
    - 이 서비스는 AIService / AIProcessingService를 import하면 안 된다.
    - 원격 DB는 READ ONLY 용도로 사용한다.
    - AI 처리와 결과 저장은 schedule_service.py / db_service.py 쪽에서 처리한다.
"""

import logging
from datetime import date
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from core.setting import Settings
from repo.battery_repo import BatteryRepository
from repo.remote_site_repo import RemoteSiteRepository


logger = logging.getLogger("app")


class DBRemoteService:
    """관제 원격 DB 조회 서비스"""

    def __init__(self, settings: Settings):
        self._settings = settings

        self._engine: AsyncEngine = create_async_engine(
            settings.async_db_remote_url,
            poolclass=NullPool,
            pool_pre_ping=True,
            echo=settings.DB_ECHO,
            future=True,
        )

        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

        self._battery_repo = BatteryRepository()
        self._site_repo = RemoteSiteRepository()

        logger.info("✅ DBRemoteService 초기화 완료")

    async def find_battery_by_date(
        self,
        target_date: date,
        site_no: Optional[int] = None,
        bms_id: Optional[str] = None,
    ) -> List[dict]:
        """관제 DB에서 특정 날짜의 배터리 원본 데이터를 조회한다."""

        async with self._session_factory() as session:
            rows = await self._battery_repo.find_by_date(
                session=session,
                target_date=target_date,
                site_no=site_no,
                bms_id=bms_id,
            )

        logger.info(
            "✅ 원격 배터리 데이터 조회 완료 "
            f"[target_date={target_date}, site_no={site_no}, "
            f"bms_id={bms_id}, count={len(rows)}건]"
        )

        return rows

    async def find_sites(self) -> List[Dict]:
        """관제 DB에서 사이트/장치 목록을 조회한다."""

        async with self._session_factory() as session:
            rows = await self._site_repo.find_sites(session)

        logger.info(f"✅ 원격 사이트/장치 목록 조회 완료: {len(rows)}건")

        return rows

    async def find_device_type_summary(self) -> List[Dict]:
        """관제 DB 장치 유형/용도 분포를 조회한다."""

        async with self._session_factory() as session:
            rows = await self._site_repo.find_device_type_summary(session)

        logger.info(f"✅ 원격 장치 유형 요약 조회 완료: {len(rows)}건")

        return rows

    async def close(self) -> None:
        """원격 DB 연결 종료"""

        await self._engine.dispose()
        logger.info("✅ DBRemoteService 종료 완료")
