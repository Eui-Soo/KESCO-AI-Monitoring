from pathlib import Path

ROOT = Path.cwd()
index_path = ROOT / 'static' / 'monitor' / 'index.html'
js_path = ROOT / 'static' / 'monitor' / 'monitor.js'
css_path = ROOT / 'static' / 'monitor' / 'monitor.css'

for path in [index_path, js_path, css_path]:
    if not path.exists():
        raise FileNotFoundError(f'Missing file: {path}')

# -----------------------------------------------------------------------------
# 1) index.html: add sidebar hierarchy tree container below navigation
# -----------------------------------------------------------------------------
index = index_path.read_text(encoding='utf-8')
if 'id="sidebarHierarchyTree"' not in index:
    marker = '      </nav>\n'
    insert = '''      </nav>\n\n      <section id="sidebarHierarchyTree" class="sidebar-tree-card" aria-label="ESS hierarchy tree">\n        <div class="sidebar-tree-title">\n          <span>▦</span>\n          <b>계층 구조 탐색</b>\n          <button type="button" class="sidebar-tree-refresh" onclick="renderSidebarHierarchyTree && renderSidebarHierarchyTree()">↻</button>\n        </div>\n        <div class="sidebar-tree-empty">사이트 데이터를 불러오는 중입니다.</div>\n      </section>\n'''
    if marker not in index:
        raise RuntimeError('Could not find </nav> marker in index.html')
    index = index.replace(marker, insert, 1)
    index_path.with_suffix(index_path.suffix + '.v18.bak').write_text(index_path.read_text(encoding='utf-8'), encoding='utf-8')
    index_path.write_text(index, encoding='utf-8')

