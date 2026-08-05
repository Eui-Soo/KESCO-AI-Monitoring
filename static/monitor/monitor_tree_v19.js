// v19 refined sidebar hierarchy tree
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
