#!/usr/bin/env python3
"""
Local prediction fallback — used by quickmlClient.js when QUICKML_ENDPOINT_URL
is not set or unreachable.
Reads a JSON file of RAW rows (timestamp + 3 weather cols) and prints a JSON
array of predicted kW values, using the local model + shared feature pipeline.

Usage:
  python3 predict_local.py <input_json_path>
"""
import json
import os
import sys
import joblib
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from features import QUICKML_FEATURES, add_features  # noqa: E402

MODEL_PATH = os.path.join(HERE, "model.pkl")


def main():
    if len(sys.argv) < 2:
        print("Usage: predict_local.py <input_json_path>", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        rows = json.load(f)

    if not rows:
        print("[]")
        return

    model = joblib.load(MODEL_PATH)
    df = pd.DataFrame(rows)
    # Keep only what add_features needs
    for col in ["timestamp", "ambient_temp_c", "humidity_pct", "solar_irradiance_wm2"]:
        if col not in df.columns:
            df[col] = 0 if col != "timestamp" else "2015-06-16 00:00:00"

    X = add_features(df)[QUICKML_FEATURES]
    predictions = model.predict(X)
    print(json.dumps([round(float(v), 2) for v in predictions]))


if __name__ == "__main__":
    main()
