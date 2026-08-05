from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
index_path = ROOT / "static" / "monitor" / "index.html"
js_path = ROOT / "static" / "monitor" / "monitor.js"
css_path = ROOT / "static" / "monitor" / "monitor_v17_ui_fix.css"

if not index_path.exists():
    raise FileNotFoundError(index_path)
if not js_path.exists():
    raise FileNotFoundError(js_path)

index_text = index_path.read_text(encoding="utf-8")
js_text = js_path.read_text(encoding="utf-8")

(index_path.with_suffix(index_path.suffix + ".v17.bak")).write_text(index_text, encoding="utf-8")
(js_path.with_suffix(js_path.suffix + ".v17.bak")).write_text(js_text, encoding="utf-8")

css_link = '  <link rel="stylesheet" href="/static/monitor/monitor_v17_ui_fix.css" />'
if "monitor_v17_ui_fix.css" not in index_text:
    if '  <link rel="stylesheet" href="/static/monitor/monitor_v7_fix.css" />' in index_text:
        index_text = index_text.replace(
            '  <link rel="stylesheet" href="/static/monitor/monitor_v7_fix.css" />',
            '  <link rel="stylesheet" href="/static/monitor/monitor_v7_fix.css" />\n' + css_link
        )
    else:
        index_text = index_text.replace("</head>", css_link + "\n</head>")

old_site_options = """function siteOptions() {
  return state.sites.map((s) => `<option value="${escapeHtml(s.site_id)}" ${String(s.site_id) === String(state.selectedSiteId) ? 'selected' : ''}>${escapeHtml(s.site_name)}</option>`).join('');
}"""
new_site_options = """function siteOptions() {
  return state.sites.map((s) => {
    const label = `${s.site_name || s.site_id} / ${s.bms_id || '-'}`;
    return `<option value="${escapeHtml(s.site_id)}" ${String(s.site_id) === String(state.selectedSiteId) ? 'selected' : ''}>${escapeHtml(label)}</option>`;
  }).join('');
}"""
if old_site_options in js_text:
    js_text = js_text.replace(old_site_options, new_site_options)

marker = """    const cells = Array.isArray(level.cells) ? level.cells : [18,22,31,26,29,34,92,45,28,33,24,37,41,27,39,32,30,25,48,21].map((v,i) => ({ cell_no:i+1, score:v, status:v>=80?'abnormal':v>=40?'warning':'normal', voltage:(3.62 + i/1000).toFixed(3), temperature:(30 + v/8).toFixed(1) }));"""
insert = marker + """

    const bankNo = Number(level.bank_no || site.selected_bank_no || 1);
    const rackNo = Number(level.rack_no || site.selected_rack_no || 1);
    const stringNo = Number(level.string_no || site.selected_string_no || 1);
    const moduleNo = Number(level.module_no || site.selected_module_no || 1);
    const levelTitleMap = { bank: 'Bank 상세', rack: 'Rack 상세', string: 'String 상세', module: 'Module 상세' };
    const levelTitle = levelTitleMap[state.level] || 'Module 상세';
    const riskLocation = level.risk_location || site.risk_location || '-';
    const breadcrumbText = `사이트 목록 > ${site.site_name || site.site_id} > Bank ${String(bankNo).padStart(2,'0')} > Rack ${String(rackNo).padStart(2,'0')} > String ${String(stringNo).padStart(2,'0')} > Module ${String(moduleNo).padStart(2,'0')}`;
"""
if marker in js_text and "const breadcrumbText =" not in js_text:
    js_text = js_text.replace(marker, insert)

js_text = js_text.replace(
"""        <div class="breadcrumb">사이트 목록 <span>›</span> ${escapeHtml(site.site_name)} <span>›</span> Bank 01 <span>›</span> Rack 03 <span>›</span> String 02 <span>›</span> Module 05</div>""",
"""        <div class="breadcrumb">${escapeHtml(breadcrumbText)}</div>"""
)
js_text = js_text.replace(
"""        <div class="detail-title detail-title-row"><div class="site-icon">▦</div><div><h1>${escapeHtml(site.site_name)} <span>›</span> Module 상세</h1><p>${escapeHtml(site.region)} · ${escapeHtml(site.manufacturer)} · ${escapeHtml(site.bms_id || '')}</p></div><select class="site-select" onchange="selectSite(this.value)">${siteOptions()}</select></div>""",
"""        <div class="detail-title detail-title-row"><div class="site-icon">▦</div><div><h1>${escapeHtml(site.site_name)} <span>›</span> ${escapeHtml(levelTitle)}</h1><p>${escapeHtml(site.region)} · ${escapeHtml(site.manufacturer)} · ${escapeHtml(site.bms_id || '')}</p></div><select class="site-select" onchange="selectSite(this.value)">${siteOptions()}</select></div>"""
)
js_text = js_text.replace(
"""<div class="info-card"><small>위험 위치</small><b>${escapeHtml(site.risk_location || '-')}</b></div>""",
"""<div class="info-card"><small>위험 위치</small><b>${escapeHtml(riskLocation)}</b></div>"""
)

