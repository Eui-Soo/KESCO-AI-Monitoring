from pathlib import Path

ROOT = Path.cwd()
index_path = ROOT / 'static' / 'monitor' / 'index.html'
js_v19_path = ROOT / 'static' / 'monitor' / 'monitor_tree_v19.js'
css_v19_path = ROOT / 'static' / 'monitor' / 'monitor_tree_v19.css'

if not index_path.exists():
    raise FileNotFoundError(f'Missing file: {index_path}')

# 1) ensure sidebar tree container exists, but do not duplicate it
index = index_path.read_text(encoding='utf-8')
index_original = index

if 'id="sidebarHierarchyTree"' not in index:
    marker = '      </nav>\n'
    insert = '''      </nav>\n\n      <section id="sidebarHierarchyTree" class="sidebar-tree-card" aria-label="ESS hierarchy tree"></section>\n'''
    if marker not in index:
        raise RuntimeError('Could not find </nav> marker in index.html')
    index = index.replace(marker, insert, 1)

# 2) link v19 css/js after existing monitor assets
if '/static/monitor/monitor_tree_v19.css' not in index:
    marker = '  <link rel="stylesheet" href="/static/monitor/monitor_v7_fix.css" />\n'
    if marker in index:
        index = index.replace(marker, marker + '  <link rel="stylesheet" href="/static/monitor/monitor_tree_v19.css" />\n', 1)
    else:
        marker = '</head>'
        index = index.replace(marker, '  <link rel="stylesheet" href="/static/monitor/monitor_tree_v19.css" />\n</head>', 1)

if '/static/monitor/monitor_tree_v19.js' not in index:
    marker = '  <script src="/static/monitor/monitor.js"></script>\n'
    if marker in index:
        index = index.replace(marker, marker + '  <script src="/static/monitor/monitor_tree_v19.js"></script>\n', 1)
    else:
        marker = '</body>'
        index = index.replace(marker, '  <script src="/static/monitor/monitor_tree_v19.js"></script>\n</body>', 1)

if index != index_original:
    bak = index_path.with_suffix(index_path.suffix + '.v19.bak')
    if not bak.exists():
        bak.write_text(index_original, encoding='utf-8')
    index_path.write_text(index, encoding='utf-8')

