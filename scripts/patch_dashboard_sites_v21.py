# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path.cwd()
MONITOR_JS = ROOT / "static" / "monitor" / "monitor.js"
MONITOR_CSS = ROOT / "static" / "monitor" / "monitor.css"
INDEX_HTML = ROOT / "static" / "monitor" / "index.html"
MONITOR_SERVICE = ROOT / "service" / "monitor_service.py"


def backup(path: Path) -> None:
    if path.exists():
        bak = path.with_suffix(path.suffix + ".v21.bak")
        bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"[backup] {bak}")


def replace_function(text: str, func_name: str, new_func: str) -> str:
    idx = text.find(f"async function {func_name}")
    if idx == -1:
        idx = text.find(f"function {func_name}")
    if idx == -1:
        raise RuntimeError(f"Cannot find function: {func_name}")

    brace = text.find("{", idx)
    if brace == -1:
        raise RuntimeError(f"Cannot find function body: {func_name}")

    depth = 0
    in_str = None
    escaped = False
    in_template = False
    i = brace

    while i < len(text):
        ch = text[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_str:
                in_str = None
            i += 1
            continue
        if in_template:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == "`":
                in_template = False
            i += 1
            continue
        if ch in ("'", '"'):
            in_str = ch
        elif ch == "`":
            in_template = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[:idx] + new_func.strip() + "\n\n" + text[i + 1:]
        i += 1
    raise RuntimeError(f"Cannot parse function boundary: {func_name}")


def patch_index() -> None:
    if not INDEX_HTML.exists():
        print("[skip] index.html not found")
        return
    backup(INDEX_HTML)
    text = INDEX_HTML.read_text(encoding="utf-8")
    text = re.sub(r'/static/monitor/monitor\.css(?:\?v=\d+)?', '/static/monitor/monitor.css?v=21', text)
    text = re.sub(r'/static/monitor/monitor_v7_fix\.css(?:\?v=\d+)?', '/static/monitor/monitor_v7_fix.css?v=21', text)
    text = re.sub(r'/static/monitor/monitor\.js(?:\?v=\d+)?', '/static/monitor/monitor.js?v=21', text)
    INDEX_HTML.write_text(text, encoding="utf-8")
    print("[ok] index.html cache busting v21")


def patch_monitor_service() -> None:
    if not MONITOR_SERVICE.exists():
        print("[skip] monitor_service.py not found")
        return
    backup(MONITOR_SERVICE)
    text = MONITOR_SERVICE.read_text(encoding="utf-8")

    helper = r'''
def _demo_site_meta(site_no: int, bms_id: str) -> dict[str, str]:
    manufacturers = [
        "Samsung SDI",
        "LG Energy Solution",
        "SK On",
        "CATL",
    ]
    regions = [
        "Daejeon",
        "Sejong",
        "Chungnam",
        "Gyeonggi",
        "Jeonbuk",
        "Jeonnam",
    ]
    install_areas = [
        "Central Area",
        "North Area",
        "South Area",
        "West Area",
        "East Area",
    ]

    seed = abs(hash(f"{site_no}:{bms_id}"))
    return {
        "manufacturer": manufacturers[seed % len(manufacturers)],
        "region": regions[(seed // 7) % len(regions)],
        "install_area": install_areas[(seed // 13) % len(install_areas)],
    }


def _format_display_datetime(value: Any) -> Any:
    if value is None:
        return None
    text = str(value).replace("T", " ")
    if "." in text:
        text = text.split(".", 1)[0]
    return text[:19]
'''
    if "def _demo_site_meta(" not in text:
        insert_at = text.find("def _find_site(")
        if insert_at == -1:
            insert_at = text.find("def _site_from_db_row(")
        if insert_at == -1:
            raise RuntimeError("Cannot find insertion point for helper")
        text = text[:insert_at] + helper + "\n\n" + text[insert_at:]

    new_site_func = r'''
def _site_from_db_row(row: dict[str, Any]) -> dict[str, Any]:
    site_no = int(row.get("site_no") or 0)
    bms_id = row.get("bms_id") or "-"
    score = _normalize_score(row.get("latest_score"))
    avg_score = _normalize_score(row.get("average_score"))
    status, status_text = _status_from_score(score)

    rack_count = int(row.get("rack_count") or 0)
    string_count = int(row.get("string_count") or 0)
    module_count = int(row.get("module_count") or 0)
    bank_count = int(row.get("bank_count") or 0)

    meta = _demo_site_meta(site_no, str(bms_id))
    safe_bms_id = str(bms_id).strip().replace(" ", "_").replace("/", "_").replace("\\", "_")
    legacy_site_id = f"SITE-{site_no:04d}"

    return {
        "site_id": f"{legacy_site_id}__BMS-{safe_bms_id}",
        "legacy_site_id": legacy_site_id,
        "site_no": site_no,
        "site_name": f"ESS Site {site_no}",
        "region": meta["region"],
        "install_area": meta["install_area"],
        "manufacturer": meta["manufacturer"],
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
        "last_data_time": _format_display_datetime(row.get("last_data_time")),
        "last_analysis_time": _format_display_datetime(row.get("last_analysis_time")),
        "data_status": "normal",
        "risk_location": "Latest anomaly_score result",
        "selected_rack_no": 1,
        "selected_string_no": 1,
        "selected_module_no": 1,
        "score_row_count": int(row.get("score_row_count") or 0),
        "data_source": "local-db",
    }
'''
    pattern = re.compile(r'\ndef _site_from_db_row\(row: dict\[str, Any\]\).*?(?=\n\ndef _status_counts_from_sites)', re.S)
    if not pattern.search(text):
        raise RuntimeError("Cannot find _site_from_db_row block")
    text = pattern.sub("\n" + new_site_func.rstrip(), text)

    MONITOR_SERVICE.write_text(text, encoding="utf-8")
    print("[ok] monitor_service.py site metadata/time patch")


JS_HELPERS = r'''
function v21StatusLabel(value) {
  const raw = typeof value === 'object' ? (value?.status || value?.status_text) : value;
  const key = String(raw || '').toLowerCase();
  if (key === 'abnormal' || key === 'danger' || key === '비정상' || key === '위험') return '비정상';
  if (key === 'warning' || key === 'caution' || key === '주의') return '주의';
  if (key === 'normal' || key === '정상') return '정상';
  if (key === 'unavailable' || key === '진단 불가') return '진단 불가';
  if (key === 'data_missing' || key === '데이터 없음') return '데이터 없음';
  return raw || '-';
}

function v21StatusClass(value) {
  const label = v21StatusLabel(value);
  if (label === '비정상') return 'bad';
  if (label === '주의') return 'warn';
  if (label === '정상') return 'good';
  return 'gray';
}

function v21Badge(value) {
  const label = v21StatusLabel(value);
  return `<span class="state-badge ${v21StatusClass(value)}">${escapeHtml(label)}</span>`;
}

function v21Time(value) {
  if (value === null || value === undefined || value === '') return '-';
  let text = String(value).replace('T', ' ');
  text = text.replace(/\.\d+/, '');
  return text.slice(0, 19);
}

function v21ScoreValue(value) {
  if (value === null || value === undefined || value === '') return '-';
  const n = Number(value);
  if (Number.isNaN(n)) return value;
  return Math.round(n * 10) / 10;
}

function v21RiskText(site) {
  const score = v21ScoreValue(site?.latest_score);
  const label = v21StatusLabel(site);
  if (label === '비정상') return `즉시 점검 권고 · 최고 이상점수 ${score}`;
  if (label === '주의') return `주의 관찰 필요 · 최고 이상점수 ${score}`;
  if (label === '정상') return `정상 범위 · 최고 이상점수 ${score}`;
  return '진단 결과 없음';
}

function v21FilterSiteRows() {
  const q = String(document.getElementById('v21SiteSearch')?.value || '').toLowerCase();
  const manufacturer = String(document.getElementById('v21Manufacturer')?.value || '');
  const region = String(document.getElementById('v21Region')?.value || '');
  const area = String(document.getElementById('v21Area')?.value || '');
  const status = String(document.getElementById('v21Status')?.value || '');

  document.querySelectorAll('.v21-site-row').forEach((row) => {
    const okSearch = !q || String(row.dataset.search || '').toLowerCase().includes(q);
    const okManufacturer = !manufacturer || row.dataset.manufacturer === manufacturer;
    const okRegion = !region || row.dataset.region === region;
    const okArea = !area || row.dataset.area === area;
    const okStatus = !status || row.dataset.status === status;
    row.style.display = okSearch && okManufacturer && okRegion && okArea && okStatus ? '' : 'none';
  });
}
window.v21FilterSiteRows = v21FilterSiteRows;
'''


RENDER_DASHBOARD = r'''
async function renderDashboard() {
  try {
    setActive('dashboard');
    setLoading('대시보드 로딩 중');
    await loadCommonData();

    const dashboardData = await fetchJson(API.dashboard, null);
    const result = dashboardData?.result || {};
    const summary = result.summary || {};
    const sites = state.sites || [];

    const ranking = sites
      .filter((s) => s.latest_score !== null && s.latest_score !== undefined)
      .slice()
      .sort((a, b) => Number(b.latest_score || 0) - Number(a.latest_score || 0))
      .slice(0, 6);

    const priority = ranking.slice(0, 3);
    const counts = {
      normal: summary.normal_site_count ?? sites.filter((s) => s.status === 'normal').length,
      warning: summary.warning_site_count ?? sites.filter((s) => s.status === 'warning').length,
      abnormal: summary.abnormal_site_count ?? sites.filter((s) => s.status === 'abnormal').length,
    };

    content.innerHTML = `
    <div class="page v21-dashboard-page">
      <div class="v21-dashboard-top">
        <section class="v21-kpi-card">
          <div class="v21-kpi-icon">▦</div>
          <div>
            <div class="v21-kpi-label">전체 사이트</div>
            <div class="v21-kpi-value">${escapeHtml(summary.total_site_count ?? sites.length)}</div>
          </div>
        </section>
        <section class="v21-kpi-card">
          <div class="v21-kpi-icon green">AI</div>
          <div>
            <div class="v21-kpi-label">AI 진단 가능</div>
            <div class="v21-kpi-value green">${escapeHtml(summary.ai_available_site_count ?? sites.filter((s) => s.is_ai_available).length)}</div>
          </div>
        </section>
        <section class="v21-status-card">
          <div class="v21-status-title">사이트 상태 요약</div>
          <div class="v21-status-counts">
            <div><b class="green">${escapeHtml(counts.normal)}</b><span>정상</span></div>
            <div><b class="orange">${escapeHtml(counts.warning)}</b><span>주의</span></div>
            <div><b class="red">${escapeHtml(counts.abnormal)}</b><span>비정상</span></div>
          </div>
        </section>
      </div>

      <div class="v21-dashboard-main">
        <section class="panel v21-ranking-panel">
          <div class="panel-title"><span class="mini-icon">▥</span>이상 점수 상위 사이트</div>
          <div class="v21-ranking-table-wrap">
            <table class="v21-table">
              <thead>
                <tr>
                  <th style="width:64px">순위</th>
                  <th>사이트 / BMS</th>
                  <th>지역</th>
                  <th>설치구역</th>
                  <th>제조사</th>
                  <th style="width:130px">최고 점수</th>
                  <th style="width:110px">상태</th>
                  <th style="width:170px">최근 분석</th>
                </tr>
              </thead>
              <tbody>
                ${ranking.map((s, i) => `
                  <tr class="clickable-row" onclick="selectSite('${escapeHtml(s.site_id)}')">
                    <td><span class="v21-rank">${escapeHtml(i + 1)}</span></td>
                    <td><b>${escapeHtml(s.site_name)}</b><small>${escapeHtml(s.bms_id || '-')}</small></td>
                    <td>${escapeHtml(s.region || '-')}</td>
                    <td>${escapeHtml(s.install_area || '-')}</td>
                    <td>${escapeHtml(s.manufacturer || '-')}</td>
                    <td>${score(v21ScoreValue(s.latest_score))}</td>
                    <td>${v21Badge(s)}</td>
                    <td>${escapeHtml(v21Time(s.last_analysis_time))}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
          <div class="more-link" onclick="nav('sites')">전체 사이트 목록으로 이동 <span>›</span></div>
        </section>

        <section class="panel v21-priority-panel">
          <div class="panel-title"><span class="mini-icon">⚠</span>우선 점검 대상 TOP 3</div>
          <div class="v21-priority-list">
            ${priority.map((s, i) => `
              <div class="v21-priority-item ${v21StatusClass(s)}" onclick="selectSite('${escapeHtml(s.site_id)}')">
                <div class="v21-priority-rank">${escapeHtml(i + 1)}</div>
                <div class="v21-priority-body">
                  <div class="v21-priority-title">${escapeHtml(s.site_name)}</div>
                  <div class="v21-priority-sub">${escapeHtml(s.bms_id || '-')} · ${escapeHtml(s.install_area || '-')} · ${escapeHtml(s.manufacturer || '-')}</div>
                </div>
                <div class="v21-priority-score">
                  <b>${escapeHtml(v21ScoreValue(s.latest_score))}</b>
                  <span>${escapeHtml(v21RiskText(s))}</span>
                </div>
                <div class="chev">›</div>
              </div>
            `).join('')}
          </div>
        </section>
      </div>
    </div>`;
  } catch (error) {
    console.error('[monitor] renderDashboard failed', error);
    showError('대시보드 표시 중 오류가 발생했습니다.', error.stack || error.message);
  }
}
'''

RENDER_SITES = r'''
async function renderSites() {
  try {
    setActive('sites');
    setLoading('사이트 목록 로딩 중');
    await loadCommonData();

    const sites = state.sites || [];
    const manufacturers = [...new Set(sites.map((s) => s.manufacturer || '-'))].sort();
    const regions = [...new Set(sites.map((s) => s.region || '-'))].sort();
    const areas = [...new Set(sites.map((s) => s.install_area || '-'))].sort();

    const aiCount = sites.filter((s) => s.is_ai_available).length;
    const abnormalCount = sites.filter((s) => s.status === 'abnormal').length;
    const warningCount = sites.filter((s) => s.status === 'warning').length;

    content.innerHTML = `
    <div class="page v21-sites-page">
      <div class="v21-page-heading">
        <div>
          <h1>사이트 목록</h1>
          <p>전체 사이트 현황 및 AI 진단 결과를 확인합니다.</p>
        </div>
        <div class="v21-site-summary">
          <div><span>표시 사이트</span><b>${escapeHtml(sites.length)}</b></div>
          <div><span>진단 가능</span><b>${escapeHtml(aiCount)}</b></div>
          <div><span>주의</span><b class="orange">${escapeHtml(warningCount)}</b></div>
          <div><span>비정상</span><b class="red">${escapeHtml(abnormalCount)}</b></div>
        </div>
      </div>

      <section class="v21-filter-card">
        <input id="v21SiteSearch" class="v21-input" oninput="v21FilterSiteRows()" placeholder="사이트명 또는 BMS ID 검색" />
        <select id="v21Manufacturer" class="v21-select" onchange="v21FilterSiteRows()">
          <option value="">제조사 전체</option>
          ${manufacturers.map((v) => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join('')}
        </select>
        <select id="v21Region" class="v21-select" onchange="v21FilterSiteRows()">
          <option value="">지역 전체</option>
          ${regions.map((v) => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join('')}
        </select>
        <select id="v21Area" class="v21-select" onchange="v21FilterSiteRows()">
          <option value="">설치구역 전체</option>
          ${areas.map((v) => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join('')}
        </select>
        <select id="v21Status" class="v21-select" onchange="v21FilterSiteRows()">
          <option value="">상태 전체</option>
          <option value="normal">정상</option>
          <option value="warning">주의</option>
          <option value="abnormal">비정상</option>
          <option value="unavailable">진단 불가</option>
        </select>
      </section>

      <section class="panel v21-sites-table-panel">
        <div class="v21-sites-table-wrap">
          <table class="v21-table v21-sites-table">
            <thead>
              <tr>
                <th>사이트 / BMS</th>
                <th>지역</th>
                <th>설치구역</th>
                <th>제조사</th>
                <th>설치일</th>
                <th>최신 이상점수</th>
                <th>상태</th>
                <th>최근 분석시각</th>
                <th>데이터</th>
                <th>상세</th>
              </tr>
            </thead>
            <tbody>
              ${sites.map((s) => `
                <tr class="v21-site-row"
                    data-search="${escapeHtml(`${s.site_name || ''} ${s.bms_id || ''} ${s.region || ''} ${s.install_area || ''} ${s.manufacturer || ''}`)}"
                    data-manufacturer="${escapeHtml(s.manufacturer || '-')}"
                    data-region="${escapeHtml(s.region || '-')}"
                    data-area="${escapeHtml(s.install_area || '-')}"
                    data-status="${escapeHtml(s.status || '')}">
                  <td><b>${escapeHtml(s.site_name || '-')}</b><small>${escapeHtml(s.bms_id || '-')}</small></td>
                  <td>${escapeHtml(s.region || '-')}</td>
                  <td>${escapeHtml(s.install_area || '-')}</td>
                  <td>${escapeHtml(s.manufacturer || '-')}</td>
                  <td>${escapeHtml(s.installed_at || '-')}</td>
                  <td>${score(v21ScoreValue(s.latest_score))}</td>
                  <td>${v21Badge(s)}</td>
                  <td>${escapeHtml(v21Time(s.last_analysis_time))}</td>
                  <td><span class="v21-data-pill">${escapeHtml(s.data_source || '-')}</span></td>
                  <td><button class="v21-detail-btn" onclick="selectSite('${escapeHtml(s.site_id)}')">상세 보기</button></td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </section>
    </div>`;
  } catch (error) {
    console.error('[monitor] renderSites failed', error);
    showError('사이트 목록 표시 중 오류가 발생했습니다.', error.stack || error.message);
  }
}
'''

CSS_APPEND = r'''
/* =========================
   v21 dashboard / sites cleanup
   ========================= */
.v21-dashboard-page,
.v21-sites-page { max-width: 1760px; }
.v21-dashboard-top { display: grid; grid-template-columns: 1fr 1fr 1.25fr; gap: 20px; margin-bottom: 22px; }
.v21-kpi-card, .v21-status-card { min-height: 160px; border: 1px solid var(--line); background: #fff; border-radius: 18px; box-shadow: var(--soft); padding: 28px; }
.v21-kpi-card { display: flex; align-items: center; gap: 24px; }
.v21-kpi-icon { width: 78px; height: 78px; border-radius: 22px; background: #e9f2ff; color: var(--blue); display: flex; align-items: center; justify-content: center; font-size: 34px; font-weight: 900; }
.v21-kpi-icon.green { background: #eafaf1; color: var(--green); font-size: 28px; }
.v21-kpi-label { color: #536276; font-weight: 850; font-size: 18px; margin-bottom: 12px; }
.v21-kpi-value { font-size: 54px; line-height: 1; font-weight: 950; color: var(--blue); }
.v21-kpi-value.green { color: var(--green); }
.v21-status-title { font-size: 22px; font-weight: 900; margin-bottom: 24px; }
.v21-status-counts { display: grid; grid-template-columns: repeat(3, 1fr); border: 1px solid var(--line2); border-radius: 16px; overflow: hidden; }
.v21-status-counts div { min-height: 82px; display: flex; flex-direction: column; align-items: center; justify-content: center; border-right: 1px solid var(--line2); }
.v21-status-counts div:last-child { border-right: 0; }
.v21-status-counts b { font-size: 38px; line-height: 1; font-weight: 950; }
.v21-status-counts span { margin-top: 8px; font-size: 15px; color: #667085; font-weight: 850; }
.v21-dashboard-main { display: grid; grid-template-columns: minmax(0, 1fr) 520px; gap: 22px; }
.v21-ranking-table-wrap, .v21-sites-table-wrap { width: 100%; overflow-x: auto; padding: 0 18px 18px; }
.v21-table { width: 100%; border-collapse: collapse; table-layout: auto; }
.v21-table th, .v21-table td { border-bottom: 1px solid var(--line2); text-align: left; padding: 17px 14px; vertical-align: middle; white-space: nowrap; }
.v21-table th { font-size: 13px; color: #667085; font-weight: 900; background: #fbfdff; }
.v21-table td { font-size: 15px; color: #152238; font-weight: 700; }
.v21-table td b { display: block; font-size: 16px; font-weight: 950; color: #101f36; margin-bottom: 5px; }
.v21-table td small { display: block; color: #68768a; font-size: 12px; font-weight: 850; }
.v21-rank { width: 34px; height: 34px; border-radius: 999px; display: inline-flex; align-items: center; justify-content: center; background: #eff6ff; color: var(--blue); font-weight: 950; }
.v21-priority-list { padding: 16px 20px 22px; display: flex; flex-direction: column; gap: 12px; }
.v21-priority-item { display: grid; grid-template-columns: 44px minmax(0, 1fr) 150px 18px; align-items: center; gap: 12px; border: 1px solid var(--line2); border-radius: 16px; padding: 14px; cursor: pointer; background: #fff; }
.v21-priority-item:hover { background: #f8fbff; border-color: #cfe2ff; }
.v21-priority-item.bad { background: #fffafa; border-color: #fecaca; }
.v21-priority-item.warn { background: #fffdf5; border-color: #fde7b1; }
.v21-priority-rank { width: 36px; height: 36px; border-radius: 999px; background: var(--red); color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 950; }
.v21-priority-item.warn .v21-priority-rank { background: var(--orange); }
.v21-priority-title { font-size: 16px; font-weight: 950; color: #0e1e37; margin-bottom: 5px; }
.v21-priority-sub { font-size: 12px; color: #667085; font-weight: 850; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.v21-priority-score { text-align: right; }
.v21-priority-score b { display: block; color: #dc2626; font-size: 24px; line-height: 1; font-weight: 950; margin-bottom: 6px; }
.v21-priority-item.warn .v21-priority-score b { color: #c77b00; }
.v21-priority-score span { display: block; font-size: 11px; color: #5f6d80; font-weight: 850; white-space: normal; line-height: 1.25; }
.v21-page-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin: 12px 0 24px; }
.v21-page-heading h1 { margin: 0 0 8px; font-size: 34px; letter-spacing: -1px; }
.v21-page-heading p { margin: 0; color: #748199; font-weight: 800; }
.v21-site-summary { display: grid; grid-template-columns: repeat(4, 110px); gap: 12px; }
.v21-site-summary div { height: 78px; border-radius: 16px; border: 1px solid var(--line); background: #fff; box-shadow: var(--soft); display: flex; flex-direction: column; align-items: center; justify-content: center; }
.v21-site-summary span { color: #667085; font-size: 12px; font-weight: 850; margin-bottom: 8px; }
.v21-site-summary b { color: var(--blue); font-size: 28px; line-height: 1; font-weight: 950; }
.v21-filter-card { border: 1px solid var(--line); background: #fff; border-radius: 18px; box-shadow: var(--soft); padding: 20px; display: grid; grid-template-columns: 1.7fr repeat(4, 1fr); gap: 14px; margin-bottom: 20px; }
.v21-input, .v21-select { height: 52px; border: 1px solid var(--line); background: #fff; border-radius: 13px; padding: 0 15px; color: #1d2a3f; font-weight: 800; outline: none; }
.v21-input:focus, .v21-select:focus { border-color: #93c5fd; box-shadow: 0 0 0 4px #eff6ff; }
.v21-sites-table-panel { width: 100%; }
.v21-sites-table { min-width: 1320px; }
.v21-data-pill { display: inline-flex; align-items: center; justify-content: center; height: 32px; padding: 0 10px; border-radius: 999px; background: #f1f5f9; color: #475569; font-size: 12px; font-weight: 900; }
.v21-detail-btn { height: 36px; border: 1px solid #bfdbfe; color: var(--blue); background: #eff6ff; border-radius: 10px; font-weight: 900; padding: 0 14px; cursor: pointer; }
.v21-detail-btn:hover { background: var(--blue); color: #fff; }
.clickable-row { cursor: pointer; }
@media (max-width: 1480px) {
  .v21-dashboard-main { grid-template-columns: 1fr; }
  .v21-filter-card { grid-template-columns: 1fr 1fr; }
  .v21-site-summary { grid-template-columns: repeat(2, 110px); }
}
'''


def patch_monitor_js() -> None:
    if not MONITOR_JS.exists():
        print("[skip] monitor.js not found")
        return
    backup(MONITOR_JS)
    text = MONITOR_JS.read_text(encoding="utf-8")

    if "function v21StatusLabel(" not in text:
        marker = "function currentSite()"
        pos = text.find(marker)
        if pos == -1:
            raise RuntimeError("Cannot find currentSite() insertion point")
        text = text[:pos] + JS_HELPERS + "\n\n" + text[pos:]

    text = replace_function(text, "renderDashboard", RENDER_DASHBOARD)
    text = replace_function(text, "renderSites", RENDER_SITES)

    MONITOR_JS.write_text(text, encoding="utf-8")
    print("[ok] monitor.js dashboard/sites v21")


def patch_monitor_css() -> None:
    if not MONITOR_CSS.exists():
        print("[skip] monitor.css not found")
        return
    backup(MONITOR_CSS)
    text = MONITOR_CSS.read_text(encoding="utf-8")
    if "v21 dashboard / sites cleanup" not in text:
        text = text.rstrip() + "\n" + CSS_APPEND + "\n"
    MONITOR_CSS.write_text(text, encoding="utf-8")
    print("[ok] monitor.css v21 append")


def main() -> None:
    print("[v21] dashboard/sites patch started")
    patch_index()
    patch_monitor_service()
    patch_monitor_js()
    patch_monitor_css()
    print("[v21] done")
    print("Next:")
    print("  python -m py_compile .\\service\\monitor_service.py")
    print("  restart uvicorn")
    print("  Ctrl+F5 in browser")


if __name__ == "__main__":
    main()
