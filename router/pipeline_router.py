"""AI 파이프라인 실행/이력 조회 API

이 라우터는 AI 파이프라인 수동 실행과 실행 이력 조회 API를 제공한다.

자동 실행:
    - 하루에 한 번 실행
    - 실행 시간은 .env.dev / .env의 SCHEDULE_HOUR, SCHEDULE_MINUTE, SCHEDULE_SECOND로 설정

주요 API:
    POST /api/v1/pipeline/run
    POST /api/v1/pipeline/run-range
    POST /api/v1/pipeline/range-runs
    GET  /api/v1/pipeline/range-runs/{range_run_id}
    GET  /api/v1/pipeline/source-data-range
    GET  /api/v1/pipeline/source-data-quality
    GET  /api/v1/pipeline/consistency-check
    GET  /api/v1/pipeline/consistency-check-range
    GET  /api/v1/pipeline/model-info
    GET  /api/v1/pipeline/schedule
    GET  /api/v1/pipeline/runs/latest
    GET  /api/v1/pipeline/runs
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
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

@router.post(
    "/run-range",
    summary="Run AI Pipeline For Date Range",
    description="""
특정 기간의 데이터를 날짜별로 순차 분석한다.

force=false:
- pipeline_run_log 기준 성공 완료된 결과가 있으면 재실행하지 않고 건너뛴다.
- 완료 판단 기준은 status='success' 그리고 saved_score_count > 0이다.

force=true:
- 이미 결과가 있어도 다시 분석한다.
- 기존 결과는 삭제하지 않고 새 pipeline_run_id로 추가 저장한다.
- 조회 API는 날짜별 최신 결과를 반환한다.
""",
)
async def run_pipeline_range(
    start_date: date = Query(
        ...,
        description="분석 시작 날짜. YYYY-MM-DD",
    ),
    end_date: date = Query(
        ...,
        description="분석 종료 날짜. YYYY-MM-DD",
    ),
    site_no: int = Query(
        ...,
        description="관제 DB 사이트 번호. 예: 1",
    ),
    bms_id: str = Query(
        ...,
        description="관제 DB BMS ID 또는 dvc_id. 예: BMS001",
    ),
    force: Optional[bool] = Query(
        default=None,
        description=(
            "강제 재실행 여부. "
            "true이면 기존 결과가 있어도 다시 실행한다. "
            "생략하면 FORCE_RERUN_DEFAULT 설정값을 사용한다."
        ),
    ),
):
    """특정 기간 AI 파이프라인 실행"""

    _validate_date_range(start_date=start_date, end_date=end_date)

    settings = container.settings()
    scheduler_service = container.scheduler_service()
    db_local_service = container.db_local_service()

    effective_force = (
        settings.FORCE_RERUN_DEFAULT
        if force is None
        else force
    )

    if effective_force and not settings.FORCE_RERUN_ENABLED:
        raise HTTPException(
            status_code=400,
            detail=(
                "Force rerun is disabled by server setting. "
                "Set FORCE_RERUN_ENABLED=true to allow force=true."
            ),
        )

    total_days = (end_date - start_date).days + 1
    results = []

    current_date = start_date

    while current_date <= end_date:
        has_completed_result = await db_local_service.exists_success_pipeline_result_by_date(
            target_date=current_date,
            site_no=site_no,
            bms_id=bms_id,
        )

        if has_completed_result and not effective_force:
            results.append(
                {
                    "date": current_date.isoformat(),
                    "status": "skipped_existing",
                    "message": (
                        "Completed AI result already exists for this date/site/bms. "
                        "Use force=true to rerun."
                    ),
                    "skip_basis": "pipeline_run_log.status=success and saved_score_count>0",
                    "run_id": None,
                    "battery_count": 0,
                    "preprocessed_count": 0,
                    "saved_score_count": 0,
                    "raw_file_path": None,
                    "preprocessed_file_path": None,
                    "result_file_path": None,
                    "error_message": None,
                }
            )

            current_date = current_date + timedelta(days=1)
            continue

        result = await scheduler_service.run_once(
            target_date=current_date,
            site_no=site_no,
            bms_id=bms_id,
        )

        results.append(
            {
                "date": current_date.isoformat(),
                "status": result.get("status"),
                "message": result.get("message"),
                "run_id": result.get("run_id"),
                "battery_count": result.get("battery_count", 0),
                "preprocessed_count": result.get("preprocessed_count", 0),
                "saved_score_count": result.get("saved_score_count", 0),
                "raw_file_path": result.get("raw_file_path"),
                "preprocessed_file_path": result.get("preprocessed_file_path"),
                "result_file_path": result.get("result_file_path"),
                "error_message": result.get("error_message"),
            }
        )

        current_date = current_date + timedelta(days=1)

    success_count = sum(1 for item in results if item.get("status") == "success")
    waiting_count = sum(1 for item in results if item.get("status") == "waiting_7days")
    empty_count = sum(1 for item in results if item.get("status") == "empty")
    error_count = sum(1 for item in results if item.get("status") == "error")
    skipped_count = sum(1 for item in results if item.get("status") == "skipped")
    skipped_existing_count = sum(
        1 for item in results if item.get("status") == "skipped_existing"
    )

    if error_count > 0:
        overall_status = "partial_error"
    elif success_count > 0:
        overall_status = "success"
    elif waiting_count > 0:
        overall_status = "waiting_7days"
    elif empty_count > 0:
        overall_status = "empty"
    elif skipped_existing_count > 0:
        overall_status = "skipped_existing"
    elif skipped_count > 0:
        overall_status = "skipped"
    else:
        overall_status = "unknown"

    return {
        "status": overall_status,
        "message": "Date range AI pipeline completed.",
        "filters": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "site_no": site_no,
            "bms_id": bms_id,
            "force": effective_force,
        },
        "settings": {
            "force_rerun_enabled": settings.FORCE_RERUN_ENABLED,
            "force_rerun_default": settings.FORCE_RERUN_DEFAULT,
        },
        "summary": {
            "total_days": total_days,
            "success_count": success_count,
            "waiting_count": waiting_count,
            "empty_count": empty_count,
            "error_count": error_count,
            "skipped_count": skipped_count,
            "skipped_existing_count": skipped_existing_count,
        },
        "results": results,
    }

@router.post(
    "/range-runs",
    summary="Start AI Pipeline Range Run In Background",
    description="""