# 3) refined css: hidden outside site detail, styled only in detail mode
css_v19 = r'''/* v19 refined sidebar hierarchy tree
   - hidden except Site Detail page
   - polished sidebar card
   - current selected site only
*/
#sidebarHierarchyTree.sidebar-tree-card{
  display:none !important;
}
body.monitor-detail-active #sidebarHierarchyTree.sidebar-tree-card{
  display:block !important;
  position:relative;
  z-index:5;
  margin:18px 20px 0;
  padding:16px;
  border:1px solid #dce6f2;
  border-radius:18px;
  background:linear-gradient(180deg,#ffffff 0%,#f8fbff 100%);
  box-shadow:0 14px 34px rgba(23,43,77,.09);
  max-height:calc(100vh - 460px);
  min-height:230px;
  overflow:auto;
  font-family:"Pretendard","Segoe UI",Arial,sans-serif;
  color:#0b1b36;
}
body.monitor-detail-active .sidebar{
  overflow-y:auto;
}
body.monitor-detail-active .ess-illustration{
  display:none !important;
}
body.monitor-detail-active .sidebar-footer{
  margin-top:18px;
}
.sidebar-tree-v19-head{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:10px;
  padding-bottom:12px;
  border-bottom:1px solid #edf2f8;
  margin-bottom:12px;
}
.sidebar-tree-v19-title{
  display:flex;
  align-items:center;
  gap:9px;
  font-size:17px;
  font-weight:900;
  letter-spacing:-.4px;
  color:#12233f;
}
.sidebar-tree-v19-title .icon{
  width:26px;
  height:26px;
  display:inline-flex;
  align-items:center;
  justify-content:center;
  border-radius:8px;
  background:#eaf2ff;
  color:#0969e8;
  font-size:15px;
}
.sidebar-tree-v19-refresh{
  width:30px;
  height:30px;
  border:1px solid #dce6f2;
  border-radius:10px;
  background:#fff;
  color:#526177;
  font-size:15px;
  font-weight:900;
  cursor:pointer;
}
.sidebar-tree-v19-refresh:hover{
  background:#f2f7ff;
  color:#0969e8;
  border-color:#bcd7ff;
}
.sidebar-tree-v19-site{
  padding:12px;
  border:1px solid #e4ecf6;
  border-radius:14px;
  background:#fbfdff;
  margin-bottom:12px;
}
.sidebar-tree-v19-site-name{
  display:flex;
  align-items:center;
  gap:8px;
  min-width:0;
  font-size:15px;
  font-weight:900;
  color:#10213c;
  line-height:1.25;
}
.sidebar-tree-v19-site-name .name{
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
}
.sidebar-tree-v19-meta{
  margin-top:6px;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:8px;
  font-size:12px;
  font-weight:800;
  color:#667085;
}
.sidebar-tree-v19-meta .bms{
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
}
.sidebar-tree-v19-score{
  flex:0 0 auto;
  min-width:48px;
  height:24px;
  padding:0 8px;
  display:inline-flex;
  align-items:center;
  justify-content:center;
  border-radius:999px;
  background:#fff0f0;
  color:#dc2626;
  border:1px solid #fecaca;
  font-size:12px;
  font-weight:900;
}
.sidebar-tree-v19-list,
.sidebar-tree-v19-list ul{
  list-style:none;
  margin:0;
  padding:0;
}
.sidebar-tree-v19-list ul{
  margin-left:13px;
  padding-left:13px;
  border-left:1px solid #dfe8f4;
}
.sidebar-tree-v19-list li{
  margin:4px 0;
  padding:0;
}
.sidebar-tree-v19-node{
  width:100%;
  min-height:34px;
  border:0;
  border-radius:11px;
  background:transparent;
  padding:7px 9px;
  display:flex;
  align-items:center;
  gap:8px;
  text-align:left;
  cursor:pointer;
  color:#2b3a52;
  font-size:14px;
  font-weight:850;
}
.sidebar-tree-v19-node .node-icon{
  width:22px;
  height:22px;
  border-radius:7px;
  background:#f2f6fb;
  color:#63728a;
  display:inline-flex;
  align-items:center;
  justify-content:center;
  font-size:12px;
  flex:0 0 auto;
}
.sidebar-tree-v19-node .node-text{
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
}
.sidebar-tree-v19-node:hover{
  background:#f3f7ff;
  color:#0969e8;
}
.sidebar-tree-v19-node.active{
  background:linear-gradient(180deg,#eef6ff,#e8f1ff);
  color:#0969e8;
  box-shadow:inset 0 0 0 1px #d2e5ff;
}
.sidebar-tree-v19-node.module.active{
  background:linear-gradient(180deg,#1174ff,#075de0);
  color:#fff;
  box-shadow:0 8px 18px rgba(9,105,232,.22);
}
.sidebar-tree-v19-node.active .node-icon{
  background:#dcecff;
  color:#0969e8;
}
.sidebar-tree-v19-node.module.active .node-icon{
  background:rgba(255,255,255,.18);
  color:#fff;
}
.sidebar-tree-v19-dot{
  width:10px;
  height:10px;
  border-radius:50%;
  display:inline-block;
  flex:0 0 10px;
}
.sidebar-tree-v19-dot.normal{background:#17b26a}.sidebar-tree-v19-dot.warning{background:#f59e0b}.sidebar-tree-v19-dot.abnormal{background:#ef4444}.sidebar-tree-v19-dot.offline{background:#98a2b3}
.sidebar-tree-v19-legend{
  display:flex;
  flex-wrap:wrap;
  gap:8px 10px;
  padding-top:12px;
  margin-top:12px;
  border-top:1px solid #edf2f8;
  color:#526177;
  font-size:12px;
  font-weight:850;
}
.sidebar-tree-v19-legend span{
  display:inline-flex;
  align-items:center;
  gap:5px;
}
.sidebar-tree-v19-empty{
  padding:18px 6px;
  color:#738399;
  font-size:13px;
  font-weight:800;
  text-align:center;
}
body:not(.monitor-detail-active) #sidebarHierarchyTree,
body:not(.monitor-detail-active) .sidebar-tree-card{
  display:none !important;
}
'''
css_v19_path.write_text(css_v19, encoding='utf-8')

