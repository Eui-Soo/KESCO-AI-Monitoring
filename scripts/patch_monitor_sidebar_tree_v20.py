from pathlib import Path

ROOT = Path.cwd()
JS = ROOT / 'static' / 'monitor' / 'monitor.js'
CSS = ROOT / 'static' / 'monitor' / 'monitor.css'

if not JS.exists():
    raise FileNotFoundError(f'Cannot find {JS}')
if not CSS.exists():
    raise FileNotFoundError(f'Cannot find {CSS}')

js = JS.read_text(encoding='utf-8')
css = CSS.read_text(encoding='utf-8')

marker = '/* === v20 detail-only interactive sidebar tree === */'
if marker not in js:
    JS.with_suffix('.js.v20.bak').write_text(js, encoding='utf-8')
    js += r'''

/* === v20 detail-only interactive sidebar tree === */
function v20RemoveLegacySidebarTrees() {
  const sidebar = document.querySelector('.sidebar');
  if (!sidebar) return;
  Array.from(sidebar.children).forEach((el) => {
    if (el.id === 'detailTreePanel') return;
    const text = (el.textContent || '').trim();
    if (text.includes('계층 구조 탐색') || text.includes('Hierarchy Explorer')) {
      el.remove();
    }
  });
}

function v20EnsureTreePanel() {
  v20RemoveLegacySidebarTrees();
  const sidebar = document.querySelector('.sidebar');
  if (!sidebar) return null;
  let panel = document.getElementById('detailTreePanel');
  if (!panel) {
    panel = document.createElement('section');
    panel.id = 'detailTreePanel';
    panel.className = 'detail-tree-panel-v20 hidden';
    const navList = sidebar.querySelector('.nav-list');
    if (navList && navList.parentNode) {
      navList.insertAdjacentElement('afterend', panel);
    } else {
      sidebar.appendChild(panel);
    }
  }
  return panel;
}

function v20HideTree() {
  const panel = v20EnsureTreePanel();
  if (panel) panel.classList.add('hidden');
  document.body.classList.remove('detail-tree-visible-v20');
}

function v20ShowTree(site) {
  const panel = v20EnsureTreePanel();
  if (!panel || !site) return;
  panel.classList.remove('hidden');
  document.body.classList.add('detail-tree-visible-v20');
  panel.innerHTML = v20TreeHtml(site);
}

function v20Number(value, fallback = 1) {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : fallback;
}

function v20Selected() {
  if (!state.selectedBankNo) state.selectedBankNo = 1;
  if (!state.selectedRackNo) state.selectedRackNo = 1;
  if (!state.selectedStringNo) state.selectedStringNo = 1;
  if (!state.selectedModuleNo) state.selectedModuleNo = 1;
  return {
    bank: v20Number(state.selectedBankNo, 1),
    rack: v20Number(state.selectedRackNo, 1),
    string: v20Number(state.selectedStringNo, 1),
    module: v20Number(state.selectedModuleNo, 1),
  };
}

function v20SetPath(level, bankNo = 1, rackNo = 1, stringNo = 1, moduleNo = 1) {
  state.level = level || 'module';
  state.selectedBankNo = v20Number(bankNo, 1);
  state.selectedRackNo = v20Number(rackNo, 1);
  state.selectedStringNo = v20Number(stringNo, 1);
  state.selectedModuleNo = v20Number(moduleNo, 1);
  renderDetail();
}
window.v20SetPath = v20SetPath;

function v20DistributeModules(site, rackNo) {
  const rackCount = v20Number(site.rack_count, 1);
  const moduleCount = v20Number(site.module_count, 1);
  const modulesPerRack = Math.max(1, Math.ceil(moduleCount / rackCount));
  const start = ((rackNo - 1) * modulesPerRack) + 1;
  const end = Math.min(moduleCount, rackNo * modulesPerRack);
  const modules = [];
  for (let m = start; m <= end; m += 1) modules.push(m);
  return modules;
}

function v20TreeHtml(site) {
  const sel = v20Selected();
  const bankCount = Math.max(1, v20Number(site.bank_count, 1));
  const rackCount = Math.max(1, v20Number(site.rack_count, 1));
  const scoreText = site.latest_score === null || site.latest_score === undefined ? '-' : site.latest_score;
  let banks = '';

  for (let bank = 1; bank <= bankCount; bank += 1) {
    const bankActive = sel.bank === bank;
    let racks = '';
    for (let rack = 1; rack <= rackCount; rack += 1) {
      const rackActive = bankActive && sel.rack === rack;
      const modules = v20DistributeModules(site, rack);
      let moduleHtml = modules.map((moduleNo) => {
        const active = rackActive && sel.module === moduleNo && state.level === 'module';
        return `<button type="button" class="tree-node-v20 module ${active ? 'active' : ''}" onclick="v20SetPath('module', ${bank}, ${rack}, 1, ${moduleNo})"><span class="node-icon">M</span><span>Module ${String(moduleNo).padStart(2, '0')}</span></button>`;
      }).join('');
      racks += `
        <div class="tree-row-v20 rack-row">
          <button type="button" class="tree-node-v20 rack ${rackActive && state.level === 'rack' ? 'active' : ''}" onclick="v20SetPath('rack', ${bank}, ${rack}, 1, ${modules[0] || 1})"><span class="node-icon">R</span><span>Rack ${String(rack).padStart(2, '0')}</span></button>
          ${rackActive ? `<div class="tree-children-v20">
            <button type="button" class="tree-node-v20 string ${state.level === 'string' ? 'active' : ''}" onclick="v20SetPath('string', ${bank}, ${rack}, 1, ${modules[0] || 1})"><span class="node-icon">S</span><span>String 01</span></button>
            <div class="tree-children-v20 module-group">${moduleHtml}</div>
          </div>` : ''}
        </div>`;
    }
    banks += `
      <div class="tree-row-v20 bank-row">
        <button type="button" class="tree-node-v20 bank ${bankActive && state.level === 'bank' ? 'active' : ''}" onclick="v20SetPath('bank', ${bank}, ${sel.rack}, ${sel.string}, ${sel.module})"><span class="node-icon">B</span><span>Bank ${String(bank).padStart(2, '0')}</span></button>
        ${bankActive ? `<div class="tree-children-v20">${racks}</div>` : ''}
      </div>`;
  }

  return `
    <div class="tree-head-v20">
      <div>
        <div class="tree-title-v20">계층 구조 탐색</div>
        <div class="tree-site-v20">${escapeHtml(site.site_name || '-')}</div>
        <div class="tree-bms-v20">${escapeHtml(site.bms_id || '-')}</div>
      </div>
      <span class="tree-score-v20 ${scoreClass(scoreText)}">${escapeHtml(scoreText)}</span>
    </div>
    <div class="tree-body-v20">${banks}</div>
    <div class="tree-legend-v20"><span><i class="dot good"></i>정상</span><span><i class="dot warn"></i>주의</span><span><i class="dot bad"></i>비정상</span><span><i class="dot off"></i>오프라인</span></div>`;
}

function v20LevelTitle(level) {
  if (level === 'bank') return 'Bank 상세';
  if (level === 'rack') return 'Rack 상세';
  if (level === 'string') return 'String 상세';
  return 'Module 상세';
}

function v20Breadcrumb(site) {
  const sel = v20Selected();
  const parts = ['사이트 목록', site.site_name || '-', `Bank ${String(sel.bank).padStart(2, '0')}`];
  if (state.level !== 'bank') parts.push(`Rack ${String(sel.rack).padStart(2, '0')}`);
  if (state.level === 'string' || state.level === 'module') parts.push(`String ${String(sel.string).padStart(2, '0')}`);
  if (state.level === 'module') parts.push(`Module ${String(sel.module).padStart(2, '0')}`);
  return parts.map(escapeHtml).join(' <span>›</span> ');
}

function v20SiteOptions() {
  return state.sites.map((s) => {
    const label = `${s.site_name || s.site_id} / ${s.bms_id || '-'}`;
    return `<option value="${escapeHtml(s.site_id)}" ${String(s.site_id) === String(state.selectedSiteId) ? 'selected' : ''}>${escapeHtml(label)}</option>`;
  }).join('');
}

function v20SummaryCards(site, level) {
  return `
    <div class="detail-grid-top">
      <div class="info-card"><small>최대 이상 점수</small><b>${score(level.max_score ?? site.latest_score)}</b></div>
      <div class="info-card"><small>상태</small><b>${badge(level.status || site.status)}</b></div>
      <div class="info-card"><small>최근 분석 시각</small><b>${escapeHtml(level.last_analysis_time || site.last_analysis_time || '-')}</b></div>
      <div class="info-card"><small>위험 위치</small><b>${escapeHtml(site.risk_location || '-')}</b></div>
    </div>`;
}

function v20FallbackCells() {
  return [18,22,31,26,29,34,92,45,28,33,24,37,41,27,39,32,30,25,48,21]
    .map((v,i) => ({ cell_no:i+1, score:v, status:v>=80?'abnormal':v>=40?'warning':'normal', voltage:(3.62 + i/1000).toFixed(3), temperature:(30 + v/8).toFixed(1) }));
}

function v20LevelSummary(site) {
  const sel = v20Selected();
  const rows = [];
  if (state.level === 'bank') {
    const rackCount = v20Number(site.rack_count, 1);
    for (let r = 1; r <= rackCount; r += 1) rows.push({ name:`Rack ${String(r).padStart(2,'0')}`, type:'rack', score: r === sel.rack ? site.latest_score : Math.max(10, Number(site.latest_score || 0) - r * 7), status: r === sel.rack ? site.status : 'normal' });
  } else if (state.level === 'rack') {
    rows.push({ name:'String 01', type:'string', score: site.latest_score, status: site.status });
  } else if (state.level === 'string') {
    v20DistributeModules(site, sel.rack).forEach((m) => rows.push({ name:`Module ${String(m).padStart(2,'0')}`, type:'module', score: m === sel.module ? site.latest_score : Math.max(10, Number(site.latest_score || 0) - m * 3), status: m === sel.module ? site.status : 'normal' }));
  }
  return `
    <section class="panel"><div class="panel-title"><span class="mini-icon">▦</span>${escapeHtml(v20LevelTitle(state.level))} 구성 요약</div>
      <div class="ranking-table"><table><thead><tr><th>구성</th><th>구분</th><th>점수</th><th>상태</th></tr></thead><tbody>
        ${rows.map((r) => `<tr><td><b>${escapeHtml(r.name)}</b></td><td>${escapeHtml(r.type)}</td><td>${score(r.score)}</td><td>${badge(r.status)}</td></tr>`).join('')}
      </tbody></table></div>
    </section>`;
}

async function renderDetail() {
  try {
    setActive('detail');
    setLoading('사이트 상세 로딩 중');
    await loadCommonData();
    const baseSite = currentSite();
    const detailData = await fetchJson(API.site(baseSite.site_id), null);
    const site = detailData?.result || baseSite;
    const levelData = await fetchJson(API.level(site.site_id, state.level), null);
    const level = levelData?.result || {};
    const recData = await fetchJson(API.recommendations(site.site_id), null);
    const recs = Array.isArray(recData?.result) ? recData.result : [];
    const cells = Array.isArray(level.cells) ? level.cells : v20FallbackCells();
    v20ShowTree(site);

    const cellSection = state.level === 'module' ? `
        <section class="panel"><div class="panel-title"><span class="mini-icon">▦</span>Cell 상태 맵</div><div class="cell-map">
          ${cells.map((c) => `<div class="cell ${c.status === 'abnormal' ? 'bad' : c.status === 'warning' ? 'warn' : 'good'}"><b>Cell ${String(c.cell_no).padStart(2,'0')}</b><span>${escapeHtml(c.score)}</span></div>`).join('')}
        </div></section>
        <section class="panel"><div class="panel-title"><span class="mini-icon">▥</span>위험 Cell 상세</div><div class="ranking-table"><table><thead><tr><th>Cell</th><th>점수</th><th>상태</th><th>전압</th><th>온도</th></tr></thead><tbody>
          ${cells.slice().sort((a,b)=>Number(b.score||0)-Number(a.score||0)).slice(0,8).map((c)=>`<tr><td><b>Cell ${String(c.cell_no).padStart(2,'0')}</b></td><td>${score(c.score)}</td><td>${badge(c.status)}</td><td>${escapeHtml(c.voltage || '-')} V</td><td>${escapeHtml(c.temperature || '-')} ℃</td></tr>`).join('')}
        </tbody></table></div></section>` : v20LevelSummary(site);

    content.innerHTML = `
    <div class="page detail-page">
      <section class="detail-left">
        <div class="breadcrumb">${v20Breadcrumb(site)}</div>
        <div class="detail-title detail-title-row"><div class="site-icon">▦</div><div><h1>${escapeHtml(site.site_name)} <span>›</span> ${escapeHtml(v20LevelTitle(state.level))}</h1><p>${escapeHtml(site.region)} · ${escapeHtml(site.manufacturer)} · ${escapeHtml(site.bms_id || '')}</p></div><select class="site-select" onchange="selectSite(this.value)">${v20SiteOptions()}</select></div>
        <div class="level-tabs"><button class="level-tab ${state.level==='bank'?'active':''}" onclick="v20SetPath('bank', v20Selected().bank, v20Selected().rack, v20Selected().string, v20Selected().module)">Bank</button><button class="level-tab ${state.level==='rack'?'active':''}" onclick="v20SetPath('rack', v20Selected().bank, v20Selected().rack, v20Selected().string, v20Selected().module)">Rack</button><button class="level-tab ${state.level==='string'?'active':''}" onclick="v20SetPath('string', v20Selected().bank, v20Selected().rack, v20Selected().string, v20Selected().module)">String</button><button class="level-tab ${state.level==='module'?'active':''}" onclick="v20SetPath('module', v20Selected().bank, v20Selected().rack, v20Selected().string, v20Selected().module)">Module</button></div>
        ${v20SummaryCards(site, level)}
        ${cellSection}
      </section>
      <aside class="detail-right"><section class="panel"><div class="panel-title"><span class="mini-icon">⚠</span>운영 권고</div><div class="alarm-list">
        ${(recs.length ? recs : [{title:'Detailed inspection required', message:'High score was detected from anomaly_score.', action:'Check selected hierarchy from the left tree.'}]).map((r)=>`<div class="alarm-item"><div class="alarm-icon red">⚠</div><div><div class="alarm-name">${escapeHtml(r.title)}</div><small>${escapeHtml(r.message || r.action || '')}</small></div></div>`).join('')}
      </div></section></aside>
    </div>`;
  } catch (error) {
    console.error('[monitor] renderDetail failed', error);
    showError('사이트 상세 표시 중 오류가 발생했습니다.', error.stack || error.message);
  }
}

function setLevel(level) {
  const sel = v20Selected();
  v20SetPath(level, sel.bank, sel.rack, sel.string, sel.module);
}
window.setLevel = setLevel;

function selectSite(siteId) {
  state.selectedSiteId = siteId;
  state.selectedBankNo = 1;
  state.selectedRackNo = 1;
  state.selectedStringNo = 1;
  state.selectedModuleNo = 1;
  state.level = 'module';
  renderDetail();
}
window.selectSite = selectSite;

function nav(page) {
  if (page !== 'detail') v20HideTree();
  if (page === 'dashboard') return renderDashboard();
  if (page === 'sites') return renderSites();
  if (page === 'detail') return renderDetail();
  if (page === 'history') return renderPlaceholder('실행 이력', '파이프라인 실행 이력 화면은 다음 단계에서 연결합니다.');
  if (page === 'settings') return renderPlaceholder('설정', '알림, 모델, 사용자 설정 화면은 다음 단계에서 연결합니다.');
}
window.nav = nav;
'''
    JS.write_text(js, encoding='utf-8')

