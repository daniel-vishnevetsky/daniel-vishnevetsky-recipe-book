#!/usr/bin/env python3
import csv
import html
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import requests

INPUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('recipe_links.csv')
OUTDIR = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('reports')
OUTDIR.mkdir(parents=True, exist_ok=True)

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36 RecipeLinkAudit/1.0'
HEADERS = {
    'User-Agent': UA,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7',
}
TIMEOUT = 15
MAX_WORKERS = 6
MAX_BYTES = 300_000

SOFT_404_TERMS = [
    '404', 'page not found', 'not found', 'page unavailable',
    'העמוד לא נמצא', 'הדף לא נמצא', 'לא נמצא', 'עמוד לא קיים'
]

def read_title(text):
    m = re.search(r'<title[^>]*>(.*?)</title>', text, re.I | re.S)
    if not m:
        return ''
    title = re.sub(r'<[^>]+>', ' ', m.group(1))
    title = re.sub(r'\s+', ' ', html.unescape(title)).strip()
    return title[:300]

def looks_like_home_redirect(original, final):
    o = urlparse(original)
    f = urlparse(final)
    opath = (o.path or '/').rstrip('/')
    fpath = (f.path or '/').rstrip('/')
    if opath in ('', '/'):
        return False
    # Specific recipe URL ending up on a homepage/root is suspicious even if HTTP 200.
    if fpath in ('', '/'):
        return True
    # Also flag obvious generic landing paths after a redirect.
    generic = {'/home', '/index', '/index.html', '/recipes', '/recipe'}
    if fpath.lower() in generic and opath.lower() != fpath.lower():
        return True
    return False

def classify_http(status):
    if status in (404, 410):
        return 'BROKEN'
    if status in (401, 403, 429):
        return 'BLOCKED'
    if 500 <= status <= 599:
        return 'SERVER_ERROR'
    if 400 <= status <= 499:
        return 'BROKEN'
    if 200 <= status <= 299:
        return 'OK'
    return 'CHECK'

def check_one(row):
    url = row['url'].strip()
    result = dict(row)
    result.update({
        'status': '', 'http_status': '', 'final_url': '', 'page_title': '', 'note': ''
    })
    try:
        with requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True,
                          stream=True) as r:
            result['http_status'] = str(r.status_code)
            result['final_url'] = r.url
            base = classify_http(r.status_code)
            content_type = (r.headers.get('content-type') or '').lower()
            body = b''
            if 'text/html' in content_type or 'application/xhtml' in content_type or not content_type:
                for chunk in r.iter_content(chunk_size=16384):
                    if chunk:
                        body += chunk
                        if len(body) >= MAX_BYTES:
                            break
                enc = r.encoding or 'utf-8'
                text = body.decode(enc, errors='replace')
                title = read_title(text)
                result['page_title'] = title
                low = (title + ' ' + text[:10000]).lower()
            else:
                low = ''

            if base == 'OK':
                if looks_like_home_redirect(url, r.url):
                    result['status'] = 'SUSPICIOUS'
                    result['note'] = 'הקישור הספציפי הגיע לדף בית/דף כללי'
                elif any(term.lower() in low for term in SOFT_404_TERMS):
                    result['status'] = 'SUSPICIOUS'
                    result['note'] = 'העמוד מחזיר 200 אבל נראה כמו דף שגיאה/404'
                elif r.history:
                    result['status'] = 'REDIRECT_OK'
                    result['note'] = f'הופנה {len(r.history)} פעם/פעמים לכתובת חדשה'
                else:
                    result['status'] = 'OK'
                    result['note'] = 'נפתח בהצלחה'
            else:
                result['status'] = base
                if base == 'BLOCKED':
                    result['note'] = 'האתר חסם בדיקה אוטומטית; לא בהכרח קישור שבור'
                elif base == 'SERVER_ERROR':
                    result['note'] = 'שגיאת שרת; כדאי לבדוק שוב'
                elif base == 'BROKEN':
                    result['note'] = f'HTTP {r.status_code}'
                else:
                    result['note'] = f'HTTP {r.status_code}'
    except requests.exceptions.Timeout:
        result['status'] = 'TIMEOUT'
        result['note'] = 'האתר לא ענה בזמן; דורש בדיקה חוזרת/ידנית'
    except requests.exceptions.SSLError as e:
        result['status'] = 'SSL_ERROR'
        result['note'] = 'שגיאת SSL'
    except requests.exceptions.ConnectionError as e:
        msg = str(e)
        result['status'] = 'BROKEN'
        if 'NameResolution' in msg or 'getaddrinfo' in msg or 'Failed to resolve' in msg:
            result['note'] = 'הדומיין לא נפתר (DNS)'
        else:
            result['note'] = 'לא ניתן להתחבר לשרת'
    except Exception as e:
        result['status'] = 'CHECK'
        result['note'] = f'{type(e).__name__}: {str(e)[:160]}'

    time.sleep(0.10)
    return result

with INPUT.open(encoding='utf-8-sig', newline='') as f:
    rows = list(csv.DictReader(f))

print(f'Checking {len(rows)} unique recipe links...')
results = []
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
    futs = {ex.submit(check_one, row): row for row in rows}
    done = 0
    for fut in as_completed(futs):
        results.append(fut.result())
        done += 1
        if done % 50 == 0 or done == len(rows):
            print(f'  {done}/{len(rows)}')