# 4) refined JS: only render in detail mode, only current selected site
js_v19 = r'''// v19 refined sidebar hierarchy tree
(function () {
  function esc(value) {
    try {
      if (typeof escapeHtml === 'function') return escapeHtml(value);
    } catch (_) {}
    return String(value ?? '').replace(/[&<>'"]/g, function (ch) {
      return {'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch];
    });
  }

  function getAppState() {
    try { return state; } catch (_) { return null; }
  }

  function getSite() {
    try {
      if (typeof currentSite === 'function') return currentSite();
    } catch (_) {}
    const s = getAppState();
    return s?.sites?.find?.((item) => String(item.site_id) === String(s.selectedSiteId)) || s?.sites?.[0] || null;
  }

  function number(value, fallback) {
    const n = Number(value);
    return Number.isFinite(n) && n > 0 ? Math.floor(n) : fallback;
  }

  function statusFromScore(score) {
    const n = Number(score);
    if (!Number.isFinite(n)) return 'normal';
    if (n >= 71) return 'abnormal';
    if (n >= 40) return 'warning';
    return 'normal';
  }

  function dot(status) {
    const s = String(status || 'normal').toLowerCase();
    if (s === 'abnormal' || s === 'danger') return '<span class="sidebar-tree-v19-dot abnormal"></span>';
    if (s === 'warning' || s === 'caution') return '<span class="sidebar-tree-v19-dot warning"></span>';
    if (s === 'offline' || s === 'unavailable') return '<span class="sidebar-tree-v19-dot offline"></span>';
    return '<span class="sidebar-tree-v19-dot normal"></span>';
  }

  function isDetailPage() {
    const s = getAppState();
    return s?.page === 'detail';
  }

  function setModeClass() {
    document.body.classList.toggle('monitor-detail-active', isDetailPage());
  }

  function setLevelSafe(level) {
    const s = getAppState();
    if (s) s.level = level;
    if (typeof renderDetail === 'function') {
      renderDetail();
    } else if (typeof window.renderDetail === 'function') {
      window.renderDetail();
    }
    setTimeout(renderSidebarHierarchyTreeV19, 80);
  }
  window.setLevelFromSidebarTree = setLevelSafe;

  function buildTree(site) {
    const rackCount = Math.max(1, Math.min(number(site?.rack_count, 1), 6));
    const stringCount = Math.max(1, Math.min(number(site?.string_count, 1), 3));
    const moduleCount = Math.max(1, Math.min(number(site?.module_count, 1), 24));
    const s = getAppState();
    const activeLevel = s?.level || 'module';

    const selectedRack = Math.max(1, Math.min(number(site?.selected_rack_no, 1), rackCount));
    const selectedString = Math.max(1, Math.min(number(site?.selected_string_no, 1), stringCount));
    const selectedModule = Math.max(1, Math.min(number(site?.selected_module_no, 1), moduleCount));
    const modulesPerRack = Math.max(1, Math.ceil(moduleCount / rackCount));

    let html = '';
    html += '<div class="sidebar-tree-v19-head">';
    html += '<div class="sidebar-tree-v19-title"><span class="icon">▦</span><b>계층 구조 탐색</b></div>';
    html += '<button type="button" class="sidebar-tree-v19-refresh" title="새로고침" onclick="renderSidebarHierarchyTreeV19()">↻</button>';
    html += '</div>';

    html += '<div class="sidebar-tree-v19-site">';
    html += '<div class="sidebar-tree-v19-site-name">' + dot(site?.status || statusFromScore(site?.latest_score)) + '<span class="name">' + esc(site?.site_name || 'ESS Site') + '</span></div>';
    html += '<div class="sidebar-tree-v19-meta"><span class="bms">' + esc(site?.bms_id || '-') + '</span><span class="sidebar-tree-v19-score">' + esc(site?.latest_score ?? '-') + '</span></div>';
    html += '</div>';

    html += '<ul class="sidebar-tree-v19-list">';
    html += '<li><button type="button" class="sidebar-tree-v19-node ' + (activeLevel === 'bank' ? 'active' : '') + '" onclick="setLevelFromSidebarTree(\'bank\')"><span class="node-icon">B</span><span class="node-text">Bank 01</span></button>';
    html += '<ul>';

    for (let rack = 1; rack <= rackCount; rack += 1) {
      const rackActive = activeLevel === 'rack' && rack === selectedRack;
      html += '<li><button type="button" class="sidebar-tree-v19-node ' + (rackActive ? 'active' : '') + '" onclick="setLevelFromSidebarTree(\'rack\')"><span class="node-icon">R</span><span class="node-text">Rack ' + String(rack).padStart(2, '0') + '</span></button>';

      if (rack === selectedRack) {
        html += '<ul>';
        for (let stringNo = 1; stringNo <= stringCount; stringNo += 1) {
          const stringActive = activeLevel === 'string' && stringNo === selectedString;
          html += '<li><button type="button" class="sidebar-tree-v19-node ' + (stringActive ? 'active' : '') + '" onclick="setLevelFromSidebarTree(\'string\')"><span class="node-icon">S</span><span class="node-text">String ' + String(stringNo).padStart(2, '0') + '</span></button>';
          if (stringNo === selectedString) {
            html += '<ul>';
            const start = (rack - 1) * modulesPerRack + 1;
            const end = Math.min(moduleCount, start + modulesPerRack - 1);
            for (let moduleNo = start; moduleNo <= end; moduleNo += 1) {
              const moduleActive = activeLevel === 'module' && moduleNo === selectedModule;
              html += '<li><button type="button" class="sidebar-tree-v19-node module ' + (moduleActive ? 'active' : '') + '" onclick="setLevelFromSidebarTree(\'module\')"><span class="node-icon">M</span><span class="node-text">Module ' + String(moduleNo).padStart(2, '0') + '</span></button></li>';
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
    html += '<div class="sidebar-tree-v19-legend"><span>' + dot('normal') + '정상</span><span>' + dot('warning') + '주의</span><span>' + dot('abnormal') + '비정상</span><span>' + dot('offline') + '오프라인</span></div>';
    return html;
  }

  function renderSidebarHierarchyTreeV19() {
    const target = document.getElementById('sidebarHierarchyTree');
    if (!target) return;
    setModeClass();

    if (!isDetailPage()) {
      target.innerHTML = '';
      return;
    }

    const site = getSite();
    if (!site) {
      target.innerHTML = '<div class="sidebar-tree-v19-empty">선택된 사이트가 없습니다.</div>';
      return;
    }

    target.innerHTML = buildTree(site);
  }

  window.renderSidebarHierarchyTreeV19 = renderSidebarHierarchyTreeV19;
  window.renderSidebarHierarchyTree = renderSidebarHierarchyTreeV19;

  function wrap(name, afterDelay) {
    const fn = window[name];
    if (typeof fn !== 'function' || fn.__v19Wrapped) return;
    const wrapped = function () {
      const result = fn.apply(this, arguments);
      Promise.resolve(result).finally(function () {
        setTimeout(renderSidebarHierarchyTreeV19, afterDelay || 80);
      });
      return result;
    };
    wrapped.__v19Wrapped = true;
    window[name] = wrapped;
  }

  document.addEventListener('DOMContentLoaded', function () {
    wrap('nav', 120);
    wrap('selectSite', 160);
    wrap('setLevel', 120);
    setTimeout(renderSidebarHierarchyTreeV19, 200);
    setInterval(renderSidebarHierarchyTreeV19, 1200);
  });

  if (document.readyState !== 'loading') {
    setTimeout(function () {
      wrap('nav', 120);
      wrap('selectSite', 160);
      wrap('setLevel', 120);
      renderSidebarHierarchyTreeV19();
    }, 120);
  }
})();
'''
js_v19_path.write_text(js_v19, encoding='utf-8')

print('v19 sidebar tree polish patch applied successfully.')
print(f'- updated: {index_path}')
print(f'- created/updated: {css_v19_path}')
print(f'- created/updated: {js_v19_path}')
