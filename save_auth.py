import json
import urllib.request
import time

platforms = ['tiktok', 'facebook', 'instagram', 'google_flow', 'capcut']

for p in platforms:
    body = json.dumps({"platform": p}).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:8081/api/auth/save",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            print(p, ":", r.read().decode())
    except Exception as e:
        print(p, ":", e)
    time.sleep(0.5)
