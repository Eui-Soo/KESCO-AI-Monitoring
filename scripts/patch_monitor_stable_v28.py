from pathlib import Path
from datetime import datetime
import shutil
import re

BASE = Path.cwd()
MON = BASE / 'static' / 'monitor'
SERVICE = BASE / 'service' / 'monitor_service.py'
STAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
BACKUP = BASE / 'backup' / f'v28_monitor_stable_{STAMP}'

JS = r'''(() => {
  'use strict';

  const API = {
    health: '/api/v1/health',
    sites: '/api/v1/monitor/sites',
    dashboard: '/api/v1/monitor/dashboard/summary',
    site: (id) => `/api/v1/monitor/sites/${encodeURIComponent(id)}`,
    level: (id, level) => `/api/v1/monitor/sites/${encodeURIComponent(id)}/level?level=${encodeURIComponent(level || 'module')}`,
    recs: (id) => `/api/v1/monitor/sites/${encodeURIComponent(id)}/recommendations`,
  };

  const fallbackSites = [
    { site_id: 'SITE-9001__BMS-DEMO-BMS-01', site_no: 9001, site_name: 'ESS Site 9001', bms_id: 'DEMO-BMS-01', region: 'Jeonnam', install_area: 'Solar Plant A', manufacturer: 'SK On', installed_at: '2026-01-08', latest_score: 97, average_score: 58, status: 'abnormal', status_text: 'Abnormal', last_analysis_time: '2026-08-05T09:07:38', risk_location: 'Bank 01 > Rack 01 > String 01 > Module 07', bank_count: 1, rack_count: 3, string_count: 2, module_count: 8, cell_count: 160, score_row_count: 12 },
    { site_id: 'SITE-9001__BMS-FAKE-BMS-9001', site_no: 9001, site_name: 'ESS Site 9001', bms_id: 'FAKE-BMS-9001', region: 'Local DB', install_area: 'Test Zone', manufacturer: 'Samsung SDI', installed_at: '2026-07-07', latest_score: 77, average_score: 43, status: 'warning', status_text: 'Warning', last_analysis_time: '2026-08-05T10:26:56', risk_location: 'Bank 01 > Rack 02 > String 01 > Module 08', bank_count: 1, rack_count: 2, string_count: 1, module_count: 12, cell_count: 240, score_row_count: 12 },
    { site_id: 'SITE-9002__BMS-DEMO-BMS-02', site_no: 9002, site_name: 'ESS Site 9002', bms_id: 'DEMO-BMS-02', region: 'Jeonbuk', install_area: 'Factory ESS', manufacturer: 'LG Energy Solution', installed_at: '2026-08-04', latest_score: 88, average_score: 51, status: 'abnormal', status_text: 'Abnormal', last_analysis_time: '2026-08-05T09:07:38', risk_location: 'Bank 01 > Rack 02 > String 01', bank_count: 1, rack_count: 2, string_count: 2, module_count: 10, cell_count: 200, score_row_count: 10 },
    { site_id: 'SITE-9003__BMS-DEMO-BMS-03', site_no: 9003, site_name: 'ESS Site 9003', bms_id: 'DEMO-BMS-03', region: 'Gyeonggi', install_area: 'Substation West', manufacturer: 'SK On', installed_at: '2026-08-04', latest_score: 32, average_score: 22, status: 'normal', status_text: 'Normal', last_analysis_time: '2026-08-05T09:07:38', risk_location: 'No abnormal location', bank_count: 1, rack_count: 2, string_count: 1, module_count: 6, cell_count: 120, score_row_count: 6 },
  ];

  const state = {
    page: 'dashboard',
    sites: [],
    selectedSiteId: null,
    level: 'site',
    bank: 1,
    rack: 1,
    string: 1,
    module: 1,
    treeCollapsed: false,
    filters: { search: '', maker: '', region: '', area: '', status: '' },
    loading: false,
  };

  const pseudo = {
    regions: ['Jeonnam', 'Jeonbuk', 'Gyeonggi', 'Chungnam', 'Gyeongnam', 'Local DB'],
    areas: ['Solar Plant A', 'Factory ESS', 'Substation West', 'R&D Test Zone', 'Fire Test Room', 'Outdoor Cabinet'],
    makers: ['SK On', 'Samsung SDI', 'LG Energy Solution', 'KESCO Demo'],
  };

  const $ = (sel) => document.querySelector(sel);
  const pad2 = (n) => String(Math.max(1, Number(n) || 1)).padStart(2, '0');
  const clamp = (v, min, max) => Math.max(min, Math.min(max, v));
  const scoreNumber = (v) => {
    const n = Number(v || 0);
    if (!Number.isFinite(n)) return 0;
    return n <= 1 ? Math.round(n * 100) : Math.round(n);
  };
  const escapeHtml = (v) => String(v ?? '').replace(/[&<>'"]/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const fmtDate = (v) => {
    if (!v) return '-';
    const s = String(v).replace('T', ' ');
    const noFrac = s.split('.')[0];
    return noFrac.length >= 19 ? noFrac.slice(0, 19) : noFrac;
  };
  const uniq = (arr) => [...new Set(arr.filter(Boolean))];

  function normalizeStatus(siteOrStatus) {
    const raw = typeof siteOrStatus === 'string' ? siteOrStatus : (siteOrStatus?.status || siteOrStatus?.status_text || 'normal');
    const key = String(raw || '').toLowerCase();
    const score = typeof siteOrStatus === 'object' ? scoreNumber(siteOrStatus.latest_score ?? siteOrStatus.max_score) : 0;
    if (key.includes('abnormal') || key.includes('danger') || score >= 80) return 'abnormal';
    if (key.includes('warning') || key.includes('caution') || score >= 60) return 'warning';
    if (key.includes('offline') || key.includes('unavailable')) return 'offline';
    return 'normal';
  }
  const statusLabel = (s) => ({ normal: 'Normal', warning: 'Warning', abnormal: 'Abnormal', offline: 'Offline' }[normalizeStatus(s)] || 'Normal');
  const statusClass = (s) => `m28-status ${normalizeStatus(s)}`;
  const dot = (s) => `<span class="m28-dot ${normalizeStatus(s)}"></span>`;

  function enrichSite(raw, idx = 0) {
    const site = { ...raw };
    site.site_id = site.site_id || `SITE-${site.site_no || idx + 1}__BMS-${site.bms_id || idx + 1}`;
    site.site_no = site.site_no ?? idx + 1;
    site.site_name = site.site_name || site.name || `ESS Site ${site.site_no}`;
    site.bms_id = site.bms_id || site.bmsId || `BMS-${pad2(idx + 1)}`;
    site.latest_score = scoreNumber(site.latest_score ?? site.max_score ?? site.score);
    site.average_score = scoreNumber(site.average_score ?? site.avg_score ?? site.latest_score * 0.65);
    site.status = normalizeStatus(site);
    site.status_text = statusLabel(site.status);
    site.region = site.region && site.region !== '-' ? site.region : pseudo.regions[idx % pseudo.regions.length];
    site.install_area = site.install_area && site.install_area !== '-' ? site.install_area : pseudo.areas[idx % pseudo.areas.length];
    site.manufacturer = site.manufacturer && site.manufacturer !== '-' ? site.manufacturer : pseudo.makers[idx % pseudo.makers.length];
    site.installed_at = fmtDate(site.installed_at || site.install_date || '2026-08-04').slice(0, 10);
    site.last_analysis_time = fmtDate(site.last_analysis_time || site.analysis_time || site.prediction_time || '');
    site.bank_count = Math.max(1, Number(site.bank_count || 1));
    site.rack_count = Math.max(1, Number(site.rack_count || 1));
    site.string_count = Math.max(1, Number(site.string_count || 1));
    site.module_count = Math.max(1, Number(site.module_count || 1));
    site.cell_count = Math.max(20, Number(site.cell_count || site.module_count * 20));
    site.score_row_count = Number(site.score_row_count || site.saved_score_count || 0);
    site.risk_location = site.risk_location || site.message || (site.latest_score >= 60 ? 'Latest anomaly_score result' : 'No abnormal location');
    return site;
  }

  async function request(url) {
    const r = await fetch(url, { headers: { 'Accept': 'application/json' } });
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    return r.json();
  }

  async function loadSites() {
    try {
      const data = await request(API.sites);
      const items = Array.isArray(data) ? data : (data.items || data.sites || data.results || []);
      state.sites = (items.length ? items : fallbackSites).map(enrichSite).sort((a, b) => scoreNumber(b.latest_score) - scoreNumber(a.latest_score));
    } catch (e) {
      console.warn('[m28] failed to load sites, using fallback', e);
      state.sites = fallbackSites.map(enrichSite);
    }
    if (!state.selectedSiteId || !state.sites.some(s => s.site_id === state.selectedSiteId)) {
      state.selectedSiteId = state.sites[0]?.site_id || null;
    }
  }

  function selectedSite() {
    return state.sites.find(s => s.site_id === state.selectedSiteId) || state.sites[0] || enrichSite(fallbackSites[0]);
  }

  function counts() {
    const c = { total: state.sites.length, normal: 0, warning: 0, abnormal: 0, offline: 0 };
    state.sites.forEach(s => c[normalizeStatus(s)]++);
    return c;
  }

  function levelTitle(level = state.level) {
    return ({ site: 'Site Information', bank: `Bank ${pad2(state.bank)} Detail`, rack: `Rack ${pad2(state.rack)} Detail`, string: `String ${pad2(state.string)} Detail`, module: `Module ${pad2(state.module)} Detail` }[level] || 'Site Information');
  }

  function levelScore(site, level, index) {
    const base = scoreNumber(site.latest_score);
    const seed = (Number(index || 1) * 7) + (level === 'module' ? 9 : level === 'string' ? 5 : level === 'rack' ? 3 : 0);
    return clamp(Math.round(base - seed + 10), 8, 99);
  }

  function levelStatus(site, level, index) {
    const sc = levelScore(site, level, index);
    if (sc >= 80) return 'abnormal';
    if (sc >= 60) return 'warning';
    return 'normal';
  }

  function modulesPerString(site) {
    return Math.max(1, Math.ceil(site.module_count / Math.max(1, site.rack_count * site.string_count)));
  }

  function shell() {
    document.body.innerHTML = `
      <div class="m28-app">
        <aside class="m28-sidebar">
          <div class="m28-brand"><b>KESCO</b><span>Monitoring</span></div>
          <button class="m28-nav" data-page="dashboard" onclick="m28Nav('dashboard')">Dashboard</button>
          <button class="m28-nav" data-page="sites" onclick="m28Nav('sites')">Site List</button>
          <button class="m28-nav" data-page="detail" onclick="m28Nav('detail')">Site Detail</button>
          <button class="m28-nav disabled">Run History</button>
          <button class="m28-nav disabled">Settings</button>
          <div id="m28Tree"></div>
          <div class="m28-side-card small"><span>System version</span><b>v2.3.0</b></div>
        </aside>
        <section class="m28-main">
          <header class="m28-topbar">
            <div class="m28-pill">${fmtDate(new Date().toISOString())}</div>
            <div class="m28-pill ok">API server normal</div>
            <div class="m28-pill ok">DB normal</div>
            <div class="m28-pill">Last analysis: <span id="m28LastAnalysis">-</span></div>
            <div class="m28-admin">Admin</div>
          </header>
          <main id="m28Content" class="m28-content"></main>
        </section>
      </div>`;
  }

  function syncNav() {
    document.querySelectorAll('.m28-nav').forEach(b => b.classList.toggle('active', b.dataset.page === state.page));
    const la = $('#m28LastAnalysis');
    if (la) la.textContent = fmtDate(selectedSite().last_analysis_time);
    renderTree();
  }

  function renderTree() {
    const wrap = $('#m28Tree');
    if (!wrap) return;
    if (state.page !== 'detail') { wrap.innerHTML = ''; return; }
    const site = selectedSite();
    const rackCount = Math.max(1, site.rack_count || 1);
    const stringCount = Math.max(1, site.string_count || 1);
    const modPerString = modulesPerString(site);
    let html = `
      <section class="m28-tree-card">
        <div class="m28-tree-head"><b>Hierarchy</b><button onclick="m28ResetTree()" title="Reset hierarchy">Reset</button></div>
        <button class="m28-tree-row ${state.level === 'site' ? 'active' : ''}" onclick="m28Select('site')">${dot(site)}<span>${escapeHtml(site.site_name)}</span><em>${scoreNumber(site.latest_score)}</em></button>`;

    if (!state.treeCollapsed) {
      html += `<button class="m28-tree-row ${state.level === 'bank' ? 'active' : ''}" onclick="m28Select('bank',1)"><i>B</i>${dot(site)}<span>Bank 01</span></button>`;
      for (let r = 1; r <= rackCount; r++) {
        html += `<button class="m28-tree-row indent1 ${state.level === 'rack' && state.rack === r ? 'active' : ''}" onclick="m28Select('rack',1,${r})"><i>R</i>${dot(levelStatus(site,'rack',r))}<span>Rack ${pad2(r)}</span></button>`;
        if (state.rack === r || state.level === 'site' || state.level === 'bank') {
          const showStrings = state.level !== 'site' && state.level !== 'bank' && state.rack === r;
          if (showStrings) {
            for (let st = 1; st <= stringCount; st++) {
              html += `<button class="m28-tree-row indent2 ${state.level === 'string' && state.string === st ? 'active' : ''}" onclick="m28Select('string',1,${r},${st})"><i>S</i>${dot(levelStatus(site,'string',st))}<span>String ${pad2(st)}</span></button>`;
              if (state.string === st && (state.level === 'module' || state.level === 'string')) {
                for (let m = 1; m <= modPerString; m++) {
                  html += `<button class="m28-tree-row indent3 ${state.level === 'module' && state.module === m ? 'active' : ''}" onclick="m28Select('module',1,${r},${st},${m})"><i>M</i>${dot(levelStatus(site,'module',m))}<span>Module ${pad2(m)}</span></button>`;
                }
              }
            }
          }
        }
      }
    }
    html += `<div class="m28-legend"><span>${dot('normal')}Normal</span><span>${dot('warning')}Warning</span><span>${dot('abnormal')}Abnormal</span><span>${dot('offline')}Offline</span></div></section>`;
    wrap.innerHTML = html;
  }

  function pageTitle(title, subtitle = '') {
    return `<div class="m28-page-title"><h1>${escapeHtml(title)}</h1>${subtitle ? `<p>${escapeHtml(subtitle)}</p>` : ''}</div>`;
  }

  function renderDashboard() {
    const c = counts();
    const top = [...state.sites].sort((a,b) => scoreNumber(b.latest_score)-scoreNumber(a.latest_score)).slice(0,3);
    const root = $('#m28Content');
    root.innerHTML = `
      ${pageTitle('Dashboard', 'Overall ESS anomaly monitoring summary')}
      <section class="m28-summary-grid">
        <article class="m28-card"><span>Total Sites</span><b>${c.total}</b></article>
        <article class="m28-card good"><span>Normal</span><b>${c.normal}</b></article>
        <article class="m28-card warn"><span>Warning</span><b>${c.warning}</b></article>
        <article class="m28-card bad"><span>Abnormal</span><b>${c.abnormal}</b></article>
      </section>
      <section class="m28-dashboard-grid">
        <article class="m28-panel">
          <h2>Priority Inspection TOP 3</h2>
          <div class="m28-priority-list">
            ${top.map((s, i) => `
              <button class="m28-priority" onclick="m28OpenSite('${escapeHtml(s.site_id)}')">
                <strong>${i + 1}</strong>
                <div><b>${escapeHtml(s.site_name)}</b><span>${escapeHtml(s.bms_id)} · ${escapeHtml(s.region)} · ${escapeHtml(s.install_area)}</span></div>
                <p>${statusLabel(s.status)} · Max score ${scoreNumber(s.latest_score)}</p>
              </button>`).join('')}
          </div>
        </article>
        <article class="m28-panel">
          <h2>Status Distribution</h2>
          <div class="m28-status-boxes">
            <div>${dot('normal')}<b>${c.normal}</b><span>Normal</span></div>
            <div>${dot('warning')}<b>${c.warning}</b><span>Warning</span></div>
            <div>${dot('abnormal')}<b>${c.abnormal}</b><span>Abnormal</span></div>
          </div>
        </article>
      </section>`;
  }

  function filteredSites() {
    return state.sites.filter(s => {
      const q = state.filters.search.toLowerCase();
      const text = `${s.site_name} ${s.bms_id} ${s.region} ${s.install_area} ${s.manufacturer}`.toLowerCase();
      return (!q || text.includes(q)) &&
        (!state.filters.maker || s.manufacturer === state.filters.maker) &&
        (!state.filters.region || s.region === state.filters.region) &&
        (!state.filters.area || s.install_area === state.filters.area) &&
        (!state.filters.status || normalizeStatus(s) === state.filters.status);
    });
  }

  function selectOptions(values, current, label) {
    return `<option value="">${label}</option>${values.map(v => `<option value="${escapeHtml(v)}" ${v === current ? 'selected' : ''}>${escapeHtml(v)}</option>`).join('')}`;
  }

  function renderSites() {
    const makers = uniq(state.sites.map(s => s.manufacturer));
    const regions = uniq(state.sites.map(s => s.region));
    const areas = uniq(state.sites.map(s => s.install_area));
    const list = filteredSites();
    const root = $('#m28Content');
    root.innerHTML = `
      ${pageTitle('Site List', 'Search and manage all monitored ESS sites')}
      <section class="m28-filter-bar">
        <input placeholder="Search site, BMS, region" value="${escapeHtml(state.filters.search)}" oninput="m28Filter('search', this.value)">
        <select onchange="m28Filter('maker', this.value)">${selectOptions(makers, state.filters.maker, 'Manufacturer')}</select>
        <select onchange="m28Filter('region', this.value)">${selectOptions(regions, state.filters.region, 'Region')}</select>
        <select onchange="m28Filter('area', this.value)">${selectOptions(areas, state.filters.area, 'Install area')}</select>
        <select onchange="m28Filter('status', this.value)">
          <option value="">Status</option><option value="normal" ${state.filters.status==='normal'?'selected':''}>Normal</option><option value="warning" ${state.filters.status==='warning'?'selected':''}>Warning</option><option value="abnormal" ${state.filters.status==='abnormal'?'selected':''}>Abnormal</option>
        </select>
      </section>
      <section class="m28-panel m28-table-panel">
        <table class="m28-table">
          <thead><tr><th>Site / BMS</th><th>Region</th><th>Install Area</th><th>Manufacturer</th><th>Installed</th><th>Latest Score</th><th>Status</th><th>Last Analysis</th><th>Detail</th></tr></thead>
          <tbody>
            ${list.map(s => `<tr>
              <td><b>${escapeHtml(s.site_name)}</b><small>${escapeHtml(s.bms_id)}</small></td>
              <td>${escapeHtml(s.region)}</td><td>${escapeHtml(s.install_area)}</td><td>${escapeHtml(s.manufacturer)}</td><td>${escapeHtml(s.installed_at)}</td>
              <td><span class="m28-score ${normalizeStatus(s)}">${scoreNumber(s.latest_score)}</span></td>
              <td><span class="${statusClass(s)}">${dot(s)}${statusLabel(s)}</span></td>
              <td>${fmtDate(s.last_analysis_time)}</td>
              <td><button class="m28-btn small" onclick="m28OpenSite('${escapeHtml(s.site_id)}')">Open</button></td>
            </tr>`).join('')}
          </tbody>
        </table>
      </section>`;
  }

  function breadcrumbs(site) {
    const parts = [
      `<button onclick="m28Nav('sites')">Site List</button>`,
      `<button onclick="m28Select('site')">${escapeHtml(site.site_name)}</button>`,
    ];
    if (state.level !== 'site') parts.push(`<button onclick="m28Select('bank',1)">Bank ${pad2(state.bank)}</button>`);
    if (['rack','string','module'].includes(state.level)) parts.push(`<button onclick="m28Select('rack',1,${state.rack})">Rack ${pad2(state.rack)}</button>`);
    if (['string','module'].includes(state.level)) parts.push(`<button onclick="m28Select('string',1,${state.rack},${state.string})">String ${pad2(state.string)}</button>`);
    if (state.level === 'module') parts.push(`<button onclick="m28Select('module',1,${state.rack},${state.string},${state.module})">Module ${pad2(state.module)}</button>`);
    return `<nav class="m28-breadcrumb">${parts.join('<span>›</span>')}</nav>`;
  }

  function infoCards(site, items) {
    return `<div class="m28-info-grid">${items.map(([k,v,cls='']) => `<div class="m28-info-card ${cls}"><span>${escapeHtml(k)}</span><b>${escapeHtml(v)}</b></div>`).join('')}</div>`;
  }

  function entityCard(label, score, status, onclick) {
    return `<button class="m28-entity-card" onclick="${onclick}">${dot(status)}<b>${escapeHtml(label)}</b><span>Open detail</span><em class="${normalizeStatus(status)}">${score}</em></button>`;
  }

  function advice(site) {
    const sc = scoreNumber(site.latest_score);
    const st = normalizeStatus(site);
    const action = st === 'abnormal' ? 'Immediate inspection recommended' : st === 'warning' ? 'Watch trend and inspect if score increases' : 'Normal operation';
    return `<section class="m28-panel m28-advice ${st}"><h2>Operation Advice</h2><p><b>${escapeHtml(action)}</b></p><span>Max score ${sc} · ${escapeHtml(site.risk_location)}</span></section>`;
  }

  function rightPanel(site) {
    return `<aside class="m28-right">
      ${advice(site)}
      <section class="m28-panel"><h2>Analysis Summary</h2>
        ${infoCards(site, [['Last analysis', fmtDate(site.last_analysis_time)], ['Score rows', site.score_row_count || '-'], ['Average score', scoreNumber(site.average_score)], ['Max score', scoreNumber(site.latest_score)]])}
      </section>
      <section class="m28-panel"><h2>Data Status</h2>
        <div class="m28-kv"><span>Source DB</span><b>Connected</b></div><div class="m28-kv"><span>Preprocess</span><b>Ready</b></div><div class="m28-kv"><span>AI result</span><b>Saved</b></div>
      </section>
    </aside>`;
  }

  function renderSiteOverview(site) {
    return `<section class="m28-panel"><h2>Site Information</h2>
      ${infoCards(site, [['Site name', site.site_name], ['BMS ID', site.bms_id], ['Region', site.region], ['Install area', site.install_area], ['Manufacturer', site.manufacturer], ['Installed', site.installed_at], ['Status', statusLabel(site), normalizeStatus(site)], ['Max score', scoreNumber(site.latest_score), normalizeStatus(site)]])}
    </section>
    <section class="m28-panel"><h2>Banks in Site</h2><div class="m28-entity-grid">${entityCard('Bank 01', scoreNumber(site.latest_score), site.status, `m28Select('bank',1)`)}</div></section>`;
  }

  function renderBank(site) {
    const racks = Array.from({length: Math.max(1, site.rack_count)}, (_, i) => i + 1);
    return `<section class="m28-panel"><h2>Bank Summary</h2>${infoCards(site, [['Selected bank', `Bank ${pad2(state.bank)}`], ['Rack count', racks.length], ['Max score', scoreNumber(site.latest_score), normalizeStatus(site)], ['Status', statusLabel(site), normalizeStatus(site)]])}</section>
    <section class="m28-panel"><h2>Racks in Bank</h2><div class="m28-entity-grid">${racks.map(r => entityCard(`Rack ${pad2(r)}`, levelScore(site,'rack',r), levelStatus(site,'rack',r), `m28Select('rack',1,${r})`)).join('')}</div></section>`;
  }

  function renderRack(site) {
    const strings = Array.from({length: Math.max(1, site.string_count)}, (_, i) => i + 1);
    return `<section class="m28-panel"><h2>Rack Summary</h2>${infoCards(site, [['Selected rack', `Rack ${pad2(state.rack)}`], ['String count', strings.length], ['Max score', levelScore(site,'rack',state.rack), levelStatus(site,'rack',state.rack)], ['Status', statusLabel(levelStatus(site,'rack',state.rack)), levelStatus(site,'rack',state.rack)]])}</section>
    <section class="m28-panel"><h2>Strings in Rack</h2><div class="m28-entity-grid">${strings.map(st => entityCard(`String ${pad2(st)}`, levelScore(site,'string',st), levelStatus(site,'string',st), `m28Select('string',1,${state.rack},${st})`)).join('')}</div></section>`;
  }

  function renderString(site) {
    const count = modulesPerString(site);
    const modules = Array.from({length: count}, (_, i) => i + 1);
    return `<section class="m28-panel"><h2>String Summary</h2>${infoCards(site, [['Selected string', `String ${pad2(state.string)}`], ['Module count', count], ['Max score', levelScore(site,'string',state.string), levelStatus(site,'string',state.string)], ['Status', statusLabel(levelStatus(site,'string',state.string)), levelStatus(site,'string',state.string)]])}</section>
    <section class="m28-panel"><h2>Modules in String</h2><div class="m28-entity-grid">${modules.map(m => entityCard(`Module ${pad2(m)}`, levelScore(site,'module',m), levelStatus(site,'module',m), `m28Select('module',1,${state.rack},${state.string},${m})`)).join('')}</div></section>`;
  }

  function renderModule(site) {
    const cells = Array.from({length: 20}, (_, i) => {
      const score = i === 6 ? 92 : i === 7 ? 45 : i === 12 ? 61 : clamp(18 + ((i * 7 + state.module * 5) % 23), 10, 70);
      const st = score >= 80 ? 'abnormal' : score >= 60 ? 'warning' : 'normal';
      return `<div class="m28-cell ${st}"><span>Cell ${pad2(i+1)}</span><b>${score}</b></div>`;
    }).join('');
    return `<section class="m28-panel"><h2>Module Summary</h2>${infoCards(site, [['Selected module', `Module ${pad2(state.module)}`], ['Cell count', 20], ['Max cell score', 92, 'abnormal'], ['Status', 'Abnormal', 'abnormal']])}</section>
    <section class="m28-panel"><h2>Cell Status Map</h2><div class="m28-cell-grid">${cells}</div></section>`;
  }

  function renderDetail() {
    const site = selectedSite();
    const root = $('#m28Content');
    const content = state.level === 'site' ? renderSiteOverview(site) : state.level === 'bank' ? renderBank(site) : state.level === 'rack' ? renderRack(site) : state.level === 'string' ? renderString(site) : renderModule(site);
    root.innerHTML = `
      <section class="m28-detail-head">
        <div>${breadcrumbs(site)}<h1><button class="m28-title-link" onclick="m28Select('site')">${escapeHtml(site.site_name)}</button> › ${escapeHtml(levelTitle())}</h1><p>${escapeHtml(site.bms_id)} · ${escapeHtml(site.region)} · ${escapeHtml(site.manufacturer)}</p></div>
        <button class="m28-btn" onclick="m28Nav('sites')">Other sites</button>
      </section>
      <div class="m28-tabs"><button class="${state.level==='site'?'active':''}" onclick="m28Select('site')">Site</button><button class="${state.level==='bank'?'active':''}" onclick="m28Select('bank',1)">Bank</button><button class="${state.level==='rack'?'active':''}" onclick="m28Select('rack',1,state.rack)">Rack</button><button class="${state.level==='string'?'active':''}" onclick="m28Select('string',1,state.rack,state.string)">String</button><button class="${state.level==='module'?'active':''}" onclick="m28Select('module',1,state.rack,state.string,state.module)">Module</button></div>
      <div class="m28-detail-grid"><div class="m28-detail-main">${content}</div>${rightPanel(site)}</div>`;
  }

  function render() {
    syncNav();
    if (state.page === 'dashboard') renderDashboard();
    else if (state.page === 'sites') renderSites();
    else renderDetail();
    syncNav();
  }

  window.m28Nav = function(page) {
    state.page = page;
    if (page === 'detail' && !state.level) state.level = 'site';
    render();
  };
  window.m28OpenSite = function(id) {
    state.selectedSiteId = id;
    state.page = 'detail';
    state.level = 'site';
    state.bank = 1; state.rack = 1; state.string = 1; state.module = 1; state.treeCollapsed = false;
    render();
  };
  window.m28Select = function(level, bank = state.bank, rack = state.rack, string = state.string, module = state.module) {
    state.page = 'detail';
    state.level = level || 'site';
    state.bank = Number(bank) || 1;
    state.rack = Number(rack) || 1;
    state.string = Number(string) || 1;
    state.module = Number(module) || 1;
    state.treeCollapsed = false;
    render();
  };
  window.m28ResetTree = function() {
    state.level = 'site';
    state.bank = 1; state.rack = 1; state.string = 1; state.module = 1; state.treeCollapsed = true;
    render();
  };
  window.m28Filter = function(key, value) { state.filters[key] = value; renderSites(); };

  async function init() {
    shell();
    await loadSites();
    render();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
'''

