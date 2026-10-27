# GridPulse — Smart Energy Microgrid & Demand Forecasting Engine (HackSphere 3.0)

End-to-end web application on **Zoho Catalyst** that forecasts hourly energy demand with a published **Zoho Catalyst QuickML** regression model and triggers automated power-source transition signals between Main Grid power and Renewable Battery Storage.

**by Mridul Gupta**

---

## Live Application

| | |
|---|---|
| **Public URL** | https://hacksphere-appsail-50047143848.development.catalystappsail.in |
| **Dashboard** | Open the URL — upload a telemetry CSV (or click **Use Sample Data**) → **Run Forecast** |
| **Forecast API** | `POST /api/forecast` |
| **Health / build** | `GET /api/health` (reports a `build` tag for each deployment) |
| **Export** | After a forecast, **⬇ Download CSV** exports `predictions.csv` in the submission-spec format (`timestamp,target_demand_kw`) |

---

## Architecture

```
Browser — glass dashboard (src/webapp/index.html, served by the AppSail)
    │  POST /api/forecast  { telemetry: [rows of timestamp + 3 weather features] }
    ▼
AppSail Backend (Node.js / Express on Zoho Catalyst, src/index.js)
    ├── services/featureEngineer.js      — derives the 9-feature vector (see below)
    ├── services/quickmlClient.js        — Zoho OAuth client-credentials + QuickML REST call
    ├── services/transitionController.js — grid-mode rules + battery SoC simulation
    ├── store/memoryStore.js             — in-memory forecast & log store
    └── routes/forecast.js, history.js, logs.js
    │
    ▼
Zoho Catalyst QuickML (published regression endpoint)
    POST https://api.catalyst.zoho.in/quickml/v1/project/90496000000013050/endpoints/predict
    Response: { "result": [ one number per input row ] }
```

`predict.py` (the submission script, in `HackSphere_Starter_Kit/`) uses the **identical 9-feature pipeline** (`scripts/features.py`) and calls the same published endpoint, so the predictions the evaluator scores are produced by the real QuickML model — not a stand-in. If the endpoint is unreachable, it transparently falls back to a locally trained scikit-learn model with the same feature set.

---

## Model & Feature Set

**Model (published in QuickML):** regression on `train_inference_safe.csv` (4000 hourly rows).
Console metrics: **RMSE 9.19 kW · R² 0.9665 · MAE 7.35 kW · MAPE 5.26%**.

**The model was trained on exactly 9 numeric features — all computable at inference time** (no lag/rolling history, which a hidden test set cannot provide):

| Group | Features | Derived from |
|---|---|---|
| Weather (raw) | `ambient_temp_c`, `humidity_pct`, `solar_irradiance_wm2` | input CSV |
| Time-of-day cycle | `hour_sin`, `hour_cos` | `timestamp` (fractional hour) |
| Day-of-week cycle | `dow_sin`, `dow_cos` | `timestamp` (0 = Monday) |
| Calendar | `is_weekend`, `month` | `timestamp` |

**Payload contract:** each row sent to the endpoint carries the 9 features **plus `timestamp`** as a `YYYY-MM-DD HH:MM:SS` string (the endpoint requires it as the dataset key column; it is *not* a model feature). Invalid or missing timestamps in an uploaded CSV are automatically repaired to sequential hourly values, so a malformed file can never break a forecast (the API reports how many were fixed via `timestamps_fixed`).

> Earlier drafts of this project used a 19-feature model with lag/rolling demand columns; that approach was retired because those features cannot be computed on a fresh test set. Do not reintroduce them.

---

## Transition Controller (exact rules, per spec §6)

For each forecast step (predicted kW + hour of its timestamp):

| Condition | Output |
|---|---|
| Demand **> 160 kW** **OR** hour ∈ 18:00–22:00 (inclusive) | `RENEWABLE_STORAGE` |
| Demand ≤ 160 kW **AND** hour outside 18:00–22:00 | `MAIN_GRID` |
| Demand **≥ 200 kW** (independent of mode) | `CRITICAL_OVERLOAD` alert |

Battery SoC: 100 kWh battery, 50 kW max charge/discharge, starting at 80%; renewable hours discharge to cover the deficit over the 100 kW grid base, grid hours charge.

---

## Repository Layout

```
├── src/
│   ├── index.js                    # Express entry; listens on X_ZOHO_CATALYST_LISTEN_PORT (cloud) or PORT (local); serves dashboard
│   ├── routes/forecast.js         # POST /api/forecast (+ GET /api/forecast/:id)
│   ├── routes/history.js          # GET  /api/history
│   ├── routes/logs.js            # GET  /api/logs
│   ├── services/featureEngineer.js# 9-feature vector + timestamp sanitization (JS)
│   ├── services/quickmlClient.js # Zoho OAuth + QuickML REST client; local-model fallback
│   ├── services/transitionController.js # grid mode + overload + battery SoC
│   ├── store/memoryStore.js      # in-memory forecast/log store
│   └── webapp/index.html         # Dashboard (glass theme, Chart.js, badges, SoC, CSV export)
├── scripts/
│   ├── features.py               # 9-feature pipeline (Python) — single source of truth shared by predict.py
│   ├── train_model.py            # trains the local fallback model (scripts/model.pkl)
│   ├── model.pkl                 # local fallback GradientBoostingRegressor
│   ├── predict_local.py          # Node → local-model bridge (used only when QuickML is unreachable)
│   ├── e2e_test.py               # live end-to-end test of the QuickML endpoint (run before submitting)
│   └── probe_new_endpoint.py     # payload-shape probe (used when retraining the QuickML model)
├── HackSphere_Starter_Kit/
│   ├── predict.py                # ★ submission script — auto-loads ../.env, calls QuickML, writes predictions.csv
│   ├── test_eval.py              # ★ pre-submission self-test — must print SUCCESS
│   ├── train_telemetry.csv       # original 4000-row training set (weather + target)
│   ├── sample_test_input.csv     # 1000-row sample test set (no target)
│   └── train_inference_safe.csv  # ★ the CSV used for the current QuickML model (9 features + target, timestamp kept as key)
├── app-config.json               # Catalyst cloud config: startup command, npm install scripts, HS_* env vars
├── app-config.example.json       # same, with placeholders (committed; credentials stay out of VCS)
├── .env / .env.example           # local credentials (endpoint URL, key, OAuth client) — .env is git-ignored
├── .catalystignore / .gitignore  # keep .env and secrets out of deploys & the repo
├── package.json / catalyst.json  # app dependencies + CLI project config
└── README.md
```

