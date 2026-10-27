#!/usr/bin/env python3
"""End-to-end live QuickML test: OAuth token → predict endpoint.
Tries payload shapes in order: array-of-records (with timestamp), single-object.
"""
import json
import os
import sys
import time
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from features import add_features, QUICKML_PAYLOAD_COLS  # noqa: E402
import pandas as pd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
env = {}
for line in open(os.path.join(ROOT, ".env")):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

# 1. OAuth token (retry — TLS flaky)
token = None
for attempt in range(6):
    try:
        r = requests.post(
            "https://accounts.zoho.in/oauth/v2/token",
            data={
                "client_id": env["CLIENT_ID"],
                "client_secret": env["CLIENT_SECRET"],
                "grant_type": "client_credentials",
                "scope": "QuickML.deployment.READ",
            },
            timeout=25,
        )
        if r.status_code == 200 and "access_token" in r.json():
            token = r.json()["access_token"]
            break
        print(f"  token attempt {attempt+1}: HTTP {r.status_code} {r.text[:120]}")
    except Exception as e:
        print(f"  token attempt {attempt+1}: {type(e).__name__}")
    time.sleep(2)
if not token:
    print("FAILED to get OAuth token"); sys.exit(1)
print("✓ Got OAuth token")

# 2. Build records (with timestamp, matching the model's Sample Request)
rows = []
for i in range(24):
    rows.append({
        "timestamp": f"2015-02-{15 if i < 12 else 16} {i:02d}:00:00",
        "ambient_temp_c": 17.25 + i * 0.3,
        "humidity_pct": 77.32 - i * 0.5,
        "solar_irradiance_wm2": 256 - i * 10,
    })
df = pd.DataFrame(rows)
records = add_features(df)[QUICKML_PAYLOAD_COLS].to_dict(orient="records")

headers = {
    "Content-Type": "application/json",
    "X-QUICKML-ENDPOINT-KEY": env["QUICKML_API_KEY"],
    "Authorization": f"Zoho-oauthtoken {token}",
    "CATALYST-ORG": env.get("CATALYST_ORG", ""),
    "Environment": env.get("CATALYST_ENVIRONMENT", "Development"),
}
URL = env["QUICKML_ENDPOINT_URL"]

# 3. Try payload shapes
attempts = [
    ("array of 24 records", {"data": records}),
    ("single record object", {"data": records[0]}),
    ("array without wrapper", records),
]
ok = False
for label, payload in attempts:
    resp = requests.post(URL, json=payload, headers=headers, timeout=60)
    print(f"\n=== {label} → HTTP {resp.status_code}")
    print(resp.text[:600])
    if resp.status_code == 200:
        out = resp.json()
        preds = out.get("result") or out.get("predictions")
        print(f"✓ Got {len(preds) if preds else '?'} prediction(s)")
        if preds:
            print(f"  Value: {preds}")
        ok = True
        break

if not ok:
    sys.exit(1)
