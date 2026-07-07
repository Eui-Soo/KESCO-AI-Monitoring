"""로컬 DB 서비스

이 파일은 AI API 서버가 직접 관리하는 로컬 DB에 접근하는 서비스다.

로컬 DB 역할:
    1. AI 서버 테이블 생성
    2. 관제 DB 사이트/장치 목록 저장 및 조회
    3. anomaly_score 저장 및 조회
    4. pipeline_run_log 저장 및 조회
"""

import logging
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from core.setting import Settings


logger = logging.getLogger("app")


class Base(DeclarativeBase):
    """SQLAlchemy Base 클래스"""

    pass


class DBLocalService:
    """우리 AI 결과 DB 서비스"""

    def __init__(self, settings: Settings):
        self._engine: AsyncEngine = create_async_engine(
            settings.async_db_url,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=settings.DB_POOL_TIMEOUT,
            pool_recycle=settings.DB_POOL_RECYCLE,
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

        logger.info("✅ DBLocalService 초기화 완료")

    async def init_db(self) -> None:
        """로컬 DB 테이블 생성"""

        async with self._engine.connect() as conn:
            async with conn.begin():
                await conn.run_sync(Base.metadata.create_all)

        logger.info(f"✅ DB 테이블 생성 완료: {list(Base.metadata.tables.keys())}")

    # ============================================================
    # Site / Device
    # ============================================================

    async def upsert_sites(self, remote_rows: List[Dict]) -> Dict:
        """관제 DB에서 가져온 사이트/장치 목록을 로컬 DB에 저장 또는 갱신한다."""

        async with self._session_factory() as session:
            async with session.begin():
                from repo.site_repo import SiteRepository

                repo = SiteRepository()
                result = await repo.upsert_sites(
                    session=session,
                    remote_rows=remote_rows,
                )

        logger.info(
            "✅ 사이트/장치 목록 로컬 DB 동기화 완료 "
            f"[site_created={result.get('site_created_count')}, "
            f"site_updated={result.get('site_updated_count')}, "
            f"device_created={result.get('device_created_count')}, "
            f"device_updated={result.get('device_updated_count')}, "
            f"skipped_device={result.get('skipped_device_count')}]"
        )

        return result

    async def find_sites(self) -> List[Dict]:
        """로컬 DB에 저장된 사이트/장치 목록을 조회한다."""

        async with self._session_factory() as session:
            from repo.site_repo import SiteRepository

            repo = SiteRepository()
            sites = await repo.find_sites(session)

        logger.info(f"✅ 로컬 사이트 목록 조회 완료: {len(sites)}개 사이트")

        return sites

    async def find_site_by_site_no(self, site_no: int) -> Optional[Dict]:
        """site_no 기준으로 특정 사이트 상세 정보를 조회한다."""

        async with self._session_factory() as session:
            from repo.site_repo import SiteRepository

            repo = SiteRepository()
            site = await repo.find_site_by_site_no(
                session=session,
                site_no=site_no,
            )

        if site is None:
            logger.warning(f"⚠️ 로컬 사이트 조회 결과 없음: site_no={site_no}")
        else:
            logger.info(f"✅ 로컬 사이트 상세 조회 완료: site_no={site_no}")

        return site

    async def find_active_ai_targets(self) -> List[Dict]:
        """AI 분석 대상으로 활성화된 사이트/장치 목록을 조회한다."""

        async with self._session_factory() as session:
            from repo.site_repo import SiteRepository

            repo = SiteRepository()
            targets = await repo.find_active_ai_targets(session)

        logger.info(f"✅ AI 분석 대상 조회 완료: {len(targets)}개")

        return targets

    # ============================================================
    # Anomaly Score / AI Result
    # ============================================================

    async def save_anomaly_scores(self, scores: List[dict]) -> int:
        """AI 결과 데이터를 anomaly_score 테이블에 일괄 저장한다."""

        if not scores:
            logger.warning("⚠️ 저장할 AI 결과 데이터 없음")
            return 0

        async with self._session_factory() as session:
            async with session.begin():
                from repo.anomaly_repo import AnomalyScoreRepository

                repo = AnomalyScoreRepository()
                count = await repo.bulk_insert(session, scores)

        logger.info(f"✅ AnomalyScore 저장 완료: {count}건")

        return count

    async def find_latest_anomaly_scores(
        self,
        site_no: Optional[int] = None,
        bms_id: Optional[str] = None,
    ) -> List[dict]:
        """가장 최근에 저장된 AI 결과 데이터를 조회한다."""

        async with self._session_factory() as session:
            from repo.anomaly_repo import AnomalyScoreRepository

            repo = AnomalyScoreRepository()
            scores = await repo.find_latest(
                session=session,
                site_no=site_no,
                bms_id=bms_id,
            )

        logger.info(
            "✅ 최신 AI 결과 데이터 조회 완료 "
            f"[site_no={site_no}, bms_id={bms_id}, count={len(scores)}건]"
        )

        return scores

    async def find_anomaly_scores_by_date(
        self,
        target_date,
        site_no: Optional[int] = None,
        bms_id: Optional[str] = None,
    ) -> List[dict]:
        """특정 날짜의 가장 최근 AI 결과 데이터를 조회한다."""

        async with self._session_factory() as session:
            from repo.anomaly_repo import AnomalyScoreRepository

            repo = AnomalyScoreRepository()
            scores = await repo.find_latest_by_date(
                session=session,
                target_date=target_date,
                site_no=site_no,
                bms_id=bms_id,
            )

        logger.info(
            "✅ 날짜별 AI 결과 데이터 조회 완료 "
            f"[target_date={target_date}, site_no={site_no}, "
            f"bms_id={bms_id}, count={len(scores)}건]"
        )

        return scores

    # ============================================================
    # Pipeline Run Log
    # ============================================================

    async def create_pipeline_run(
        self,
        ess_id: str,
        target_date,
        message: Optional[str] = None,
        site_no: Optional[int] = None,
        bms_id: Optional[str] = None,
    ) -> int:
        """파이프라인 실행 시작 로그 생성"""

        async with self._session_factory() as session:
            async with session.begin():
                from repo.pipeline_run_repo import PipelineRunRepository

                repo = PipelineRunRepository()
                log = await repo.create_running(
                    session=session,
                    ess_id=ess_id,
                    target_date=target_date,
                    message=message,
                    site_no=site_no,
                    bms_id=bms_id,
                )
                run_id = log.id

        logger.info(
            "✅ PipelineRunLog 시작 기록 완료 "
            f"[run_id={run_id}, ess_id={ess_id}, "
            f"site_no={site_no}, bms_id={bms_id}]"
        )

        return run_id

    async def mark_pipeline_success(
        self,
        run_id: int,
        battery_count: int,
        saved_score_count: int,
        deleted_preprocessed_count: int,
        raw_file_path: Optional[str],
        preprocessed_file_path: Optional[str],
        result_file_path: Optional[str],
        message: Optional[str] = None,
    ) -> None:
        """파이프라인 성공 처리"""

        async with self._session_factory() as session:
            async with session.begin():
                from repo.pipeline_run_repo import PipelineRunRepository

                repo = PipelineRunRepository()
                await repo.mark_success(
                    session=session,
                    run_id=run_id,
                    battery_count=battery_count,
                    saved_score_count=saved_score_count,
                    deleted_preprocessed_count=deleted_preprocessed_count,
                    raw_file_path=raw_file_path,
                    preprocessed_file_path=preprocessed_file_path,
                    result_file_path=result_file_path,
                    message=message,
                )

        logger.info(f"✅ PipelineRunLog 성공 처리 완료: run_id={run_id}")

    async def mark_pipeline_empty(
        self,
        run_id: int,
        battery_count: int = 0,
        saved_score_count: int = 0,
        deleted_preprocessed_count: int = 0,
        message: Optional[str] = None,
    ) -> None:
        """파이프라인 empty 처리"""

        async with self._session_factory() as session:
            async with session.begin():
                from repo.pipeline_run_repo import PipelineRunRepository

                repo = PipelineRunRepository()
                await repo.mark_empty(
                    session=session,
                    run_id=run_id,
                    battery_count=battery_count,
                    saved_score_count=saved_score_count,
                    deleted_preprocessed_count=deleted_preprocessed_count,
                    message=message,
                )

        logger.info(f"✅ PipelineRunLog empty 처리 완료: run_id={run_id}")

    async def mark_pipeline_error(
        self,
        run_id: int,
        error_message: str,
        battery_count: int = 0,
        saved_score_count: int = 0,
        deleted_preprocessed_count: int = 0,
        raw_file_path: Optional[str] = None,
        preprocessed_file_path: Optional[str] = None,
        result_file_path: Optional[str] = None,
    ) -> None:
        """파이프라인 실패 처리"""

        async with self._session_factory() as session:
            async with session.begin():
                from repo.pipeline_run_repo import PipelineRunRepository

                repo = PipelineRunRepository()
                await repo.mark_error(
                    session=session,
                    run_id=run_id,
                    error_message=error_message,
                    battery_count=battery_count,
                    saved_score_count=saved_score_count,
                    deleted_preprocessed_count=deleted_preprocessed_count,
                    raw_file_path=raw_file_path,
                    preprocessed_file_path=preprocessed_file_path,
                    result_file_path=result_file_path,
                )

        logger.info(f"✅ PipelineRunLog 실패 처리 완료: run_id={run_id}")

    async def find_latest_pipeline_run(
        self,
        site_no: Optional[int] = None,
        bms_id: Optional[str] = None,
    ) -> Optional[Dict]:
        """가장 최근 파이프라인 실행 이력 조회"""

        async with self._session_factory() as session:
            from repo.pipeline_run_repo import PipelineRunRepository

            repo = PipelineRunRepository()
            run = await repo.find_latest(
                session=session,
                site_no=site_no,
                bms_id=bms_id,
            )

        logger.info(
            "✅ 최신 PipelineRunLog 조회 완료 "
            f"[site_no={site_no}, bms_id={bms_id}]"
        )

        return run

    async def find_recent_pipeline_runs(
        self,
        limit: int = 20,
        site_no: Optional[int] = None,
        bms_id: Optional[str] = None,
    ) -> List[Dict]:
        """최근 파이프라인 실행 이력 목록 조회"""

        async with self._session_factory() as session:
            from repo.pipeline_run_repo import PipelineRunRepository

            repo = PipelineRunRepository()
            runs = await repo.find_recent(
                session=session,
                limit=limit,
                site_no=site_no,
                bms_id=bms_id,
            )

        logger.info(
            "✅ 최근 PipelineRunLog 조회 완료 "
            f"[site_no={site_no}, bms_id={bms_id}, count={len(runs)}건]"
        )

        return runs

    async def close(self) -> None:
        """DB 연결 종료"""

        await self._engine.dispose()
        logger.info("✅ DBLocalService 종료 완료")
