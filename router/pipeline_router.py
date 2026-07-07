"""AI 파이프라인 실행/이력 조회 API

이 라우터는 AI 파이프라인 수동 실행과 실행 이력 조회 API를 제공한다.

자동 실행:
    - 하루에 한 번 실행
    - 실행 시간은 .env.dev / .env의 SCHEDULE_HOUR, SCHEDULE_MINUTE, SCHEDULE_SECOND로 설정

주요 API:
    POST /api/v1/pipeline/run
    GET  /api/v1/pipeline/schedule
    GET  /api/v1/pipeline/runs/latest
    GET  /api/v1/pipeline/runs
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from core.container import container


router = APIRouter(
    prefix="/api/v1/pipeline",
    tags=["Pipeline"],
)


@router.post(
    "/run",
    summary="Run AI Pipeline Manually",
    description="""
AI 파이프라인을 수동으로 1회 실행한다.

운영 중에는 스케줄러가 하루에 한 번 자동 실행한다.
이 API는 개발/테스트/장애 대응용 수동 실행 API다.

사용 예:
- 전체 활성 대상 수동 실행
  POST /api/v1/pipeline/run

- 특정 날짜로 전체 활성 대상 수동 실행
  POST /api/v1/pipeline/run?date=2026-07-05

- 특정 사이트/BMS만 수동 실행
  POST /api/v1/pipeline/run?site_no=1&bms_id=BMS001

- 특정 날짜 + 특정 사이트/BMS 수동 실행
  POST /api/v1/pipeline/run?date=2026-07-05&site_no=1&bms_id=BMS001

주의:
- site_no와 bms_id는 둘 다 넣거나 둘 다 빼야 한다.
""",
)
async def run_pipeline_manually(
    target_date: Optional[date] = Query(
        default=None,
        alias="date",
        description=(
            "분석 대상 날짜. YYYY-MM-DD 형식. "
            "생략하면 TARGET_DATE_OFFSET_DAYS 설정 기준 날짜를 사용한다."
        ),
    ),
    site_no: Optional[int] = Query(
        default=None,
        description="관제 DB 사이트 번호. 예: 1",
    ),
    bms_id: Optional[str] = Query(
        default=None,
        description="관제 DB BMS ID 또는 dvc_id. 예: BMS001",
    ),
):
    """AI 파이프라인 수동 실행"""

    _validate_site_bms_pair(site_no=site_no, bms_id=bms_id)

    scheduler_service = container.scheduler_service()

    result = await scheduler_service.run_once(
        target_date=target_date,
        site_no=site_no,
        bms_id=bms_id,
    )

    return {
        "status": result.get("status", "unknown"),
        "message": result.get("message", "AI pipeline manual run completed."),
        "filters": {
            "date": target_date.isoformat() if target_date else None,
            "site_no": site_no,
            "bms_id": bms_id,
        },
        "result": result,
    }


@router.get(
    "/schedule",
    summary="Get Daily Pipeline Schedule",
    description="""
현재 AI 파이프라인 자동 실행 시간을 조회한다.

자동 실행 시간은 .env.dev 또는 .env에서 설정한다.

예:
SCHEDULE_HOUR=2
SCHEDULE_MINUTE=30
SCHEDULE_SECOND=0

위 설정이면 매일 02:30:00에 실행된다.
""",
)
async def get_pipeline_schedule():
    """현재 스케줄 설정 조회"""

    settings = container.settings()

    return {
        "status": "success",
        "message": "Daily AI pipeline schedule retrieved successfully.",
        "schedule": {
            "type": "daily",
            "hour": settings.SCHEDULE_HOUR,
            "minute": settings.SCHEDULE_MINUTE,
            "second": settings.SCHEDULE_SECOND,
            "time": (
                f"{settings.SCHEDULE_HOUR:02d}:"
                f"{settings.SCHEDULE_MINUTE:02d}:"
                f"{settings.SCHEDULE_SECOND:02d}"
            ),
            "target_date_offset_days": settings.TARGET_DATE_OFFSET_DAYS,
            "target_date_meaning": _get_target_date_meaning(
                settings.TARGET_DATE_OFFSET_DAYS
            ),
        },
    }


@router.get(
    "/runs/latest",
    summary="Get Latest AI Pipeline Run Log",
    description="""
