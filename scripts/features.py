#!/usr/bin/env python3
"""
Single source of truth for the QuickML feature set (Python side).
Must mirror src/services/featureEngineer.js exactly.

Model (retrained, inference-safe): 9 numeric features, NO timestamp column:
  ambient_temp_c, humidity_pct, solar_irradiance_wm2,
  hour_sin, hour_cos, dow_sin, dow_cos, is_weekend, month

The `timestamp` input column is still required to DERIVE the time features;
it is never sent to the endpoint.
"""
import os
import re
import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

# The exact feature set the retrained QuickML model expects (numeric only)
QUICKML_FEATURES = [
    "ambient_temp_c",
    "humidity_pct",
    "solar_irradiance_wm2",
    "hour_sin",
    "hour_cos",
    "dow_sin",
    "dow_cos",
    "is_weekend",
    "month",
]

# Payload = the 9 model features + timestamp (string key column the endpoint
# requires; it is NOT a model feature — only used for row identification).
QUICKML_PAYLOAD_COLS = ["timestamp"] + QUICKML_FEATURES

_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?$")


def _sanitize_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    """Timestamp is only needed to derive time features. If a CSV lacks a
    usable timestamp column, synthesize sequential hourly values anchored at
    2024-01-01 00:00:00 so the derived features stay well-defined."""
    if "timestamp" not in df.columns:
        df["timestamp"] = ""

    valid = df["timestamp"].astype(str).str.strip().str.match(_TS_RE)
    bad = ~valid
    if bad.any():
        anchor = "2024-01-01 00:00:00"
        if valid.any():
            anchor = df.loc[valid, "timestamp"].astype(str).str.strip().iloc[0]
            if len(anchor) == 16:
                anchor += ":00"
        base = pd.Timestamp(anchor.replace(" ", "T"))
        anchor_idx = int(np.where(valid.values)[0][0]) if valid.any() else 0
        idx = np.where(bad.values)[0]
        df.loc[bad, "timestamp"] = [
            (base + pd.Timedelta(hours=int(i - anchor_idx))).strftime("%Y-%m-%d %H:%M:%S")
            for i in idx
        ]
    # Normalize: T → space; append ":00" ONLY to "YYYY-MM-DD HH:MM" (no seconds).
    # Never pad values that already carry seconds.
    ts = df["timestamp"].astype(str).str.strip().str.replace("T", " ", regex=False)
    mask16 = ts.str.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
    ts.loc[mask16] = ts.loc[mask16] + ":00"
    df["timestamp"] = ts
    return df


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df = _sanitize_timestamps(df.copy())
    dt = pd.to_datetime(df["timestamp"], errors="coerce")

    # If even the derived parsing failed, fall back to the default anchor
    if dt.isna().any():
        default = pd.Timestamp("2024-01-01 00:00:00")
        na_idx = np.where(dt.isna().values)[0]
        fillvals = pd.DatetimeIndex([default + pd.Timedelta(hours=int(i)) for i in na_idx])
        dt = dt.fillna(pd.Series(fillvals, index=na_idx)).reset_index(drop=True)

    hour_frac = dt.dt.hour + dt.dt.minute / 60.0
    df["hour_sin"] = np.sin(2 * np.pi * hour_frac / 24)
    df["hour_cos"] = np.cos(2 * np.pi * hour_frac / 24)

    # day-of-week: pandas dayofweek is 0=Mon..6=Sun
    dow = dt.dt.dayofweek
    df["dow_sin"] = np.sin(2 * np.pi * dow / 7)
    df["dow_cos"] = np.cos(2 * np.pi * dow / 7)

    df["is_weekend"] = (dow >= 5).astype(int)
    df["month"] = dt.dt.month

    return df


def feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Return only the model's feature columns (numeric)."""
    return add_features(df)[QUICKML_FEATURES]


def payload_records(df: pd.DataFrame) -> list:
    """Records to send as the QuickML `data` field — features only."""
    return add_features(df)[QUICKML_PAYLOAD_COLS].to_dict(orient="records")
