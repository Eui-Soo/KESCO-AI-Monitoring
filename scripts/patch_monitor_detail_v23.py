from pathlib import Path
import re
from datetime import datetime

ROOT = Path.cwd()
JS_PATH = ROOT / "static" / "monitor" / "monitor.js"
CSS_PATH = ROOT / "static" / "monitor" / "monitor.css"
INDEX_PATH = ROOT / "static" / "monitor" / "index.html"
SERVICE_PATH = ROOT / "service" / "monitor_service.py"

STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

for path in [JS_PATH, CSS_PATH, INDEX_PATH, SERVICE_PATH]:
    if path.exists():
        backup = path.with_suffix(path.suffix + f".v23_{STAMP}.bak")
        backup.write_text(path.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
        print(f"backup: {backup}")

# Fix a known broken escape sequence left by earlier patch attempts.
if SERVICE_PATH.exists():
    service = SERVICE_PATH.read_text(encoding="utf-8", errors="ignore")
    service = service.replace('replace("\\", "_")', 'replace("\\\\", "_")')
    service = service.replace('replace("\\\", "_")', 'replace("\\\\", "_")')
    # If a line became syntactically broken, replace the whole safe_bms_id line.
    service = re.sub(
        r'safe_bms_id\s*=\s*str\(bms_id\)\.strip\(\)\.replace\(" ", "_"\)\.replace\("/", "_"\).*',
        'safe_bms_id = str(bms_id).strip().replace(" ", "_").replace("/", "_").replace("\\\\", "_")',
        service,
    )
    SERVICE_PATH.write_text(service, encoding="utf-8")

# Cache busting for Mac/Windows browser differences.
if INDEX_PATH.exists():
    html = INDEX_PATH.read_text(encoding="utf-8", errors="ignore")
    html = re.sub(r'/static/monitor/monitor\.css(?:\?v=\d+)?', '/static/monitor/monitor.css?v=23', html)
    html = re.sub(r'/static/monitor/monitor_v7_fix\.css(?:\?v=\d+)?', '/static/monitor/monitor_v7_fix.css?v=23', html)
    html = re.sub(r'/static/monitor/monitor\.js(?:\?v=\d+)?', '/static/monitor/monitor.js?v=23', html)
    INDEX_PATH.write_text(html, encoding="utf-8")

V23_JS = r'''

/* === KESCO monitor detail UX v23: site/bank/rack/string/module split === */
function v23EnsureDetailState() {
  if (!state.detailPath) {
    state.detailPath = { level: 'site', bank: 1, rack: 1, string: 1, module: 1 };
  }
  if (!state.detailPath.level) state.detailPath.level = state.level || 'site';
  if (!state.detailPath.bank) state.detailPath.bank = 1;
  if (!state.detailPath.rack) state.detailPath.rack = 1;
  if (!state.detailPath.string) state.detailPath.string = 1;
  if (!state.detailPath.module) state.detailPath.module = 1;
}

function v23SetPath(level, bank = null, rack = null, stringNo = null, module = null) {
  v23EnsureDetailState();
  state.detailPath.level = level || 'site';
  if (bank !== null) state.detailPath.bank = Number(bank) || 1;
  if (rack !== null) state.detailPath.rack = Number(rack) || 1;
  if (stringNo !== null) state.detailPath.string = Number(stringNo) || 1;
  if (module !== null) state.detailPath.module = Number(module) || 1;
  state.level = state.detailPath.level;
  renderDetail();
}
window.v23SetPath = v23SetPath;

function v23GoSites() { nav('sites'); }
window.v23GoSites = v23GoSites;

function v23ResetTree() {
  v23EnsureDetailState();
  state.detailPath = { level: 'site', bank: 1, rack: 1, string: 1, module: 1 };
  state.level = 'site';
  renderDetail();
}
window.v23ResetTree = v23ResetTree;

function v23StatusKo(status) {
  const value = String(status || '').toLowerCase();
  if (value === 'abnormal' || value === 'danger') return '비정상';
  if (value === 'warning' || value === 'caution') return '주의';
  if (value === 'offline' || value === 'unavailable' || value === 'data_missing') return '오프라인';
  return '정상';
}

function v23StatusFromScore(value) {
  const n = Number(value);
  if (Number.isNaN(n)) return 'offline';
  if (n >= 71) return 'abnormal';
  if (n >= 40) return 'warning';
  return 'normal';
}

function v23Score(site, depth = 0) {
  const base = Number(site?.latest_score ?? 0);
  const n = Math.max(0, Math.min(99, Math.round(base - depth)));
  return n;
}

function v23StatusDot(status) {
  return `<span class="tree-dot ${escapeHtml(status || 'normal')}" title="${escapeHtml(v23StatusKo(status))}"></span>`;
}

function v23FmtDate(value) {
  if (!value) return '-';
  return String(value).replace('T', ' ').split('.')[0].slice(0, 19);
}

function v23Counts(site) {
  return {
    bank: Math.max(1, Number(site?.bank_count || 1)),
    rack: Math.max(1, Number(site?.rack_count || 1)),
    string: Math.max(1, Number(site?.string_count || 1)),
    module: Math.max(1, Number(site?.module_count || 1)),
    cell: Math.max(20, Number(site?.cell_count || 20)),
  };
}

function v23TreeModuleRange(site, rackNo) {
  const counts = v23Counts(site);
  const perRack = Math.max(1, Math.ceil(counts.module / counts.rack));
  const start = (rackNo - 1) * perRack + 1;
  const end = Math.min(counts.module, rackNo * perRack);
  return { start, end };
}

function v23BuildSidebarTree(site) {
  v23EnsureDetailState();
  const p = state.detailPath;
  const counts = v23Counts(site);
  const siteStatus = site.status || v23StatusFromScore(site.latest_score);
  const bankStatus = v23StatusFromScore(v23Score(site, 0));
  const rows = [];

  rows.push(`
    <div class="tree-site-card ${p.level === 'site' ? 'active' : ''}" onclick="v23SetPath('site')">
      <div>${v23StatusDot(siteStatus)}<b>${escapeHtml(site.site_name || 'ESS Site')}</b></div>
      <small>${escapeHtml(site.bms_id || '-')}</small>
      <span class="tree-score ${escapeHtml(siteStatus)}">${escapeHtml(site.latest_score ?? '-')}</span>
    </div>
  `);

  rows.push(`<div class="tree-branch">`);
  rows.push(`
    <button class="tree-node level-bank ${p.level === 'bank' ? 'active' : ''}" onclick="v23SetPath('bank',1,1,1,1)">
      ${v23StatusDot(bankStatus)}<span class="tree-kind">B</span><b>Bank 01</b>
    </button>
  `);

  for (let r = 1; r <= counts.rack; r++) {
    const rackScore = v23Score(site, r * 6);
    const rackStatus = v23StatusFromScore(rackScore);
    const rackOpen = p.rack === r || p.level === 'site';
    rows.push(`
      <button class="tree-node level-rack ${p.level === 'rack' && p.rack === r ? 'active' : ''}" onclick="v23SetPath('rack',1,${r},1,1)">
        ${v23StatusDot(rackStatus)}<span class="tree-kind">R</span><b>Rack ${String(r).padStart(2,'0')}</b><em>${rackScore}</em>
      </button>
    `);
    if (rackOpen) {
      rows.push(`<div class="tree-nested rack-${r}">`);
      const stringCountForRack = Math.min(2, counts.string || 1);
      for (let s = 1; s <= stringCountForRack; s++) {
        const stringScore = v23Score(site, r * 6 + s * 3);
        const stringStatus = v23StatusFromScore(stringScore);
        const stringOpen = p.rack === r && (p.string === s || p.level === 'rack');
        rows.push(`
          <button class="tree-node level-string ${p.level === 'string' && p.rack === r && p.string === s ? 'active' : ''}" onclick="v23SetPath('string',1,${r},${s},1)">
            ${v23StatusDot(stringStatus)}<span class="tree-kind">S</span><b>String ${String(s).padStart(2,'0')}</b><em>${stringScore}</em>
          </button>
        `);
        if (stringOpen || (p.level === 'module' && p.rack === r && p.string === s)) {
          const range = v23TreeModuleRange(site, r);
          rows.push(`<div class="tree-nested module-list">`);
          for (let m = range.start; m <= range.end; m++) {
            const moduleScore = v23Score(site, m * 2);
            const moduleStatus = v23StatusFromScore(moduleScore);
            rows.push(`
              <button class="tree-node level-module ${p.level === 'module' && p.rack === r && p.string === s && p.module === m ? 'active' : ''}" onclick="v23SetPath('module',1,${r},${s},${m})">
                ${v23StatusDot(moduleStatus)}<span class="tree-kind">M</span><b>Module ${String(m).padStart(2,'0')}</b><em>${moduleScore}</em>
              </button>
            `);
          }
          rows.push(`</div>`);
        }
      }
      rows.push(`</div>`);
    }
  }
  rows.push(`</div>`);

  return `
    <div class="sidebar-tree v23-detail-only">
      <div class="tree-title"><span>▦</span><b>계층 구조 탐색</b><button title="계층 접기" onclick="v23ResetTree()">↻</button></div>
      ${rows.join('')}
      <div class="tree-legend">
        <span><i class="tree-dot normal"></i>정상</span>
        <span><i class="tree-dot warning"></i>주의</span>
        <span><i class="tree-dot abnormal"></i>비정상</span>
        <span><i class="tree-dot offline"></i>오프라인</span>
      </div>
    </div>
  `;
}

function v23UpdateSidebarTree(site) {
  const existing = document.querySelectorAll('.sidebar-tree');
  existing.forEach((el) => el.remove());
  const footer = document.querySelector('.sidebar-footer');
  const side = document.querySelector('.sidebar');
  if (!side || !footer || state.page !== 'detail') return;
  footer.insertAdjacentHTML('beforebegin', v23BuildSidebarTree(site));
}

function v23HideSidebarTree() {
  document.querySelectorAll('.sidebar-tree').forEach((el) => el.remove());
}

function v23Breadcrumb(site) {
  v23EnsureDetailState();
  const p = state.detailPath;
  const chunks = [];
  chunks.push(`<button onclick="nav('sites')">사이트 목록</button>`);
  chunks.push(`<button onclick="v23SetPath('site')">${escapeHtml(site.site_name)}</button>`);
  if (p.level !== 'site') chunks.push(`<button onclick="v23SetPath('bank',1,1,1,1)">Bank 01</button>`);
  if (['rack','string','module'].includes(p.level)) chunks.push(`<button onclick="v23SetPath('rack',1,${p.rack},1,1)">Rack ${String(p.rack).padStart(2,'0')}</button>`);
  if (['string','module'].includes(p.level)) chunks.push(`<button onclick="v23SetPath('string',1,${p.rack},${p.string},1)">String ${String(p.string).padStart(2,'0')}</button>`);
  if (p.level === 'module') chunks.push(`<button onclick="v23SetPath('module',1,${p.rack},${p.string},${p.module})">Module ${String(p.module).padStart(2,'0')}</button>`);
  return chunks.join('<span>›</span>');
}

function v23LevelLabel(level) {
  return level === 'site' ? 'Site 정보' : level === 'bank' ? 'Bank 상세' : level === 'rack' ? 'Rack 상세' : level === 'string' ? 'String 상세' : 'Module 상세';
}

function v23Tabs(p) {
  return `<div class="level-tabs v23-tabs">
    <button class="level-tab ${p.level==='site'?'active':''}" onclick="v23SetPath('site')">Site</button>
    <button class="level-tab ${p.level==='bank'?'active':''}" onclick="v23SetPath('bank',1,1,1,1)">Bank</button>
    <button class="level-tab ${p.level==='rack'?'active':''}" onclick="v23SetPath('rack',1,${p.rack},1,1)">Rack</button>
    <button class="level-tab ${p.level==='string'?'active':''}" onclick="v23SetPath('string',1,${p.rack},${p.string},1)">String</button>
    <button class="level-tab ${p.level==='module'?'active':''}" onclick="v23SetPath('module',1,${p.rack},${p.string},${p.module})">Module</button>
  </div>`;
}

function v23InfoCards(site) {
  const p = state.detailPath || { level: 'site' };
  return `<div class="detail-grid-top v23-info-cards">
    <div class="info-card"><small>최대 이상 점수</small><b>${score(site.latest_score)}</b></div>
    <div class="info-card"><small>상태</small><b>${badge(site.status)}</b></div>
    <div class="info-card"><small>최근 분석 시각</small><b>${escapeHtml(v23FmtDate(site.last_analysis_time))}</b></div>
    <div class="info-card"><small>현재 위치</small><b>${escapeHtml(v23LocationText(p))}</b></div>
  </div>`;
}

function v23LocationText(p) {
  if (!p || p.level === 'site') return 'Site overview';
  if (p.level === 'bank') return 'Bank 01';
  if (p.level === 'rack') return `Bank 01 > Rack ${String(p.rack).padStart(2,'0')}`;
  if (p.level === 'string') return `Bank 01 > Rack ${String(p.rack).padStart(2,'0')} > String ${String(p.string).padStart(2,'0')}`;
  return `Bank 01 > Rack ${String(p.rack).padStart(2,'0')} > String ${String(p.string).padStart(2,'0')} > Module ${String(p.module).padStart(2,'0')}`;
}

function v23SitePanel(site) {
  const c = v23Counts(site);
  const items = [
    ['BMS ID', site.bms_id || '-'], ['지역', site.region || '-'], ['설치구역', site.install_area || '-'], ['제조사', site.manufacturer || '-'],
    ['설치일', site.installed_at || '-'], ['분석 Row', site.score_row_count || 0], ['Bank', c.bank], ['Rack', c.rack], ['String', c.string], ['Module', c.module], ['Cell', c.cell]
  ];
  return `<section class="panel v23-overview"><div class="panel-title"><span class="mini-icon">▦</span>사이트 정보</div>
    <div class="site-info-grid">${items.map(([k,v]) => `<div><small>${escapeHtml(k)}</small><b>${escapeHtml(v)}</b></div>`).join('')}</div>
  </section>
  <section class="panel v23-card-panel"><div class="panel-title"><span class="mini-icon">▧</span>Bank 구성</div><div class="hierarchy-card-grid">
    <button class="hierarchy-card ${escapeHtml(site.status)}" onclick="v23SetPath('bank',1,1,1,1)"><span>${v23StatusDot(site.status)}</span><b>Bank 01</b><small>Rack ${c.rack} · Module ${c.module} · Cell ${c.cell}</small><em>${escapeHtml(site.latest_score ?? '-')}</em></button>
  </div></section>`;
}

function v23BankPanel(site) {
  const c = v23Counts(site);
  return `<section class="panel v23-card-panel"><div class="panel-title"><span class="mini-icon">▧</span>Rack 구성</div><div class="hierarchy-card-grid">
    ${Array.from({length:c.rack}, (_,i) => {
      const no = i+1; const sc = v23Score(site, no*6); const st = v23StatusFromScore(sc);
      return `<button class="hierarchy-card ${st}" onclick="v23SetPath('rack',1,${no},1,1)"><span>${v23StatusDot(st)}</span><b>Rack ${String(no).padStart(2,'0')}</b><small>String ${Math.min(2,c.string)} · Module ${Math.ceil(c.module/c.rack)}</small><em>${sc}</em></button>`;
    }).join('')}
  </div></section>`;
}

function v23RackPanel(site) {
  const p = state.detailPath; const c = v23Counts(site); const stringCount = Math.min(2, c.string || 1);
  return `<section class="panel v23-card-panel"><div class="panel-title"><span class="mini-icon">▧</span>String 구성</div><div class="hierarchy-card-grid">
    ${Array.from({length:stringCount}, (_,i) => {
      const no = i+1; const sc = v23Score(site, p.rack*6 + no*3); const st = v23StatusFromScore(sc);
      return `<button class="hierarchy-card ${st}" onclick="v23SetPath('string',1,${p.rack},${no},1)"><span>${v23StatusDot(st)}</span><b>String ${String(no).padStart(2,'0')}</b><small>Rack ${String(p.rack).padStart(2,'0')} 하위 String</small><em>${sc}</em></button>`;
    }).join('')}
  </div></section>`;
}

function v23StringPanel(site) {
  const p = state.detailPath; const range = v23TreeModuleRange(site, p.rack);
  return `<section class="panel v23-card-panel"><div class="panel-title"><span class="mini-icon">▧</span>Module 구성</div><div class="hierarchy-card-grid">
    ${Array.from({length: range.end - range.start + 1}, (_,i) => {
      const no = range.start + i; const sc = v23Score(site, no*2); const st = v23StatusFromScore(sc);
      return `<button class="hierarchy-card ${st}" onclick="v23SetPath('module',1,${p.rack},${p.string},${no})"><span>${v23StatusDot(st)}</span><b>Module ${String(no).padStart(2,'0')}</b><small>Cell 20개 · 최고 점수 ${sc}</small><em>${sc}</em></button>`;
    }).join('')}
  </div></section>`;
}

function v23ModulePanel(site, level) {
  const cells = Array.isArray(level?.cells) ? level.cells : [18,22,31,26,29,34,92,45,28,33,24,37,41,27,39,32,30,25,48,21].map((v,i) => ({ cell_no:i+1, score:v, status:v>=71?'abnormal':v>=40?'warning':'normal', voltage:(3.62 + i/1000).toFixed(3), temperature:(30 + v/8).toFixed(1) }));
  return `<section class="panel"><div class="panel-title"><span class="mini-icon">▦</span>Cell 상태 맵</div><div class="cell-map">
      ${cells.map((c) => `<div class="cell ${c.status === 'abnormal' ? 'bad' : c.status === 'warning' ? 'warn' : 'good'}"><b>Cell ${String(c.cell_no).padStart(2,'0')}</b><span>${escapeHtml(c.score)}</span></div>`).join('')}
    </div></section>
    <section class="panel"><div class="panel-title"><span class="mini-icon">▥</span>위험 Cell 상세</div><div class="ranking-table"><table><thead><tr><th>Cell</th><th>점수</th><th>상태</th><th>전압</th><th>온도</th></tr></thead><tbody>
      ${cells.slice().sort((a,b)=>Number(b.score||0)-Number(a.score||0)).slice(0,8).map((c)=>`<tr><td><b>Cell ${String(c.cell_no).padStart(2,'0')}</b></td><td>${score(c.score)}</td><td>${badge(c.status)}</td><td>${escapeHtml(c.voltage || '-')} V</td><td>${escapeHtml(c.temperature || '-')} ℃</td></tr>`).join('')}
    </tbody></table></div></section>`;
}

function v23MainPanel(site, level) {
  v23EnsureDetailState();
  const p = state.detailPath;
  if (p.level === 'site') return v23SitePanel(site);
  if (p.level === 'bank') return v23BankPanel(site);
  if (p.level === 'rack') return v23RackPanel(site);
  if (p.level === 'string') return v23StringPanel(site);
  return v23ModulePanel(site, level || {});
}

function v23RightPanel(site) {
  const scoreValue = Number(site.latest_score || 0);
  const levelText = scoreValue >= 71 ? '즉시 점검 권고' : scoreValue >= 40 ? '주의 관찰 필요' : '정상 운전 범위';
  const action = scoreValue >= 71 ? '최고 위험 위치부터 현장 점검을 진행하세요.' : scoreValue >= 40 ? '추이 변화를 확인하고 재분석 결과를 비교하세요.' : '정상 상태를 유지하며 정기 점검만 진행하세요.';
  return `<aside class="detail-right v23-right">
    <section class="panel"><div class="panel-title"><span class="mini-icon">⚠</span>운영 권고</div>
      <div class="v23-advice"><b>${escapeHtml(levelText)}</b><p>${escapeHtml(action)}</p><dl><dt>최고 점수</dt><dd>${escapeHtml(site.latest_score ?? '-')}</dd><dt>상태</dt><dd>${escapeHtml(v23StatusKo(site.status))}</dd><dt>위험 위치</dt><dd>${escapeHtml(site.risk_location || 'Latest anomaly_score result')}</dd></dl></div>
    </section>
    <section class="panel"><div class="panel-title"><span class="mini-icon">▤</span>분석 요약</div>
      <div class="v23-summary-list"><div><span>최근 분석</span><b>${escapeHtml(v23FmtDate(site.last_analysis_time))}</b></div><div><span>저장 Row</span><b>${escapeHtml(site.score_row_count || 0)}</b></div><div><span>평균 점수</span><b>${escapeHtml(site.average_score ?? '-')}</b></div><div><span>데이터 소스</span><b>${escapeHtml(site.data_source || 'local-db')}</b></div></div>
    </section>
  </aside>`;
}

async function renderDetail() {
  try {
    setActive('detail');
    setLoading('사이트 상세 로딩 중');
    await loadCommonData();
    v23EnsureDetailState();
    const baseSite = currentSite();
    const detailData = await fetchJson(API.site(baseSite.site_id), null);
    const site = detailData?.result || baseSite;
    const levelData = state.detailPath.level === 'module' ? await fetchJson(API.level(site.site_id, 'module'), null) : null;
    const level = levelData?.result || {};
    v23UpdateSidebarTree(site);

    content.innerHTML = `
    <div class="page detail-page v23-detail-page">
      <section class="detail-left">
        <div class="breadcrumb v23-breadcrumb">${v23Breadcrumb(site)}</div>
        <div class="detail-title detail-title-row v23-title-row">
          <div class="site-icon">▦</div>
          <div><h1>${escapeHtml(site.site_name)} <span>›</span> ${escapeHtml(v23LevelLabel(state.detailPath.level))}</h1><p>${escapeHtml(site.region)} · ${escapeHtml(site.manufacturer)} · ${escapeHtml(site.bms_id || '')}</p></div>
          <button class="v23-other-site" onclick="v23GoSites()">다른 사이트 보기</button>
        </div>
        ${v23Tabs(state.detailPath)}
        ${v23InfoCards(site)}
        ${v23MainPanel(site, level)}
      </section>
      ${v23RightPanel(site)}
    </div>`;
  } catch (error) {
    console.error('[monitor] v23 renderDetail failed', error);
    showError('사이트 상세 표시 중 오류가 발생했습니다.', error.stack || error.message);
  }
}

function nav(page) {
  if (page !== 'detail') v23HideSidebarTree();
  if (page === 'dashboard') return renderDashboard();
  if (page === 'sites') return renderSites();
  if (page === 'detail') return renderDetail();
  if (page === 'history') return renderPlaceholder('실행 이력', '파이프라인 실행 이력 화면은 다음 단계에서 연결합니다.');
  if (page === 'settings') return renderPlaceholder('설정', '알림, 모델, 사용자 설정 화면은 다음 단계에서 연결합니다.');
}
window.nav = nav;

function selectSite(siteId) {
  state.selectedSiteId = siteId;
  v23EnsureDetailState();
  renderDetail();
}
window.selectSite = selectSite;

function setLevel(level) {
  v23EnsureDetailState();
  v23SetPath(level || 'site');
}
window.setLevel = setLevel;

async function init() {
  try {
    if (!content) return;
    bindNav();
    await fetchJson(API.system, null);
    await renderDashboard();
  } catch (error) {
    console.error('[monitor] v23 init failed', error);
    showError('초기화 중 오류가 발생했습니다.', error.stack || error.message);
  }
}
/* === end KESCO monitor detail UX v23 === */
'''

V23_CSS = r'''

/* === KESCO monitor detail UX v23 === */
.sidebar-tree{margin:18px 18px 14px;padding:16px;border:1px solid #dce6f2;border-radius:16px;background:rgba(255,255,255,.96);box-shadow:0 10px 24px rgba(23,43,77,.07);max-height:390px;overflow:auto;position:relative;z-index:4}.tree-title{display:flex;align-items:center;gap:8px;margin-bottom:12px;font-size:16px;color:#10284b}.tree-title span{color:#0969e8}.tree-title button{margin-left:auto;width:30px;height:30px;border:1px solid #d7e4f3;border-radius:9px;background:#fff;color:#4b607c;cursor:pointer;font-weight:900}.tree-site-card{position:relative;border:1px solid #e2edf8;border-radius:14px;background:#fbfdff;padding:12px 54px 12px 12px;margin-bottom:12px;cursor:pointer}.tree-site-card.active{background:#edf5ff;border-color:#bfdbfe}.tree-site-card>div{display:flex;align-items:center;gap:8px}.tree-site-card b{font-size:14px}.tree-site-card small{display:block;margin-top:6px;color:#65758e;font-weight:800}.tree-score{position:absolute;right:12px;top:50%;transform:translateY(-50%);min-width:38px;height:28px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-weight:900}.tree-score.abnormal{background:#fff0f0;color:#dc2626}.tree-score.warning{background:#fff6df;color:#c77b00}.tree-score.normal{background:#eafaf1;color:#128a52}.tree-branch,.tree-nested{display:flex;flex-direction:column;gap:5px}.tree-nested{margin-left:18px;padding-left:12px;border-left:1px solid #dbe7f5}.tree-node{width:100%;min-height:34px;border:0;background:transparent;border-radius:10px;display:grid;grid-template-columns:10px 22px 1fr auto;align-items:center;gap:8px;padding:6px 8px;text-align:left;cursor:pointer;color:#21324b;font-family:inherit}.tree-node:hover{background:#f3f8ff}.tree-node.active{background:#e9f2ff;color:#0969e8;box-shadow:inset 0 0 0 1px #cae0ff}.tree-node b{font-size:14px}.tree-node em{font-style:normal;font-size:12px;font-weight:900;color:#6e7f96}.tree-kind{width:20px;height:20px;border-radius:7px;background:#edf4fb;color:#506580;display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:900}.tree-node.active .tree-kind{background:#dcecff;color:#0969e8}.tree-dot{width:9px;height:9px;border-radius:50%;display:inline-block;flex:none}.tree-dot.normal{background:#17b26a}.tree-dot.warning{background:#f59e0b}.tree-dot.abnormal,.tree-dot.danger{background:#ef4444}.tree-dot.offline,.tree-dot.unavailable,.tree-dot.data_missing{background:#98a2b3}.tree-legend{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;padding-top:10px;border-top:1px solid #edf2f8;color:#53647b;font-size:11px;font-weight:800}.tree-legend span{display:flex;align-items:center;gap:4px}.v23-breadcrumb{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.v23-breadcrumb button{border:0;background:transparent;color:#63738a;font-weight:850;cursor:pointer;padding:0}.v23-breadcrumb button:hover{color:#0969e8;text-decoration:underline}.v23-title-row{gap:18px}.v23-other-site{margin-left:auto;height:48px;border:1px solid #cfe0f4;border-radius:13px;background:#fff;color:#0969e8;font-weight:900;padding:0 18px;box-shadow:0 6px 16px rgba(44,63,93,.04);cursor:pointer}.v23-other-site:hover{background:#f3f8ff}.v23-tabs{grid-template-columns:repeat(5,1fr);width:430px;max-width:100%}.v23-info-cards{grid-template-columns:repeat(4,1fr)}.site-info-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;padding:22px}.site-info-grid div{border:1px solid #edf2f8;border-radius:14px;background:#fbfdff;padding:16px}.site-info-grid small{display:block;color:#6b7a90;font-weight:800;margin-bottom:8px}.site-info-grid b{font-size:18px}.hierarchy-card-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;padding:22px}.hierarchy-card{position:relative;min-height:116px;border:1px solid #dfe9f5;border-radius:16px;background:#fff;text-align:left;padding:18px 58px 18px 18px;cursor:pointer;box-shadow:0 8px 18px rgba(23,43,77,.04);font-family:inherit}.hierarchy-card:hover{transform:translateY(-1px);box-shadow:0 12px 22px rgba(23,43,77,.08)}.hierarchy-card b{display:block;font-size:20px;margin:8px 0}.hierarchy-card small{color:#6b7a90;font-weight:800}.hierarchy-card em{position:absolute;right:16px;top:16px;font-style:normal;min-width:38px;height:32px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-weight:900}.hierarchy-card.abnormal{border-color:#fecaca;background:#fffafa}.hierarchy-card.abnormal em{background:#fff0f0;color:#dc2626}.hierarchy-card.warning{border-color:#fde7b1;background:#fffdf5}.hierarchy-card.warning em{background:#fff6df;color:#c77b00}.hierarchy-card.normal em{background:#eafaf1;color:#128a52}.v23-right{display:flex;flex-direction:column;gap:18px}.v23-advice{padding:20px 24px}.v23-advice>b{font-size:20px;color:#0b1b36}.v23-advice p{margin:8px 0 16px;color:#627188;font-weight:750;line-height:1.5}.v23-advice dl{display:grid;grid-template-columns:92px 1fr;gap:10px;margin:0}.v23-advice dt{color:#6b7a90;font-weight:800}.v23-advice dd{margin:0;font-weight:900}.v23-summary-list{padding:10px 22px 20px}.v23-summary-list div{display:flex;justify-content:space-between;gap:12px;border-bottom:1px solid #edf2f8;padding:13px 0}.v23-summary-list div:last-child{border-bottom:0}.v23-summary-list span{color:#6b7a90;font-weight:800}.v23-summary-list b{font-weight:900}.cell-map .cell b{display:block;font-size:13px;margin-bottom:8px}.cell-map .cell span{display:block;font-size:24px;font-weight:950}.nav-item[data-page="detail"].active~*{}@media(max-width:1400px){.hierarchy-card-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.v23-info-cards{grid-template-columns:repeat(2,1fr)}.site-info-grid{grid-template-columns:repeat(2,1fr)}}
/* === end KESCO monitor detail UX v23 === */
'''

if JS_PATH.exists():
    js = JS_PATH.read_text(encoding="utf-8", errors="ignore")
    js = re.sub(r'/\* === KESCO monitor detail UX v23: site/bank/rack/string/module split === \*/.*?/\* === end KESCO monitor detail UX v23 === \*/', '', js, flags=re.S)
    js = js.rstrip() + V23_JS + "\n"
    JS_PATH.write_text(js, encoding="utf-8")
    print(f"patched: {JS_PATH}")
else:
    raise FileNotFoundError(JS_PATH)

if CSS_PATH.exists():
    css = CSS_PATH.read_text(encoding="utf-8", errors="ignore")
    css = re.sub(r'/\* === KESCO monitor detail UX v23 === \*/.*?/\* === end KESCO monitor detail UX v23 === \*/', '', css, flags=re.S)
    css = css.rstrip() + V23_CSS + "\n"
    CSS_PATH.write_text(css, encoding="utf-8")
    print(f"patched: {CSS_PATH}")
else:
    raise FileNotFoundError(CSS_PATH)

print("v23 detail UX patch applied.")