특정 기간 AI 분석 작업을 백그라운드로 등록한다.

기존 /run-range API는 분석이 모두 끝날 때까지 응답을 기다리는 동기 실행 방식이다.
이 API는 긴 기간 분석에서 Swagger/브라우저 timeout을 방지하기 위해 즉시 range_run_id를 반환한다.

사용 예:
POST /api/v1/pipeline/range-runs?start_date=2026-07-01&end_date=2026-07-10&site_no=1&bms_id=BMS001
POST /api/v1/pipeline/range-runs?start_date=2026-07-01&end_date=2026-07-10&site_no=1&bms_id=BMS001&force=true

진행 상태는 아래 API로 조회한다.
GET /api/v1/pipeline/range-runs/{range_run_id}

주의:
- 현재 range_run 상태는 메모리에서 관리한다.
- 서버가 재시작되면 백그라운드 range_run 상태는 초기화된다.
- 운영 고도화 단계에서는 range_run_log 테이블로 영속화하는 것을 권장한다.
""",
)
async def start_pipeline_range_run_background(
    start_date: date = Query(
        ...,
        description="분석 시작 날짜. YYYY-MM-DD",
    ),
    end_date: date = Query(
        ...,
        description="분석 종료 날짜. YYYY-MM-DD",
    ),
    site_no: int = Query(
        ...,
        description="관제 DB 사이트 번호. 예: 1",
    ),
    bms_id: str = Query(
        ...,
        description="관제 DB BMS ID 또는 dvc_id. 예: BMS001",
    ),
    force: Optional[bool] = Query(
        default=None,
        description=(
            "강제 재실행 여부. "
            "true이면 기존 결과가 있어도 다시 실행한다. "
            "생략하면 FORCE_RERUN_DEFAULT 설정값을 사용한다."
        ),
    ),
):
    """기간 AI 파이프라인 백그라운드 작업 등록"""

    _validate_date_range(start_date=start_date, end_date=end_date)

    scheduler_service = container.scheduler_service()

    try:
        result = scheduler_service.start_range_run_background(
            start_date=start_date,
            end_date=end_date,
            site_no=site_no,
            bms_id=bms_id,
            force=force,
        )

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "status": "accepted",
        "message": "Range pipeline job accepted.",
        "range_run_id": result.get("range_run_id"),
        "result": result,
    }


@router.get(
    "/range-runs/{range_run_id}",
    summary="Get Background Range Run Status",
    description="""