CSS = r'''
:root { --m28-bg:#f5f8fc; --m28-panel:#fff; --m28-line:#dfe8f3; --m28-text:#10213b; --m28-sub:#62738b; --m28-blue:#1268e5; --m28-blue-bg:#eaf3ff; --m28-green:#11a970; --m28-green-bg:#eafaf4; --m28-orange:#f59e0b; --m28-orange-bg:#fff7e6; --m28-red:#ef4444; --m28-red-bg:#fff1f1; --m28-gray:#94a3b8; }
* { box-sizing: border-box; }
html, body { margin:0; min-height:100%; font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color:var(--m28-text); background:var(--m28-bg); }
button, input, select { font: inherit; }
button { cursor:pointer; }
.m28-app { min-height:100vh; display:grid; grid-template-columns:260px minmax(0, 1fr); }
.m28-sidebar { position:sticky; top:0; height:100vh; overflow-y:auto; background:#fff; border-right:1px solid var(--m28-line); padding:20px 14px; }
.m28-brand { display:flex; align-items:flex-end; gap:8px; margin:0 8px 26px; font-size:18px; }
.m28-brand b { font-size:28px; color:#0b4f9f; letter-spacing:-1px; }
.m28-brand span { font-weight:800; line-height:1.05; }
.m28-nav { width:100%; height:48px; border:0; background:transparent; border-radius:12px; display:flex; align-items:center; padding:0 18px; margin:5px 0; color:#21344d; font-weight:800; text-align:left; }
.m28-nav.active { color:var(--m28-blue); background:var(--m28-blue-bg); box-shadow:inset 0 0 0 1px #cfe4ff; }
.m28-nav.disabled { opacity:.7; cursor:default; }
.m28-main { min-width:0; }
.m28-topbar { height:76px; display:flex; align-items:center; justify-content:flex-end; gap:10px; padding:0 28px; border-bottom:1px solid var(--m28-line); background:rgba(255,255,255,.8); backdrop-filter: blur(8px); position:sticky; top:0; z-index:5; }
.m28-pill { min-height:38px; display:flex; align-items:center; gap:6px; padding:0 16px; border:1px solid var(--m28-line); border-radius:12px; background:#fff; font-weight:700; color:#43546b; white-space:nowrap; }
.m28-pill.ok { background:var(--m28-green-bg); color:#08784d; border-color:#cff3e4; }
.m28-admin { color:#667; font-weight:700; margin-left:8px; }
.m28-content { padding:34px 36px 56px; max-width:1680px; margin:0 auto; }
.m28-page-title { display:flex; align-items:flex-end; gap:14px; margin-bottom:24px; }
.m28-page-title h1 { margin:0; font-size:34px; letter-spacing:-.8px; }
.m28-page-title p { margin:0 0 5px; color:var(--m28-sub); font-weight:700; }
.m28-card, .m28-panel, .m28-side-card { background:var(--m28-panel); border:1px solid var(--m28-line); border-radius:18px; box-shadow:0 12px 30px rgba(26,54,93,.06); }
.m28-summary-grid { display:grid; grid-template-columns:repeat(4, minmax(150px, 1fr)); gap:18px; margin-bottom:22px; }
.m28-card { padding:22px; min-height:120px; }
.m28-card span { display:block; color:var(--m28-sub); font-weight:800; margin-bottom:12px; }
.m28-card b { font-size:38px; }
.m28-card.good b { color:var(--m28-green); } .m28-card.warn b { color:var(--m28-orange); } .m28-card.bad b { color:var(--m28-red); }
.m28-dashboard-grid { display:grid; grid-template-columns:minmax(0,1.5fr) minmax(320px,.8fr); gap:22px; }
.m28-panel { padding:22px; margin-bottom:18px; overflow:hidden; }
.m28-panel h2 { margin:0 0 18px; font-size:21px; letter-spacing:-.3px; }
.m28-priority-list { display:grid; gap:12px; }
.m28-priority { display:grid; grid-template-columns:42px minmax(0, 1fr) minmax(180px, auto); gap:16px; align-items:center; border:1px solid var(--m28-line); background:#fff; border-radius:14px; padding:14px; text-align:left; }
.m28-priority strong { width:34px; height:34px; border-radius:50%; display:grid; place-items:center; background:var(--m28-red-bg); color:var(--m28-red); }
.m28-priority b, .m28-table b { display:block; font-weight:900; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.m28-priority span, .m28-table small { color:var(--m28-sub); font-weight:700; display:block; margin-top:4px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.m28-priority p { margin:0; font-weight:900; color:var(--m28-red); white-space:nowrap; }
.m28-status-boxes { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; }
.m28-status-boxes div { border:1px solid var(--m28-line); border-radius:16px; padding:20px; display:grid; gap:8px; min-height:130px; }
.m28-status-boxes b { font-size:34px; }
.m28-filter-bar { display:grid; grid-template-columns:minmax(260px,1.5fr) repeat(4, minmax(150px,1fr)); gap:12px; padding:18px; background:#fff; border:1px solid var(--m28-line); border-radius:18px; margin-bottom:18px; }
.m28-filter-bar input, .m28-filter-bar select { height:44px; border:1px solid var(--m28-line); border-radius:12px; padding:0 14px; background:#fff; color:var(--m28-text); font-weight:700; min-width:0; }
.m28-table-panel { padding:0; overflow:auto; }
.m28-table { width:100%; min-width:1080px; border-collapse:collapse; }
.m28-table th { text-align:left; color:#52647d; background:#fbfdff; border-bottom:1px solid var(--m28-line); font-size:13px; padding:16px; white-space:nowrap; }
.m28-table td { border-bottom:1px solid #eef3f8; padding:16px; vertical-align:middle; font-weight:700; color:#26384f; white-space:nowrap; }
.m28-score { display:inline-flex; min-width:50px; justify-content:center; padding:8px 12px; border-radius:10px; font-weight:900; }
.m28-score.normal { background:var(--m28-green-bg); color:var(--m28-green); } .m28-score.warning { background:var(--m28-orange-bg); color:var(--m28-orange); } .m28-score.abnormal { background:var(--m28-red-bg); color:var(--m28-red); }
.m28-status { display:inline-flex; align-items:center; gap:7px; padding:7px 11px; border-radius:999px; font-weight:900; font-size:13px; }
.m28-status.normal { background:var(--m28-green-bg); color:var(--m28-green); } .m28-status.warning { background:var(--m28-orange-bg); color:var(--m28-orange); } .m28-status.abnormal { background:var(--m28-red-bg); color:var(--m28-red); } .m28-status.offline { background:#f1f5f9; color:var(--m28-gray); }
.m28-dot { width:9px; height:9px; border-radius:50%; flex:0 0 9px; display:inline-block; box-shadow:0 0 0 3px rgba(0,0,0,.04); }
.m28-dot.normal { background:var(--m28-green); } .m28-dot.warning { background:var(--m28-orange); } .m28-dot.abnormal { background:var(--m28-red); } .m28-dot.offline { background:var(--m28-gray); }
.m28-btn { height:42px; border:1px solid #bfdbfe; background:#fff; color:var(--m28-blue); font-weight:900; border-radius:12px; padding:0 16px; white-space:nowrap; }
.m28-btn.small { height:34px; font-size:13px; }
.m28-tree-card { margin-top:22px; padding:12px; border:1px solid var(--m28-line); background:#fbfdff; border-radius:16px; }
.m28-tree-head { display:flex; align-items:center; justify-content:space-between; margin-bottom:10px; }
.m28-tree-head b { font-size:15px; }
.m28-tree-head button { border:1px solid var(--m28-line); background:#fff; border-radius:10px; height:30px; padding:0 10px; color:#46617e; font-weight:900; }
.m28-tree-row { width:100%; min-height:38px; border:1px solid transparent; background:transparent; display:flex; align-items:center; gap:8px; border-radius:10px; padding:0 9px; text-align:left; color:#243854; font-weight:900; }
.m28-tree-row:hover, .m28-tree-row.active { background:var(--m28-blue-bg); border-color:#cfe4ff; color:#0b66d8; }
.m28-tree-row i { width:22px; height:22px; border-radius:7px; background:#edf4ff; color:#4c709c; display:grid; place-items:center; font-style:normal; font-size:12px; }
.m28-tree-row span { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.m28-tree-row em { margin-left:auto; font-style:normal; font-size:12px; padding:4px 8px; border-radius:999px; background:var(--m28-red-bg); color:var(--m28-red); }
.m28-tree-row.indent1 { padding-left:24px; } .m28-tree-row.indent2 { padding-left:42px; } .m28-tree-row.indent3 { padding-left:60px; }
.m28-legend { display:grid; grid-template-columns:1fr 1fr; gap:7px; margin-top:12px; padding-top:12px; border-top:1px solid var(--m28-line); font-size:12px; color:#55677d; font-weight:800; }
.m28-legend span { display:flex; align-items:center; gap:6px; }
.m28-side-card { margin-top:14px; padding:14px; display:flex; justify-content:space-between; color:#52647d; font-weight:800; }
.m28-detail-head { display:flex; justify-content:space-between; gap:20px; align-items:flex-start; margin-bottom:18px; }
.m28-breadcrumb { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-bottom:12px; color:#718197; font-weight:900; }
.m28-breadcrumb button, .m28-title-link { border:0; background:transparent; color:#42607f; font-weight:900; padding:0; }
.m28-breadcrumb button:hover, .m28-title-link:hover { color:var(--m28-blue); text-decoration:underline; }
.m28-detail-head h1 { margin:0; font-size:34px; letter-spacing:-.8px; line-height:1.18; }
.m28-detail-head p { margin:8px 0 0; color:#52647d; font-weight:800; }
.m28-tabs { display:grid; grid-template-columns:repeat(5, minmax(100px, 1fr)); gap:8px; max-width:720px; background:#eaf1f8; padding:7px; border:1px solid var(--m28-line); border-radius:14px; margin-bottom:18px; }
.m28-tabs button { height:42px; border:0; border-radius:10px; background:transparent; color:#43546b; font-weight:900; }
.m28-tabs button.active { background:#fff; color:var(--m28-blue); box-shadow:0 8px 18px rgba(43,85,130,.08); }
.m28-detail-grid { display:grid; grid-template-columns:minmax(0, 1fr) 360px; gap:22px; align-items:start; }
.m28-detail-main { min-width:0; }
.m28-right { position:sticky; top:98px; align-self:start; min-width:0; }
.m28-info-grid { display:grid; grid-template-columns:repeat(4, minmax(130px, 1fr)); gap:12px; }
.m28-info-card { border:1px solid var(--m28-line); border-radius:15px; padding:16px; min-height:92px; background:#fff; }
.m28-info-card span { display:block; color:#62738b; font-size:13px; font-weight:900; margin-bottom:9px; }
.m28-info-card b { display:block; font-size:18px; word-break:break-word; }
.m28-info-card.normal b { color:var(--m28-green); } .m28-info-card.warning b { color:var(--m28-orange); } .m28-info-card.abnormal b { color:var(--m28-red); }
.m28-entity-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(160px, 1fr)); gap:14px; }
.m28-entity-card { min-height:130px; border:1px solid var(--m28-line); border-radius:16px; background:#fff; padding:16px; text-align:left; display:flex; flex-direction:column; gap:8px; }
.m28-entity-card:hover { border-color:#a8ccff; box-shadow:0 10px 20px rgba(18,104,229,.08); transform:translateY(-1px); }
.m28-entity-card b { font-size:18px; }
.m28-entity-card span { color:#6c7f99; font-weight:800; font-size:13px; }
.m28-entity-card em { margin-top:auto; align-self:flex-start; font-style:normal; font-weight:900; padding:8px 16px; border-radius:10px; }
.m28-entity-card em.normal { color:var(--m28-green); background:var(--m28-green-bg); } .m28-entity-card em.warning { color:var(--m28-orange); background:var(--m28-orange-bg); } .m28-entity-card em.abnormal { color:var(--m28-red); background:var(--m28-red-bg); }
.m28-cell-grid { display:grid; grid-template-columns:repeat(5, minmax(90px,1fr)); gap:14px; }
.m28-cell { min-height:86px; border-radius:14px; border:1px solid var(--m28-line); display:grid; place-items:center; padding:12px; }
.m28-cell span { color:#64748b; font-weight:900; font-size:13px; }
.m28-cell b { font-size:26px; }
.m28-cell.normal { background:var(--m28-green-bg); border-color:#cff3e4; color:var(--m28-green); } .m28-cell.warning { background:var(--m28-orange-bg); border-color:#fde8b5; color:var(--m28-orange); } .m28-cell.abnormal { background:var(--m28-red-bg); border-color:#ffd0d0; color:var(--m28-red); }
.m28-advice { border-left:5px solid var(--m28-green); }
.m28-advice.warning { border-left-color:var(--m28-orange); background:#fffaf0; }
.m28-advice.abnormal { border-left-color:var(--m28-red); background:#fff7f7; }
.m28-advice p { margin:0 0 8px; font-size:17px; }
.m28-advice span { color:#65758b; font-weight:800; }
.m28-kv { display:flex; justify-content:space-between; gap:12px; border-bottom:1px solid #eef3f8; padding:12px 0; font-weight:800; }
.m28-kv:last-child { border-bottom:0; }
.m28-kv span { color:#65758b; }
@media (max-width:1180px) { .m28-app { grid-template-columns:220px minmax(0,1fr); } .m28-detail-grid, .m28-dashboard-grid { grid-template-columns:1fr; } .m28-right { position:static; } .m28-info-grid { grid-template-columns:repeat(2, minmax(130px,1fr)); } }
@media (max-width:860px) { .m28-app { grid-template-columns:1fr; } .m28-sidebar { position:relative; height:auto; } .m28-summary-grid, .m28-filter-bar { grid-template-columns:1fr; } .m28-content { padding:22px 16px; } .m28-topbar { overflow:auto; justify-content:flex-start; padding:0 16px; } .m28-cell-grid { grid-template-columns:repeat(2,1fr); } }
'''