js_text = js_text.replace(
"""<div class="cell ${c.status === 'abnormal' ? 'bad' : c.status === 'warning' ? 'warn' : 'good'}"><b>${String(c.cell_no).padStart(2,'0')}</b><span>${escapeHtml(c.score)}</span></div>""",
"""<div class="cell ${c.status === 'abnormal' ? 'bad' : c.status === 'warning' ? 'warn' : 'good'}"><b>Cell ${String(c.cell_no).padStart(2,'0')}</b><span>${escapeHtml(c.score)}</span></div>"""
)

css_text = """:root {
  --v17-blue: #0969e8;
  --v17-line: #dce6f2;
  --v17-text: #0b1b36;
  --v17-green: #17b26a;
}

.detail-page {
  display: grid !important;
  grid-template-columns: minmax(0, 1fr) 420px !important;
  gap: 28px !important;
  align-items: start !important;
}

.detail-left,
.detail-right {
  min-width: 0;
}

.breadcrumb {
  display: flex !important;
  flex-wrap: wrap !important;
  gap: 8px !important;
  align-items: center !important;
  color: #64748b !important;
  font-weight: 800 !important;
  margin: 0 0 22px !important;
}

.detail-title-row {
  display: grid !important;
  grid-template-columns: 78px minmax(0, 1fr) 420px !important;
  gap: 18px !important;
  align-items: center !important;
  margin-bottom: 24px !important;
}

.detail-title-row h1 {
  margin: 0 0 8px !important;
  font-size: 34px !important;
  letter-spacing: -1px !important;
  color: var(--v17-text) !important;
}

.detail-title-row p {
  margin: 0 !important;
  color: #334155 !important;
  font-weight: 750 !important;
}

.site-select {
  height: 48px !important;
  border: 1px solid var(--v17-line) !important;
  border-radius: 12px !important;
  background: #fff !important;
  padding: 0 14px !important;
  font-weight: 800 !important;
  color: #10213d !important;
  min-width: 0 !important;
  width: 100% !important;
}

.level-tabs {
  display: inline-flex !important;
  gap: 8px !important;
  padding: 4px !important;
  border: 1px solid var(--v17-line) !important;
  border-radius: 14px !important;
  background: #f3f7fc !important;
  margin: 0 0 16px !important;
}

.level-tab {
  height: 42px !important;
  min-width: 86px !important;
  border: 0 !important;
  border-radius: 11px !important;
  background: transparent !important;
  color: #475569 !important;
  font-weight: 900 !important;
  cursor: pointer !important;
}

.level-tab.active {
  background: #fff !important;
  color: var(--v17-blue) !important;
  box-shadow: 0 4px 12px rgba(9, 105, 232, .12) !important;
}

.detail-grid-top {
  display: grid !important;
  grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
  gap: 14px !important;
  margin-bottom: 16px !important;
}

.info-card {
  min-height: 86px !important;
  border: 1px solid var(--v17-line) !important;
  border-radius: 16px !important;
  background: #fff !important;
  box-shadow: 0 8px 22px rgba(23,43,77,.06) !important;
  padding: 18px 20px !important;
  display: flex !important;
  flex-direction: column !important;
  align-items: flex-start !important;
  justify-content: center !important;
  gap: 10px !important;
}

.info-card small {
  color: #64748b !important;
  font-size: 13px !important;
  font-weight: 900 !important;
}

.info-card b {
  color: #0b1b36 !important;
  font-size: 16px !important;
  font-weight: 900 !important;
  word-break: break-word !important;
}

.cell-map {
  display: grid !important;
  grid-template-columns: repeat(5, minmax(90px, 1fr)) !important;
  gap: 12px !important;
  padding: 20px !important;
}

.cell {
  height: 74px !important;
  border-radius: 12px !important;
  display: flex !important;
  flex-direction: column !important;
  justify-content: center !important;
  align-items: center !important;
  gap: 8px !important;
  font-weight: 900 !important;
  border: 1px solid #dce6f2 !important;
}

.cell b {
  display: block !important;
  font-size: 13px !important;
  color: #475569 !important;
  line-height: 1 !important;
}

.cell span {
  display: block !important;
  font-size: 22px !important;
  line-height: 1 !important;
}

.cell.good {
  background: #ecfdf5 !important;
  border-color: #cdeedc !important;
  color: var(--v17-green) !important;
}

.cell.warn {
  background: #fff7e6 !important;
  border-color: #fde7b1 !important;
  color: #c77b00 !important;
}

.cell.bad {
  background: #fff1f2 !important;
  border-color: #fecaca !important;
  color: #dc2626 !important;
}

@media (max-width: 1280px) {
  .detail-page {
    grid-template-columns: 1fr !important;
  }

  .detail-title-row {
    grid-template-columns: 78px minmax(0, 1fr) !important;
  }

  .site-select {
    grid-column: 1 / -1;
  }

  .detail-grid-top {
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
  }
}
"""

index_path.write_text(index_text, encoding="utf-8")
js_path.write_text(js_text, encoding="utf-8")
css_path.write_text(css_text, encoding="utf-8")

print("[OK] v17 monitor UI patch applied.")
print(f"[OK] updated: {index_path}")
print(f"[OK] updated: {js_path}")
print(f"[OK] created: {css_path}")
print("[OK] backups:")
print(f" - {index_path.with_suffix(index_path.suffix + '.v17.bak')}")
print(f" - {js_path.with_suffix(js_path.suffix + '.v17.bak')}")