css_marker = '/* === v20 detail-only interactive sidebar tree css === */'
if css_marker not in css:
    CSS.with_suffix('.css.v20.bak').write_text(css, encoding='utf-8')
    css += r'''

/* === v20 detail-only interactive sidebar tree css === */
.detail-tree-panel-v20.hidden{display:none!important}
.detail-tree-panel-v20{margin:16px 16px 0;padding:16px;border:1px solid #dce6f2;border-radius:18px;background:rgba(255,255,255,.94);box-shadow:0 12px 30px rgba(23,43,77,.08);position:relative;z-index:5;max-height:44vh;overflow:auto}.detail-tree-visible-v20 .ess-illustration{display:none!important}.tree-head-v20{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;padding-bottom:12px;border-bottom:1px solid #edf2f8}.tree-title-v20{font-size:15px;font-weight:900;color:#0b1b36;margin-bottom:8px}.tree-site-v20{font-size:16px;font-weight:900;color:#0b1b36;line-height:1.2}.tree-bms-v20{font-size:12px;font-weight:800;color:#61708a;margin-top:5px;word-break:break-all}.tree-score-v20{min-width:44px;height:30px;border-radius:10px;display:inline-flex;align-items:center;justify-content:center;font-weight:900;font-size:13px}.tree-score-v20.bad{background:#fff0f0;color:#dc2626;border:1px solid #fecaca}.tree-score-v20.warn{background:#fff6df;color:#c77b00;border:1px solid #fde7b1}.tree-score-v20.good{background:#eafaf1;color:#128a52;border:1px solid #cdeedc}.tree-body-v20{padding:12px 0 4px}.tree-row-v20{position:relative}.tree-children-v20{margin-left:18px;padding-left:13px;border-left:1px solid #dce6f2}.tree-node-v20{width:100%;height:34px;border:0;background:transparent;border-radius:10px;display:flex;align-items:center;gap:8px;padding:0 9px;margin:2px 0;color:#24364f;font-size:13px;font-weight:850;text-align:left;cursor:pointer;appearance:none}.tree-node-v20:hover{background:#f2f7ff}.tree-node-v20.active{background:#e8f1ff;color:#0969e8;box-shadow:inset 0 0 0 1px #cfe3ff}.tree-node-v20.module{font-size:12.5px}.node-icon{width:20px;height:20px;border-radius:6px;background:#f2f6fb;color:#64748b;font-size:11px;font-weight:900;display:inline-flex;align-items:center;justify-content:center;flex:0 0 auto}.tree-node-v20.active .node-icon{background:#0969e8;color:#fff}.tree-legend-v20{display:grid;grid-template-columns:1fr 1fr;gap:7px 8px;border-top:1px solid #edf2f8;margin-top:10px;padding-top:12px;font-size:11px;font-weight:800;color:#5a677b}.tree-legend-v20 span{display:flex;align-items:center;gap:6px}.tree-legend-v20 .dot{width:8px;height:8px;border-radius:50%;display:inline-block}.tree-legend-v20 .dot.good{background:#17b26a}.tree-legend-v20 .dot.warn{background:#f59e0b}.tree-legend-v20 .dot.bad{background:#ef4444}.tree-legend-v20 .dot.off{background:#94a3b8}.detail-page .level-tabs{display:inline-grid!important;grid-template-columns:repeat(4,1fr);gap:4px;background:#f2f6fb;border:1px solid #dce6f2;border-radius:16px;padding:5px;margin:14px 0 16px}.detail-page .level-tab{height:42px;min-width:88px;border:0;border-radius:12px;background:transparent;color:#526177;font-weight:900;cursor:pointer}.detail-page .level-tab.active{background:#fff;color:#0969e8;box-shadow:0 6px 16px rgba(23,43,77,.08)}.detail-page .site-select{height:46px;border:1px solid #dce6f2;border-radius:12px;background:#fff;padding:0 14px;font-weight:850;color:#0b1b36;min-width:320px}.detail-page .cell{display:flex!important;flex-direction:column!important;align-items:center!important;justify-content:center!important;gap:7px!important;min-height:72px!important}.detail-page .cell b{font-size:13px!important;color:#526177!important}.detail-page .cell span{font-size:24px!important;font-weight:950!important;line-height:1!important}.detail-page .cell.good span{color:#17b26a}.detail-page .cell.warn span{color:#c77b00}.detail-page .cell.bad span{color:#dc2626}@media(max-height:850px){.detail-tree-panel-v20{max-height:38vh;padding:13px}.tree-node-v20{height:31px}}
'''
    CSS.write_text(css, encoding='utf-8')

print('v20 patch applied')
print(f'- {JS}')
print(f'- {CSS}')