백그라운드 기간 분석 작업의 진행 상태를 조회한다.

사용 예:
GET /api/v1/pipeline/range-runs/RANGE_20260720_153000_2026-07-01_2026-07-10_SITE_1_BMS_BMS001_abcd1234

응답에는 전체 일수, 완료 일수, 현재 처리 날짜, 날짜별 실행 결과가 포함된다.
""",
)
async def get_pipeline_range_run_status(
    range_run_id: str,
):
    """기간 AI 파이프라인 백그라운드 작업 상태 조회"""

    scheduler_service = container.scheduler_service()
    result = scheduler_service.get_range_run_status(range_run_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Range run not found. range_run_id={range_run_id}",
        )

    return {
        "status": result.get("status", "unknown"),
        "message": "Range pipeline job status retrieved successfully.",
        "range_run_id": range_run_id,
        "result": result,
    }


@router.get(
    "/range-runs",
    summary="Get Recent Background Range Runs",
    description="""
최근 백그라운드 기간 분석 작업 목록을 조회한다.

사용 예:
GET /api/v1/pipeline/range-runs
GET /api/v1/pipeline/range-runs?limit=50
""",
)
async def get_recent_pipeline_range_runs(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="조회할 최근 기간 분석 작업 개수. 1~100",
    ),
):
    """최근 기간 AI 파이프라인 백그라운드 작업 목록 조회"""

    scheduler_service = container.scheduler_service()
    results = scheduler_service.get_recent_range_runs(limit=limit)

    if not results:
        return {
            "status": "empty",
            "count": 0,
            "message": "No range pipeline jobs found.",
            "results": [],
        }

    return {
        "status": "success",
        "count": len(results),
        "message": "Recent range pipeline jobs retrieved successfully.",
        "results": results,
    }


@router.get(
    "/source-data-range",
    summary="Get Source Data Range",
    description="""
관제시스템 원본 DB에 저장된 배터리 데이터의 보유 기간을 조회한다.

이 API는 특정 기간 분석을 실행하기 전에,
해당 사이트 또는 BMS가 실제로 어느 기간의 데이터를 가지고 있는지 확인하기 위한 API다.

사용 예:
- 전체 관제 DB 데이터 보유 기간 조회
  GET /api/v1/pipeline/source-data-range

- 특정 사이트 데이터 보유 기간 조회
  GET /api/v1/pipeline/source-data-range?site_no=1

- 특정 사이트/BMS 데이터 보유 기간 조회
  GET /api/v1/pipeline/source-data-range?site_no=1&bms_id=BMS001

주의:
- bms_id를 넣을 경우 site_no도 같이 넣어야 한다.
- site_no만 넣는 것은 허용한다.
""",
)
async def get_source_data_range(
    site_no: Optional[int] = Query(
        default=None,
        description="관제 DB 사이트 번호. 예: 1",
    ),
    bms_id: Optional[str] = Query(
        default=None,
        description="관제 DB BMS ID 또는 dvc_id. 예: BMS001",
    ),
):
    """관제 DB 원본 데이터 보유 기간 조회"""

    _validate_bms_requires_site(site_no=site_no, bms_id=bms_id)

    remote_db_service = container.remote_db_service()

    data_range = await remote_db_service.find_battery_data_range(
        site_no=site_no,
        bms_id=bms_id,
    )

    status = "success" if data_range.get("available") else "empty"

    response = {
        "status": status,
        "message": (
            "Source data range retrieved successfully."
            if status == "success"
            else "No source data found."
        ),
        "filters": {
            "site_no": site_no,
            "bms_id": bms_id,
        },
        "data_range": data_range,
    }

    return jsonable_encoder(response)



@router.get(
    "/source-data-quality",
    summary="Get Source Data Quality",
    description="""
