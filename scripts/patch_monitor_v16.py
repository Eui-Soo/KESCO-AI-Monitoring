from pathlib import Path
import re

ROOT = Path.cwd()
TARGET = ROOT / "service" / "monitor_service.py"

if not TARGET.exists():
    raise SystemExit(f"monitor_service.py not found: {TARGET}")

text = TARGET.read_text(encoding="utf-8")
backup = TARGET.with_suffix(".py.v16.bak")
if not backup.exists():
    backup.write_text(text, encoding="utf-8")

# ------------------------------------------------------------------
# 1) Make site_id unique by site_no + bms_id.
#    Existing SITE-{site_no} IDs collide when one site has multiple BMS.
# ------------------------------------------------------------------
helper_block = r'''

def _safe_site_token(value: Any) -> str:
    text = str(value or "").strip()
    safe = []
    for ch in text:
        if ch.isalnum() or ch in {"-", "_"}:
            safe.append(ch)
        else:
            safe.append("-")
    result = "".join(safe).strip("-")
    return result or "UNKNOWN"


def _make_monitor_site_id(site_no: int, bms_id: Any) -> str:
    return f"SITE-{int(site_no):04d}__BMS-{_safe_site_token(bms_id)}"


def _legacy_monitor_site_id(site_no: int) -> str:
    return f"SITE-{int(site_no):04d}"
'''

if "def _make_monitor_site_id" not in text:
    marker = "\ndef _find_site(site_id: str) -> dict[str, Any]:"
    if marker not in text:
        raise SystemExit("Cannot find _find_site marker")
    text = text.replace(marker, helper_block + marker, 1)

old_find_optional = r'''def _find_site_optional(site_id: str, sites: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    for site in sites:
        if site.get("site_id") == site_id or str(site.get("site_no")) == str(site_id):
            return site
    return None
'''
new_find_optional = r'''def _find_site_optional(site_id: str, sites: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    requested = str(site_id or "")

    # 1순위: site_no + bms_id가 포함된 새 site_id 정확 매칭
    for site in sites:
        if str(site.get("site_id")) == requested:
            return site

    # 2순위: BMS ID 자체로 조회하는 경우
    for site in sites:
        if str(site.get("bms_id")) == requested:
            return site

    # 3순위: legacy SITE-0001 또는 숫자 site_no 조회.
    # 같은 site_no에 여러 BMS가 있으면 가장 위험점수가 높은 항목을 반환한다.
    candidates = []
    for site in sites:
        legacy_id = _legacy_monitor_site_id(int(site.get("site_no") or 0))
        if legacy_id == requested or str(site.get("site_no")) == requested:
            candidates.append(site)

    if candidates:
        candidates.sort(
            key=lambda item: item.get("latest_score") if item.get("latest_score") is not None else -1,
            reverse=True,
        )
        return candidates[0]

    return None
'''
if old_find_optional in text:
    text = text.replace(old_find_optional, new_find_optional, 1)
else:
    text = re.sub(
        r'def _find_site_optional\(site_id: str, sites: list\[dict\[str, Any\]\]\) -> Optional\[dict\[str, Any\]\]:\n(?:    .*\n)+?    return None\n',
        new_find_optional,
        text,
        count=1,
    )

# ------------------------------------------------------------------
# 2) Replace DB-generated Korean strings with ASCII strings.
#    This prevents mojibake in PowerShell/API checks and keeps UI stable.
# ------------------------------------------------------------------
old_status_from_score = r'''def _status_from_score(score: Optional[float]) -> tuple[str, str]:
    if score is None:
        return "unavailable", "진단 불가"
    if score >= 71:
        return "abnormal", "비정상"
    if score >= 40:
        return "warning", "주의"
    return "normal", "정상"
'''
new_status_from_score = r'''def _status_from_score(score: Optional[float]) -> tuple[str, str]:
    if score is None:
        return "unavailable", "Unavailable"
    if score >= 71:
        return "abnormal", "Abnormal"
    if score >= 40:
        return "warning", "Warning"
    return "normal", "Normal"
'''
if old_status_from_score in text:
    text = text.replace(old_status_from_score, new_status_from_score, 1)