# -----------------------------------------------------------------------------
# 2) monitor.js: append sidebar tree rendering/wrapping logic
# -----------------------------------------------------------------------------
js = js_path.read_text(encoding='utf-8')
if 'function renderSidebarHierarchyTree' not in js:
    append = r'''

// -----------------------------------------------------------------------------
// v18 sidebar hierarchy tree
// -----------------------------------------------------------------------------
function _treeNumber(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : fallback;
}

function _treeStatusClass(scoreValue) {
  const n = Number(scoreValue);
  if (!Number.isFinite(n)) return 'normal';
  if (n >= 71) return 'abnormal';
  if (n >= 40) return 'warning';
  return 'normal';
}

function _treeDot(status) {
  const value = String(status || 'normal').toLowerCase();
  if (value === 'abnormal' || value === 'danger') return '<span class="tree-dot abnormal"></span>';
  if (value === 'warning' || value === 'caution') return '<span class="tree-dot warning"></span>';
  if (value === 'offline' || value === 'unavailable') return '<span class="tree-dot offline"></span>';
  return '<span class="tree-dot normal"></span>';
}

function _makeSidebarTreeRows(site) {
  const rackCount = Math.max(1, Math.min(_treeNumber(site?.rack_count, 1), 8));
  const stringCount = Math.max(1, Math.min(_treeNumber(site?.string_count, 1), 4));
  const moduleCount = Math.max(1, Math.min(_treeNumber(site?.module_count, 1), 24));
  const modulesPerRack = Math.max(1, Math.ceil(moduleCount / rackCount));
  const siteStatus = site?.status || _treeStatusClass(site?.latest_score);

  let html = '';
  html += `<div class="tree-site-line" title="${escapeHtml(site?.bms_id || '')}">${_treeDot(siteStatus)}<span>${escapeHtml(site?.site_name || 'ESS Site')}</span></div>`;
  html += `<div class="tree-meta-line">${escapeHtml(site?.bms_id || '-')} · Score ${escapeHtml(site?.latest_score ?? '-')}</div>`;
  html += '<ul class="tree-list depth-0">';
  html += `<li><button type="button" class="tree-node ${state.level === 'bank' ? 'active' : ''}" onclick="setLevel('bank')"><span>▦</span><b>Bank 01</b></button>`;
  html += '<ul class="tree-list depth-1">';

  for (let rack = 1; rack <= rackCount; rack += 1) {
    const rackActive = state.level === 'rack' && rack === Number(site?.selected_rack_no || 1);
    html += `<li><button type="button" class="tree-node ${rackActive ? 'active' : ''}" onclick="setLevel('rack')"><span>▤</span><b>Rack ${String(rack).padStart(2, '0')}</b></button>`;

    // Keep the tree compact: expand the selected/first rack only.
    const shouldExpandRack = rack === Number(site?.selected_rack_no || 1) || rack === 1;
    if (shouldExpandRack) {
      html += '<ul class="tree-list depth-2">';
      const stringLimit = Math.max(1, Math.min(stringCount, 2));
      for (let stringNo = 1; stringNo <= stringLimit; stringNo += 1) {
        const stringActive = state.level === 'string' && stringNo === Number(site?.selected_string_no || 1);
        html += `<li><button type="button" class="tree-node ${stringActive ? 'active' : ''}" onclick="setLevel('string')"><span>▧</span><b>String ${String(stringNo).padStart(2, '0')}</b></button>`;
        if (stringNo === Number(site?.selected_string_no || 1) || stringNo === 1) {
          html += '<ul class="tree-list depth-3">';
          const startModule = (rack - 1) * modulesPerRack + 1;
          const endModule = Math.min(moduleCount, startModule + modulesPerRack - 1);
          for (let moduleNo = startModule; moduleNo <= endModule; moduleNo += 1) {
            const moduleActive = state.level === 'module' && moduleNo === Number(site?.selected_module_no || 1);
            html += `<li><button type="button" class="tree-node module ${moduleActive ? 'active' : ''}" onclick="setLevel('module')"><span>▩</span><b>Module ${String(moduleNo).padStart(2, '0')}</b></button></li>`;
          }
          html += '</ul>';
        }
        html += '</li>';
      }
      html += '</ul>';
    }
    html += '</li>';
  }

  html += '</ul></li></ul>';
  html += '<div class="tree-legend"><span><i class="normal"></i>정상</span><span><i class="warning"></i>주의</span><span><i class="abnormal"></i>비정상</span><span><i class="offline"></i>오프라인</span></div>';
  return html;
}

function renderSidebarHierarchyTree() {
  const target = document.getElementById('sidebarHierarchyTree');
  if (!target) return;
  const site = currentSite ? currentSite() : null;
  if (!site) {
    target.innerHTML = '<div class="sidebar-tree-title"><span>▦</span><b>계층 구조 탐색</b></div><div class="sidebar-tree-empty">선택된 사이트가 없습니다.</div>';
    return;
  }
  target.innerHTML = `
    <div class="sidebar-tree-title">
      <span>▦</span>
      <b>계층 구조 탐색</b>
      <button type="button" class="sidebar-tree-refresh" onclick="renderSidebarHierarchyTree()">↻</button>
    </div>
    ${_makeSidebarTreeRows(site)}
  `;
}
window.renderSidebarHierarchyTree = renderSidebarHierarchyTree;

try {
  const __v18LoadCommonData = loadCommonData;
  loadCommonData = async function(...args) {
    const result = await __v18LoadCommonData.apply(this, args);
    renderSidebarHierarchyTree();
    return result;
  };

  const __v18SetLevel = window.setLevel;
  window.setLevel = function(level) {
    state.level = level;
    renderSidebarHierarchyTree();
    renderDetail();
  };

  const __v18SelectSite = window.selectSite;
  window.selectSite = function(siteId) {
    state.selectedSiteId = siteId;
    renderSidebarHierarchyTree();
    renderDetail();
  };

  document.addEventListener('DOMContentLoaded', () => {
    setTimeout(renderSidebarHierarchyTree, 700);
  });
} catch (error) {
  console.warn('[monitor] sidebar tree patch failed', error);
}
'''
    js_path.with_suffix(js_path.suffix + '.v18.bak').write_text(js, encoding='utf-8')
    js_path.write_text(js + append, encoding='utf-8')

