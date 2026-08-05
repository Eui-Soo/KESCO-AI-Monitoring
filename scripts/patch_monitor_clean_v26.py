from pathlib import Path
import re

ROOT = Path.cwd()
monitor = ROOT / 'static' / 'monitor'
js_path = monitor / 'monitor.js'
css_path = monitor / 'monitor.css'
idx_path = monitor / 'index.html'

if not js_path.exists():
    raise SystemExit(f'not found: {js_path}')

bak = js_path.with_suffix('.js.v26.bak')
bak.write_text(js_path.read_text(encoding='utf-8', errors='replace'), encoding='utf-8')

clean_js = r'''
/* KESCO Monitor UI - v26 clean rebuild
 * ASCII-only labels to avoid Windows/Mac mojibake while UI is being developed.
 */

const content = document.getElementById('content');
const navItems = document.querySelectorAll('.nav-item');
const topbarTitle = document.getElementById('topbarTitle');

const API = {
  system: '/api/v1/monitor/system-status',
  dashboard: '/api/v1/monitor/dashboard/summary',
  sites: '/api/v1/monitor/sites',
  site: (id) => `/api/v1/monitor/sites/${encodeURIComponent(id)}`,
  level: (id, level = 'module') => `/api/v1/monitor/sites/${encodeURIComponent(id)}/level?level=${encodeURIComponent(level)}`,
  trend: (id) => `/api/v1/monitor/sites/${encodeURIComponent(id)}/trend?level=module`,
  recommendations: (id) => `/api/v1/monitor/recommendations?site_id=${encodeURIComponent(id || '')}`,
};

const fallbackSites = [
  { site_id:'SITE-0021__BMS-DEMO', site_no:21, site_name:'ESS Site 21', region:'Local DB', install_area:'South-West', manufacturer:'Samsung SDI', installed_at:'2024-11-15', bms_id:'DEMO-BMS-21', latest_score:93.7, average_score:70.1, status:'abnormal', status_text:'Abnormal', last_analysis_time:'2025-05-19T10:20:15', risk_location:'Latest anomaly_score result', bank_count:1, rack_count:4, string_count:2, module_count:12, cell_count:240, score_row_count:12 },
  { site_id:'SITE-0022__BMS-DEMO', site_no:22, site_name:'ESS Site 22', region:'Local DB', install_area:'South', manufacturer:'LG Energy Solution', installed_at:'2024-08-21', bms_id:'DEMO-BMS-22', latest_score:68.1, average_score:51.4, status:'warning', status_text:'Warning', last_analysis_time:'2025-05-19T10:15:12', risk_location:'Latest anomaly_score result', bank_count:1, rack_count:3, string_count:2, module_count:12, cell_count:240, score_row_count:12 },
  { site_id:'SITE-0023__BMS-DEMO', site_no:23, site_name:'ESS Site 23', region:'Local DB', install_area:'East', manufacturer:'SK On', installed_at:'2024-09-30', bms_id:'DEMO-BMS-23', latest_score:32.4, average_score:22.7, status:'normal', status_text:'Normal', last_analysis_time:'2025-05-19T10:18:09', risk_location:'-', bank_count:1, rack_count:2, string_count:1, module_count:8, cell_count:160, score_row_count:8 },
];

const state = {
  page: 'dashboard',
  sites: fallbackSites,
  selectedSiteId: fallbackSites[0].site_id,
  level: 'site',
  selectedBank: 1,
  selectedRack: 1,
  selectedString: 1,
  selectedModule: 1,
  treeCollapsed: false,
};

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
}

function fmtTime(value) {
  if (!value) return '-';
  const text = String(value).replace('T', ' ');
  return text.split('.')[0].slice(0, 19);
}

function normalizeScore(value) {
  if (value === null || value === undefined || value === '') return null;
  let n = Number(value);
  if (Number.isNaN(n)) return null;
  if (n <= 1) n *= 100;
  return Math.round(n * 10) / 10;
}

function statusKey(input) {
  const raw = typeof input === 'string' ? input : (input?.status || input?.max_level || input?.status_text || 'normal');
  const key = String(raw || 'normal').toLowerCase();
  if (['abnormal','danger','critical','error','bad'].includes(key)) return 'abnormal';
  if (['warning','caution','warn'].includes(key)) return 'warning';
  if (['offline','unavailable','data_missing','missing'].includes(key)) return 'offline';
  return 'normal';
}

function statusLabel(input) {
  const key = statusKey(input);
  if (key === 'abnormal') return 'Abnormal';
  if (key === 'warning') return 'Warning';
  if (key === 'offline') return 'Offline';
  return 'Normal';
}

function statusClass(input) {
  const key = statusKey(input);
  if (key === 'abnormal') return 'bad';
  if (key === 'warning') return 'warn';
  if (key === 'offline') return 'gray';
  return 'good';
}

function dot(input) {
  return `<span class="tree-dot ${statusKey(input)}" title="${statusLabel(input)}"></span>`;
}

function badge(input) {
  return `<span class="state-badge ${statusClass(input)}">${escapeHtml(statusLabel(input))}</span>`;
}

function scoreBadge(value) {
  const n = normalizeScore(value);
  const cls = n === null ? 'gray' : n >= 71 ? 'bad' : n >= 40 ? 'warn' : 'good';
  return `<span class="score-badge ${cls}">${escapeHtml(n === null ? '-' : n)}</span>`;
}

async function fetchJson(url, fallback = null) {
  try {
    const res = await fetch(url, { headers: { Accept: 'application/json' }, cache: 'no-store' });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText} - ${url}`);
    return await res.json();
  } catch (error) {
    console.warn('[monitor] API fallback:', url, error);
    return fallback;
  }
}

function normalizeSites(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.items)) return data.items;
  if (Array.isArray(data?.result?.items)) return data.result.items;
  if (Array.isArray(data?.result)) return data.result;
  return fallbackSites;
}

function currentSite() {
  return state.sites.find((s) => String(s.site_id) === String(state.selectedSiteId)) || state.sites[0] || fallbackSites[0];
}

function countsForSites(sites) {
  return {
    normal: sites.filter((s) => statusKey(s) === 'normal').length,
    warning: sites.filter((s) => statusKey(s) === 'warning').length,
    abnormal: sites.filter((s) => statusKey(s) === 'abnormal').length,
    offline: sites.filter((s) => statusKey(s) === 'offline').length,
  };
}

function setActive(page) {
  state.page = page;
  if (topbarTitle) topbarTitle.textContent = page === 'dashboard' ? 'Dashboard' : page === 'sites' ? 'Site List' : page === 'detail' ? 'Site Detail' : page === 'history' ? 'Run History' : 'Settings';
  navItems.forEach((item) => item.classList.toggle('active', item.dataset.page === page));
}

function setLoading(title = 'Loading') {
  if (!content) return;
  content.innerHTML = `<div class="page"><section class="panel loading-panel"><div class="loading-icon">...</div><h2>${escapeHtml(title)}</h2><p>Loading AI monitoring data.</p></section></div>`;
}

function showError(message, detail = '') {
  if (!content) return;
  content.innerHTML = `<div class="page"><section class="panel error-panel"><div class="panel-title">Render Error</div><p>${escapeHtml(message)}</p><pre>${escapeHtml(detail)}</pre><button class="table-action" onclick="location.reload()">Reload</button></section></div>`;
}

async function loadCommonData() {
  const sitesData = await fetchJson(API.sites, { items: fallbackSites });
  state.sites = normalizeSites(sitesData).map((site, idx) => ({
    bank_count: 1,
    rack_count: 2,
    string_count: 1,
    module_count: 12,
    cell_count: 240,
    manufacturer: site.manufacturer && site.manufacturer !== '-' ? site.manufacturer : ['Samsung SDI','LG Energy Solution','SK On','Kokam'][idx % 4],
    region: site.region && site.region !== '-' ? site.region : ['Local DB','Daejeon','Sejong','Jeonbuk'][idx % 4],
    install_area: site.install_area && site.install_area !== '-' ? site.install_area : ['R&D Center','South-West','East','North'][idx % 4],
    ...site,
  }));
  if (!state.sites.some((s) => String(s.site_id) === String(state.selectedSiteId))) {
    state.selectedSiteId = state.sites[0]?.site_id || fallbackSites[0].site_id;
  }
}

function nav(page) {
  if (page === 'dashboard') return renderDashboard();
  if (page === 'sites') return renderSites();
  if (page === 'detail') return renderDetail();
  if (page === 'history') return renderPlaceholder('Run History', 'Pipeline run history will be connected later.');
  if (page === 'settings') return renderPlaceholder('Settings', 'Notification, model, and user settings will be connected later.');
}
window.nav = nav;

function renderPlaceholder(title, desc) {
  setActive(title === 'Run History' ? 'history' : 'settings');
  content.innerHTML = `<div class="page"><section class="panel"><div class="panel-title">${escapeHtml(title)}</div><p class="muted-text">${escapeHtml(desc)}</p></section></div>`;
}

function selectSite(siteId) {
  state.selectedSiteId = siteId;
  state.level = 'site';
  state.selectedBank = 1;
  state.selectedRack = 1;
  state.selectedString = 1;
  state.selectedModule = 1;
  renderDetail();
}
window.selectSite = selectSite;

function goLevel(level, bank = state.selectedBank, rack = state.selectedRack, stringNo = state.selectedString, moduleNo = state.selectedModule) {
  state.level = level;
  state.selectedBank = Number(bank) || 1;
  state.selectedRack = Number(rack) || 1;
  state.selectedString = Number(stringNo) || 1;
  state.selectedModule = Number(moduleNo) || 1;
  state.treeCollapsed = false;
  renderDetail();
}
window.goLevel = goLevel;

function resetTree() {
  state.level = 'site';
  state.selectedBank = 1;
  state.selectedRack = 1;
  state.selectedString = 1;
  state.selectedModule = 1;
  state.treeCollapsed = true;
  renderDetail();
}
window.resetTree = resetTree;

function otherSites() { renderSites(); }
window.otherSites = otherSites;

async function renderDashboard() {
  try {
    setActive('dashboard');
    setLoading('Dashboard loading');
    await loadCommonData();
    const dashboardData = await fetchJson(API.dashboard, null);
    const result = dashboardData?.result || {};
    const summary = result.summary || {};
    const counts = countsForSites(state.sites);
    const ranking = state.sites
      .filter((s) => normalizeScore(s.latest_score) !== null)
      .slice()
      .sort((a,b) => normalizeScore(b.latest_score) - normalizeScore(a.latest_score))
      .slice(0, 6);
    const priority = ranking.slice(0, 3);

    content.innerHTML = `
    <div class="page">
      <div class="dashboard-grid v26-dashboard-grid">
        <div class="hero-card"><div class="hero-left"><div class="hero-icon">▦</div><div><div class="hero-title">Total Sites</div><div class="hero-value">${escapeHtml(summary.total_site_count ?? state.sites.length)}</div></div></div></div>
        <div class="hero-card"><div class="hero-left"><div class="hero-icon ai">AI</div><div><div class="hero-title">AI Available</div><div class="hero-value green">${escapeHtml(summary.ai_available_site_count ?? state.sites.filter(s=>s.is_ai_available !== false).length)}</div></div></div></div>
        <div class="stat-split hero-card"><h3>Status Summary</h3><div class="split-row"><div class="split-box"><div class="split-label green">Normal</div><div class="split-num green">${counts.normal}</div></div><div class="split-box"><div class="split-label orange">Warning</div><div class="split-num orange">${counts.warning}</div></div><div class="split-box"><div class="split-label red">Abnormal</div><div class="split-num red">${counts.abnormal}</div></div></div></div>
      </div>
      <div class="dash-main">
        <section class="panel">
          <div class="panel-title">Risk Ranking</div>
          <div class="ranking-table"><table><thead><tr><th>Site / BMS</th><th>Region</th><th>Area</th><th>Maker</th><th>Score</th><th>Status</th></tr></thead><tbody>
            ${ranking.map((s) => `<tr class="clickable-row" onclick="selectSite('${escapeHtml(s.site_id)}')"><td><b>${escapeHtml(s.site_name)}</b><small>${escapeHtml(s.bms_id || '-')}</small></td><td>${escapeHtml(s.region || '-')}</td><td>${escapeHtml(s.install_area || '-')}</td><td>${escapeHtml(s.manufacturer || '-')}</td><td>${scoreBadge(s.latest_score)}</td><td>${badge(s)}</td></tr>`).join('')}
          </tbody></table></div>
          <div class="more-link" onclick="nav('sites')">View all sites ›</div>
        </section>
        <section class="panel priority-panel"><div class="panel-title">Priority Check TOP 3</div><div class="priority-list">
          ${priority.map((s, i) => `<div class="priority-item v26-priority" onclick="selectSite('${escapeHtml(s.site_id)}')"><div class="rank-circle ${i===1?'r2':i===2?'r3':''}">${i+1}</div><div><div class="priority-name">${escapeHtml(s.site_name)}</div><small>${escapeHtml(s.bms_id || '-')} · ${escapeHtml(s.risk_location || 'Latest anomaly_score result')}</small></div><div class="priority-reason ${statusClass(s)}">${adviceText(s)}</div></div>`).join('')}
        </div></section>
      </div>
    </div>`;
  } catch (error) { showError('Dashboard render failed.', error.stack || error.message); }
}

function adviceText(site) {
  const score = normalizeScore(site.latest_score) ?? '-';
  const key = statusKey(site);
  if (key === 'abnormal') return `Immediate check · Max ${score}`;
  if (key === 'warning') return `Watch required · Max ${score}`;
  return `Normal range · Max ${score}`;
}

async function renderSites() {
  try {
    setActive('sites');
    setLoading('Site list loading');
    await loadCommonData();
    const items = state.sites.slice().sort((a,b) => (normalizeScore(b.latest_score) ?? -1) - (normalizeScore(a.latest_score) ?? -1));
    const counts = countsForSites(items);
    content.innerHTML = `
    <div class="page sites-page-wide">
      <div class="page-heading"><div><h1>Site List</h1><p>Check ESS site status, score, maker, area, and latest analysis time.</p></div></div>
      <div class="site-summary-strip"><div><b>${items.length}</b><span>Total</span></div><div><b class="green">${counts.normal}</b><span>Normal</span></div><div><b class="orange">${counts.warning}</b><span>Warning</span></div><div><b class="red">${counts.abnormal}</b><span>Abnormal</span></div><div><b>${counts.offline}</b><span>Offline</span></div></div>
      <section class="table-card"><table class="data-table wide-site-table"><thead><tr><th>Site / BMS</th><th>Region</th><th>Area</th><th>Maker</th><th>Installed</th><th>Score</th><th>Status</th><th>Last Analysis</th><th>Action</th></tr></thead><tbody>
        ${items.map((s) => `<tr><td><b>${escapeHtml(s.site_name)}</b><small>${escapeHtml(s.bms_id || '-')}</small></td><td>${escapeHtml(s.region || '-')}</td><td>${escapeHtml(s.install_area || '-')}</td><td>${escapeHtml(s.manufacturer || '-')}</td><td>${escapeHtml(s.installed_at || '-')}</td><td>${scoreBadge(s.latest_score)}</td><td>${badge(s)}</td><td>${escapeHtml(fmtTime(s.last_analysis_time))}</td><td><button class="table-action" onclick="selectSite('${escapeHtml(s.site_id)}')">Detail</button></td></tr>`).join('')}
      </tbody></table></section>
    </div>`;
  } catch (error) { showError('Site list render failed.', error.stack || error.message); }
}

function levelTitle(level) {
  if (level === 'site') return 'Site Overview';
  if (level === 'bank') return `Bank ${String(state.selectedBank).padStart(2,'0')} Detail`;
  if (level === 'rack') return `Rack ${String(state.selectedRack).padStart(2,'0')} Detail`;
  if (level === 'string') return `String ${String(state.selectedString).padStart(2,'0')} Detail`;
  return `Module ${String(state.selectedModule).padStart(2,'0')} Detail`;
}

function childStatus(baseScore, idx) {
  const n = (normalizeScore(baseScore) ?? 20) - idx * 4;
  if (n >= 71) return 'abnormal';
  if (n >= 40) return 'warning';
  return 'normal';
}

function renderTree(site) {
  const bankCount = Math.max(1, Number(site.bank_count || 1));
  const rackCount = Math.max(1, Number(site.rack_count || 2));
  const stringCount = Math.max(1, Number(site.string_count || 1));
  const moduleCount = Math.max(1, Number(site.module_count || 12));
  let html = `<aside class="hierarchy-card v26-tree-card"><div class="hierarchy-head"><div><b onclick="goLevel('site')">${escapeHtml(site.site_name)}</b><span>${escapeHtml(site.bms_id || '-')} · Score ${escapeHtml(normalizeScore(site.latest_score) ?? '-')}</span></div><button onclick="resetTree()" title="Collapse tree">Reset</button></div>`;
  html += `<button class="tree-site ${state.level==='site'?'active':''}" onclick="goLevel('site')">${dot(site)} Site information</button>`;
  if (!state.treeCollapsed) {
    for (let b = 1; b <= bankCount; b++) {
      const bStatus = childStatus(site.latest_score, b-1);
      html += `<button class="tree-row tree-bank ${state.level==='bank' && state.selectedBank===b?'active':''}" onclick="goLevel('bank',${b},1,1,1)">${dot(bStatus)} Bank ${String(b).padStart(2,'0')}</button>`;
      if (state.selectedBank === b || state.level === 'site') {
        for (let r = 1; r <= rackCount; r++) {
          const rStatus = childStatus(site.latest_score, r);
          html += `<button class="tree-row tree-rack ${state.level==='rack' && state.selectedRack===r?'active':''}" onclick="goLevel('rack',${b},${r},1,1)">${dot(rStatus)} Rack ${String(r).padStart(2,'0')}</button>`;
          if (state.selectedRack === r && ['rack','string','module'].includes(state.level)) {
            for (let s = 1; s <= stringCount; s++) {
              const sStatus = childStatus(site.latest_score, s+2);
              html += `<button class="tree-row tree-string ${state.level==='string' && state.selectedString===s?'active':''}" onclick="goLevel('string',${b},${r},${s},1)">${dot(sStatus)} String ${String(s).padStart(2,'0')}</button>`;
              if (state.selectedString === s && ['string','module'].includes(state.level)) {
                for (let m = 1; m <= moduleCount; m++) {
                  const mStatus = childStatus(site.latest_score, m+3);
                  html += `<button class="tree-row tree-module ${state.level==='module' && state.selectedModule===m?'active':''}" onclick="goLevel('module',${b},${r},${s},${m})">${dot(mStatus)} Module ${String(m).padStart(2,'0')}</button>`;
                }
              }
            }
          }
        }
      }
    }
  }
  html += `<div class="tree-legend"><span>${dot('normal')}Normal</span><span>${dot('warning')}Warning</span><span>${dot('abnormal')}Abnormal</span><span>${dot('offline')}Offline</span></div></aside>`;
  return html;
}

function breadcrumb(site) {
  const parts = [
    `<button onclick="nav('sites')">Site List</button>`,
    `<button onclick="goLevel('site')">${escapeHtml(site.site_name)}</button>`,
  ];
  if (['bank','rack','string','module'].includes(state.level)) parts.push(`<button onclick="goLevel('bank',${state.selectedBank},1,1,1)">Bank ${String(state.selectedBank).padStart(2,'0')}</button>`);
  if (['rack','string','module'].includes(state.level)) parts.push(`<button onclick="goLevel('rack',${state.selectedBank},${state.selectedRack},1,1)">Rack ${String(state.selectedRack).padStart(2,'0')}</button>`);
  if (['string','module'].includes(state.level)) parts.push(`<button onclick="goLevel('string',${state.selectedBank},${state.selectedRack},${state.selectedString},1)">String ${String(state.selectedString).padStart(2,'0')}</button>`);
  if (state.level === 'module') parts.push(`<button onclick="goLevel('module',${state.selectedBank},${state.selectedRack},${state.selectedString},${state.selectedModule})">Module ${String(state.selectedModule).padStart(2,'0')}</button>`);
  return `<div class="breadcrumb v26-breadcrumb">${parts.join('<span>›</span>')}</div>`;
}

function metricCard(label, value, extra = '') {
  return `<div class="info-card"><small>${escapeHtml(label)}</small><b>${value}</b>${extra ? `<em>${escapeHtml(extra)}</em>` : ''}</div>`;
}

function renderSiteOverview(site) {
  return `<section class="panel"><div class="panel-title">Site Information</div><div class="overview-grid">
    ${metricCard('BMS ID', escapeHtml(site.bms_id || '-'))}
    ${metricCard('Region', escapeHtml(site.region || '-'))}
    ${metricCard('Area', escapeHtml(site.install_area || '-'))}
    ${metricCard('Maker', escapeHtml(site.manufacturer || '-'))}
    ${metricCard('Latest Score', scoreBadge(site.latest_score))}
    ${metricCard('Status', badge(site))}
    ${metricCard('Last Analysis', escapeHtml(fmtTime(site.last_analysis_time)))}
    ${metricCard('Rows', escapeHtml(site.score_row_count || 0))}
  </div></section>
  <section class="panel"><div class="panel-title">Hierarchy Summary</div><div class="level-card-grid">
    <button onclick="goLevel('bank',1,1,1,1)">${dot(site)}<b>${escapeHtml(site.bank_count || 1)} Banks</b><span>Open bank level</span></button>
    <button onclick="goLevel('rack',1,1,1,1)">${dot(childStatus(site.latest_score,1))}<b>${escapeHtml(site.rack_count || 0)} Racks</b><span>Open rack level</span></button>
    <button onclick="goLevel('string',1,1,1,1)">${dot(childStatus(site.latest_score,2))}<b>${escapeHtml(site.string_count || 0)} Strings</b><span>Open string level</span></button>
    <button onclick="goLevel('module',1,1,1,1)">${dot(childStatus(site.latest_score,3))}<b>${escapeHtml(site.module_count || 0)} Modules</b><span>Open module level</span></button>
  </div></section>`;
}

function renderBank(site) {
  const rackCount = Math.max(1, Number(site.rack_count || 2));
  const cards = Array.from({length:rackCount}, (_,i) => i+1).map((r) => `<button onclick="goLevel('rack',${state.selectedBank},${r},1,1)">${dot(childStatus(site.latest_score,r))}<b>Rack ${String(r).padStart(2,'0')}</b><span>Open rack detail</span>${scoreBadge((normalizeScore(site.latest_score) ?? 20) - r*4)}</button>`).join('');
  return `<section class="panel"><div class="panel-title">Bank Summary</div><div class="overview-grid">${metricCard('Selected Bank', `Bank ${String(state.selectedBank).padStart(2,'0')}`)}${metricCard('Rack Count', rackCount)}${metricCard('Max Score', scoreBadge(site.latest_score))}${metricCard('Status', badge(site))}</div></section><section class="panel"><div class="panel-title">Racks in Bank</div><div class="level-card-grid">${cards}</div></section>`;
}

function renderRack(site) {
  const stringCount = Math.max(1, Number(site.string_count || 1));
  const cards = Array.from({length:stringCount}, (_,i) => i+1).map((s) => `<button onclick="goLevel('string',${state.selectedBank},${state.selectedRack},${s},1)">${dot(childStatus(site.latest_score,s+2))}<b>String ${String(s).padStart(2,'0')}</b><span>Open string detail</span>${scoreBadge((normalizeScore(site.latest_score) ?? 20) - s*5)}</button>`).join('');
  return `<section class="panel"><div class="panel-title">Rack Summary</div><div class="overview-grid">${metricCard('Selected Rack', `Rack ${String(state.selectedRack).padStart(2,'0')}`)}${metricCard('String Count', stringCount)}${metricCard('Max Score', scoreBadge(site.latest_score))}${metricCard('Status', badge(childStatus(site.latest_score,state.selectedRack)))}</div></section><section class="panel"><div class="panel-title">Strings in Rack</div><div class="level-card-grid">${cards}</div></section>`;
}

function renderString(site) {
  const moduleCount = Math.max(1, Number(site.module_count || 12));
  const cards = Array.from({length:moduleCount}, (_,i) => i+1).map((m) => `<button onclick="goLevel('module',${state.selectedBank},${state.selectedRack},${state.selectedString},${m})">${dot(childStatus(site.latest_score,m+3))}<b>Module ${String(m).padStart(2,'0')}</b><span>Open module detail</span>${scoreBadge((normalizeScore(site.latest_score) ?? 20) - m*3)}</button>`).join('');
  return `<section class="panel"><div class="panel-title">String Summary</div><div class="overview-grid">${metricCard('Selected String', `String ${String(state.selectedString).padStart(2,'0')}`)}${metricCard('Module Count', moduleCount)}${metricCard('Max Score', scoreBadge(site.latest_score))}${metricCard('Status', badge(childStatus(site.latest_score,state.selectedString+2)))}</div></section><section class="panel"><div class="panel-title">Modules in String</div><div class="level-card-grid module-grid">${cards}</div></section>`;
}

function renderModule(site, levelData) {
  const cells = Array.isArray(levelData?.cells) && levelData.cells.length
    ? levelData.cells
    : Array.from({length:20}, (_,i) => {
        const score = Math.max(5, (normalizeScore(site.latest_score) ?? 20) - state.selectedModule * 2 + (i % 5) * 6);
        return { cell_no:i+1, score:Math.round(score), status: score>=71?'abnormal':score>=40?'warning':'normal', voltage:(3.62 + i/1000).toFixed(3), temperature:(28 + score/10).toFixed(1) };
      });
  return `<section class="panel"><div class="panel-title">Module Summary</div><div class="overview-grid">${metricCard('Selected Module', `Module ${String(state.selectedModule).padStart(2,'0')}`)}${metricCard('Max Score', scoreBadge(levelData?.max_score ?? site.latest_score))}${metricCard('Status', badge(levelData?.status || site.status))}${metricCard('Cell Count', cells.length)}</div></section>
  <section class="panel"><div class="panel-title">Cell Status Map</div><div class="cell-map v26-cell-map">${cells.map(c => `<div class="cell ${statusClass(c.status)}"><b>Cell ${String(c.cell_no).padStart(2,'0')}</b><span>${escapeHtml(normalizeScore(c.score) ?? c.score)}</span></div>`).join('')}</div></section>
  <section class="panel"><div class="panel-title">High Risk Cells</div><div class="ranking-table"><table><thead><tr><th>Cell</th><th>Score</th><th>Status</th><th>Voltage</th><th>Temp</th></tr></thead><tbody>${cells.slice().sort((a,b)=>Number(b.score||0)-Number(a.score||0)).slice(0,8).map(c => `<tr><td><b>Cell ${String(c.cell_no).padStart(2,'0')}</b></td><td>${scoreBadge(c.score)}</td><td>${badge(c.status)}</td><td>${escapeHtml(c.voltage || '-')} V</td><td>${escapeHtml(c.temperature || '-')} C</td></tr>`).join('')}</tbody></table></div></section>`;
}

function sidePanel(site) {
  return `<aside class="detail-right"><section class="panel fixed-side-card"><div class="panel-title">Operation Advice</div><div class="advice-main ${statusClass(site)}"><b>${escapeHtml(adviceText(site))}</b><span>${escapeHtml(site.risk_location || 'Latest anomaly_score result')}</span></div></section><section class="panel fixed-side-card"><div class="panel-title">Analysis Summary</div><div class="side-kv"><span>Last Analysis</span><b>${escapeHtml(fmtTime(site.last_analysis_time))}</b></div><div class="side-kv"><span>Score Rows</span><b>${escapeHtml(site.score_row_count || 0)}</b></div><div class="side-kv"><span>Max Score</span><b>${escapeHtml(normalizeScore(site.latest_score) ?? '-')}</b></div><div class="side-kv"><span>Average</span><b>${escapeHtml(normalizeScore(site.average_score) ?? '-')}</b></div></section></aside>`;
}

async function renderDetail() {
  try {
    setActive('detail');
    await loadCommonData();
    const base = currentSite();
    const detailData = await fetchJson(API.site(base.site_id), null);
    const site = detailData?.result || base;
    const levelData = state.level === 'module' ? (await fetchJson(API.level(site.site_id, 'module'), null))?.result || {} : {};
    let body = '';
    if (state.level === 'site') body = renderSiteOverview(site);
    else if (state.level === 'bank') body = renderBank(site);
    else if (state.level === 'rack') body = renderRack(site);
    else if (state.level === 'string') body = renderString(site);
    else body = renderModule(site, levelData);

    content.innerHTML = `<div class="page detail-page v26-detail-page">${renderTree(site)}<section class="detail-left">${breadcrumb(site)}<div class="detail-title detail-title-row v26-title-row"><div class="site-icon">▦</div><div><h1>${escapeHtml(site.site_name)} <span>›</span> ${escapeHtml(levelTitle(state.level))}</h1><p>${escapeHtml(site.bms_id || '-')} · ${escapeHtml(site.region || '-')} · ${escapeHtml(site.manufacturer || '-')}</p></div><button class="table-action" onclick="otherSites()">Other sites</button></div><div class="level-tabs"><button class="level-tab ${state.level==='site'?'active':''}" onclick="goLevel('site')">Site</button><button class="level-tab ${state.level==='bank'?'active':''}" onclick="goLevel('bank',${state.selectedBank},1,1,1)">Bank</button><button class="level-tab ${state.level==='rack'?'active':''}" onclick="goLevel('rack',${state.selectedBank},${state.selectedRack},1,1)">Rack</button><button class="level-tab ${state.level==='string'?'active':''}" onclick="goLevel('string',${state.selectedBank},${state.selectedRack},${state.selectedString},1)">String</button><button class="level-tab ${state.level==='module'?'active':''}" onclick="goLevel('module',${state.selectedBank},${state.selectedRack},${state.selectedString},${state.selectedModule})">Module</button></div>${body}</section>${sidePanel(site)}</div>`;
  } catch (error) { console.error('[monitor] renderDetail failed', error); showError('Site detail render failed.', error.stack || error.message); }
}
window.renderDetail = renderDetail;

function bindNav() {
  navItems.forEach((item) => item.addEventListener('click', () => nav(item.dataset.page)));
}

async function init() {
  try {
    if (!content) return;
    bindNav();
    await fetchJson(API.system, null);
    await renderDashboard();
  } catch (error) { showError('Initialization failed.', error.stack || error.message); }
}

document.addEventListener('DOMContentLoaded', init);
if (document.readyState !== 'loading') init();
'''

