#!/usr/bin/env python3
"""Verify that predict.py works BARE (no .env, no env vars) against the live
QuickML endpoint, using its embedded defaults. Run from repo root:
  python3 scripts/verify_bare_predict.py
"""
import importlib.util
import os
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
kit = os.path.join(ROOT, "HackSphere_Starter_Kit")

# Simulate a grader environment: no QUICKML_* vars set
for var in ["QUICKML_ENDPOINT_URL", "QUICKML_API_KEY", "CLIENT_ID",
           "CLIENT_SECRET", "CATALYST_ORG", "CATALYST_ENVIRONMENT"]:
    os.environ.pop(var, None)

spec = importlib.util.spec_from_file_location("predict", os.path.join(kit, "predict.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

print("bare endpoint URL:", m.QUICKML_ENDPOINT_URL[:60], "...")
print("org:", m.CATALYST_ORG, "| key set:", bool(m.QUICKML_API_KEY),
      "| client set:", bool(m.CLIENT_ID))

df = pd.read_csv(os.path.join(kit, "sample_test_input.csv")).head(4)
preds = m.predict(df)
print("bare predict() results:", [round(float(p), 2) for p in preds])
print("(values ~220-287 = live QuickML model · ~147-174 = local fallback)")
