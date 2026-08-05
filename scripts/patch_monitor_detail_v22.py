from pathlib import Path
import re

ROOT = Path.cwd()
service_path = ROOT / 'service' / 'monitor_service.py'
js_path = ROOT / 'static' / 'monitor' / 'monitor.js'
css_path = ROOT / 'static' / 'monitor' / 'monitor.css'
index_path = ROOT / 'static' / 'monitor' / 'index.html'

for p in [service_path, js_path, css_path, index_path]:
    if not p.exists():
        raise FileNotFoundError(f'Missing file: {p}')

# 0) Fix v21 bad backslash escape if it exists
service = service_path.read_text(encoding='utf-8')
service = service.replace('replace("\\", "_")', 'replace("\\\\", "_")')
# also repair the exact broken physical line if present using regex
service = re.sub(r'\.replace\("/", "_"\)\.replace\("\\", "_"\)', '.replace("/", "_").replace("\\\\", "_")', service)
service_path.write_text(service, encoding='utf-8')

# 1) Cache busting for Mac/Chrome/Safari stale static files
index = index_path.read_text(encoding='utf-8')
index = re.sub(r'/static/monitor/monitor\.css(?:\?v=\d+)?', '/static/monitor/monitor.css?v=22', index)
index = re.sub(r'/static/monitor/monitor_v7_fix\.css(?:\?v=\d+)?', '/static/monitor/monitor_v7_fix.css?v=22', index)
index = re.sub(r'/static/monitor/monitor\.js(?:\?v=\d+)?', '/static/monitor/monitor.js?v=22', index)
index_path.write_text(index, encoding='utf-8')