# -----------------------------------------------------------------------------
# 3) monitor.css: append sidebar tree styling
# -----------------------------------------------------------------------------
css = css_path.read_text(encoding='utf-8')
if '.sidebar-tree-card' not in css:
    css_append = r'''

/* --------------------------------------------------------------------------
   v18 sidebar hierarchy tree
   -------------------------------------------------------------------------- */
.sidebar-tree-card{
  position:relative;
  z-index:2;
  margin:18px 24px 0;
  padding:16px 14px 12px;
  border:1px solid var(--line);
  border-radius:16px;
  background:rgba(255,255,255,.94);
  box-shadow:0 10px 24px rgba(23,43,77,.07);
  max-height:430px;
  overflow:auto;
}
.sidebar-tree-title{
  display:flex;
  align-items:center;
  gap:10px;
  height:34px;
  margin-bottom:10px;
  color:#17243b;
}
.sidebar-tree-title span{color:var(--blue);font-size:19px}.sidebar-tree-title b{font-size:18px;font-weight:900;letter-spacing:-.3px}.sidebar-tree-refresh{margin-left:auto;width:28px;height:28px;border:0;border-radius:9px;background:#f2f7ff;color:#4b6387;font-size:16px;font-weight:900;cursor:pointer}.sidebar-tree-refresh:hover{background:#e7f0ff;color:var(--blue)}.sidebar-tree-empty{font-size:13px;font-weight:750;color:#738399;padding:12px 4px}.tree-site-line{display:flex;align-items:center;gap:8px;min-height:28px;font-weight:900;color:#10213c}.tree-site-line span:last-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.tree-meta-line{font-size:12px;font-weight:800;color:#738399;margin:0 0 8px 22px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.tree-list{list-style:none;margin:0;padding:0}.tree-list.depth-1{margin-left:12px;padding-left:14px;border-left:2px solid #e4ecf6}.tree-list.depth-2{margin-left:12px;padding-left:14px;border-left:2px solid #e4ecf6}.tree-list.depth-3{margin-left:12px;padding-left:14px;border-left:2px solid #e4ecf6}.tree-node{width:100%;min-height:32px;border:0;background:transparent;border-radius:10px;display:flex;align-items:center;gap:8px;padding:6px 9px;color:#2b3a52;font-size:15px;font-weight:850;cursor:pointer;text-align:left}.tree-node span{width:20px;color:#63728a}.tree-node b{font-weight:850;white-space:nowrap}.tree-node:hover{background:#f2f7ff}.tree-node.active{background:#eaf2ff;color:var(--blue);box-shadow:inset 0 0 0 1px #d6e7ff}.tree-node.active span{color:var(--blue)}.tree-node.module.active{background:linear-gradient(180deg,#1174ff,#075de0);color:white;box-shadow:0 8px 16px rgba(9,105,232,.2)}.tree-node.module.active span{color:white}.tree-dot{width:10px;height:10px;border-radius:50%;display:inline-flex;flex:0 0 10px}.tree-dot.normal,.tree-legend i.normal{background:#17b26a}.tree-dot.warning,.tree-legend i.warning{background:#f59e0b}.tree-dot.abnormal,.tree-legend i.abnormal{background:#ef4444}.tree-dot.offline,.tree-legend i.offline{background:#98a2b3}.tree-legend{display:flex;flex-wrap:wrap;gap:8px 10px;margin-top:12px;padding-top:10px;border-top:1px solid var(--line2);font-size:12px;font-weight:850;color:#526177}.tree-legend span{display:flex;align-items:center;gap:5px}.tree-legend i{width:9px;height:9px;border-radius:50%;display:inline-block}.sidebar-tree-card::-webkit-scrollbar{width:8px}.sidebar-tree-card::-webkit-scrollbar-thumb{background:#d8e3f0;border-radius:20px}.sidebar-tree-card::-webkit-scrollbar-track{background:transparent}
@media (max-height: 880px){.sidebar-tree-card{max-height:330px}.ess-illustration{opacity:.18}}
'''
    css_path.with_suffix(css_path.suffix + '.v18.bak').write_text(css, encoding='utf-8')
    css_path.write_text(css + css_append, encoding='utf-8')

print('v18 sidebar hierarchy tree patch applied successfully.')
print(f'- updated: {index_path}')
print(f'- updated: {js_path}')
print(f'- updated: {css_path}')
