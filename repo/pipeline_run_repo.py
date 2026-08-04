"""AI 파이프라인 실행 이력 Repository

이 파일은 pipeline_run_log 테이블의 WRITE / READ를 담당한다.

pipeline_run_log의 역할:
    1. AI 파이프라인이 언제 실행됐는지 기록
    2. 어떤 사이트 / BMS / 날짜 데이터를 처리했는지 기록
    3. 수집 데이터 건수와 저장 결과 건수 기록
    4. raw / preprocessed / result Parquet 파일 경로 기록
    5. 실패 시 에러 메시지 기록

사이트별 관리 도입 후:
    - site_no
    - bms_id
    - ess_id

세 값을 함께 사용한다.

ess_id:
    파일 저장 경로와 기존 코드 호환을 위한 문자열 ID
    예: SITE_1_BMS_BMS001

site_no / bms_id:
    실제 관제 DB 기준 식별자
"""

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.model.models import PipelineRunLog


class PipelineRunRepository:
    """pipeline_run_log 테이블 WRITE / READ 전담 Repository"""

    async def create_running(
        self,
        session: AsyncSession,
        ess_id: str,
        target_date,
        message: Optional[str] = None,
        site_no: Optional[int] = None,
        bms_id: Optional[str] = None,
        model_name: Optional[str] = None,
        model_version: Optional[str] = None,
        model_maker: Optional[str] = None,
        model_root: Optional[str] = None,
        fold_count: Optional[int] = None,
        preprocess_version: Optional[str] = None,
        code_version: Optional[str] = None,
    ) -> PipelineRunLog:
        """파이프라인 실행 시작 로그 생성

        Args:
            session:
                SQLAlchemy AsyncSession

            ess_id:
                파일 저장 경로와 기존 코드 호환을 위한 문자열 ID
                예: SITE_1_BMS_BMS001

            target_date:
                분석 대상 날짜

            message:
                실행 시작 메시지

            site_no:
                관제 DB 기준 사이트 번호

            bms_id:
                관제 DB 기준 BMS ID 또는 dvc_id

            model_name / model_version / preprocess_version:
                해당 실행 결과를 만든 AI 모델과 전처리 버전 정보

        Returns:
            생성된 PipelineRunLog ORM 객체
        """

        log = PipelineRunLog(
            ess_id=ess_id,
            site_no=site_no,
            bms_id=bms_id,
            target_date=target_date,
            status="running",
            model_name=model_name,
            model_version=model_version,
            model_maker=model_maker,
            model_root=model_root,
            fold_count=fold_count,
            preprocess_version=preprocess_version,
            code_version=code_version,
            message=message or "AI pipeline started.",
        )

        session.add(log)
        await session.flush()
        await session.refresh(log)

        return log

    async def mark_success(
        self,
        session: AsyncSession,
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

        log = await session.get(PipelineRunLog, run_id)

        if log is None:
            return

        log.status = "success"
        log.finished_at = datetime.now()
        log.battery_count = battery_count
        log.saved_score_count = saved_score_count
        log.deleted_preprocessed_count = deleted_preprocessed_count
        log.raw_file_path = raw_file_path
        log.preprocessed_file_path = preprocessed_file_path
        log.result_file_path = result_file_path
        log.message = message or "AI pipeline completed successfully."
        log.error_message = None

    async def mark_empty(
        self,
        session: AsyncSession,
        run_id: int,
        battery_count: int = 0,
        saved_score_count: int = 0,
        deleted_preprocessed_count: int = 0,
        raw_file_path: Optional[str] = None,
        preprocessed_file_path: Optional[str] = None,
        result_file_path: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        """조회/전처리 결과가 비었을 때 empty 처리

        데이터가 없는 것은 서버 오류가 아니므로 error가 아니라 empty로 남긴다.
        단, raw 저장 이후 전처리 결과가 비는 경우에는 raw_file_path가 존재할 수 있으므로
        전달받은 파일 경로는 실행 이력에 그대로 보존한다.
        """

        log = await session.get(PipelineRunLog, run_id)

        if log is None:
            return

        log.status = "empty"
        log.finished_at = datetime.now()
        log.battery_count = battery_count
        log.saved_score_count = saved_score_count
        log.deleted_preprocessed_count = deleted_preprocessed_count
        log.raw_file_path = raw_file_path
        log.preprocessed_file_path = preprocessed_file_path
        log.result_file_path = result_file_path
        log.message = message or "No battery data found or preprocess result is empty."
        log.error_message = None

    async def mark_error(
        self,
        session: AsyncSession,
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

        log = await session.get(PipelineRunLog, run_id)

        if log is None:
            return

        log.status = "error"
        log.finished_at = datetime.now()
        log.battery_count = battery_count
        log.saved_score_count = saved_score_count
        log.deleted_preprocessed_count = deleted_preprocessed_count
        log.raw_file_path = raw_file_path
        log.preprocessed_file_path = preprocessed_file_path
        log.result_file_path = result_file_path
        log.message = "AI pipeline failed."
        log.error_message = error_message

    async def find_latest(
        self,
        session: AsyncSession,
        site_no: Optional[int] = None,
        bms_id: Optional[str] = None,
    ) -> Optional[Dict]:
        """가장 최근 파이프라인 실행 이력 조회

        site_no, bms_id가 둘 다 있으면 해당 사이트/BMS의 최신 실행 이력만 조회한다.
        둘 중 하나라도 없으면 전체 기준 최신 실행 이력을 조회한다.
        """

        stmt = select(PipelineRunLog)

        if site_no is not None:
            stmt = stmt.where(PipelineRunLog.site_no == site_no)

        if bms_id is not None:
            stmt = stmt.where(PipelineRunLog.bms_id == bms_id)

        stmt = (
            stmt
            .order_by(desc(PipelineRunLog.started_at), desc(PipelineRunLog.id))
            .limit(1)
        )

        result = await session.execute(stmt)
        row = result.scalar_one_or_none()

        if row is None:
            return None

        return self._to_dict(row)

    async def find_latest_by_date(
        self,
        session: AsyncSession,
        target_date,
        site_no: Optional[int] = None,
        bms_id: Optional[str] = None,
    ) -> Optional[Dict]:
        """특정 날짜/site/bms 기준 가장 최근 파이프라인 실행 이력을 조회한다."""

        stmt = select(PipelineRunLog).where(PipelineRunLog.target_date == target_date)

        if site_no is not None:
            stmt = stmt.where(PipelineRunLog.site_no == site_no)

        if bms_id is not None:
            stmt = stmt.where(PipelineRunLog.bms_id == bms_id)

        stmt = (
            stmt
            .order_by(desc(PipelineRunLog.started_at), desc(PipelineRunLog.id))
            .limit(1)
        )

        result = await session.execute(stmt)
        row = result.scalar_one_or_none()

        if row is None:
            return None

        return self._to_dict(row)

    async def find_recent(
        self,
        session: AsyncSession,
        limit: int = 20,
        site_no: Optional[int] = None,
        bms_id: Optional[str] = None,
    ) -> List[Dict]:
        """최근 파이프라인 실행 이력 목록 조회

        site_no, bms_id가 들어오면 해당 사이트/BMS의 실행 이력만 조회한다.
        """

        stmt = select(PipelineRunLog)

        if site_no is not None:
            stmt = stmt.where(PipelineRunLog.site_no == site_no)

        if bms_id is not None:
            stmt = stmt.where(PipelineRunLog.bms_id == bms_id)

        stmt = (
            stmt
            .order_by(desc(PipelineRunLog.started_at), desc(PipelineRunLog.id))
            .limit(limit)
        )

        result = await session.execute(stmt)
        rows = result.scalars().all()

        return [self._to_dict(row) for row in rows]


    async def exists_success_result_by_date(
        self,
        session: AsyncSession,
        target_date,
        site_no: Optional[int] = None,
        bms_id: Optional[str] = None,
    ) -> bool:
        """특정 날짜/site/bms 기준으로 성공 완료된 AI 결과가 있는지 확인한다.

        force=false 스킵 기준으로 사용한다.

        단순히 anomaly_score row가 1건이라도 있는지만 보면,
        일부 결과만 저장된 불완전한 날짜도 완료된 것으로 오판할 수 있다.
        따라서 pipeline_run_log에서 아래 조건을 만족하는 실행 이력이 있을 때만
        기존 결과가 있다고 판단한다.

        조건:
            - target_date 일치
            - site_no / bms_id 일치
            - status = 'success'
            - saved_score_count > 0
        """

        stmt = select(PipelineRunLog.id).where(
            PipelineRunLog.target_date == target_date,
            PipelineRunLog.status == "success",
            PipelineRunLog.saved_score_count > 0,
        )

        if site_no is not None:
            stmt = stmt.where(PipelineRunLog.site_no == site_no)

        if bms_id is not None:
            stmt = stmt.where(PipelineRunLog.bms_id == bms_id)

        stmt = stmt.order_by(desc(PipelineRunLog.finished_at), desc(PipelineRunLog.id)).limit(1)

        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    def _to_dict(self, row: PipelineRunLog) -> Dict:
        """ORM 객체를 API 응답용 dict로 변환"""

        return {
            "id": row.id,
            "ess_id": row.ess_id,
            "site_no": row.site_no,
            "bms_id": row.bms_id,
            "target_date": row.target_date.isoformat() if row.target_date else None,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            "status": row.status,
            "battery_count": row.battery_count,
            "saved_score_count": row.saved_score_count,
            "deleted_preprocessed_count": row.deleted_preprocessed_count,
            "raw_file_path": row.raw_file_path,
            "preprocessed_file_path": row.preprocessed_file_path,
            "result_file_path": row.result_file_path,
            "model_info": {
                "model_name": row.model_name,
                "model_version": row.model_version,
                "model_maker": row.model_maker,
                "model_root": row.model_root,
                "fold_count": row.fold_count,
                "preprocess_version": row.preprocess_version,
                "code_version": row.code_version,
            },
            "message": row.message,
            "error_message": row.error_message,
            "inserted": row.inserted.isoformat() if row.inserted else None,
            "updated": row.updated.isoformat() if row.updated else None,
        }