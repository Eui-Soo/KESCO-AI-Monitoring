from pathlib import Path
import re

ROOT = Path.cwd()
js_path = ROOT / "static" / "monitor" / "monitor.js"
html_path = ROOT / "static" / "monitor" / "index.html"

if not js_path.exists():
    raise FileNotFoundError(f"not found: {js_path}")

text = js_path.read_text(encoding="utf-8", errors="replace")
backup = js_path.with_suffix(".js.v25.bak")
backup.write_text(text, encoding="utf-8")

fallback_sites = '''const fallbackSites = [
  { site_id:'SITE-0021', site_no:21, site_name:'Yeonggwang ESS Unit 2', region:'Jeonnam Yeonggwang', install_area:'Southwest Power Area', manufacturer:'Samsung SDI', installed_at:'2024-11-15', latest_score:93.7, status:'abnormal', status_text:'Abnormal', last_analysis_time:'2025-05-19 10:20:15', risk_location:'Bank 01 > Rack 03 > String 02 > Module 05 > Cell 07' },
  { site_id:'SITE-0022', site_no:22, site_name:'Pyeongtaek ESS Unit 1', region:'Gyeonggi Pyeongtaek', install_area:'South Gyeonggi Area', manufacturer:'LG Energy Solution', installed_at:'2024-08-21', latest_score:87.2, status:'abnormal', status_text:'Abnormal', last_analysis_time:'2025-05-19 10:15:12', risk_location:'Bank 01 > Rack 01 > String 04 > Module 02 > Cell 12' },
  { site_id:'SITE-0023', site_no:23, site_name:'Gunsan ESS Unit 3', region:'Jeonbuk Gunsan', install_area:'East Power Area', manufacturer:'Samsung SDI', installed_at:'2024-09-30', latest_score:72.4, status:'warning', status_text:'Warning', last_analysis_time:'2025-05-19 10:18:09', risk_location:'Bank 01 > Rack 02 > String 01 > Module 08' },
  { site_id:'SITE-0024', site_no:24, site_name:'Gimhae ESS Unit 1', region:'Gyeongnam Gimhae', install_area:'West Gyeongnam Area', manufacturer:'LG Energy Solution', installed_at:'2024-07-10', latest_score:68.1, status:'warning', status_text:'Warning', last_analysis_time:'2025-05-19 10:10:23', risk_location:'Bank 01 > Rack 04 > String 03' },
  { site_id:'SITE-0025', site_no:25, site_name:'Jeju ESS Unit 2', region:'Jeju', install_area:'Jeju Area', manufacturer:'CATL', installed_at:'2024-12-05', latest_score:34.6, status:'normal', status_text:'Normal', last_analysis_time:'2025-05-19 10:05:08', risk_location:'-' },
  { site_id:'SITE-0026', site_no:26, site_name:'Ulsan ESS Unit 1', region:'Ulsan Ulju', install_area:'East Yeongnam Area', manufacturer:'LG Energy Solution', installed_at:'2024-10-22', latest_score:null, status:'unavailable', status_text:'Unavailable', last_analysis_time:null, risk_location:'-' },
];

const state ='''
text, n = re.subn(r"const fallbackSites\s*=\s*\[[\s\S]*?\];\s*\n\s*const state\s*=", fallback_sites, text, count=1)
print(f"[v25] fallbackSites replaced: {n}")

status_text_func = '''function statusText(siteOrStatus) {
  const raw = typeof siteOrStatus === 'string'
    ? siteOrStatus
    : (siteOrStatus?.status || siteOrStatus?.status_text || 'normal');
  const key = String(raw || 'normal').toLowerCase();
  if (key === 'abnormal' || key === 'danger') return 'Abnormal';
  if (key === 'warning' || key === 'caution') return 'Warning';
  if (key === 'normal') return 'Normal';
  if (key === 'unavailable' || key === 'offline') return 'Unavailable';
  if (key === 'data_missing') return 'Data Missing';
  return String(raw || 'Normal');
}

function statusClassByText(text) {
  const value = String(typeof text === 'string' ? text : (text?.status || text?.status_text || '')).toLowerCase();
  if (value === 'normal') return 'good';
  if (value === 'warning' || value === 'caution') return 'warn';
  if (value === 'abnormal' || value === 'danger') return 'bad';
  return 'gray';
}
'''
text, n = re.subn(r"function statusText\(siteOrStatus\)\s*\{[\s\S]*?\}\s*\n\s*function statusClassByText\(text\)\s*\{[\s\S]*?\}\s*", status_text_func, text, count=1)
print(f"[v25] statusText/statusClassByText replaced: {n}")

clean_status_ko = '''function v23StatusKo(status) {
  const key = String(status || '').toLowerCase();
  if (key === 'abnormal' || key === 'danger') return 'Abnormal';
  if (key === 'warning' || key === 'caution') return 'Warning';
  if (key === 'normal') return 'Normal';
  if (key === 'offline' || key === 'unavailable') return 'Offline';
  return 'Normal';
}
'''
text, n = re.subn(r"function v23StatusKo\(status\)\s*\{[\s\S]*?\}\s*", clean_status_ko, text, count=1)
print(f"[v25] v23StatusKo replaced: {n}")

text, n = re.subn(
    r"html\s*\+=\s*`<div class=\"tree-legend\">[\s\S]*?</div>`;",
    "html += `<div class=\"tree-legend\"><span><i class=\"tree-dot normal\"></i>Normal</span><span><i class=\"tree-dot warning\"></i>Warning</span><span><i class=\"tree-dot abnormal\"></i>Abnormal</span><span><i class=\"tree-dot offline\"></i>Offline</span></div>`;",
    text
)
print(f"[v25] tree legend replaced: {n}")

replace_map = {
    "鍮꾩젙??": "Abnormal",
    "二쇱쓽": "Warning",
    "?뺤긽": "Normal",
    "?ㅽ봽?쇱씤": "Offline",
    "利됱떆 ?먭? 沅뚭퀬": "Immediate inspection required",
    "二쇱쓽 愿李??꾩슂": "Caution monitoring required",
    "?뺤긽 ?댁쟾": "Normal operation",
    "쨌": "·",
}
for bad, good in replace_map.items():
    text = text.replace(bad, good)

js_path.write_text(text, encoding="utf-8")

if html_path.exists():
    h = html_path.read_text(encoding="utf-8", errors="replace")
    h = re.sub(r"monitor\.css(?:\?v=\d+)?", "monitor.css?v=25", h)
    h = re.sub(r"monitor_v7_fix\.css(?:\?v=\d+)?", "monitor_v7_fix.css?v=25", h)
    h = re.sub(r"monitor\.js(?:\?v=\d+)?", "monitor.js?v=25", h)
    html_path.with_suffix(".html.v25.bak").write_text(h, encoding="utf-8")
    html_path.write_text(h, encoding="utf-8")
    print("[v25] index.html cache version bumped to v25")

print("[v25] done")
print(f"[v25] backup: {backup}")
