#!/usr/bin/env python3
"""Probe the retrained endpoint to find the exact payload it accepts.
Tries 9-features-only, 9-features+timestamp(string), 9-features+timestamp(int)."""
import json
import os
import sys
import time
import requests
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from features import add_features, QUICKML_FEATURES  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
env = {}
for line in open(os.path.join(ROOT, ".env")):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

URL = env["QUICKML_ENDPOINT_URL"]
API_KEY = env["QUICKML_API_KEY"]

# Fresh OAuth token (TLS flaky — retry)
token = None
for _ in range(6):
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
    except Exception:
        time.sleep(2)
if not token:
    print("FAILED to get OAuth token"); sys.exit(1)

rows = [
    {"timestamp": "2015-06-16 15:00:00", "ambient_temp_c": 35.66, "humidity_pct": 56.38, "solar_irradiance_wm2": 169},
    {"timestamp": "2015-06-16 16:00:00", "ambient_temp_c": 34.55, "humidity_pct": 54.73, "solar_irradiance_wm2": 112},
]
feats = add_features(pd.DataFrame(rows))[QUICKML_FEATURES].to_dict(orient="records")

headers = {
    "Content-Type": "application/json",
    "X-QUICKML-ENDPOINT-KEY": API_KEY,
    "Authorization": f"Zoho-oauthtoken {token}",
    "CATALYST-ORG": env.get("CATALYST_ORG", ""),
    "Environment": env.get("CATALYST_ENVIRONMENT", "Development"),
}

tests = [
    ("9 features only", feats),
    ("9 features + timestamp(string)", [dict(f, timestamp=rows[i]["timestamp"]) for i, f in enumerate(feats)]),
]

for label, data in tests:
    r = requests.post(URL, json={"data": data}, headers=headers, timeout=60)
    print(f"=== {label} → HTTP {r.status_code}")
    print(r.text[:400])
    if r.status_code == 200:
        print(f"\n✓ WORKING SHAPE: {label}")
        break
