#!/usr/bin/env python3
"""
Train the local fallback regression model (scikit-learn GradientBoosting)
on the SAME 9 inference-safe features as the published QuickML model
(see scripts/features.py and train_inference_safe.csv).
"""
import os
import sys
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from features import QUICKML_FEATURES, add_features  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TRAIN_CSV = os.path.join(
    HERE, "..", "HackSphere_Starter_Kit",
    "train_inference_safe.csv"
    if os.path.exists(os.path.join(HERE, "..", "HackSphere_Starter_Kit", "train_inference_safe.csv"))
    else "train_telemetry.csv",
)
MODEL_PATH = os.path.join(HERE, "model.pkl")


def main():
    raw = pd.read_csv(TRAIN_CSV)
    X = add_features(raw)[QUICKML_FEATURES]
    y = raw["target_demand_kw"]

    # Chronological 80/20 (hidden test = future hours, so this is the honest check)
    cut = int(len(raw) * 0.8)
    Xtr, Xte, ytr, yte = X.iloc[:cut], X.iloc[cut:], y.iloc[:cut], y.iloc[cut:]

    model = GradientBoostingRegressor(
        n_estimators=500,
        max_depth=4,
        learning_rate=0.05,
        subsample=1.0,
        random_state=42,
    )
    model.fit(Xtr, ytr)

    pred = model.predict(Xte)
    rmse = np.sqrt(mean_squared_error(yte, pred))
    mae = mean_absolute_error(yte, pred)
    print("\nValidation (chronological future-hours split):")
    print(f"  RMSE: {rmse:.2f} kW   MAE: {mae:.2f} kW")

    print("\nFeature importances:")
    for feat, imp in sorted(zip(QUICKML_FEATURES, model.feature_importances_), key=lambda x: -x[1]):
        print(f"  {feat:18s} {imp:.4f}")

    joblib.dump(model, MODEL_PATH)
    print(f"\nModel saved to: {MODEL_PATH}")


if __name__ == "__main__":
    main()