관제시스템 원본 DB의 일자별 데이터 품질을 조회한다.

이 API는 특정 기간 분석을 실행하기 전에,
날짜별로 원본 데이터가 충분히 쌓였는지 확인하기 위한 API다.

사용 예:
- 특정 사이트/BMS의 기간별 데이터 품질 조회
  GET /api/v1/pipeline/source-data-quality?start_date=2026-07-01&end_date=2026-07-10&site_no=1&bms_id=BMS001

- 하루 기대 row 수를 직접 지정하여 품질 판단
  GET /api/v1/pipeline/source-data-quality?start_date=2026-07-01&end_date=2026-07-10&site_no=1&bms_id=BMS001&expected_row_count_per_day=27360

응답 상태:
- complete: 기대 row 수 대비 충분한 데이터가 있는 날짜
- insufficient: 데이터는 있으나 기대 row 수 대비 부족한 날짜
- missing: 데이터가 없는 날짜
- present: 기대 row 수를 산정할 수 없지만 데이터는 있는 날짜

주의:
- expected_row_count_per_day를 생략하면 조회 기간 중 가장 큰 module row 수를 임시 기대 row 수로 사용한다.
- bms_id를 넣을 경우 site_no도 같이 넣어야 한다.
""",
)
async def get_source_data_quality(
    start_date: date = Query(
        ...,
        description="품질 조회 시작 날짜. YYYY-MM-DD",
    ),
    end_date: date = Query(
        ...,
        description="품질 조회 종료 날짜. YYYY-MM-DD",
    ),
    site_no: Optional[int] = Query(
        default=None,
        description="관제 DB 사이트 번호. 예: 1",
    ),
    bms_id: Optional[str] = Query(
        default=None,
        description="관제 DB BMS ID 또는 dvc_id. 예: BMS001",
    ),
    expected_row_count_per_day: Optional[int] = Query(
        default=None,
        ge=1,
        description=(
            "하루 기대 module row 수. "
            "생략하면 조회 기간 중 가장 큰 일자별 row 수를 기준으로 판단한다."
        ),
    ),
    minimum_completeness_rate: float = Query(
        default=0.8,
        ge=0,
        le=1,
        description="complete 판단 최소 충족률. 기본값 0.8",
    ),
):
    """관제 DB 원본 데이터 일자별 품질 조회"""

    _validate_date_range(start_date=start_date, end_date=end_date)
    _validate_bms_requires_site(site_no=site_no, bms_id=bms_id)

    remote_db_service = container.remote_db_service()

    quality = await remote_db_service.find_battery_data_quality(
        start_date=start_date,
        end_date=end_date,
        site_no=site_no,
        bms_id=bms_id,
        expected_row_count_per_day=expected_row_count_per_day,
        minimum_completeness_rate=minimum_completeness_rate,
    )

    return jsonable_encoder(
        {
            "status": quality.get("status", "unknown"),
            "message": "Source data quality retrieved successfully.",
            "data_quality": quality,
        }
    )


@router.get(
    "/consistency-check",
    summary="Check File And DB Consistency",
    description="""
특정 날짜/site/bms 기준으로 파일 저장 상태와 DB 저장 상태의 정합성을 확인한다.

확인 항목:
- raw parquet 파일 존재 여부 및 row 수
- preprocess parquet 파일 존재 여부 및 row 수
- result parquet 파일 존재 여부 및 row 수
- pipeline_run_log 존재 여부 및 상태
- anomaly_score DB 저장 row 수
- pipeline_run_log.saved_score_count와 anomaly_score row 수 일치 여부

사용 예:
GET /api/v1/pipeline/consistency-check?date=2026-07-10&site_no=1&bms_id=BMS001
""",
)
async def get_pipeline_consistency_check(
    target_date: date = Query(
        ...,
        alias="date",
        description="정합성 검사 대상 날짜. YYYY-MM-DD",
    ),
    site_no: int = Query(
        ...,
        description="관제 DB 사이트 번호. 예: 1",
    ),
    bms_id: str = Query(
        ...,
        description="관제 DB BMS ID 또는 dvc_id. 예: BMS001",
    ),
):
    """특정 날짜 파일/DB 정합성 검사"""

    result = await _build_daily_consistency_result(
        target_date=target_date,
        site_no=site_no,
        bms_id=bms_id,
    )

    return jsonable_encoder(
        {
            "status": result.get("status"),
            "message": "File and DB consistency check completed.",
            "result": result,
        }
    )


@router.get(
    "/consistency-check-range",
    summary="Check File And DB Consistency By Date Range",
    description="""
