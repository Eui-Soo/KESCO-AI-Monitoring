"""AI 결과 데이터 조회 API

이 라우터는 anomaly_score 테이블에 저장된 AI 결과 데이터를 조회한다.

현재 결과 규격:
    - serial_number
    - date_time / sensing_datetime
    - prediction_time
    - bank_no
    - rack_no
    - string_no
    - module_no
    - cell_1_score ~ cell_20_score
    - cell_1_level ~ cell_20_level
    - max_score
    - max_level
    - average_score

점수 범위:
    - 0.00 ~ 1.00

조회 API:
    GET /api/v1/anomaly-scores/latest
    GET /api/v1/anomaly-scores/latest?site_no=1&bms_id=BMS001

    GET /api/v1/anomaly-scores?date=2026-07-05
    GET /api/v1/anomaly-scores?date=2026-07-05&site_no=1&bms_id=BMS001
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Query

from core.container import container


router = APIRouter(
    prefix="/api/v1/anomaly-scores",
    tags=["Anomaly Scores"],
)


@router.get(
    "/latest",
    summary="Get Latest AI Result Data",
    description="""
가장 최근에 저장된 AI 결과 데이터를 조회한다.

사용 예:
- 전체 최신 결과 조회
  GET /api/v1/anomaly-scores/latest

- 특정 사이트/BMS 최신 결과 조회
  GET /api/v1/anomaly-scores/latest?site_no=1&bms_id=BMS001

응답 점수:
- 0.00 ~ 1.00 범위
- 0~100점으로 변환하지 않는다.

응답 등급:
- Normal
- Caution
- Warning
- Danger
""",
)
async def get_latest_anomaly_scores(
    site_no: Optional[int] = Query(
        default=None,
        description="관제 DB 사이트 번호. 예: 1",
    ),
    bms_id: Optional[str] = Query(
        default=None,
        description="관제 DB BMS ID 또는 dvc_id. 예: BMS001",
    ),
):
    """가장 최근 AI 결과 데이터 조회"""

    db_local_service = container.db_local_service()

    scores = await db_local_service.find_latest_anomaly_scores(
        site_no=site_no,
        bms_id=bms_id,
    )

    if not scores:
        return {
            "status": "empty",
            "count": 0,
            "message": "No latest AI result data found.",
            "filters": {
                "site_no": site_no,
                "bms_id": bms_id,
            },
            "results": [],
        }

    return {
        "status": "success",
        "count": len(scores),
        "message": "Latest AI result data retrieved successfully.",
        "filters": {
            "site_no": site_no,
            "bms_id": bms_id,
        },
        "results": scores,
    }


@router.get(
    "",
    summary="Get AI Result Data By Date",
    description="""
특정 날짜의 AI 결과 데이터를 조회한다.

같은 날짜에 파이프라인이 여러 번 실행됐을 수 있으므로,
해당 날짜 중 가장 최근 실행 결과만 반환한다.

사용 예:
- 전체 사이트의 특정 날짜 결과 조회
  GET /api/v1/anomaly-scores?date=2026-07-05

- 특정 사이트/BMS의 특정 날짜 결과 조회
  GET /api/v1/anomaly-scores?date=2026-07-05&site_no=1&bms_id=BMS001

필수 query parameter:
- date: 조회할 날짜, YYYY-MM-DD 형식

선택 query parameter:
- site_no
- bms_id
""",
)
async def get_anomaly_scores_by_date(
    target_date: date = Query(
        ...,
        alias="date",
        description="조회할 날짜. YYYY-MM-DD 형식. 예: 2026-07-05",
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
    """특정 날짜 AI 결과 데이터 조회"""

    db_local_service = container.db_local_service()

    scores = await db_local_service.find_anomaly_scores_by_date(
        target_date=target_date,
        site_no=site_no,
        bms_id=bms_id,
    )

    if not scores:
        return {
            "status": "empty",
            "count": 0,
            "message": "No AI result data found for target date.",
            "filters": {
                "date": target_date.isoformat(),
                "site_no": site_no,
                "bms_id": bms_id,
            },
            "results": [],
        }

    return {
        "status": "success",
        "count": len(scores),
        "message": "AI result data retrieved successfully.",
        "filters": {
            "date": target_date.isoformat(),
            "site_no": site_no,
            "bms_id": bms_id,
        },
        "results": scores,
    }
