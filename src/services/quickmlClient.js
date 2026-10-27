/**
 * QuickML REST client.
 *
 * Auth (from Catalyst console → Endpoints → Required Headers):
 *   X-QUICKML-ENDPOINT-KEY : .env QUICKML_API_KEY
 *   Authorization          : Zoho-oauthtoken <token>  (from OAuth client-credentials)
 *   CATALYST-ORG           : .env CATALYST_ORG
 *   Environment            : Development (or Production)
 *
 * Features: built by featureEngineer.featureVectors() — the exact column
 * set the model was trained on.
 */

const { featureVectors } = require("./featureEngineer");

// Cloud (app-config.json) uses HS_* keys to avoid Catalyst's reserved-keyword
// list (CLIENT_*, CATALYST_*, PORT, …). Local dev uses the .env standard names.
const QUICKML_ENDPOINT_URL = process.env.HS_QUICKML_URL   || process.env.QUICKML_ENDPOINT_URL || "";
const QUICKML_API_KEY      = process.env.HS_QUICKML_KEY   || process.env.QUICKML_API_KEY      || "";
const CLIENT_ID            = process.env.HS_CLIENT_ID     || process.env.CLIENT_ID            || "";
const CLIENT_SECRET        = process.env.HS_CLIENT_SECRET || process.env.CLIENT_SECRET        || "";
const CATALYST_ORG         = process.env.HS_ORG           || process.env.CATALYST_ORG         || "";
const ENVIRONMENT          = process.env.HS_ENV           || process.env.CATALYST_ENVIRONMENT || "Development";

// ── OAuth token cache ────────────────────────────────────────────────────────
let tokenCache = { token: "", expiry: 0 };

async function getOAuthToken() {
  if (tokenCache.token && Date.now() < tokenCache.expiry - 60000) {
    return tokenCache.token;
  }
  if (!CLIENT_ID || !CLIENT_SECRET) {
    throw new Error("CLIENT_ID / CLIENT_SECRET not set — cannot obtain OAuth token");
  }

  // Region from endpoint URL (zoho.in → accounts.zoho.in, else accounts.zoho.com)
  const isIN = QUICKML_ENDPOINT_URL.includes("zoho.in");
  const host = isIN ? "accounts.zoho.in" : "accounts.zoho.com";

  const body = new URLSearchParams({
    client_id: CLIENT_ID,
    client_secret: CLIENT_SECRET,
    grant_type: "client_credentials",
    scope: "QuickML.deployment.READ"
  });

  const resp = await fetch(`https://${host}/oauth/v2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body
  });
  if (!resp.ok) {
    throw new Error(`OAuth token fetch failed (${resp.status}): ${await resp.text()}`);
  }
  const json = await resp.json();
  tokenCache = {
    token: json.access_token,
    expiry: Date.now() + (json.expires_in || 3600) * 1000
  };
  return tokenCache.token;
}

// ── Prediction ───────────────────────────────────────────────────────────────
async function getPredictions(rows) {
  if (QUICKML_ENDPOINT_URL) {
    return callQuickML(rows);
  }
  return callLocalModel(rows);
}

async function callQuickML(rows) {
  const data = featureVectors(rows);
  const headers = {
    "Content-Type": "application/json",
    "X-QUICKML-ENDPOINT-KEY": QUICKML_API_KEY,
    "Environment": ENVIRONMENT
  };
  if (CATALYST_ORG) headers["CATALYST-ORG"] = CATALYST_ORG;

  // The QuickML predict endpoint requires the OAuth ticket (endpoint key alone → INVALID_TICKET)
  if (CLIENT_ID && CLIENT_SECRET) {
    headers["Authorization"] = `Zoho-oauthtoken ${await getOAuthToken()}`;
  }

  const resp = await fetch(QUICKML_ENDPOINT_URL, {
    method: "POST",
    headers,
    body: JSON.stringify({ data })
  });

  if (!resp.ok) {
    const text = await resp.text();
    // Some Zoho endpoints accept the endpoint key alone — surface the error clearly
    throw new Error(`QuickML error ${resp.status}: ${text.slice(0, 300)}`);
  }

  const result = await resp.json();
  // QuickML response: { "result": [ {predicted-value}, ... ] } or { "predictions": [...] }
  let preds = result.result || result.predictions || result.data;
  if (!Array.isArray(preds)) {
    throw new Error(`Unexpected QuickML response: ${JSON.stringify(result).slice(0, 200)}`);
  }
  return preds.map(p =>
    Number(typeof p === "object" ? (p.value ?? p.prediction ?? p.target_demand_kw) : p)
  );
}

// ── Local fallback (development without QuickML) ─────────────────────────────
const { execSync } = require("child_process");
const path = require("path");
const fs = require("fs");

function callLocalModel(rows) {
  const { addFeatures } = require("./featureEngineer");
  const featureRows = addFeatures(rows);
  const tmpInput = path.join(__dirname, `._tmp_input_${Date.now()}.json`);
  fs.writeFileSync(tmpInput, JSON.stringify(featureRows));

  try {
    const scriptPath = path.join(__dirname, "..", "..", "scripts", "predict_local.py");
    const out = execSync(
      `python3 "${scriptPath}" "${tmpInput}"`,
      { encoding: "utf-8", timeout: 30000 }
    );
    return JSON.parse(out.trim());
  } finally {
    try { fs.unlinkSync(tmpInput); } catch (_) {}
  }
}

module.exports = { getPredictions };