특정 기간의 파일/DB 정합성을 날짜별로 확인한다.

긴 기간 분석 후 아래 항목을 한 번에 검증할 때 사용한다.
- 날짜별 raw/preprocess/result 파일 존재 여부
- 날짜별 pipeline_run_log 상태
- 날짜별 anomaly_score 저장 건수
- 실행 로그의 saved_score_count와 실제 anomaly_score row 수 일치 여부

사용 예:
GET /api/v1/pipeline/consistency-check-range?start_date=2026-07-01&end_date=2026-07-10&site_no=1&bms_id=BMS001
""",
)
async def get_pipeline_consistency_check_range(
    start_date: date = Query(
        ...,
        description="정합성 검사 시작 날짜. YYYY-MM-DD",
    ),
    end_date: date = Query(
        ...,
        description="정합성 검사 종료 날짜. YYYY-MM-DD",
    ),
    site_no: int = Query(
        ...,
        description="관제 DB 사이트 번호. 예: 1",
    ),
    bms_id: str = Query(
        ...,
        description="관제 DB BMS ID 또는 dvc_id. 예: BMS001",
    ),
):
    """기간 파일/DB 정합성 검사"""

    _validate_date_range(start_date=start_date, end_date=end_date)

    results = []
    current_date = start_date

    while current_date <= end_date:
        daily_result = await _build_daily_consistency_result(
            target_date=current_date,
            site_no=site_no,
            bms_id=bms_id,
        )
        results.append(daily_result)
        current_date = current_date + timedelta(days=1)

    success_count = sum(1 for item in results if item.get("status") == "success")
    warning_count = sum(1 for item in results if item.get("status") == "warning")
    error_count = sum(1 for item in results if item.get("status") == "error")
    missing_count = sum(1 for item in results if item.get("status") == "missing")

    if error_count > 0:
        overall_status = "error"
    elif warning_count > 0 or missing_count > 0:
        overall_status = "warning"
    else:
        overall_status = "success"

    return jsonable_encoder(
        {
            "status": overall_status,
            "message": "File and DB consistency range check completed.",
            "filters": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "site_no": site_no,
                "bms_id": bms_id,
            },
            "summary": {
                "total_days": len(results),
                "success_count": success_count,
                "warning_count": warning_count,
                "error_count": error_count,
                "missing_count": missing_count,
            },
            "results": results,
        }
    )


@router.get(
    "/model-info",
    summary="Get AI Model Version Info",
    description="""
현재 AI 서버에 설정된 모델/전처리 버전 정보를 조회한다.

이 정보는 pipeline_run_log에도 함께 저장되므로,
특정 분석 결과가 어떤 모델과 전처리 버전으로 생성되었는지 추적할 수 있다.