order = {'BROKEN':0, 'SUSPICIOUS':1, 'TIMEOUT':2, 'SSL_ERROR':3, 'SERVER_ERROR':4,
         'BLOCKED':5, 'CHECK':6, 'REDIRECT_OK':7, 'OK':8}
results.sort(key=lambda r: (order.get(r['status'], 99), int(r['pages'].split(',')[0] or 9999), r.get('title','')))

fields = ['pages','title','url','domain','type','status','http_status','final_url','page_title','note']
csv_path = OUTDIR / 'link-report.csv'
with csv_path.open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader(); w.writerows(results)

from collections import Counter
counts = Counter(r['status'] for r in results)
problem_statuses = {'BROKEN','SUSPICIOUS','TIMEOUT','SSL_ERROR','SERVER_ERROR','CHECK'}
problems = [r for r in results if r['status'] in problem_statuses]
manual = [r for r in results if r['status'] == 'BLOCKED']

status_he = {
    'OK':'תקין', 'REDIRECT_OK':'תקין אחרי הפניה', 'BROKEN':'שבור',
    'SUSPICIOUS':'חשוד', 'BLOCKED':'חסום לבדיקה אוטומטית', 'TIMEOUT':'לא ענה בזמן',
    'SSL_ERROR':'שגיאת SSL', 'SERVER_ERROR':'שגיאת שרת', 'CHECK':'דורש בדיקה'
}
status_class = {
    'OK':'ok','REDIRECT_OK':'redirect','BROKEN':'bad','SUSPICIOUS':'warn','BLOCKED':'blocked',
    'TIMEOUT':'warn','SSL_ERROR':'bad','SERVER_ERROR':'warn','CHECK':'warn'
}

def esc(x): return html.escape(str(x or ''))

def tr(r):
    s = r['status']
    return f'''<tr class="{status_class.get(s,'')}">
      <td>{esc(r['pages'])}</td>
      <td>{esc(r['title'])}</td>
      <td><a href="{esc(r['url'])}" target="_blank">קישור מקורי</a></td>
      <td>{esc(r['domain'])}</td>
      <td><b>{esc(status_he.get(s,s))}</b></td>
      <td>{esc(r['http_status'])}</td>
      <td>{esc(r['note'])}</td>
      <td>{('<a href="'+esc(r['final_url'])+'" target="_blank">כתובת סופית</a>') if r['final_url'] else ''}</td>
    </tr>'''

cards = ''.join(f'<div class="card"><strong>{esc(status_he.get(k,k))}</strong><span>{v}</span></div>' for k,v in sorted(counts.items(), key=lambda kv: order.get(kv[0],99)))
html_path = OUTDIR / 'link-report.html'
html_path.write_text(f'''<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8">
<title>בדיקת קישורים - ספר המתכונים</title><style>
body{{font-family:Arial,sans-serif;margin:24px;background:#f6f7f8;color:#111}} h1{{margin-bottom:6px}}
.cards{{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0}} .card{{background:white;border:1px solid #ddd;border-radius:10px;padding:10px 14px;display:flex;gap:12px}}
.card span{{font-size:20px;font-weight:700}} table{{width:100%;border-collapse:collapse;background:white;font-size:14px}}
th,td{{border:1px solid #ddd;padding:8px;vertical-align:top}} th{{position:sticky;top:0;background:#eee}} a{{color:#0645d8}}
.bad{{background:#fff0f0}} .warn{{background:#fff8e6}} .blocked{{background:#f3f0ff}} .redirect{{background:#eff8ff}} .ok{{background:#f2fff4}}
.note{{color:#555}} .section{{margin-top:28px}}
</style></head><body>
<h1>בדיקת קישורים - ספר המתכונים</h1>
<p class="note">נבדקו {len(results)} כתובות ייחודיות מתוך עמודי המתכונים (עמ' 21-174). קישורים חסומים לא בהכרח שבורים; Instagram/Facebook ואתרים עם הגנת bot עלולים לחסום בדיקה אוטומטית.</p>
<div class="cards">{cards}</div>
<div class="section"><h2>מה דורש טיפול / בדיקה ({len(problems)})</h2>
<table><thead><tr><th>עמוד</th><th>מתכון</th><th>קישור</th><th>דומיין</th><th>מצב</th><th>HTTP</th><th>הערה</th><th>יעד סופי</th></tr></thead><tbody>
{''.join(tr(r) for r in problems)}
</tbody></table></div>
<div class="section"><h2>כל התוצאות ({len(results)})</h2>
<table><thead><tr><th>עמוד</th><th>מתכון</th><th>קישור</th><th>דומיין</th><th>מצב</th><th>HTTP</th><th>הערה</th><th>יעד סופי</th></tr></thead><tbody>
{''.join(tr(r) for r in results)}
</tbody></table></div>
</body></html>''', encoding='utf-8')

summary = os.getenv('GITHUB_STEP_SUMMARY')
if summary:
    with open(summary, 'a', encoding='utf-8') as f:
        f.write('# בדיקת קישורים - ספר המתכונים\n\n')
        f.write(f'נבדקו **{len(results)}** כתובות ייחודיות.\n\n')
        for k,v in sorted(counts.items(), key=lambda kv: order.get(kv[0],99)):
            f.write(f'- **{status_he.get(k,k)}:** {v}\n')
        f.write(f'\nקישורים שדורשים טיפול/בדיקה: **{len(problems)}**.\n')
        f.write('\nהדו״ח המלא נמצא ב-Artifact בשם `recipe-link-audit`.\n')

print('Done.')
print('CSV:', csv_path)
print('HTML:', html_path)
