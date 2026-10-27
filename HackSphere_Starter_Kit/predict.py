#!/usr/bin/env python3
"""
HackSphere 3.0 — Final predict.py
Calls the published QuickML endpoint with the exact 9-feature vector the
model was trained on (see scripts/features.py), plus timestamp as the
row key. Falls back to the locally trained model only if the endpoint
call fails.

Runs standalone (no .env / environment variables required): the endpoint
URL and credentials are embedded below as defaults. Real environment
variables or the repo-root .env always override the embedded defaults.

Must return exactly one prediction per input row, preserving original order.
"""
import os
import sys
import time
import joblib
import numpy as np
import pandas as pd
import requests

# ── Configure your QuickML endpoint ──────────────────────────────────────────
# Environment variables (and repo-root .env, loaded below) override these
# embedded defaults. The defaults make predict.py work bare on any machine,
# so automated evaluation always uses the published QuickML endpoint.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from features import add_features, QUICKML_FEATURES, QUICKML_PAYLOAD_COLS  # noqa: E402

_DEFAULTS = {
    "QUICKML_ENDPOINT_URL": "https://api.catalyst.zoho.in/quickml/v1/project/90496000000013050/endpoints/predict",
    "QUICKML_API_KEY": "0674abbe063709f207601634744e7ab29f57e44ac336c1101171c016fbdadf6057a9811b46d076acbcecb01e12c7e5e8",
    "CATALYST_ORG": "60093145356",
    "CATALYST_ENVIRONMENT": "Development",
    "CLIENT_ID": "1000.X0H251O5DH6AIEC1EW7ZA8CWRV31FT",
    "CLIENT_SECRET": "468d8c00d6aa0ded89633edf69cddb33cf984bb7d4",
}


def _load_env_file(path):
    """Minimal .env loader (no external dependency)."""
    if not os.path.exists(path):
        return
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


# .env (if present) > process env vars > embedded defaults
_load_env_file(os.path.join(os.path.dirname(__file__), "..", ".env"))

QUICKML_ENDPOINT_URL = os.environ.get("QUICKML_ENDPOINT_URL", _DEFAULTS["QUICKML_ENDPOINT_URL"])
QUICKML_API_KEY      = os.environ.get("QUICKML_API_KEY", _DEFAULTS["QUICKML_API_KEY"])
CATALYST_ORG         = os.environ.get("CATALYST_ORG", _DEFAULTS["CATALYST_ORG"])
CATALYST_ENV         = os.environ.get("CATALYST_ENVIRONMENT", _DEFAULTS["CATALYST_ENVIRONMENT"])
CLIENT_ID            = os.environ.get("CLIENT_ID", _DEFAULTS["CLIENT_ID"])
CLIENT_SECRET        = os.environ.get("CLIENT_SECRET", _DEFAULTS["CLIENT_SECRET"])

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "scripts", "model.pkl")


def _oauth_headers(retries=4, backoff=2.0):
    """Client-credentials OAuth (Zoho). The token endpoint occasionally resets
    connections, so retry a few times before giving up."""
    if not (CLIENT_ID and CLIENT_SECRET):
        return {}
    host = "accounts.zoho.in" if "zoho.in" in QUICKML_ENDPOINT_URL else "accounts.zoho.com"
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.post(
                f"https://{host}/oauth/v2/token",
                data={
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "grant_type": "client_credentials",
                    "scope": "QuickML.deployment.READ",
                },
                timeout=25,
            )
            resp.raise_for_status()
            token = resp.json()["access_token"]
            return {"Authorization": f"Zoho-oauthtoken {token}"}
        except Exception as e:  # transient TLS/network resets
            last_err = e
            time.sleep(backoff)
    print(f"Warning: OAuth token failed after {retries} attempts ({last_err}).")
    return {}


def predict(input_df: pd.DataFrame):
    """
    Parameters:
        input_df (pandas.DataFrame): DataFrame with columns
            ['timestamp', 'ambient_temp_c', 'humidity_pct', 'solar_irradiance_wm2']

    Returns:
        numpy.ndarray: Predicted demand (kW) for each input row.
    """
    # ── Try QuickML first (embedded endpoint URL — works bare) ────────────
    X = add_features(input_df)[QUICKML_PAYLOAD_COLS]
    headers = {"Content-Type": "application/json"}
    if QUICKML_API_KEY:
        headers["X-QUICKML-ENDPOINT-KEY"] = QUICKML_API_KEY
    if CATALYST_ORG:
        headers["CATALYST-ORG"] = CATALYST_ORG
    headers["Environment"] = CATALYST_ENV

    last_err = None
    for attempt in range(3):
        try:
            headers.update(_oauth_headers())
            resp = requests.post(
                QUICKML_ENDPOINT_URL,
                json={"data": X.to_dict(orient="records")},
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()
            preds = result.get("result") or result.get("predictions") or result.get("data")
            if preds is None:
                raise ValueError(f"Unexpected QuickML response: {str(result)[:200]}")
            preds = [float(p.get("value", p.get("prediction", p)) if isinstance(p, dict) else p)
                     for p in preds]
            return np.array(preds, dtype=float)
        except Exception as e:
            last_err = e
            time.sleep(2)
    print(f"Warning: QuickML endpoint call failed ({last_err}). Falling back to local model.")

    # ── Fallback: locally trained model ───────────────────────────────────
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"Local model not found at {MODEL_PATH}. Run: python3 scripts/train_model.py"
        )
    model = joblib.load(MODEL_PATH)
    X = add_features(input_df)[QUICKML_FEATURES]
    return np.array(model.predict(X), dtype=float)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--input",  default="sample_test_input.csv")
    parser.add_argument("--output", default="predictions.csv")
    args = parser.parse_args()

    sample_df = pd.read_csv(args.input)
    preds = predict(sample_df)

    out = pd.DataFrame({
        "timestamp": sample_df["timestamp"],
        "target_demand_kw": preds
    })
    out.to_csv(args.output, index=False)
    print(f"✓ Wrote {len(preds)} predictions to {args.output}")
    print(f"  First 5: {np.round(preds[:5], 2)}")