**Legacy / unused files (safe to delete, but harmless):** `handler.js` (broken early scaffold — the deployed entry point is `src/index.js`), `scripts/build_feature_stats.py` and `scripts/feature_stats.json` (belonged to the retired 19-feature model), `scripts/probe_quickml.py`, `scripts/test_quickml_live.py`, `scripts/get_oauth_token.py`, `scripts/repro_upload.py`, `scripts/test_api.py` (debugging helpers, superseded by `e2e_test.py`).

---

## Local Development

Prerequisites: Node.js ≥ 16, Python 3.9+, `pip install pandas numpy scikit-learn joblib requests`, Zoho Catalyst CLI (`npm install -g zcatalyst-cli`, binary `catalyst`).

```bash
cd ~/Hacksphere
npm install
cp .env.example .env       # fill in your QuickML endpoint + credentials
node src/index.js          # dashboard at http://localhost:3000
```

Retrain the local fallback (optional, only if you change the feature set):
```bash
python3 scripts/train_model.py
```

Run the submission contract check (must print SUCCESS, and with a configured `.env` it hits the *live* endpoint — watch for the "falling back to local model" warning, which means the endpoint call failed):
```bash
cd HackSphere_Starter_Kit
python3 test_eval.py
python3 predict.py --input sample_test_input.csv --output predictions.csv
```

Live endpoint regression test (verifies OAuth + payload shape + 24 predictions):
```bash
python3 scripts/e2e_test.py
```

---

## Deploying to Zoho Catalyst

`app-config.json` drives the cloud run:

- **`command`** `node src/index.js` — the app listens on the platform-injected `X_ZOHO_CATALYST_LISTEN_PORT`
- **`scripts.preserve: npm install`** — installs dependencies inside the container before startup
- **`env_variables` (`HS_*`)** — QuickML endpoint URL, endpoint key, OAuth client credentials, org ID. Custom `HS_` prefixes are used because `PORT`, `CLIENT_*` and `CATALYST_*` are reserved by the platform.
- **`stack: node18`, `memory: 256`**

The Node client reads `HS_*` values first and falls back to the standard names, so the same code works locally (`.env`) and in the cloud.

```bash
catalyst login
catalyst project:use 90496000000013050 --org 60093145356
catalyst deploy appsail --name hacksphere-appsail
# → prints the public URL: https://hacksphere-appsail-50047143848.development.catalystappsail.in
```

Verify after each deploy:
```bash
curl https://hacksphere-appsail-50047143848.development.catalystappsail.in/api/health   # status + build tag
```

> For a production link, use the **Deploy to Production** button in the Catalyst console (the URL above is the Development environment).

---

## Environment Variables

| Variable | Where | Meaning |
|---|---|---|
| `QUICKML_ENDPOINT_URL` | `.env` / `HS_QUICKML_URL` in cloud | Published QuickML predict endpoint |
| `QUICKML_API_KEY` | `.env` / `HS_QUICKML_KEY` | `X-QUICKML-ENDPOINT-KEY` from the Endpoints page |
| `CLIENT_ID` / `CLIENT_SECRET` | `.env` / `HS_CLIENT_ID` / `HS_CLIENT_SECRET` | Zoho OAuth client-credentials (fetches the `Zoho-oauthtoken` the endpoint requires) |
| `CATALYST_ORG` / `CATALYST_ENVIRONMENT` | `.env` / `HS_ORG` / `HS_ENV` | Org ZUID + Development/Production |
| `PORT` | `.env` | Local dev port (3000) — ignored in the cloud, where the platform injects `X_ZOHO_CATALYST_LISTEN_PORT` |

**Credentials are never committed** (`.env` and `app-config.json` are git-ignored; `*.example.json` files are committed as templates).

---

## Evaluation Readiness

| Criteria (weight) | Status |
|---|---|
| Model accuracy (35%) | QuickML model RMSE 9.19 kW (validation); honest future-hours estimate ≈ 11–13 kW. `predict.py` calls the published endpoint directly |
| Deployment & functionality (35%) | Live public Catalyst URL; end-to-end forecast verified (24-row and 1000-row inputs) |
| Transition controller (20%) | Exact spec rules, edge cases verified (>160 vs =160, ≥200, 18:00–22:00 inclusive) |
| UI & UX (10%) | Glass dashboard: load-curve chart, grid-state badges, SoC gauge, overload banner, system log, CSV export |