가장 최근 AI 파이프라인 실행 이력을 조회한다.

사용 예:
- 전체 기준 최신 실행 이력
  GET /api/v1/pipeline/runs/latest

- 특정 사이트/BMS 기준 최신 실행 이력
  GET /api/v1/pipeline/runs/latest?site_no=1&bms_id=BMS001
""",
)
async def get_latest_pipeline_run(
    site_no: Optional[int] = Query(
        default=None,
        description="관제 DB 사이트 번호. 예: 1",
    ),
    bms_id: Optional[str] = Query(
        default=None,
        description="관제 DB BMS ID 또는 dvc_id. 예: BMS001",
    ),
):
    """가장 최근 파이프라인 실행 이력 조회"""

    _validate_site_bms_pair(site_no=site_no, bms_id=bms_id)

    db_local_service = container.db_local_service()

    run = await db_local_service.find_latest_pipeline_run(
        site_no=site_no,
        bms_id=bms_id,
    )

    if run is None:
        return {
            "status": "empty",
            "message": "No pipeline run log found.",
            "filters": {
                "site_no": site_no,
                "bms_id": bms_id,
            },
            "result": None,
        }

    return {
        "status": "success",
        "message": "Latest pipeline run log retrieved successfully.",
        "filters": {
            "site_no": site_no,
            "bms_id": bms_id,
        },
        "result": run,
    }


@router.get(
    "/runs",
    summary="Get Recent AI Pipeline Run Logs",
    description="""
최근 AI 파이프라인 실행 이력 목록을 조회한다.

사용 예:
- 전체 최근 실행 이력 20개
  GET /api/v1/pipeline/runs

- 전체 최근 실행 이력 50개
  GET /api/v1/pipeline/runs?limit=50

- 특정 사이트/BMS 최근 실행 이력
  GET /api/v1/pipeline/runs?site_no=1&bms_id=BMS001

- 특정 사이트/BMS 최근 실행 이력 50개
  GET /api/v1/pipeline/runs?limit=50&site_no=1&bms_id=BMS001
""",
)
async def get_recent_pipeline_runs(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="조회할 최근 실행 이력 개수. 1~100",
    ),
    site_no: Optional[int] = Query(
        default=None,
        description="관제 DB 사이트 번호. 예: 1",
    ),
    bms_id: Optional[str] = Query(
        default=None,
        description="관제 DB BMS ID 또는 dvc_id. 예: BMS001",
    ),
):
    """최근 파이프라인 실행 이력 목록 조회"""

    _validate_site_bms_pair(site_no=site_no, bms_id=bms_id)

    db_local_service = container.db_local_service()

    runs = await db_local_service.find_recent_pipeline_runs(
        limit=limit,
        site_no=site_no,
        bms_id=bms_id,
    )

    if not runs:
        return {
            "status": "empty",
            "count": 0,
            "message": "No pipeline run logs found.",
            "filters": {
                "limit": limit,
                "site_no": site_no,
                "bms_id": bms_id,
            },
            "results": [],
        }

    return {
        "status": "success",
        "count": len(runs),
        "message": "Recent pipeline run logs retrieved successfully.",
        "filters": {
            "limit": limit,
            "site_no": site_no,
            "bms_id": bms_id,
        },
        "results": runs,
    }


def _validate_site_bms_pair(
    site_no: Optional[int],
    bms_id: Optional[str],
) -> None:
    """site_no / bms_id 입력 조합 검증"""

    if site_no is None and bms_id is None:
        return

    if site_no is not None and bms_id:
        return

    raise HTTPException(
        status_code=400,
        detail=(
            "site_no and bms_id must be provided together. "
            "Use both values or omit both values."
        ),
    )


def _get_target_date_meaning(offset_days: int) -> str:
    """TARGET_DATE_OFFSET_DAYS 의미 설명"""

    if offset_days == 0:
        return "today"

    if offset_days == -1:
        return "yesterday"

    if offset_days < 0:
        return f"{abs(offset_days)} days ago"

    return f"{offset_days} days later"
