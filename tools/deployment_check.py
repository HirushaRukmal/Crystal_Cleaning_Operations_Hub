"""Public smoke test. No credentials or personal data required.
Usage: python tools/deployment_check.py https://your-site.onrender.com
"""
import sys, json, urllib.request, urllib.error
from urllib.parse import urlsplit
if len(sys.argv)!=2:raise SystemExit('Usage: python tools/deployment_check.py https://your-site.onrender.com')
base=sys.argv[1].rstrip('/')
if urlsplit(base).scheme!='https':raise SystemExit('An HTTPS URL is required')
for path,expected in [('/api/health','application/json'),('/api/bootstrap','application/json'),('/','text/html'),('/static/app.js','javascript')]:
    with urllib.request.urlopen(base+path,timeout=150) as response:
        body=response.read()
        ctype=response.headers.get('Content-Type','')
        assert response.status==200 and expected in ctype, (path,response.status,ctype)
        print(f'PASS {path} HTTP {response.status} ({len(body)} bytes)')
print('Basic public deployment smoke check passed. Database writes, user permissions and scheduled jobs still need manual verification.')