else:
    text = re.sub(
        r'def _status_from_score\(score: Optional\[float\]\) -> tuple\[str, str\]:\n(?:    .*\n)+?    return "normal", .*\n',
        new_status_from_score,
        text,
        count=1,
    )

old_site_func = re.search(r'def _site_from_db_row\(row: dict\[str, Any\]\) -> dict\[str, Any\]:\n(?:    .*\n)+?\n\ndef _status_counts_from_sites', text)
new_site_func = r'''def _site_from_db_row(row: dict[str, Any]) -> dict[str, Any]:
    site_no = int(row.get("site_no") or 0)
    bms_id = row.get("bms_id") or "-"
    score = _normalize_score(row.get("latest_score"))
    avg_score = _normalize_score(row.get("average_score"))
    status, status_text = _status_from_score(score)
    rack_count = int(row.get("rack_count") or 0)
    string_count = int(row.get("string_count") or 0)
    module_count = int(row.get("module_count") or 0)
    bank_count = int(row.get("bank_count") or 0)

    return {
        "site_id": _make_monitor_site_id(site_no, bms_id),
        "legacy_site_id": _legacy_monitor_site_id(site_no),
        "site_no": site_no,
        "site_name": f"ESS Site {site_no}",
        "region": "Local DB",
        "install_area": "-",
        "manufacturer": "-",
        "installed_at": str(row.get("target_date") or "-"),
        "bms_id": bms_id,
        "ess_capacity": "-",
        "bank_count": bank_count,
        "rack_count": rack_count,
        "string_count": string_count,
        "module_count": module_count,
        "cell_count": module_count * 20 if module_count else 20,
        "is_ai_available": score is not None,
        "latest_score": score,
        "average_score": avg_score,
        "status": status,
        "status_text": status_text,
        "last_data_time": row.get("last_data_time"),
        "last_analysis_time": row.get("last_analysis_time"),
        "data_status": "normal",
        "risk_location": "Latest anomaly_score result",
        "selected_rack_no": 1,
        "selected_string_no": 1,
        "selected_module_no": 1,
        "score_row_count": int(row.get("score_row_count") or 0),
        "data_source": "local-db",
    }


def _status_counts_from_sites'''
if old_site_func:
    text = text[:old_site_func.start()] + new_site_func + text[old_site_func.end():]
else:
    raise SystemExit("Cannot find _site_from_db_row block")

# Additional DB-dashboard generated strings that commonly appear in PowerShell output.
replacements = {
    '"이상 점수 높음"': '"High anomaly score"',
    '"이상 점수 상승/주의 구간"': '"Score increased / warning zone"',
    '"상세 화면에서 Bank/Rack/Module 단위 점검 필요"': '"Check Bank/Rack/Module detail view"',
    '"로컬 DB 연동 활성화"': '"Local DB connected"',
    '"anomaly_score 기반 대시보드 요약을 표시 중입니다."': '"Dashboard is using anomaly_score data."',
    '"파이프라인 실행 이력"': '"Pipeline run history"',
    '"위험 점수 대상 정밀 점검 필요"': '"Detailed inspection required"',
    '"anomaly_score 기준 높은 점수가 확인되었습니다."': '"High score was detected from anomaly_score."',
    '"최신 AI 분석 결과 기반 위험도 산정"': '"Risk based on latest analysis result"',
    '"상세 화면에서 Bank/Rack/String/Module/Cell 위치를 확인하고 현장 점검 여부를 판단하세요."': '"Check Bank/Rack/String/Module/Cell detail and decide field inspection."',
    '"분석 결과 추이 관찰"': '"Watch analysis trend"',
    '"실제 추이 API 연동 전까지는 최근 분석 결과 중심으로 표시합니다."': '"Showing latest analysis results until trend API is connected."',
    '"v11 단계: 대시보드/목록/모듈 상세 DB 전환"': '"v11: dashboard/list/module detail DB bridge"',
    '"다음 단계에서 target_date별 trend 조회를 연결하세요."': '"Connect trend query by target_date in the next step."',
}
for src, dst in replacements.items():
    text = text.replace(src, dst)

TARGET.write_text(text, encoding="utf-8")
print("v16 monitor patch applied")
print(f"backup: {backup}")