# 2) Append polished detail/navigation override JS.
js = js_path.read_text(encoding='utf-8')
marker = '/* === KESCO detail UX v22 override === */'
if marker not in js:
    js += r'''

/* === KESCO detail UX v22 override === */
(function () {
  const DETAIL_STORAGE_KEY = 'kesco.monitor.lastDetail.v22';

  function toInt(value, fallback = 1) {
    const n = parseInt(value, 10);
    return Number.isFinite(n) && n > 0 ? n : fallback;
  }

  function clamp(value, min, max) {
    const n = toInt(value, min);
    return Math.max(min, Math.min(max, n));
  }

  function siteCounts(site) {
    return {
      bank: Math.max(1, toInt(site?.bank_count, 1)),
      rack: Math.max(1, toInt(site?.rack_count, 1)),
      string: Math.max(1, toInt(site?.string_count, 1)),
      module: Math.max(1, toInt(site?.module_count, 1)),
    };
  }

  function normalizeStatus(value) {
    const v = String(value || '').toLowerCase();
    if (['danger', 'critical', 'abnormal', 'bad', '비정상'].includes(v)) return 'abnormal';
    if (['warning', 'caution', 'warn', '주의', '경고'].includes(v)) return 'warning';
    if (['offline', 'unavailable', 'data_missing', '오프라인'].includes(v)) return 'offline';
    return 'normal';
  }

  function scoreToStatus(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return 'offline';
    if (n >= 71) return 'abnormal';
    if (n >= 40) return 'warning';
    return 'normal';
  }

  function statusKo(value) {
    const s = normalizeStatus(value);
    if (s === 'abnormal') return '비정상';
    if (s === 'warning') return '주의';
    if (s === 'offline') return '오프라인';
    return '정상';
  }

  function statusDot(status, title = '') {
    const s = normalizeStatus(status);
    return `<span class="tree-status-dot ${s}" title="${escapeHtml(title || statusKo(s))}"></span>`;
  }

  function formatDateTime(value) {
    if (!value) return '-';
    return String(value).replace('T', ' ').split('.')[0].slice(0, 19);
  }

  function getSavedDetail() {
    try {
      return JSON.parse(localStorage.getItem(DETAIL_STORAGE_KEY) || '{}');
    } catch (_) {
      return {};
    }
  }

  function saveDetail(siteId, patch = {}) {
    const current = getSavedDetail();
    const next = {
      site_id: siteId || current.site_id || state.selectedSiteId,
      level: patch.level || state.level || current.level || 'site',
      bank_no: toInt(patch.bank_no ?? current.bank_no, 1),
      rack_no: toInt(patch.rack_no ?? current.rack_no, 1),
      string_no: toInt(patch.string_no ?? current.string_no, 1),
      module_no: toInt(patch.module_no ?? current.module_no, 1),
    };
    localStorage.setItem(DETAIL_STORAGE_KEY, JSON.stringify(next));
    return next;
  }

  function ensureDetailState(site) {
    const saved = getSavedDetail();
    const counts = siteCounts(site);
    state.selectedSiteId = saved.site_id || state.selectedSiteId || site?.site_id;
    state.level = saved.level || state.level || 'site';
    state.selectedPath = {
      bank_no: clamp(saved.bank_no || 1, 1, counts.bank),
      rack_no: clamp(saved.rack_no || 1, 1, counts.rack),
      string_no: clamp(saved.string_no || 1, 1, counts.string),
      module_no: clamp(saved.module_no || 1, 1, counts.module),
    };
  }

  function pickCurrentSite() {
    const saved = getSavedDetail();
    if (saved.site_id && state.sites?.some((s) => String(s.site_id) === String(saved.site_id))) {
      state.selectedSiteId = saved.site_id;
    }
    return currentSite();
  }

  function estimateModuleStatus(site, moduleNo) {
    // 임시 개발 데이터용: 실제 module row 조회 API가 붙기 전까지 시각 테스트용으로 점수 분포를 만든다.
    const base = Number(site?.latest_score ?? 0);
    const score = Math.max(5, Math.min(99, base - ((moduleNo - 1) % 6) * 7 + ((moduleNo % 3) * 3)));
    return scoreToStatus(score);
  }

  function aggregateStatus(site, type, no) {
    if (type === 'site') return scoreToStatus(site?.latest_score);
    if (type === 'bank') return scoreToStatus(site?.latest_score);
    if (type === 'rack') {
      const base = Number(site?.latest_score ?? 0) - (toInt(no, 1) - 1) * 8;
      return scoreToStatus(base);
    }
    if (type === 'string') {
      const base = Number(site?.latest_score ?? 0) - (toInt(no, 1) - 1) * 5;
      return scoreToStatus(base);
    }
    return estimateModuleStatus(site, no);
  }

  function treeButton({ type, label, status, depth, active, onclick }) {
    return `<button type="button" class="sidebar-tree-row depth-${depth} ${active ? 'active' : ''}" onclick="${onclick}">
      ${statusDot(status)}
      <span class="tree-node-type">${escapeHtml(type)}</span>
      <span class="tree-node-label">${escapeHtml(label)}</span>
    </button>`;
  }

  function renderSidebarTreeCard(site) {
    const holder = document.getElementById('sidebarTreeCard');
    if (!holder) return;

    if (state.page !== 'detail') {
      holder.innerHTML = '';
      holder.classList.remove('visible');
      document.body.classList.remove('detail-tree-mode');
      return;
    }

    document.body.classList.add('detail-tree-mode');
    holder.classList.add('visible');

    const counts = siteCounts(site);
    const p = state.selectedPath || { bank_no: 1, rack_no: 1, string_no: 1, module_no: 1 };
    const bankNo = clamp(p.bank_no, 1, counts.bank);
    const rackNo = clamp(p.rack_no, 1, counts.rack);
    const stringNo = clamp(p.string_no, 1, counts.string);
    const moduleNo = clamp(p.module_no, 1, counts.module);

    const rackRows = [];
    for (let rack = 1; rack <= counts.rack; rack += 1) {
      const isRackOpen = rack === rackNo;
      rackRows.push(treeButton({
        type: 'R', label: `Rack ${String(rack).padStart(2, '0')}`, depth: 1,
        status: aggregateStatus(site, 'rack', rack), active: state.level === 'rack' && isRackOpen,
        onclick: `selectTreeNode('rack', ${bankNo}, ${rack}, 1, 1)`,
      }));
      if (!isRackOpen) continue;

      const stringRows = [];
      for (let string = 1; string <= counts.string; string += 1) {
        const isStringOpen = string === stringNo;
        stringRows.push(treeButton({
          type: 'S', label: `String ${String(string).padStart(2, '0')}`, depth: 2,
          status: aggregateStatus(site, 'string', string), active: state.level === 'string' && isStringOpen,
          onclick: `selectTreeNode('string', ${bankNo}, ${rack}, ${string}, 1)`,
        }));
        if (!isStringOpen) continue;

        const perRack = Math.max(1, Math.ceil(counts.module / Math.max(1, counts.rack)));
        const startModule = Math.min(counts.module, (rack - 1) * perRack + 1);
        const endModule = Math.min(counts.module, rack * perRack);
        for (let module = startModule; module <= endModule; module += 1) {
          stringRows.push(treeButton({
            type: 'M', label: `Module ${String(module).padStart(2, '0')}`, depth: 3,
            status: aggregateStatus(site, 'module', module), active: state.level === 'module' && module === moduleNo,
            onclick: `selectTreeNode('module', ${bankNo}, ${rack}, ${string}, ${module})`,
          }));
        }
      }
      rackRows.push(`<div class="tree-children">${stringRows.join('')}</div>`);
    }

    holder.innerHTML = `
      <div class="sidebar-tree-card">
        <div class="sidebar-tree-title">
          <div><b>계층 구조 탐색</b><span>현재 사이트 기준</span></div>
          <button type="button" onclick="refreshCurrentDetail()" title="새로고침">↻</button>
        </div>
        <button type="button" class="sidebar-tree-site ${state.level === 'site' ? 'active' : ''}" onclick="selectTreeNode('site', ${bankNo}, ${rackNo}, ${stringNo}, ${moduleNo})">
          <div>${statusDot(aggregateStatus(site, 'site'))}<b>${escapeHtml(site.site_name || '-')}</b></div>
          <span>${escapeHtml(site.bms_id || '-')}</span>
          <strong>${escapeHtml(site.latest_score ?? '-')}</strong>
        </button>
        ${treeButton({ type: 'B', label: `Bank ${String(bankNo).padStart(2, '0')}`, depth: 0, status: aggregateStatus(site, 'bank', bankNo), active: state.level === 'bank', onclick: `selectTreeNode('bank', ${bankNo}, ${rackNo}, ${stringNo}, ${moduleNo})` })}
        <div class="tree-children">${rackRows.join('')}</div>
        <div class="tree-legend">
          <span>${statusDot('normal')}정상</span>
          <span>${statusDot('warning')}주의</span>
          <span>${statusDot('abnormal')}비정상</span>
          <span>${statusDot('offline')}오프라인</span>
        </div>
      </div>`;
  }

  function levelTitle(level) {
    if (level === 'site') return '사이트 개요';
    if (level === 'bank') return 'Bank 상세';
    if (level === 'rack') return 'Rack 상세';
    if (level === 'string') return 'String 상세';
    return 'Module 상세';
  }

  function breadcrumbText(site) {
    const p = state.selectedPath || { bank_no: 1, rack_no: 1, string_no: 1, module_no: 1 };
    const parts = ['사이트 목록', site.site_name || '-'];
    if (state.level !== 'site') parts.push(`Bank ${String(p.bank_no).padStart(2, '0')}`);
    if (['rack', 'string', 'module'].includes(state.level)) parts.push(`Rack ${String(p.rack_no).padStart(2, '0')}`);
    if (['string', 'module'].includes(state.level)) parts.push(`String ${String(p.string_no).padStart(2, '0')}`);
    if (state.level === 'module') parts.push(`Module ${String(p.module_no).padStart(2, '0')}`);
    return parts.map(escapeHtml).join(' <span>›</span> ');
  }

  function renderSiteOverview(site) {
    return `
      <section class="panel site-overview-panel">
        <div class="panel-title"><span class="mini-icon">▦</span>사이트 정보</div>
        <div class="site-overview-grid">
          <div><small>사이트명</small><b>${escapeHtml(site.site_name || '-')}</b></div>
          <div><small>BMS ID</small><b>${escapeHtml(site.bms_id || '-')}</b></div>
          <div><small>지역</small><b>${escapeHtml(site.region || '-')}</b></div>
          <div><small>설치구역</small><b>${escapeHtml(site.install_area || '-')}</b></div>
          <div><small>제조사</small><b>${escapeHtml(site.manufacturer || '-')}</b></div>
          <div><small>설치일</small><b>${escapeHtml(site.installed_at || '-')}</b></div>
          <div><small>Bank / Rack</small><b>${escapeHtml(site.bank_count || 0)} / ${escapeHtml(site.rack_count || 0)}</b></div>
          <div><small>Module / Cell</small><b>${escapeHtml(site.module_count || 0)} / ${escapeHtml(site.cell_count || 0)}</b></div>
        </div>
      </section>`;
  }

  window.selectTreeNode = function (level, bankNo = 1, rackNo = 1, stringNo = 1, moduleNo = 1) {
    state.page = 'detail';
    state.level = level || 'site';
    state.selectedPath = {
      bank_no: toInt(bankNo, 1),
      rack_no: toInt(rackNo, 1),
      string_no: toInt(stringNo, 1),
      module_no: toInt(moduleNo, 1),
    };
    saveDetail(state.selectedSiteId, { level: state.level, ...state.selectedPath });
    renderDetail();
  };

  window.refreshCurrentDetail = function () {
    renderDetail();
  };

  const oldSelectSite = selectSite;
  selectSite = function (siteId) {
    state.selectedSiteId = siteId;
    state.page = 'detail';
    const saved = saveDetail(siteId, { level: state.level || 'site' });
    state.level = saved.level || 'site';
    renderDetail();
  };
  window.selectSite = selectSite;

  const oldNav = nav;
  nav = function (page) {
    if (page === 'detail') {
      const saved = getSavedDetail();
      if (saved.site_id) state.selectedSiteId = saved.site_id;
      state.level = saved.level || state.level || 'site';
      return renderDetail();
    }
    const holder = document.getElementById('sidebarTreeCard');
    if (holder) holder.innerHTML = '';
    document.body.classList.remove('detail-tree-mode');
    return oldNav(page);
  };
  window.nav = nav;

  renderDetail = async function () {
    try {
      setActive('detail');
      state.page = 'detail';
      setLoading('사이트 상세 로딩 중');
      await loadCommonData();
      const baseSite = pickCurrentSite();
      ensureDetailState(baseSite);
      const detailData = await fetchJson(API.site(baseSite.site_id), null);
      const site = detailData?.result || baseSite;
      ensureDetailState(site);
      saveDetail(site.site_id, { level: state.level, ...state.selectedPath });
      renderSidebarTreeCard(site);

      const levelData = state.level !== 'site' ? await fetchJson(API.level(site.site_id, state.level), null) : null;
      const level = levelData?.result || {};
      const recData = await fetchJson(API.recommendations(site.site_id), null);
      const recs = Array.isArray(recData?.result) ? recData.result : [];
      const fallbackCells = [18,22,31,26,29,34,92,45,28,33,24,37,41,27,39,32,30,25,48,21].map((v,i) => ({ cell_no:i+1, score:v, status:v>=80?'abnormal':v>=40?'warning':'normal', voltage:(3.62 + i/1000).toFixed(3), temperature:(30 + v/8).toFixed(1) }));
      const cells = Array.isArray(level.cells) ? level.cells : fallbackCells;
      const path = state.selectedPath || { bank_no: 1, rack_no: 1, string_no: 1, module_no: 1 };
      const maxScore = level.max_score ?? site.latest_score;
      const currentStatus = level.status || site.status || scoreToStatus(maxScore);

      const levelBody = state.level === 'site'
        ? renderSiteOverview(site)
        : `<section class="panel"><div class="panel-title"><span class="mini-icon">▦</span>Cell 상태 맵</div><div class="cell-map">
            ${cells.map((c) => `<div class="cell ${normalizeStatus(c.status) === 'abnormal' ? 'bad' : normalizeStatus(c.status) === 'warning' ? 'warn' : 'good'}"><b>Cell ${String(c.cell_no).padStart(2,'0')}</b><span>${escapeHtml(c.score)}</span></div>`).join('')}
          </div></section>
          <section class="panel"><div class="panel-title"><span class="mini-icon">▥</span>위험 Cell 상세</div><div class="ranking-table"><table><thead><tr><th>Cell</th><th>점수</th><th>상태</th><th>전압</th><th>온도</th></tr></thead><tbody>
            ${cells.slice().sort((a,b)=>Number(b.score||0)-Number(a.score||0)).slice(0,8).map((c)=>`<tr><td><b>Cell ${String(c.cell_no).padStart(2,'0')}</b></td><td>${score(c.score)}</td><td>${badge(c.status)}</td><td>${escapeHtml(c.voltage || '-')} V</td><td>${escapeHtml(c.temperature || '-')} ℃</td></tr>`).join('')}
          </tbody></table></div></section>`;

      content.innerHTML = `
      <div class="page detail-page">
        <section class="detail-left">
          <div class="breadcrumb">${breadcrumbText(site)}</div>
          <div class="detail-title detail-title-row"><div class="site-icon">▦</div><div><h1>${escapeHtml(site.site_name)} <span>›</span> ${levelTitle(state.level)}</h1><p>${escapeHtml(site.region)} · ${escapeHtml(site.manufacturer)} · ${escapeHtml(site.bms_id || '')}</p></div><select class="site-select" onchange="selectSite(this.value)">${siteOptions()}</select></div>
          <div class="level-tabs"><button class="level-tab ${state.level==='site'?'active':''}" onclick="selectTreeNode('site', ${path.bank_no}, ${path.rack_no}, ${path.string_no}, ${path.module_no})">Site</button><button class="level-tab ${state.level==='bank'?'active':''}" onclick="selectTreeNode('bank', ${path.bank_no}, ${path.rack_no}, ${path.string_no}, ${path.module_no})">Bank</button><button class="level-tab ${state.level==='rack'?'active':''}" onclick="selectTreeNode('rack', ${path.bank_no}, ${path.rack_no}, ${path.string_no}, ${path.module_no})">Rack</button><button class="level-tab ${state.level==='string'?'active':''}" onclick="selectTreeNode('string', ${path.bank_no}, ${path.rack_no}, ${path.string_no}, ${path.module_no})">String</button><button class="level-tab ${state.level==='module'?'active':''}" onclick="selectTreeNode('module', ${path.bank_no}, ${path.rack_no}, ${path.string_no}, ${path.module_no})">Module</button></div>
          <div class="detail-grid-top"><div class="info-card"><small>최대 이상 점수</small><b>${score(maxScore)}</b></div><div class="info-card"><small>상태</small><b>${badge(currentStatus)}</b></div><div class="info-card"><small>최근 분석 시각</small><b>${escapeHtml(formatDateTime(level.last_analysis_time || site.last_analysis_time))}</b></div><div class="info-card"><small>위험 위치</small><b>${escapeHtml(site.risk_location || '-')}</b></div></div>
          ${levelBody}
        </section>
        <aside class="detail-right"><section class="panel"><div class="panel-title"><span class="mini-icon">⚠</span>운영 권고</div><div class="alarm-list">
          ${(recs.length ? recs : [{title:'상세 점검 권고', message:'현재 선택된 계층의 이상 점수와 상태를 확인하세요.'}]).map((r)=>`<div class="alarm-item"><div class="alarm-icon red">⚠</div><div><div class="alarm-name">${escapeHtml(r.title)}</div><small>${escapeHtml(r.message || r.action || '')}</small></div></div>`).join('')}
        </div></section></aside>
      </div>`;
      renderSidebarTreeCard(site);
    } catch (error) {
      console.error('[monitor] renderDetail v22 failed', error);
      showError('사이트 상세 표시 중 오류가 발생했습니다.', error.stack || error.message);
    }
  };

  setLevel = function (level) {
    window.selectTreeNode(level, state.selectedPath?.bank_no || 1, state.selectedPath?.rack_no || 1, state.selectedPath?.string_no || 1, state.selectedPath?.module_no || 1);
  };
  window.setLevel = setLevel;
})();
'''
    js_path.write_text(js, encoding='utf-8')