js_path.write_text(clean_js.strip() + '\n', encoding='utf-8')

# Append clean v26 CSS safely.
css_append = r'''

/* v26 clean UI refinements */
body{font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic","Segoe UI",Arial,sans-serif}.loading-panel{min-height:360px;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:12px}.loading-icon{font-size:32px;font-weight:900;color:var(--blue)}.error-panel{padding:24px}.error-panel pre{white-space:pre-wrap;background:#fff7f7;border:1px solid #fecaca;border-radius:12px;padding:14px;max-height:260px;overflow:auto}.muted-text{color:#738399;font-weight:700}.ranking-table td small,.data-table td small{display:block;margin-top:5px;color:#6b7a90;font-weight:700}.hero-icon.ai{font-size:28px;font-weight:950}.priority-panel .priority-list{padding-top:16px}.v26-priority{grid-template-columns:44px 1fr auto!important;cursor:pointer;border-radius:12px;padding:8px 10px}.v26-priority:hover{background:#f7fbff}.priority-reason.good{color:var(--green)}.priority-reason.warn{color:var(--orange)}.priority-reason.bad{color:var(--red)}.priority-reason.gray{color:#667085}.sites-page-wide{max-width:1800px}.site-summary-strip{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:18px}.site-summary-strip div{height:82px;border:1px solid var(--line);border-radius:16px;background:#fff;box-shadow:var(--soft);display:flex;align-items:center;justify-content:center;flex-direction:column}.site-summary-strip b{font-size:30px;font-weight:950}.site-summary-strip span{font-size:13px;color:#6b7a90;font-weight:800}.wide-site-table th,.wide-site-table td{white-space:nowrap}.wide-site-table td:first-child,.wide-site-table th:first-child{min-width:240px}.table-action{height:38px;border:1px solid #cfe0f5;border-radius:10px;background:#f7fbff;color:var(--blue);font-weight:900;padding:0 14px;cursor:pointer}.table-action:hover{background:#eaf4ff}.v26-detail-page{max-width:1880px;display:grid;grid-template-columns:300px minmax(0,1fr) 330px;gap:20px}.hierarchy-card.v26-tree-card{position:sticky;top:0;align-self:start;background:#fff;border:1px solid var(--line);border-radius:18px;box-shadow:var(--soft);padding:16px;max-height:calc(100vh - 165px);overflow:auto}.hierarchy-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;border-bottom:1px solid var(--line2);padding-bottom:12px;margin-bottom:10px}.hierarchy-head b{font-size:16px;cursor:pointer}.hierarchy-head span{display:block;font-size:12px;color:#6b7a90;font-weight:800;margin-top:5px}.hierarchy-head button{border:1px solid var(--line);background:#fff;border-radius:10px;height:34px;padding:0 10px;font-weight:900;color:#526177;cursor:pointer}.tree-site,.tree-row{width:100%;height:34px;border:0;background:transparent;border-radius:10px;text-align:left;display:flex;align-items:center;gap:8px;font-weight:850;color:#23344d;cursor:pointer;margin:2px 0;padding:0 8px}.tree-site:hover,.tree-row:hover{background:#f4f8ff}.tree-site.active,.tree-row.active{background:#eaf3ff;color:var(--blue);box-shadow:inset 0 0 0 1px #cfe2ff}.tree-bank{padding-left:8px}.tree-rack{padding-left:24px}.tree-string{padding-left:40px}.tree-module{padding-left:56px;font-size:13px}.tree-dot{width:10px;height:10px;display:inline-block;border-radius:50%;flex:0 0 10px;border:2px solid #fff;box-shadow:0 0 0 1px #d7dee8}.tree-dot.normal{background:var(--green)}.tree-dot.warning{background:var(--orange)}.tree-dot.abnormal{background:var(--red)}.tree-dot.offline{background:#98a2b3}.tree-legend{display:grid;grid-template-columns:1fr 1fr;gap:8px;border-top:1px solid var(--line2);margin-top:12px;padding-top:12px;font-size:12px;color:#667085;font-weight:800}.tree-legend span{display:flex;align-items:center;gap:6px}.v26-breadcrumb{display:flex;align-items:center;gap:8px;margin-bottom:14px;color:#738399;font-weight:850}.v26-breadcrumb button{border:0;background:transparent;color:var(--blue);font-weight:900;cursor:pointer;padding:0}.v26-title-row{margin-bottom:16px;background:#fff;border:1px solid var(--line);border-radius:18px;box-shadow:var(--soft);padding:22px;display:flex;align-items:center;gap:18px}.v26-title-row h1{margin:0;font-size:28px}.v26-title-row p{margin:6px 0 0;color:#6b7a90;font-weight:800}.v26-title-row .table-action{margin-left:auto}.level-tabs{margin-bottom:16px}.overview-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;padding:18px}.info-card{min-height:92px;border:1px solid var(--line2);border-radius:14px;background:#fbfdff;padding:16px;display:flex;flex-direction:column;gap:8px;justify-content:center}.info-card small{color:#6b7a90;font-weight:850}.info-card b{font-size:20px;word-break:break-word}.info-card em{font-style:normal;color:#6b7a90;font-size:12px;font-weight:800}.level-card-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;padding:18px}.level-card-grid.module-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.level-card-grid button{border:1px solid var(--line);background:#fff;border-radius:16px;box-shadow:var(--soft);min-height:118px;padding:18px;text-align:left;display:flex;flex-direction:column;gap:9px;cursor:pointer}.level-card-grid button:hover{border-color:#add0ff;background:#f8fbff}.level-card-grid button b{font-size:19px}.level-card-grid button span{color:#6b7a90;font-weight:800}.fixed-side-card{margin-bottom:16px}.advice-main{padding:20px;display:flex;flex-direction:column;gap:12px}.advice-main b{font-size:18px}.advice-main span{color:#6b7a90;font-weight:800}.advice-main.bad{color:var(--red);background:#fff7f7}.advice-main.warn{color:var(--orange);background:#fffaf0}.advice-main.good{color:var(--green);background:#f1fcf6}.advice-main.gray{color:#667085;background:#f6f7f9}.side-kv{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:13px 18px;border-bottom:1px solid var(--line2);font-weight:850}.side-kv span{color:#6b7a90}.v26-cell-map .cell{min-height:74px;display:flex;flex-direction:column;justify-content:center;gap:5px}.v26-cell-map .cell b{font-size:13px}.v26-cell-map .cell span{font-size:18px;font-weight:950}.cell.bad{background:var(--red-bg);border-color:#fecaca;color:#dc2626}.cell.warn{background:var(--orange-bg);border-color:#fde7b1;color:#c77b00}.cell.good{background:var(--green-bg);border-color:#cdeedc;color:#128a52}@media(max-width:1400px){.v26-detail-page{grid-template-columns:280px minmax(0,1fr)}.detail-right{grid-column:2}.overview-grid{grid-template-columns:repeat(2,1fr)}.level-card-grid{grid-template-columns:repeat(2,1fr)}}
'''
css_text = css_path.read_text(encoding='utf-8', errors='replace') if css_path.exists() else ''
if 'v26 clean UI refinements' not in css_text:
    css_path.write_text(css_text.rstrip() + css_append + '\n', encoding='utf-8')

# Cache bust index.html
if idx_path.exists():
    idx = idx_path.read_text(encoding='utf-8', errors='replace')
    idx = re.sub(r'/static/monitor/monitor\.css(?:\?v=\d+)?', '/static/monitor/monitor.css?v=26', idx)
    idx = re.sub(r'/static/monitor/monitor_v7_fix\.css(?:\?v=\d+)?', '/static/monitor/monitor_v7_fix.css?v=26', idx)
    idx = re.sub(r'/static/monitor/monitor\.js(?:\?v=\d+)?', '/static/monitor/monitor.js?v=26', idx)
    idx_path.write_text(idx, encoding='utf-8')

print('[v26] monitor.js clean rebuild complete')
print('[v26] backup:', bak)
print('[v26] cache version updated to v26')
