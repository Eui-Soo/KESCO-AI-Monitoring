"""KESCO AI Monitoring service.

현재 화면 응답은 mock 데이터를 유지하되, DB 연결 상태/최근 anomaly_score 확인용
repository 계층을 붙여 실제 DB 연동 전환을 준비한다.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Literal, Optional

from fastapi import HTTPException

from repository.monitor_repository import MonitorRepository


NOW_TEXT = "2025-05-19 10:32:48"
LAST_ANALYSIS_TEXT = "2025-05-19 10:20:15"


SITES: list[dict[str, Any]] = [
    {
        "site_id": "SITE-0021",
        "site_no": 21,
        "site_name": "영광 ESS 2호기",
        "region": "전라남도 영광군",
        "install_area": "전력남서부",
        "manufacturer": "삼성SDI",
        "installed_at": "2024-11-15",
        "bms_id": "BMS-210531-KO001",
        "ess_capacity": "2.4 MWh",
        "bank_count": 2,
        "rack_count": 8,
        "string_count": 32,
        "module_count": 256,
        "cell_count": 5120,
        "is_ai_available": True,
        "latest_score": 93.7,
        "status": "abnormal",
        "status_text": "비정상",
        "last_data_time": "2025-05-19 10:20:00",
        "last_analysis_time": "2025-05-19 10:20:15",
        "data_status": "normal",
        "risk_location": "Bank 01 > Rack 03 > String 02 > Module 05 > Cell 07",
    },
    {
        "site_id": "SITE-0022",
        "site_no": 22,
        "site_name": "평택 ESS 1호기",
        "region": "경기도 평택시",
        "install_area": "경기남부",
        "manufacturer": "LG에너지솔루션",
        "installed_at": "2024-08-21",
        "bms_id": "BMS-210531-LG001",
        "ess_capacity": "1.8 MWh",
        "bank_count": 2,
        "rack_count": 6,
        "string_count": 24,
        "module_count": 192,
        "cell_count": 3840,
        "is_ai_available": True,
        "latest_score": 87.2,
        "status": "abnormal",
        "status_text": "비정상",
        "last_data_time": "2025-05-19 10:15:00",
        "last_analysis_time": "2025-05-19 10:15:12",
        "data_status": "normal",
        "risk_location": "Bank 01 > Rack 01 > String 04 > Module 02 > Cell 12",
    },
    {
        "site_id": "SITE-0023",
        "site_no": 23,
        "site_name": "군산 ESS 3호기",
        "region": "전라북도 군산시",
        "install_area": "전력동부",
        "manufacturer": "삼성SDI",
        "installed_at": "2024-09-30",
        "bms_id": "BMS-210531-KO003",
        "ess_capacity": "2.0 MWh",
        "bank_count": 1,
        "rack_count": 5,
        "string_count": 20,
        "module_count": 160,
        "cell_count": 3200,
        "is_ai_available": True,
        "latest_score": 72.4,
        "status": "warning",
        "status_text": "주의",
        "last_data_time": "2025-05-19 10:18:00",
        "last_analysis_time": "2025-05-19 10:18:09",
        "data_status": "normal",
        "risk_location": "Bank 01 > Rack 02 > String 01 > Module 08",
    },
    {
        "site_id": "SITE-0024",
        "site_no": 24,
        "site_name": "김해 ESS 1호기",
        "region": "경상남도 김해시",
        "install_area": "경남서부",
        "manufacturer": "LG에너지솔루션",
        "installed_at": "2024-07-10",
        "bms_id": "BMS-210531-LG004",
        "ess_capacity": "1.2 MWh",
        "bank_count": 1,
        "rack_count": 4,
        "string_count": 16,
        "module_count": 128,
        "cell_count": 2560,
        "is_ai_available": True,
        "latest_score": 68.1,
        "status": "warning",
        "status_text": "주의",
        "last_data_time": "2025-05-19 10:10:00",
        "last_analysis_time": "2025-05-19 10:10:23",
        "data_status": "normal",
        "risk_location": "Bank 01 > Rack 04 > String 03",
    },
    {
        "site_id": "SITE-0025",
        "site_no": 25,
        "site_name": "제주 ESS 2호기",
        "region": "제주특별자치도 제주시",
        "install_area": "제주권",
        "manufacturer": "CATL",
        "installed_at": "2024-12-05",
        "bms_id": "BMS-210531-CT002",
        "ess_capacity": "1.5 MWh",
        "bank_count": 1,
        "rack_count": 3,
        "string_count": 12,
        "module_count": 96,
        "cell_count": 1920,
        "is_ai_available": True,
        "latest_score": 34.6,
        "status": "normal",
        "status_text": "정상",
        "last_data_time": "2025-05-19 10:05:00",
        "last_analysis_time": "2025-05-19 10:05:08",
        "data_status": "normal",
        "risk_location": "-",
    },
    {
        "site_id": "SITE-0026",
        "site_no": 26,
        "site_name": "울산 ESS 1호기",
        "region": "울산광역시 울주군",
        "install_area": "영남동부",
        "manufacturer": "LG에너지솔루션",
        "installed_at": "2024-10-22",
        "bms_id": "BMS-210531-LG006",
        "ess_capacity": "1.0 MWh",
        "bank_count": 1,
        "rack_count": 2,
        "string_count": 8,
        "module_count": 64,
        "cell_count": 1280,
        "is_ai_available": False,
        "latest_score": None,
        "status": "unavailable",
        "status_text": "진단 불가",
        "last_data_time": "2025-05-18 18:45:00",
        "last_analysis_time": None,
        "data_status": "offline",
        "risk_location": "-",
    },
]


class MonitorService:
    def __init__(self, repository: Optional[MonitorRepository] = None):
        self.repository = repository or MonitorRepository()

    async def get_system_status(self) -> dict[str, Any]:
        db_ping = await self.repository.ping()
        return {
            "status": "success",
            "result": {
                "system_time": NOW_TEXT,
                "api_status": "normal",
                "db_status": "normal" if db_ping["ok"] else "abnormal",
                "db_message": db_ping["message"],
                "last_analysis_time": LAST_ANALYSIS_TEXT,
                "server_name": "kesco-ai-monitor-01",
                "server_ip": "10.10.10.25",
                "system_version": "1.0.0",
                "model_version": "cnn_lstm_ensemble_v1.0.0",
                "environment": "production",
                "data_source": "mock-ui + local-db-status",
            },
        }

    async def get_dashboard_summary(self) -> dict[str, Any]:
        counts = _status_counts()
        return {
            "status": "success",
            "result": {
                "summary": {
                    "total_site_count": 128,
                    "ai_available_site_count": 96,
                    **counts,
                    "recent_failed_analysis_count": 2,
                    "data_source": "mock",
                },
                "risk_ranking": _risk_ranking(limit=6),
                "priority_sites": [
                    {
                        "priority_rank": 1,
                        "site_id": "SITE-0021",
                        "site_name": "영광 ESS 2호기",
                        "reason": "이상 점수 매우 높음",
                        "score": 93.7,
                        "risk_level": "abnormal",
                        "recommend_action": "Cell 07 과열/전압 편차 즉시 점검",
                    },
                    {
                        "priority_rank": 2,
                        "site_id": "SITE-0022",
                        "site_name": "평택 ESS 1호기",
                        "reason": "이상 점수 높음",
                        "score": 87.2,
                        "risk_level": "abnormal",
                        "recommend_action": "Rack 01 Module 02 정밀 점검",
                    },
                    {
                        "priority_rank": 3,
                        "site_id": "SITE-0023",
                        "site_name": "군산 ESS 3호기",
                        "reason": "이상 점수 상승 추세",
                        "score": 72.4,
                        "risk_level": "warning",
                        "recommend_action": "최근 7일 추이 지속 관찰",
                    },
                ],
                "alerts": [
                    {"alert_type": "data_missing", "alert_level": "warning", "title": "데이터 수집 누락 사이트", "message": "최근 수집 누락 사이트가 존재합니다.", "site_count": 3, "created_at": NOW_TEXT},
                    {"alert_type": "analysis_failed", "alert_level": "abnormal", "title": "최근 분석 실패", "message": "최근 24시간 기준 분석 실패 2건이 발생했습니다.", "site_count": 2, "created_at": NOW_TEXT},
                ],
            },
        }

    async def get_sites(
        self,
        keyword: Optional[str] = None,
        manufacturer: Optional[str] = None,
        region: Optional[str] = None,
        install_area: Optional[str] = None,
        status: Optional[str] = None,
        sort: Literal["name", "installed_at", "score"] = "score",
        order: Literal["asc", "desc"] = "desc",
        page: int = 1,
        page_size: int = 24,
    ) -> dict[str, Any]:
        items = list(SITES)
        if keyword:
            keyword_lower = keyword.lower()
            items = [site for site in items if keyword_lower in f"{site['site_name']} {site['region']} {site['manufacturer']}".lower()]
        if manufacturer:
            items = [site for site in items if site["manufacturer"] == manufacturer]
        if region:
            items = [site for site in items if region in site["region"]]
        if install_area:
            items = [site for site in items if site["install_area"] == install_area]
        if status:
            items = [site for site in items if site["status"] == status]

        reverse = order == "desc"
        if sort == "name":
            items.sort(key=lambda site: site["site_name"], reverse=reverse)
        elif sort == "installed_at":
            items.sort(key=lambda site: site["installed_at"], reverse=reverse)
        else:
            items.sort(key=lambda site: site["latest_score"] if site["latest_score"] is not None else -1, reverse=reverse)

        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        return {
            "status": "success",
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "items": items[start:end],
            "filters": {
                "manufacturers": sorted({site["manufacturer"] for site in SITES}),
                "regions": sorted({site["region"] for site in SITES}),
                "install_areas": sorted({site["install_area"] for site in SITES}),
                "statuses": ["normal", "warning", "abnormal", "unavailable", "data_missing"],
            },
            "data_source": "mock",
        }

    async def get_site_detail(self, site_id: str) -> dict[str, Any]:
        site = _find_site(site_id)
        return {
            "status": "success",
            "result": {
                **site,
                "model_name": "CNN-LSTM Ensemble",
                "model_version": "cnn_lstm_ensemble_v1.0.0",
                "selected_level": "module",
                "selected_bank_id": "BANK-01",
                "selected_rack_id": "RACK-03",
                "selected_string_id": "STRING-02",
                "selected_module_id": "MODULE-05",
                "breadcrumb": [site["site_name"], "Bank 01", "Rack 03", "String 02", "Module 05"],
                "data_source": "mock",
            },
        }

    async def get_site_tree(self, site_id: str) -> dict[str, Any]:
        site = _find_site(site_id)
        return {"status": "success", "result": _tree(site)}

    async def get_level_detail(self, site_id: str, level: str = "module", bank_id: str = "BANK-01", rack_id: Optional[str] = "RACK-03", string_id: Optional[str] = "STRING-02", module_id: Optional[str] = "MODULE-05", target_date: Optional[str] = None) -> dict[str, Any]:
        site = _find_site(site_id)
        base = {
            "site_id": site["site_id"],
            "site_name": site["site_name"],
            "target_date": target_date,
            "level": level,
            "bank_id": bank_id,
            "rack_id": rack_id,
            "string_id": string_id,
            "module_id": module_id,
            "status": site["status"],
            "status_text": site["status_text"],
            "max_score": site["latest_score"] or 0,
            "avg_score": 54.2 if site["latest_score"] else 0,
            "last_analysis_time": site["last_analysis_time"],
            "data_source": "mock",
        }
        if level == "module":
            result = {**base, "module_name": "Module 05", "module_no": 5, "module_voltage": 74.1, "module_current": 38.2, "module_temperature": 33.6, "soc": 78.0, "soh": 96.2, "danger_cell_count": 1, "warning_cell_count": 3, "normal_cell_count": 16, "cells": _cells()}
        elif level == "string":
            result = {**base, "string_name": "String 02", "string_no": 2, "module_count": 6, "danger_cell_count": 3, "string_voltage": 444.6, "string_current": 38.2, "temperature_avg": 32.4, "modules": [{"module_id": f"MODULE-{i:02d}", "module_name": f"Module {i:02d}", "module_no": i, "status": "abnormal" if i == 5 else "normal", "max_score": 93.7 if i == 5 else 20 + i, "avg_score": 54.2 if i == 5 else 18.5 + i, "voltage": 74.0 + i / 10, "current": 38.2, "temperature": 31.5 + i / 2, "danger_cell_count": 1 if i == 5 else 0, "worst_cell_no": 7 if i == 5 else None} for i in range(1, 7)]}
        elif level == "rack":
            result = {**base, "rack_name": "Rack 03", "rack_no": 3, "string_count": 4, "module_count": 24, "danger_cell_count": 5, "rack_voltage": 1778.4, "rack_current": 38.2, "rack_temperature_avg": 31.8, "strings": [{"string_id": f"STRING-{i:02d}", "string_name": f"String {i:02d}", "string_no": i, "status": "abnormal" if i == 2 else "normal", "max_score": 79.4 if i == 2 else 28 + i, "avg_score": 46.2 if i == 2 else 21 + i, "module_count": 6, "danger_module_count": 1 if i == 2 else 0, "danger_cell_count": 3 if i == 2 else 0} for i in range(1, 5)]}
        else:
            result = {**base, "bank_name": "Bank 01", "bank_no": 1, "rack_count": 4, "normal_rack_count": 3, "warning_rack_count": 0, "abnormal_rack_count": 1, "offline_rack_count": 0, "racks": [{"rack_id": f"RACK-{i:02d}", "rack_name": f"Rack {i:02d}", "rack_no": i, "status": "abnormal" if i == 3 else "normal", "max_score": 86.5 if i == 3 else 31 + i, "avg_score": 52.7 if i == 3 else 22 + i, "string_count": 4, "module_count": 24, "danger_cell_count": 5 if i == 3 else 0} for i in range(1, 5)]}
        return {"status": "success", "result": result}

    async def get_trend(self, site_id: str, level: str = "module", bank_id: Optional[str] = None, rack_id: Optional[str] = None, string_id: Optional[str] = None, module_id: Optional[str] = None, cell_no: Optional[int] = None, days: int = 7) -> dict[str, Any]:
        _find_site(site_id)
        return {"status": "success", "result": {"target_level": level, "target_id": cell_no or module_id or string_id or rack_id or bank_id or site_id, "days": days, "trend": _trend(days=days), "data_source": "mock"}}

    async def get_recommendations(self, target_level: str = "module", site_id: Optional[str] = "SITE-0021", bank_id: Optional[str] = None, rack_id: Optional[str] = None, string_id: Optional[str] = None, module_id: Optional[str] = None, cell_no: Optional[int] = None) -> dict[str, Any]:
        target_id = cell_no or module_id or string_id or rack_id or bank_id or site_id
        return {"status": "success", "result": [{"recommendation_id": "REC-0001", "target_level": target_level, "target_id": target_id, "severity": "abnormal", "title": "위험 Cell에 대한 정밀 점검 필요", "message": "Cell 07에서 과열 및 전압 편차가 동시에 확인되었습니다.", "reason": "이상 점수 92/100, 전압 편차 +128mV, 온도 48.7℃", "action": "냉각 상태 점검 및 셀 단위 전압/저항 측정을 수행하세요.", "created_at": NOW_TEXT}, {"recommendation_id": "REC-0002", "target_level": target_level, "target_id": target_id, "severity": "warning", "title": "최근 이상 점수 상승 추세 관찰", "message": "최근 7일 기준 이상 점수가 상승하고 있습니다.", "reason": "7일 전 32점 → 현재 63점", "action": "다음 분석 주기까지 추이를 모니터링하고 점수 상승 지속 시 현장 점검을 예약하세요.", "created_at": NOW_TEXT}], "data_source": "mock"}

    async def get_db_summary(self) -> dict[str, Any]:
        return {"status": "success", "result": await self.repository.get_db_summary()}

    async def get_recent_anomaly_scores(self, limit: int = 20) -> dict[str, Any]:
        try:
            result = await self.repository.get_recent_anomaly_scores(limit=limit)
            return {"status": "success", "result": result}
        except Exception as exc:
            return {"status": "success", "result": {"table": "anomaly_score", "exists": False, "error": str(exc), "items": []}}


def _find_site(site_id: str) -> dict[str, Any]:
    for site in SITES:
        if site["site_id"] == site_id or str(site["site_no"]) == str(site_id):
            return site
    raise HTTPException(status_code=404, detail=f"Monitor site not found. site_id={site_id}")


def _status_counts() -> dict[str, int]:
    return {"normal_site_count": sum(1 for site in SITES if site["status"] == "normal"), "warning_site_count": sum(1 for site in SITES if site["status"] == "warning"), "abnormal_site_count": sum(1 for site in SITES if site["status"] == "abnormal"), "unavailable_site_count": sum(1 for site in SITES if site["status"] == "unavailable"), "data_missing_site_count": sum(1 for site in SITES if site["status"] == "data_missing")}


def _risk_ranking(limit: int = 10) -> list[dict[str, Any]]:
    ranked = [site for site in SITES if site["latest_score"] is not None]
    ranked.sort(key=lambda item: item["latest_score"], reverse=True)
    return [{"rank": index + 1, "site_id": site["site_id"], "site_no": site["site_no"], "site_name": site["site_name"], "region": site["region"], "install_area": site["install_area"], "manufacturer": site["manufacturer"], "latest_score": site["latest_score"], "status": site["status"], "status_text": site["status_text"], "last_analysis_time": site["last_analysis_time"], "risk_location": site["risk_location"]} for index, site in enumerate(ranked[:limit])]


def _tree(site: dict[str, Any]) -> dict[str, Any]:
    return {"site_id": site["site_id"], "site_name": site["site_name"], "tree": [{"bank_id": "BANK-01", "bank_name": "Bank 01", "status": "abnormal" if site["status"] == "abnormal" else site["status"], "score": site["latest_score"] or 0, "racks": [{"rack_id": f"RACK-{rack_no:02d}", "rack_name": f"Rack {rack_no:02d}", "status": "abnormal" if rack_no == 3 and site["status"] == "abnormal" else "normal", "score": 86.5 if rack_no == 3 and site["status"] == "abnormal" else 28.2 + rack_no, "strings": [{"string_id": f"STRING-{string_no:02d}", "string_name": f"String {string_no:02d}", "status": "abnormal" if rack_no == 3 and string_no == 2 and site["status"] == "abnormal" else "normal", "score": 79.4 if rack_no == 3 and string_no == 2 and site["status"] == "abnormal" else 25.0 + string_no, "modules": [{"module_id": f"MODULE-{module_no:02d}", "module_name": f"Module {module_no:02d}", "status": "abnormal" if rack_no == 3 and string_no == 2 and module_no == 5 and site["status"] == "abnormal" else "normal", "score": 93.7 if rack_no == 3 and string_no == 2 and module_no == 5 and site["status"] == "abnormal" else 18.0 + module_no} for module_no in range(1, 7)]} for string_no in range(1, 5)]} for rack_no in range(1, 5)]}]}


def _cells() -> list[dict[str, Any]]:
    scores = [18, 22, 31, 26, 29, 34, 92, 45, 28, 33, 24, 37, 41, 27, 39, 32, 30, 25, 48, 21]
    cells = []
    for index, score in enumerate(scores, start=1):
        if score >= 80:
            status, status_text = "abnormal", "위험"
        elif score >= 40:
            status, status_text = "warning", "주의"
        else:
            status, status_text = "normal", "정상"
        cells.append({"cell_no": index, "cell_name": f"Cell {index:02d}", "score": score, "status": status, "status_text": status_text, "voltage": round(3.63 - (index * 0.006) + (score / 1000), 3), "temperature": round(31.5 + (score / 8), 1), "internal_resistance": round(1.05 + (score / 120), 2), "capacity": round(99.0 - (score / 30), 1), "soc": round(78.5 - (index % 5), 1), "trend_score": score + 4})
    return cells


def _trend(days: int = 7) -> list[dict[str, Any]]:
    base_date = datetime(2025, 5, 15)
    values = [32, 35, 41, 48, 55, 63, 58]
    return [{"date": (base_date + timedelta(days=index)).strftime("%Y-%m-%d"), "max_score": value, "avg_score": round(value * 0.68, 1), "status": "abnormal" if value >= 71 else "warning" if value >= 40 else "normal"} for index, value in enumerate(values[-days:])]
