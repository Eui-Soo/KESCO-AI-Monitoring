"""KESCO AI Monitoring Web API router."""

from typing import Literal, Optional

from fastapi import APIRouter, Query

from service.monitor_service import MonitorService


router = APIRouter(prefix="/api/v1/monitor", tags=["Monitor"])
monitor_service = MonitorService()


@router.get("/system-status", summary="Get Monitor System Status")
async def get_system_status():
    return await monitor_service.get_system_status()


@router.get("/dashboard/summary", summary="Get Monitor Dashboard Summary")
async def get_dashboard_summary():
    return await monitor_service.get_dashboard_summary()


@router.get("/sites", summary="Get Monitor Site List")
async def get_sites(
    keyword: Optional[str] = Query(default=None, description="사이트명/지역/제조사 검색어"),
    manufacturer: Optional[str] = Query(default=None, description="제조사 필터"),
    region: Optional[str] = Query(default=None, description="지역 필터"),
    install_area: Optional[str] = Query(default=None, description="설치 구역 필터"),
    status: Optional[str] = Query(default=None, description="normal/warning/abnormal/unavailable/data_missing"),
    sort: Literal["name", "installed_at", "score"] = Query(default="score"),
    order: Literal["asc", "desc"] = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
):
    return await monitor_service.get_sites(
        keyword=keyword,
        manufacturer=manufacturer,
        region=region,
        install_area=install_area,
        status=status,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )


@router.get("/sites/{site_id}", summary="Get Monitor Site Detail")
async def get_site_detail(site_id: str):
    return await monitor_service.get_site_detail(site_id)


@router.get("/sites/{site_id}/tree", summary="Get Monitor Site Hierarchy Tree")
async def get_site_tree(site_id: str):
    return await monitor_service.get_site_tree(site_id)


@router.get("/sites/{site_id}/level", summary="Get Monitor Site Level Detail")
async def get_level_detail(
    site_id: str,
    level: Literal["bank", "rack", "string", "module"] = Query(default="module"),
    bank_id: str = Query(default="BANK-01"),
    rack_id: Optional[str] = Query(default="RACK-03"),
    string_id: Optional[str] = Query(default="STRING-02"),
    module_id: Optional[str] = Query(default="MODULE-05"),
    target_date: Optional[str] = Query(default=None),
):
    return await monitor_service.get_level_detail(
        site_id=site_id,
        level=level,
        bank_id=bank_id,
        rack_id=rack_id,
        string_id=string_id,
        module_id=module_id,
        target_date=target_date,
    )


@router.get("/sites/{site_id}/trend", summary="Get Monitor Trend")
async def get_trend(
    site_id: str,
    level: Literal["site", "bank", "rack", "string", "module", "cell"] = Query(default="module"),
    bank_id: Optional[str] = None,
    rack_id: Optional[str] = None,
    string_id: Optional[str] = None,
    module_id: Optional[str] = None,
    cell_no: Optional[int] = None,
    days: int = Query(default=7, ge=1, le=30),
):
    return await monitor_service.get_trend(
        site_id=site_id,
        level=level,
        bank_id=bank_id,
        rack_id=rack_id,
        string_id=string_id,
        module_id=module_id,
        cell_no=cell_no,
        days=days,
    )


@router.get("/recommendations", summary="Get Monitor Recommendations")
async def get_recommendations(
    target_level: Literal["site", "bank", "rack", "string", "module", "cell"] = Query(default="module"),
    site_id: Optional[str] = Query(default="SITE-0021"),
    bank_id: Optional[str] = None,
    rack_id: Optional[str] = None,
    string_id: Optional[str] = None,
    module_id: Optional[str] = None,
    cell_no: Optional[int] = None,
):
    return await monitor_service.get_recommendations(
        target_level=target_level,
        site_id=site_id,
        bank_id=bank_id,
        rack_id=rack_id,
        string_id=string_id,
        module_id=module_id,
        cell_no=cell_no,
    )


@router.get("/db-summary", summary="Get Monitor Local DB Summary")
async def get_db_summary():
    """로컬 DB 연결 상태와 anomaly_score/pipeline_run_log 테이블 요약을 확인한다."""
    return await monitor_service.get_db_summary()


@router.get("/db-recent-scores", summary="Get Recent Anomaly Score Rows")
async def get_recent_anomaly_scores(limit: int = Query(default=20, ge=1, le=100)):
    """anomaly_score 최근 행을 스키마 유연하게 조회한다."""
    return await monitor_service.get_recent_anomaly_scores(limit=limit)
