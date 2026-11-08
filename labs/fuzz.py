#!/usr/bin/env python3
# 简易目录/参数爆破器（本地靶场用）
import sys, requests
from concurrent.futures import ThreadPoolExecutor

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8899"
WORDS = ["", "admin", "login", "api", "search", "ping", "read", "files",
         "backup.zip", ".git/config", "config.php", "robots.txt", "user",
         "api/user/1", "api/user/2", "db.sql", "index.php", "upload"]

def probe(w):
    url = f"{BASE}/{w}"
    try:
        r = requests.get(url, timeout=4, allow_redirects=False)
        return (r.status_code, len(r.content), url)
    except Exception as e:
        return (0, 0, url)

with ThreadPoolExecutor(max_workers=10) as ex:
    for code, size, url in sorted(ex.map(probe, WORDS), reverse=True):
        flag = "✅" if code in (200, 301, 302, 403) else "  "
        print(f"{flag} {code:>4}  {size:>6}B  {url}")