사용 예:
GET /api/v1/pipeline/model-info
""",
)
async def get_pipeline_model_info():
    """현재 AI 모델/전처리 버전 정보 조회"""

    db_local_service = container.db_local_service()

    return {
        "status": "success",
        "message": "AI model version info retrieved successfully.",
        "model_info": db_local_service.get_model_metadata(),
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


async def _build_daily_consistency_result(
    target_date: date,
    site_no: int,
    bms_id: str,
):
    """특정 날짜의 파일/DB 정합성 검사 결과를 구성한다."""

    ess_id = _make_ess_id(site_no=site_no, bms_id=bms_id)

    file_service = container.file_service()
    db_local_service = container.db_local_service()

    file_status = file_service.inspect_pipeline_files(
        target_date=target_date,
        ess_id=ess_id,
    )

    latest_run = await db_local_service.find_latest_pipeline_run_by_date(
        target_date=target_date,
        site_no=site_no,
        bms_id=bms_id,
    )

    anomaly_score_count = 0

    if latest_run and latest_run.get("id") is not None:
        anomaly_score_count = await db_local_service.count_anomaly_scores_by_pipeline_run_id(
            pipeline_run_id=int(latest_run["id"]),
        )
    else:
        anomaly_score_count = await db_local_service.count_anomaly_scores_by_date(
            target_date=target_date,
            site_no=site_no,
            bms_id=bms_id,
        )

    saved_score_count = (latest_run or {}).get("saved_score_count") or 0
    pipeline_status = (latest_run or {}).get("status")

    result_row_count = file_status["result"].get("row_count")

    score_count_matched = (
        latest_run is not None
        and int(saved_score_count) == int(anomaly_score_count)
    )

    result_file_count_matched = None
    if result_row_count is not None:
        result_file_count_matched = int(result_row_count) == int(anomaly_score_count)

    checks = {
        "raw_file_exists": file_status["raw"].get("exists"),
        "preprocess_file_exists": file_status["preprocess"].get("exists"),
        "result_file_exists": file_status["result"].get("exists"),
        "pipeline_run_exists": latest_run is not None,
        "pipeline_status": pipeline_status,
        "saved_score_count": saved_score_count,
        "anomaly_score_count": anomaly_score_count,
        "score_count_matched": score_count_matched,
        "result_file_count_matched": result_file_count_matched,
    }

    issues = []

    if not checks["raw_file_exists"]:
        issues.append("raw parquet file is missing.")

    if not checks["preprocess_file_exists"]:
        issues.append("preprocess parquet file is missing.")

    if latest_run is None:
        issues.append("pipeline_run_log is missing.")

    if pipeline_status == "success":
        if not checks["result_file_exists"]:
            issues.append("pipeline status is success but result parquet file is missing.")

        if not score_count_matched:
            issues.append(
                "pipeline_run_log.saved_score_count and anomaly_score row count do not match."
            )

        if result_file_count_matched is False:
            issues.append(
                "result parquet row count and anomaly_score row count do not match."
            )

    elif pipeline_status == "error":
        issues.append("latest pipeline run status is error.")

    elif pipeline_status in {"empty", "waiting_7days"}:
        issues.append(f"latest pipeline run status is {pipeline_status}.")

    for data_type, status in file_status.items():
        if status.get("metadata_error"):
            issues.append(f"{data_type} metadata.json read error: {status.get('metadata_error')}")

        if status.get("read_error"):
            issues.append(f"{data_type} parquet read error: {status.get('read_error')}")

    if pipeline_status == "error":
        status = "error"
    elif latest_run is None and anomaly_score_count == 0 and not any(
        item.get("exists") for item in file_status.values()
    ):
        status = "missing"
    elif issues:
        status = "warning"
    else:
        status = "success"

    return {
        "status": status,
        "date": target_date.isoformat(),
        "site_no": site_no,
        "bms_id": bms_id,
        "ess_id": ess_id,
        "checks": checks,
        "issues": issues,
        "files": file_status,
        "latest_pipeline_run": latest_run,
    }


def _make_ess_id(site_no: int, bms_id: str) -> str:
    """파일 저장 경로에 사용할 ESS ID를 만든다."""

    safe_bms_id = str(bms_id).strip()

    for ch in ['\\', '/', ':', '*', '?', '"', '<', '>', '|', ' ']:
        safe_bms_id = safe_bms_id.replace(ch, "_")

    return f"SITE_{site_no}_BMS_{safe_bms_id}"


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

def _validate_bms_requires_site(
    site_no: Optional[int],
    bms_id: Optional[str],
) -> None:
    """bms_id를 사용할 경우 site_no도 같이 입력해야 한다."""

    if bms_id and site_no is None:
        raise HTTPException(
            status_code=400,
            detail="site_no is required when bms_id is provided.",
        )

def _validate_date_range(
    start_date: date,
    end_date: date,
) -> None:
    """기간 분석 날짜 범위 검증"""

    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be less than or equal to end_date.",
        )

    max_days = 366
    total_days = (end_date - start_date).days + 1

    if total_days > max_days:
        raise HTTPException(
            status_code=400,
            detail=f"Date range is too long. Maximum allowed days: {max_days}",
        )