# 3) Append CSS for polished sidebar tree + site overview. It overrides ugly native UI.
css = css_path.read_text(encoding='utf-8')
css_marker = '/* === KESCO detail UX v22 styles === */'
if css_marker not in css:
    css += r'''

/* === KESCO detail UX v22 styles === */
#sidebarTreeCard { display: none; padding: 0 18px 18px; }
#sidebarTreeCard.visible { display: block; }
body.detail-tree-mode .ess-illustration { display: none; }
body.detail-tree-mode .sidebar { overflow-y: auto; }
.sidebar-tree-card { margin-top: 12px; padding: 16px; border: 1px solid var(--line); border-radius: 18px; background: linear-gradient(180deg,#fff,#f8fbff); box-shadow: var(--soft); }
.sidebar-tree-title { display:flex; align-items:center; justify-content:space-between; margin-bottom: 12px; }
.sidebar-tree-title b { display:block; font-size: 17px; letter-spacing:-.3px; color: var(--text); }
.sidebar-tree-title span { display:block; margin-top:3px; font-size: 12px; font-weight: 800; color: var(--muted); }
.sidebar-tree-title button { width: 32px; height: 32px; border-radius: 10px; border: 1px solid var(--line); background: #fff; color: var(--blue); font-weight: 900; cursor: pointer; }
.sidebar-tree-site, .sidebar-tree-row { appearance:none; -webkit-appearance:none; width:100%; border:0; background:transparent; font-family:inherit; cursor:pointer; }
.sidebar-tree-site { position:relative; display:grid; grid-template-columns: 1fr auto; gap: 6px 10px; padding: 12px; border:1px solid var(--line2); border-radius: 14px; background:#fff; text-align:left; margin-bottom:12px; }
.sidebar-tree-site.active, .sidebar-tree-site:hover { background:#eef6ff; border-color:#cfe3ff; }
.sidebar-tree-site div { display:flex; align-items:center; gap:8px; min-width:0; }
.sidebar-tree-site b { font-size:15px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.sidebar-tree-site span { grid-column:1/2; font-size:12px; font-weight:800; color:#667085; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.sidebar-tree-site strong { grid-row:1/3; grid-column:2/3; align-self:center; min-width:42px; height:32px; padding:0 8px; border-radius:10px; display:flex; align-items:center; justify-content:center; background:var(--red-bg); color:#dc2626; border:1px solid #fecaca; font-size:14px; }
.sidebar-tree-row { height:34px; display:flex; align-items:center; gap:7px; border-radius:10px; padding:0 10px; margin: 2px 0; color:#26364d; font-size:13px; font-weight:850; text-align:left; }
.sidebar-tree-row:hover { background:#f1f6ff; }
.sidebar-tree-row.active { background:#e8f2ff; color:var(--blue); box-shadow: inset 0 0 0 1px #cfe3ff; }
.sidebar-tree-row.depth-0 { padding-left: 10px; }
.sidebar-tree-row.depth-1 { padding-left: 24px; }
.sidebar-tree-row.depth-2 { padding-left: 38px; }
.sidebar-tree-row.depth-3 { padding-left: 52px; }
.tree-node-type { width:22px; height:22px; border-radius:7px; display:inline-flex; align-items:center; justify-content:center; background:#f1f5fb; color:#53657d; font-size:11px; font-weight:900; flex:0 0 auto; }
.sidebar-tree-row.active .tree-node-type { background:var(--blue); color:#fff; }
.tree-node-label { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.tree-children { position: relative; }
.tree-children:before { content:""; position:absolute; left: 19px; top:0; bottom:0; width:1px; background:#e3ebf5; }
.tree-status-dot { width:9px; height:9px; border-radius:50%; display:inline-block; flex:0 0 auto; box-shadow:0 0 0 3px rgba(0,0,0,.03); }
.tree-status-dot.normal { background:var(--green); }
.tree-status-dot.warning { background:var(--orange); }
.tree-status-dot.abnormal { background:var(--red); }
.tree-status-dot.offline { background:#98a2b3; }
.tree-legend { display:flex; flex-wrap:wrap; gap:8px 10px; padding-top:12px; margin-top:12px; border-top:1px solid var(--line2); color:#667085; font-size:12px; font-weight:850; }
.tree-legend span { display:inline-flex; align-items:center; gap:5px; }
.site-overview-panel { margin-top: 14px; }
.site-overview-grid { padding: 22px; display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 14px; }
.site-overview-grid div { min-height: 82px; border: 1px solid var(--line2); background:#fbfdff; border-radius: 14px; padding: 15px 16px; display:flex; flex-direction:column; justify-content:center; }
.site-overview-grid small { display:block; color:#667085; font-size:13px; font-weight:800; margin-bottom:8px; }
.site-overview-grid b { font-size:17px; color:var(--text); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.level-tabs { grid-template-columns: repeat(5, 1fr) !important; }
.detail-grid-top .info-card b { word-break: break-word; }
.cell-map .cell { display:flex !important; flex-direction:column !important; align-items:center !important; justify-content:center !important; gap:7px !important; }
.cell-map .cell b { font-size:13px !important; color:#526177 !important; }
.cell-map .cell span { font-size:23px !important; font-weight:950 !important; }
@media (max-width: 1500px) { .site-overview-grid { grid-template-columns: repeat(2, minmax(0,1fr)); } }
'''
    css_path.write_text(css, encoding='utf-8')

print('[v22] detail navigation patch applied successfully')
print(f'- fixed: {service_path}')
print(f'- updated: {index_path}')
print(f'- updated: {js_path}')
print(f'- updated: {css_path}')
