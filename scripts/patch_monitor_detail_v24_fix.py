from pathlib import Path
import re

ROOT = Path.cwd()
monitor_js = ROOT / 'static' / 'monitor' / 'monitor.js'
monitor_css = ROOT / 'static' / 'monitor' / 'monitor.css'
index_html = ROOT / 'static' / 'monitor' / 'index.html'

if not monitor_js.exists():
    raise FileNotFoundError(f'not found: {monitor_js}')

text = monitor_js.read_text(encoding='utf-8', errors='replace')
backup = monitor_js.with_suffix('.js.v24fix.bak')
backup.write_text(text, encoding='utf-8')

first = text.find('async function renderDetail()')
if first == -1:
    # v22 used assignment form sometimes
    first = text.find('renderDetail = async function')
if first == -1:
    raise RuntimeError('Could not find renderDetail block in monitor.js')

prefix = text[:first].rstrip()
# Remove older accidental partial patches by keeping only code before first renderDetail.
# Then append one clean detail/navigation implementation.
append = r'''

/* v24 detail clean rebuild: single renderDetail, clean tree, site/bank/rack/string/module views */
function v24EnsureDetailPath() {
  if (!state.detailPath) state.detailPath = { level: 'site', bank: 1, rack: 1, string: 1, module: 1, collapsed: false };
  if (!state.detailPath.level) state.detailPath.level = state.level || 'site';
  return state.detailPath;
}

function v24StatusKey(value) {
  const v = String(value || '').toLowerCase();
  if (v === 'abnormal' || v === 'danger' || v === 'bad') return 'abnormal';
  if (v === 'warning' || v === 'caution' || v === 'warn') return 'warning';
  if (v === 'offline' || v === 'unavailable' || v === 'data_missing') return 'offline';
  return 'normal';
}

function v24StatusText(value) {
  const key = v24StatusKey(value);
  if (key === 'abnormal') return '비정상';
  if (key === 'warning') return '주의';
  if (key === 'offline') return '오프라인';
  return '정상';
}

function v24StatusDot(status) {
  const key = v24StatusKey(status);
  return `<span class="tree-dot ${key}" title="${v24StatusText(key)}"></span>`;
}

function v24LevelTitle(level) {
  if (level === 'site') return 'Site 정보';
  if (level === 'bank') return 'Bank 상세';
  if (level === 'rack') return 'Rack 상세';
  if (level === 'string') return 'String 상세';
  return 'Module 상세';
}

function v24LevelKo(level) {
  if (level === 'site') return 'Site';
  if (level === 'bank') return 'Bank';
  if (level === 'rack') return 'Rack';
  if (level === 'string') return 'String';
  return 'Module';
}

function v24FormatTime(value) {
  if (!value) return '-';
  return String(value).replace('T', ' ').split('.')[0];
}

function v24ScoreValue(value) {
  if (value === null || value === undefined || value === '') return '-';
  const n = Number(value);
  if (Number.isNaN(n)) return value;
  return Math.round(n);
}

function v24MakeChildStatus(site, seed) {
  const base = Number(site?.latest_score ?? 0);
  const n = Math.max(0, Math.min(100, base - (seed % 5) * 7 + (seed % 3) * 3));
  if (n >= 71) return 'abnormal';
  if (n >= 40) return 'warning';
  return 'normal';
}

function v24Counts(site) {
  return {
    banks: Math.max(1, Number(site?.bank_count || 1)),
    racks: Math.max(1, Number(site?.rack_count || 1)),
    strings: Math.max(1, Number(site?.string_count || 1)),
    modules: Math.max(1, Number(site?.module_count || 1)),
    cells: Math.max(20, Number(site?.cell_count || 20)),
  };
}

function v24SetDetailLevel(level, bank = null, rack = null, stringNo = null, module = null) {
  const p = v24EnsureDetailPath();
  p.level = level;
  state.level = level === 'site' ? 'site' : level;
  if (bank !== null) p.bank = Number(bank) || 1;
  if (rack !== null) p.rack = Number(rack) || 1;
  if (stringNo !== null) p.string = Number(stringNo) || 1;
  if (module !== null) p.module = Number(module) || 1;
  p.collapsed = false;
  renderDetail();
}
window.v24SetDetailLevel = v24SetDetailLevel;

function v24ResetDetailTree() {
  const p = v24EnsureDetailPath();
  p.level = 'site';
  p.bank = 1;
  p.rack = 1;
  p.string = 1;
  p.module = 1;
  p.collapsed = true;
  state.level = 'site';
  renderDetail();
}
window.v24ResetDetailTree = v24ResetDetailTree;

function v24GoSites() {
  removeDetailTree();
  renderSites();
}
window.v24GoSites = v24GoSites;

function v24TreeItem(level, label, status, active, onclick, depth = 0) {
  return `<button type="button" class="v24-tree-item ${active ? 'active' : ''} depth-${depth}" onclick="${onclick}">
    ${v24StatusDot(status)}<span class="tree-level-code">${escapeHtml(v24LevelKo(level).slice(0,1))}</span><span class="tree-label">${escapeHtml(label)}</span>
  </button>`;
}

function updateDetailTree(site) {
  const sidebar = document.querySelector('.sidebar');
  if (!sidebar) return;
  let box = document.getElementById('detailTreeBox');
  if (!box) {
    box = document.createElement('section');
    box.id = 'detailTreeBox';
    box.className = 'v24-detail-tree-card';
    const nav = sidebar.querySelector('.nav-list');
    if (nav && nav.parentNode) nav.parentNode.insertBefore(box, nav.nextSibling);
    else sidebar.appendChild(box);
  }
  const p = v24EnsureDetailPath();
  const c = v24Counts(site);
  const siteStatus = v24StatusKey(site.status);
  let html = `
    <div class="tree-card-head">
      <div><b>계층 구조 탐색</b><small>현재 사이트 기준</small></div>
      <button type="button" class="tree-reset-btn" onclick="v24ResetDetailTree()" title="계층 접기">초기화</button>
    </div>
    <button type="button" class="tree-site-summary ${p.level === 'site' ? 'active' : ''}" onclick="v24SetDetailLevel('site')">
      ${v24StatusDot(siteStatus)}
      <div><b>${escapeHtml(site.site_name || 'Site')}</b><small>${escapeHtml(site.bms_id || '-')}</small></div>
      <em>${escapeHtml(v24ScoreValue(site.latest_score))}</em>
    </button>
  `;
  if (!p.collapsed) {
    html += `<div class="tree-branch">`;
    html += v24TreeItem('bank', `Bank ${String(p.bank).padStart(2,'0')}`, v24MakeChildStatus(site, 1), p.level === 'bank', `v24SetDetailLevel('bank', ${p.bank})`, 0);
    for (let r = 1; r <= Math.min(c.racks, 8); r++) {
      const rActive = p.rack === r && ['rack','string','module'].includes(p.level);
      html += v24TreeItem('rack', `Rack ${String(r).padStart(2,'0')}`, v24MakeChildStatus(site, r + 2), rActive, `v24SetDetailLevel('rack', ${p.bank}, ${r})`, 1);
      if (r === p.rack) {
        const stringsPerRack = Math.max(1, Math.ceil(c.strings / c.racks));
        for (let s = 1; s <= Math.min(stringsPerRack, 4); s++) {
          const sActive = p.string === s && ['string','module'].includes(p.level);
          html += v24TreeItem('string', `String ${String(s).padStart(2,'0')}`, v24MakeChildStatus(site, r * 10 + s), sActive, `v24SetDetailLevel('string', ${p.bank}, ${r}, ${s})`, 2);
          if (s === p.string) {
            const modulesPerRack = Math.max(1, Math.ceil(c.modules / c.racks));
            for (let m = 1; m <= Math.min(modulesPerRack, 12); m++) {
              const moduleNo = (r - 1) * modulesPerRack + m;
              if (moduleNo > c.modules) break;
              const mActive = p.module === moduleNo && p.level === 'module';
              html += v24TreeItem('module', `Module ${String(moduleNo).padStart(2,'0')}`, v24MakeChildStatus(site, moduleNo), mActive, `v24SetDetailLevel('module', ${p.bank}, ${r}, ${s}, ${moduleNo})`, 3);
            }
          }
        }
      }
    }
    html += `</div>`;
  }
  html += `<div class="tree-legend"><span><i class="tree-dot normal"></i>정상</span><span><i class="tree-dot warning"></i>주의</span><span><i class="tree-dot abnormal"></i>비정상</span><span><i class="tree-dot offline"></i>오프라인</span></div>`;
  box.innerHTML = html;
}

function removeDetailTree() {
  const box = document.getElementById('detailTreeBox');
  if (box) box.remove();
}

function v24Breadcrumb(site, p) {
  const parts = [
    `<button type="button" onclick="v24GoSites()">사이트 목록</button>`,
    `<button type="button" onclick="v24SetDetailLevel('site')">${escapeHtml(site.site_name)}</button>`,
  ];
  if (['bank','rack','string','module'].includes(p.level)) parts.push(`<button type="button" onclick="v24SetDetailLevel('bank', ${p.bank})">Bank ${String(p.bank).padStart(2,'0')}</button>`);
  if (['rack','string','module'].includes(p.level)) parts.push(`<button type="button" onclick="v24SetDetailLevel('rack', ${p.bank}, ${p.rack})">Rack ${String(p.rack).padStart(2,'0')}</button>`);
  if (['string','module'].includes(p.level)) parts.push(`<button type="button" onclick="v24SetDetailLevel('string', ${p.bank}, ${p.rack}, ${p.string})">String ${String(p.string).padStart(2,'0')}</button>`);
  if (p.level === 'module') parts.push(`<button type="button" onclick="v24SetDetailLevel('module', ${p.bank}, ${p.rack}, ${p.string}, ${p.module})">Module ${String(p.module).padStart(2,'0')}</button>`);
  return `<div class="breadcrumb v24-breadcrumb">${parts.join('<span>›</span>')}</div>`;
}

function v24InfoCard(title, value, cls = '') {
  return `<div class="info-card ${cls}"><small>${escapeHtml(title)}</small><b>${value}</b></div>`;
}

function v24EntityCards(site, p) {
  const c = v24Counts(site);
  if (p.level === 'site') {
    const banks = Array.from({ length: c.banks }, (_, i) => i + 1);
    return `<section class="panel v24-level-panel"><div class="panel-title"><span class="mini-icon">▦</span>Bank 구성</div><div class="v24-card-grid">
      ${banks.map((b) => `<button class="v24-entity-card" onclick="v24SetDetailLevel('bank', ${b})">${v24StatusDot(v24MakeChildStatus(site, b))}<strong>Bank ${String(b).padStart(2,'0')}</strong><small>Rack ${c.racks} · Module ${c.modules}</small><em>${escapeHtml(v24StatusText(v24MakeChildStatus(site, b)))}</em></button>`).join('')}
    </div></section>`;
  }
  if (p.level === 'bank') {
    return `<section class="panel v24-level-panel"><div class="panel-title"><span class="mini-icon">▦</span>Rack 구성</div><div class="v24-card-grid">
      ${Array.from({ length: Math.min(c.racks, 12) }, (_, i) => i + 1).map((r) => `<button class="v24-entity-card" onclick="v24SetDetailLevel('rack', ${p.bank}, ${r})">${v24StatusDot(v24MakeChildStatus(site, r + 2))}<strong>Rack ${String(r).padStart(2,'0')}</strong><small>String ${Math.max(1, Math.ceil(c.strings / c.racks))} · Module ${Math.max(1, Math.ceil(c.modules / c.racks))}</small><em>${escapeHtml(v24StatusText(v24MakeChildStatus(site, r + 2)))}</em></button>`).join('')}
    </div></section>`;
  }
  if (p.level === 'rack') {
    const stringsPerRack = Math.max(1, Math.ceil(c.strings / c.racks));
    return `<section class="panel v24-level-panel"><div class="panel-title"><span class="mini-icon">▦</span>String 구성</div><div class="v24-card-grid">
      ${Array.from({ length: Math.min(stringsPerRack, 8) }, (_, i) => i + 1).map((s) => `<button class="v24-entity-card" onclick="v24SetDetailLevel('string', ${p.bank}, ${p.rack}, ${s})">${v24StatusDot(v24MakeChildStatus(site, p.rack * 10 + s))}<strong>String ${String(s).padStart(2,'0')}</strong><small>Module ${Math.max(1, Math.ceil(c.modules / c.racks))}</small><em>${escapeHtml(v24StatusText(v24MakeChildStatus(site, p.rack * 10 + s)))}</em></button>`).join('')}
    </div></section>`;
  }
  if (p.level === 'string') {
    const modulesPerRack = Math.max(1, Math.ceil(c.modules / c.racks));
    return `<section class="panel v24-level-panel"><div class="panel-title"><span class="mini-icon">▦</span>Module 구성</div><div class="v24-card-grid">
      ${Array.from({ length: Math.min(modulesPerRack, 16) }, (_, i) => (p.rack - 1) * modulesPerRack + i + 1).filter((m) => m <= c.modules).map((m) => `<button class="v24-entity-card" onclick="v24SetDetailLevel('module', ${p.bank}, ${p.rack}, ${p.string}, ${m})">${v24StatusDot(v24MakeChildStatus(site, m))}<strong>Module ${String(m).padStart(2,'0')}</strong><small>Cell 20</small><em>${escapeHtml(v24StatusText(v24MakeChildStatus(site, m)))}</em></button>`).join('')}
    </div></section>`;
  }
  return '';
}

function v24ModuleCells(level) {
  const cells = Array.isArray(level.cells) ? level.cells : [18,22,31,26,29,34,92,45,28,33,24,37,41,27,39,32,30,25,48,21].map((v,i) => ({ cell_no:i+1, score:v, status:v>=80?'abnormal':v>=40?'warning':'normal', voltage:(3.62 + i/1000).toFixed(3), temperature:(30 + v/8).toFixed(1) }));
  return `<section class="panel"><div class="panel-title"><span class="mini-icon">▦</span>Cell 상태 맵</div><div class="cell-map">
    ${cells.map((c) => `<div class="cell ${v24StatusKey(c.status)}"><b>Cell ${String(c.cell_no).padStart(2,'0')}</b><span>${escapeHtml(v24ScoreValue(c.score))}</span></div>`).join('')}
  </div></section>
  <section class="panel"><div class="panel-title"><span class="mini-icon">▥</span>위험 Cell 상세</div><div class="ranking-table"><table><thead><tr><th>Cell</th><th>점수</th><th>상태</th><th>전압</th><th>온도</th></tr></thead><tbody>
    ${cells.slice().sort((a,b)=>Number(b.score||0)-Number(a.score||0)).slice(0,8).map((c)=>`<tr><td><b>Cell ${String(c.cell_no).padStart(2,'0')}</b></td><td>${score(v24ScoreValue(c.score))}</td><td>${badge(v24StatusKey(c.status))}</td><td>${escapeHtml(c.voltage || '-')} V</td><td>${escapeHtml(c.temperature || '-')} ℃</td></tr>`).join('')}
  </tbody></table></div></section>`;
}

function v24RightPanel(site, level) {
  const maxScore = v24ScoreValue(level.max_score ?? site.latest_score);
  const status = v24StatusKey(level.status || site.status);
  const action = status === 'abnormal' ? '즉시 점검 권고' : status === 'warning' ? '주의 관찰 필요' : '정상 운전';
  return `<aside class="detail-right v24-right-stack">
    <section class="panel v24-side-card"><div class="panel-title"><span class="mini-icon">⚠</span>운영 권고</div>
      <div class="v24-reco-main ${status}"><b>${escapeHtml(action)}</b><span>최고 이상점수 ${escapeHtml(maxScore)}</span></div>
      <div class="v24-reco-row"><span>현재 상태</span><b>${escapeHtml(v24StatusText(status))}</b></div>
      <div class="v24-reco-row"><span>위험 위치</span><b>${escapeHtml(site.risk_location || 'Latest anomaly_score result')}</b></div>
    </section>
    <section class="panel v24-side-card compact"><div class="panel-title"><span class="mini-icon">▤</span>분석 요약</div>
      <div class="v24-reco-row"><span>최근 분석</span><b>${escapeHtml(v24FormatTime(site.last_analysis_time))}</b></div>
      <div class="v24-reco-row"><span>Score Rows</span><b>${escapeHtml(site.score_row_count || '-')}</b></div>
      <div class="v24-reco-row"><span>BMS ID</span><b>${escapeHtml(site.bms_id || '-')}</b></div>
    </section>
  </aside>`;
}

async function renderDetail() {
  try {
    setActive('detail');
    setLoading('사이트 상세 로딩 중');
    await loadCommonData();
    const baseSite = currentSite();
    const detailData = await fetchJson(API.site(baseSite.site_id), null);
    const site = detailData?.result || baseSite;
    if (site?.site_id) state.selectedSiteId = site.site_id;
    const p = v24EnsureDetailPath();
    const apiLevel = p.level === 'site' ? 'module' : p.level;
    const levelData = await fetchJson(API.level(site.site_id, apiLevel), null);
    const level = levelData?.result || {};
    updateDetailTree(site);
    const levelTitle = v24LevelTitle(p.level);
    const selectedName = p.level === 'site' ? 'Site' : p.level === 'bank' ? `Bank ${String(p.bank).padStart(2,'0')}` : p.level === 'rack' ? `Rack ${String(p.rack).padStart(2,'0')}` : p.level === 'string' ? `String ${String(p.string).padStart(2,'0')}` : `Module ${String(p.module).padStart(2,'0')}`;
    const c = v24Counts(site);
    content.innerHTML = `
    <div class="page detail-page v24-detail-page">
      <section class="detail-left">
        ${v24Breadcrumb(site, p)}
        <div class="detail-title detail-title-row v24-title-row">
          <button type="button" class="site-icon v24-site-click" onclick="v24SetDetailLevel('site')">▦</button>
          <div><h1>${escapeHtml(site.site_name)} <span>›</span> ${escapeHtml(levelTitle)}</h1><p>${escapeHtml(site.region)} · ${escapeHtml(site.install_area || '-')} · ${escapeHtml(site.manufacturer)} · ${escapeHtml(site.bms_id || '')}</p></div>
          <button type="button" class="v24-other-site-btn" onclick="v24GoSites()">다른 사이트 보기</button>
        </div>
        <div class="level-tabs v24-level-tabs">
          ${['site','bank','rack','string','module'].map((lv) => `<button class="level-tab ${p.level===lv?'active':''}" onclick="v24SetDetailLevel('${lv}', ${p.bank}, ${p.rack}, ${p.string}, ${p.module})">${escapeHtml(v24LevelKo(lv))}</button>`).join('')}
        </div>
        <div class="detail-grid-top">
          ${v24InfoCard('선택 계층', escapeHtml(selectedName))}
          ${v24InfoCard('최대 이상 점수', score(v24ScoreValue(level.max_score ?? site.latest_score)))}
          ${v24InfoCard('상태', badge(v24StatusKey(level.status || site.status)))}
          ${v24InfoCard('최근 분석 시각', escapeHtml(v24FormatTime(site.last_analysis_time)))}
        </div>
        ${p.level === 'site' ? `<section class="panel v24-site-overview"><div class="panel-title"><span class="mini-icon">▦</span>사이트 정보</div><div class="v24-overview-grid">
          ${v24InfoCard('사이트명', escapeHtml(site.site_name))}
          ${v24InfoCard('BMS ID', escapeHtml(site.bms_id || '-'))}
          ${v24InfoCard('지역 / 설치구역', `${escapeHtml(site.region || '-')} / ${escapeHtml(site.install_area || '-')}`)}
          ${v24InfoCard('제조사', escapeHtml(site.manufacturer || '-'))}
          ${v24InfoCard('Bank / Rack', `${c.banks} / ${c.racks}`)}
          ${v24InfoCard('String / Module / Cell', `${c.strings} / ${c.modules} / ${c.cells}`)}
        </div></section>` : ''}
        ${v24EntityCards(site, p)}
        ${p.level === 'module' ? v24ModuleCells(level) : ''}
      </section>
      ${v24RightPanel(site, level)}
    </div>`;
  } catch (error) {
    console.error('[monitor] v24 renderDetail failed', error);
    showError('사이트 상세 표시 중 오류가 발생했습니다.', error.stack || error.message);
  }
}

function setLevel(level) {
  v24SetDetailLevel(level);
}
window.setLevel = setLevel;

function selectSite(siteId) {
  state.selectedSiteId = siteId;
  state.detailPath = { level: 'site', bank: 1, rack: 1, string: 1, module: 1, collapsed: false };
  renderDetail();
}
window.selectSite = selectSite;

function nav(page) {
  if (page !== 'detail') removeDetailTree();
  if (page === 'dashboard') return renderDashboard();
  if (page === 'sites') return renderSites();
  if (page === 'detail') return renderDetail();
  if (page === 'history') return renderPlaceholder('실행 이력', '파이프라인 실행 이력 화면은 다음 단계에서 연결합니다.');
  if (page === 'settings') return renderPlaceholder('설정', '알림, 모델, 사용자 설정 화면은 다음 단계에서 연결합니다.');
}
window.nav = nav;

function bindNav() {
  navItems.forEach((item) => {
    item.addEventListener('click', () => nav(item.dataset.page));
  });
}

async function init() {
  try {
    if (!content) return;
    bindNav();
    await fetchJson(API.system, null);
    await renderDashboard();
  } catch (error) {
    console.error('[monitor] init failed', error);
    showError('초기화 중 오류가 발생했습니다.', error.stack || error.message);
  }
}

document.addEventListener('DOMContentLoaded', init);
if (document.readyState !== 'loading') init();
'''

