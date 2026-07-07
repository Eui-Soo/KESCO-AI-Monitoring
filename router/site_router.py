"""ESS 사이트/장치 관리 API

관제 DB에 등록된 ESS 사이트/장치 정보를 조회하고,
AI 서버 로컬 DB에 동기화하는 API를 제공한다.

제공 API:
    GET  /api/v1/sites/remote
    GET  /api/v1/sites/device-type-summary
    POST /api/v1/sites/sync
    GET  /api/v1/sites
    GET  /api/v1/sites/{site_no}
"""

from fastapi import APIRouter, HTTPException, Path

from core.container import container


router = APIRouter(
    prefix="/api/v1/sites",
    tags=["Sites"],
)


@router.get(
    "/remote",
    summary="Get Remote ESS Site List",
    description="""
관제 DB에서 ESS 사이트/장치 목록을 직접 조회한다.

사용 테이블:
- tb_emc_site_info
- tb_emc_dvc_info

이 API는 관제 DB 연결이 정상인지,
실제 사이트/장치 데이터가 어떤 형태로 들어있는지 확인하기 위한 API다.

주의:
- 원격 관제 DB를 직접 조회한다.
- 로컬 DB에는 저장하지 않는다.
- 로컬 DB 저장은 POST /api/v1/sites/sync 에서 처리한다.
""",
)
async def get_remote_sites():
    """관제 DB 사이트/장치 목록 조회"""

    remote_db_service = container.remote_db_service()
    sites = await remote_db_service.find_sites()

    if not sites:
        return {
            "status": "empty",
            "count": 0,
            "message": "No ESS sites found in remote monitoring DB.",
            "results": [],
        }

    return {
        "status": "success",
        "count": len(sites),
        "message": "Remote ESS site list retrieved successfully.",
        "results": sites,
    }


@router.get(
    "/device-type-summary",
    summary="Get Remote Device Type Summary",
    description="""
관제 DB의 장치 유형/용도 분포를 조회한다.

사용 테이블:
- tb_emc_dvc_info

왜 필요한가?
- tb_emc_dvc_info에는 BMS 외에도 PCS, EMS, 계측기 등 다른 장치가 섞여 있을 수 있다.
- 어떤 dvc_type / dvc_usg 값이 AI 분석 대상 BMS인지 먼저 확인해야 한다.
""",
)
async def get_device_type_summary():
    """관제 DB 장치 유형/용도 분포 조회"""

    remote_db_service = container.remote_db_service()
    summary = await remote_db_service.find_device_type_summary()

    if not summary:
        return {
            "status": "empty",
            "count": 0,
            "message": "No device type summary found in remote monitoring DB.",
            "results": [],
        }

    return {
        "status": "success",
        "count": len(summary),
        "message": "Remote device type summary retrieved successfully.",
        "results": summary,
    }


@router.post(
    "/sync",
    summary="Sync Remote ESS Sites To Local DB",
    description="""
관제 DB의 사이트/장치 목록을 AI 서버 로컬 DB에 저장 또는 갱신한다.

처리 흐름:
1. 원격 관제 DB에서 tb_emc_site_info + tb_emc_dvc_info 조회
2. 로컬 DB ess_site 테이블에 site_no 기준 저장/갱신
3. 로컬 DB ess_device 테이블에 dvc_id 기준 저장/갱신

주의:
- ai_enabled 값은 사용자가 직접 끄거나 켤 수 있는 값이므로 동기화 시 덮어쓰지 않는다.
- 관제 DB에는 쓰기 작업을 하지 않는다.
""",
)
async def sync_sites():
    """관제 DB 사이트/장치 목록을 로컬 DB에 동기화"""

    remote_db_service = container.remote_db_service()
    db_local_service = container.db_local_service()

    remote_sites = await remote_db_service.find_sites()

    if not remote_sites:
        return {
            "status": "empty",
            "message": "No remote ESS sites found. Nothing synced.",
            "remote_count": 0,
            "sync_result": {
                "site_created_count": 0,
                "site_updated_count": 0,
                "device_created_count": 0,
                "device_updated_count": 0,
                "skipped_device_count": 0,
            },
        }

    sync_result = await db_local_service.upsert_sites(remote_sites)

    return {
        "status": "success",
        "message": "Remote ESS site/device list synced to local DB successfully.",
        "remote_count": len(remote_sites),
        "sync_result": sync_result,
    }


@router.get(
    "",
    summary="Get Local ESS Site List",
    description="""
AI 서버 로컬 DB에 저장된 ESS 사이트/장치 목록을 조회한다.

사용 전:
- 먼저 POST /api/v1/sites/sync 를 실행해야 데이터가 들어온다.

응답:
- 사이트 1개 안에 devices 배열이 포함된다.
- 각 device에는 dvc_id, bms_id, serial_number가 포함된다.
""",
)
async def get_local_sites():
    """로컬 DB 사이트/장치 목록 조회"""

    db_local_service = container.db_local_service()
    sites = await db_local_service.find_sites()

    if not sites:
        return {
            "status": "empty",
            "count": 0,
            "message": "No local ESS sites found. Run POST /api/v1/sites/sync first.",
            "results": [],
        }

    return {
        "status": "success",
        "count": len(sites),
        "message": "Local ESS site list retrieved successfully.",
        "results": sites,
    }


@router.get(
    "/{site_no}",
    summary="Get Local ESS Site Detail",
    description="""
AI 서버 로컬 DB에 저장된 특정 ESS 사이트 상세 정보를 조회한다.

조회 기준:
- site_no

사용 예:
- GET /api/v1/sites/1
""",
)
async def get_local_site_detail(
    site_no: int = Path(
        ...,
        ge=1,
        description="관제 DB 사이트 번호. 예: 1",
    )
):
    """특정 사이트 상세 조회"""

    db_local_service = container.db_local_service()
    site = await db_local_service.find_site_by_site_no(site_no)

    if site is None:
        raise HTTPException(
            status_code=404,
            detail=f"ESS site not found. site_no={site_no}",
        )

    return {
        "status": "success",
        "message": "Local ESS site detail retrieved successfully.",
        "result": site,
    }
