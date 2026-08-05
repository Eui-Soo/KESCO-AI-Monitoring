# -*- coding: utf-8 -*-
from pathlib import Path
from datetime import datetime
import re, shutil
root = Path.cwd()
base = Path(__file__).resolve().parents[1]
mon = root / 'static' / 'monitor'
mon.mkdir(parents=True, exist_ok=True)
stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
for name in ['monitor.js','monitor.css','index.html']:
    p = mon / name
    if p.exists():
        p.with_suffix(p.suffix + f'.bak_v27_{stamp}').write_text(p.read_text(encoding='utf-8', errors='ignore'), encoding='utf-8')
shutil.copyfile(base / 'static' / 'monitor' / 'monitor.js', mon / 'monitor.js')
shutil.copyfile(base / 'static' / 'monitor' / 'monitor.css', mon / 'monitor.css')
idx = mon / 'index.html'
if idx.exists():
    s = idx.read_text(encoding='utf-8', errors='ignore')
    if 'charset' not in s.lower():
        s = s.replace('<head>', '<head>\n  <meta charset="utf-8" />')
    s = re.sub(r'/static/monitor/monitor\.css(?:\?v=\d+)?', '/static/monitor/monitor.css?v=27', s)
    s = re.sub(r'/static/monitor/monitor\.js(?:\?v=\d+)?', '/static/monitor/monitor.js?v=27', s)
    idx.write_text(s, encoding='utf-8')
else:
    idx.write_text('<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>KESCO Monitoring</title><link rel="stylesheet" href="/static/monitor/monitor.css?v=27"></head><body><div id="app"></div><script src="/static/monitor/monitor.js?v=27"></script></body></html>', encoding='utf-8')
# fix monitor_service.py broken backslash if still present
svc = root / 'service' / 'monitor_service.py'
if svc.exists():
    txt = svc.read_text(encoding='utf-8', errors='ignore')
    txt = txt.replace('replace("\\", "_")', 'replace("\\\\", "_")')
    # handle the exact broken literal by line rewrite
    lines=[]
    for line in txt.splitlines():
        if 'safe_bms_id = str(bms_id).strip()' in line and 'replace("/", "_")' in line:
            indent = line[:len(line)-len(line.lstrip())]
            line = indent + 'safe_bms_id = str(bms_id).strip().replace(" ", "_").replace("/", "_").replace("\\\\", "_")'
        lines.append(line)
    svc.write_text('\n'.join(lines)+'\n', encoding='utf-8')
print('[OK] v27 stable monitor applied')
print('[OK] backups saved with suffix .bak_v27_' + stamp)