monitor_js.write_text(prefix + append + '\n', encoding='utf-8')

# CSS append/replace marker block
css = monitor_css.read_text(encoding='utf-8', errors='replace') if monitor_css.exists() else ''
css_backup = monitor_css.with_suffix('.css.v24fix.bak')
css_backup.write_text(css, encoding='utf-8')
css = re.sub(r'/\* v24-detail-clean-start \*/.*?/\* v24-detail-clean-end \*/', '', css, flags=re.S)
css += r'''

/* v24-detail-clean-start */
.v24-detail-page{grid-template-columns:minmax(760px,1fr) 360px;gap:24px}.v24-breadcrumb{display:flex;align-items:center;gap:8px;margin-bottom:22px}.v24-breadcrumb button{border:0;background:transparent;color:#607089;font-weight:800;cursor:pointer;padding:0}.v24-breadcrumb button:hover{color:#0969e8;text-decoration:underline}.v24-title-row{align-items:center}.v24-site-click{border:1px solid var(--line);background:#f7fbff;cursor:pointer}.v24-other-site-btn{margin-left:auto;height:52px;border:1px solid #cfe1fb;background:#f7fbff;color:#0969e8;border-radius:13px;padding:0 20px;font-weight:900;cursor:pointer}.v24-other-site-btn:hover{background:#eaf3ff}.v24-level-tabs{display:grid;grid-template-columns:repeat(5,1fr);max-width:560px}.v24-level-tabs .level-tab{height:52px}.v24-site-overview,.v24-level-panel{margin-top:16px}.v24-overview-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;padding:20px}.v24-card-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;padding:20px}.v24-entity-card{min-height:118px;border:1px solid var(--line);background:#fff;border-radius:16px;padding:18px;text-align:left;display:grid;grid-template-columns:auto 1fr;grid-template-rows:auto auto auto;gap:8px 10px;box-shadow:0 6px 18px rgba(16,35,66,.04);cursor:pointer}.v24-entity-card:hover{border-color:#96c2ff;background:#f8fbff;transform:translateY(-1px)}.v24-entity-card strong{font-size:18px}.v24-entity-card small{grid-column:2;color:#718198;font-weight:750}.v24-entity-card em{grid-column:2;font-style:normal;font-weight:900;color:#0b1b36}.tree-dot{width:10px;height:10px;border-radius:50%;display:inline-block;flex:0 0 10px}.tree-dot.normal{background:#17b26a}.tree-dot.warning{background:#f59e0b}.tree-dot.abnormal{background:#ef4444}.tree-dot.offline{background:#94a3b8}.v24-detail-tree-card{margin:18px 20px 0;background:#fff;border:1px solid var(--line);border-radius:16px;box-shadow:var(--soft);padding:14px;max-height:430px;overflow:auto}.tree-card-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}.tree-card-head b{font-size:16px}.tree-card-head small{display:block;color:#738399;font-weight:750;margin-top:2px}.tree-reset-btn{height:30px;border:1px solid var(--line);background:#f8fbff;border-radius:9px;color:#52677f;font-weight:900;cursor:pointer}.tree-site-summary{width:100%;border:1px solid var(--line2);background:#fbfdff;border-radius:13px;padding:12px;display:grid;grid-template-columns:auto 1fr auto;gap:10px;align-items:center;text-align:left;cursor:pointer;margin-bottom:10px}.tree-site-summary.active{border-color:#a8ceff;background:#eef6ff}.tree-site-summary b{font-size:14px}.tree-site-summary small{display:block;color:#68788f;font-weight:800;margin-top:3px}.tree-site-summary em{font-style:normal;background:#fff1f1;color:#ef4444;border:1px solid #fecaca;border-radius:10px;padding:5px 10px;font-weight:900}.tree-branch{display:flex;flex-direction:column;gap:5px}.v24-tree-item{height:34px;border:0;background:transparent;border-radius:10px;display:flex;align-items:center;gap:8px;text-align:left;color:#20314b;font-weight:850;cursor:pointer;padding:0 8px}.v24-tree-item:hover{background:#f3f7ff}.v24-tree-item.active{background:#eaf3ff;color:#0969e8;box-shadow:inset 0 0 0 1px #cfe2ff}.v24-tree-item.depth-1{margin-left:18px}.v24-tree-item.depth-2{margin-left:36px}.v24-tree-item.depth-3{margin-left:54px}.tree-level-code{width:20px;height:20px;border-radius:7px;background:#eef3f9;color:#607089;display:inline-flex;align-items:center;justify-content:center;font-size:12px;font-weight:900}.tree-label{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.tree-legend{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px;padding-top:12px;border-top:1px solid var(--line2);font-size:12px;color:#66758c;font-weight:800}.tree-legend span{display:flex;align-items:center;gap:6px}.v24-right-stack{display:flex;flex-direction:column;gap:16px}.v24-side-card{min-height:210px}.v24-side-card.compact{min-height:170px}.v24-reco-main{margin:18px;padding:18px;border-radius:14px;border:1px solid var(--line);display:flex;flex-direction:column;gap:6px}.v24-reco-main b{font-size:19px}.v24-reco-main span{font-weight:800;color:#64748b}.v24-reco-main.abnormal{background:#fff3f3;border-color:#fecaca;color:#dc2626}.v24-reco-main.warning{background:#fff8e7;border-color:#fde7b1;color:#b77900}.v24-reco-main.normal{background:#ecfdf3;border-color:#cdeedc;color:#128a52}.v24-reco-row{display:flex;justify-content:space-between;gap:14px;padding:12px 18px;border-top:1px solid var(--line2);font-weight:800}.v24-reco-row span{color:#6b7a90}.v24-reco-row b{text-align:right}.cell.abnormal{background:var(--red-bg);border-color:#fecaca;color:#dc2626}.cell.warning{background:var(--orange-bg);border-color:#fde7b1;color:#c77b00}.cell.normal{background:var(--green-bg);border-color:#cdeedc;color:#17b26a}.cell.offline{background:#f1f4f8;border-color:#e1e7ef;color:#64748b}@media(max-width:1400px){.v24-detail-page{grid-template-columns:1fr}.v24-right-stack{display:grid;grid-template-columns:1fr 1fr}.v24-card-grid{grid-template-columns:repeat(3,1fr)}}
/* v24-detail-clean-end */
'''
monitor_css.write_text(css, encoding='utf-8')

# index cache bust
if index_html.exists():
    idx = index_html.read_text(encoding='utf-8', errors='replace')
    idx_bak = index_html.with_suffix('.html.v24fix.bak')
    idx_bak.write_text(idx, encoding='utf-8')
    idx = re.sub(r'/static/monitor/monitor\.css(?:\?v=\d+)?', '/static/monitor/monitor.css?v=24', idx)
    idx = re.sub(r'/static/monitor/monitor_v7_fix\.css(?:\?v=\d+)?', '/static/monitor/monitor_v7_fix.css?v=24', idx)
    idx = re.sub(r'/static/monitor/monitor\.js(?:\?v=\d+)?', '/static/monitor/monitor.js?v=24', idx)
    index_html.write_text(idx, encoding='utf-8')

print('v24 fix applied')
print(f'backup js: {backup}')
print(f'backup css: {css_backup}')