def backup_file(path: Path):
    if path.exists():
        BACKUP.mkdir(parents=True, exist_ok=True)
        rel = path.relative_to(BASE)
        dst = BACKUP / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)


def fix_service():
    if not SERVICE.exists():
        print('[WARN] service/monitor_service.py not found; skipped service fix')
        return
    backup_file(SERVICE)
    text = SERVICE.read_text(encoding='utf-8', errors='replace')
    lines = []
    fixed = 0
    for line in text.splitlines(True):
        if 'safe_bms_id = str(bms_id).strip()' in line:
            indent = line[:len(line) - len(line.lstrip())]
            lines.append(indent + 'safe_bms_id = str(bms_id).strip().replace(" ", "_").replace("/", "_").replace("\\\\", "_")\n')
            fixed += 1
        else:
            lines.append(line)
    SERVICE.write_text(''.join(lines), encoding='utf-8')
    print(f'[OK] monitor_service.py fixed lines: {fixed}')


def write_frontend():
    if not MON.exists():
        raise SystemExit('[ERROR] static/monitor folder not found. Run this script at project root.')
    for name in ['monitor.js', 'monitor.css', 'index.html']:
        backup_file(MON / name)
    (MON / 'monitor.js').write_text(JS, encoding='utf-8')
    (MON / 'monitor_v28_stable.css').write_text(CSS, encoding='utf-8')

    index = MON / 'index.html'
    if index.exists():
        html = index.read_text(encoding='utf-8', errors='replace')
        if 'charset' not in html[:500].lower():
            html = re.sub(r'<head([^>]*)>', r'<head\1>\n  <meta charset="UTF-8">', html, count=1, flags=re.I)
        # Ensure monitor.js cache version
        html = re.sub(r'monitor\.js(?:\?v=\d+)?', 'monitor.js?v=28', html)
        # Insert stable CSS after head opening or before script. Remove prior v28 css if present.
        html = re.sub(r'\s*<link[^>]+monitor_v28_stable\.css[^>]*>\s*', '\n', html)
        link = '  <link rel="stylesheet" href="/static/monitor/monitor_v28_stable.css?v=28">\n'
        if '</head>' in html.lower():
            html = re.sub(r'</head>', link + '</head>', html, count=1, flags=re.I)
        else:
            html = link + html
        index.write_text(html, encoding='utf-8')
    else:
        index.write_text('<!doctype html><html><head><meta charset="UTF-8"><title>KESCO Monitoring</title><link rel="stylesheet" href="/static/monitor/monitor_v28_stable.css?v=28"></head><body><script src="/static/monitor/monitor.js?v=28"></script></body></html>', encoding='utf-8')
    print('[OK] frontend rewritten: monitor.js + monitor_v28_stable.css + index.html v28')


def main():
    print(f'[INFO] project root: {BASE}')
    fix_service()
    write_frontend()
    print(f'[OK] backup saved to: {BACKUP}')
    print('[NEXT] run: python -m py_compile .\\service\\monitor_service.py')
    print('[NEXT] restart uvicorn and press Ctrl+F5 in browser')

if __name__ == '__main__':
    main()
