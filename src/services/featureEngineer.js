/**
 * Feature engineering — must mirror scripts/features.py exactly.
 *
 * Model (retrained, inference-safe): 9 numeric features, NO timestamp column:
 *   ambient_temp_c, humidity_pct, solar_irradiance_wm2,
 *   hour_sin, hour_cos, dow_sin, dow_cos, is_weekend, month
 *
 * `timestamp` is only used to DERIVE the time features; it is never sent.
 */

// The exact feature set the retrained QuickML model expects (numeric only)
const QUICKML_FEATURES = [
  "ambient_temp_c",
  "humidity_pct",
  "solar_irradiance_wm2",
  "hour_sin",
  "hour_cos",
  "dow_sin",
  "dow_cos",
  "is_weekend",
  "month"
];

// Payload = the 9 model features + timestamp (string key column the endpoint
// requires; it is NOT a model feature — only row identification).
const QUICKML_PAYLOAD = ["timestamp", ...QUICKML_FEATURES];

// ── Timestamp sanitization (only needed to derive time features) ────────────
const TS_RE = /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?$/;
const pad2 = n => String(n).padStart(2, "0");

function isValidTs(ts) {
  return typeof ts === "string" && TS_RE.test(ts.trim());
}
function normTs(ts) {
  let s = ts.trim().replace("T", " ");
  const [d, t] = s.split(" ");
  const [hh, mm, ...rest] = t.split(":");
  return `${d} ${hh}:${mm || "00"}:${rest[0] || "00"}`;
}
function parseTimestamp(ts) {
  const [datePart, timePart] = ts.split(" ");
  const [y, m, d] = datePart.split("-").map(Number);
  const [H, M] = timePart.split(":").map(Number);
  const date = new Date(y, m - 1, d);
  // JS getDay: 0=Sun..6=Sat → 0=Mon..6=Sun (matches pandas dayofweek)
  const dow = (date.getDay() + 6) % 7;
  const isWeekend = date.getDay() === 0 || date.getDay() === 6 ? 1 : 0;
  return { y, m, d, H, M, dow, isWeekend };
}

function sanitizeTimestamps(rows) {
  // Mirror scripts/features.py: anchor at the first valid timestamp (its index),
  // synthesize the invalid ones as hourly offsets relative to that anchor. Falls
  // back to 2024-01-01 00:00:00 when no row has a valid timestamp.
  let anchorIdx = -1;
  let base = null;
  rows.forEach((r, i) => {
    if (anchorIdx === -1 && isValidTs(r.timestamp)) {
      anchorIdx = i;
      base = new Date(normTs(r.timestamp).replace(" ", "T"));
    }
  });
  if (!base) { base = new Date(2024, 0, 1, 0, 0, 0); anchorIdx = 0; }

  let fixed = 0;
  rows.forEach((row, idx) => {
    if (isValidTs(row.timestamp)) {
      row.timestamp = normTs(row.timestamp);
    } else {
      const dd = new Date(base.getTime() + (idx - anchorIdx) * 3600000);
      row.timestamp = `${dd.getFullYear()}-${pad2(dd.getMonth() + 1)}-${pad2(dd.getDate())} ` +
        `${pad2(dd.getHours())}:${pad2(dd.getMinutes())}:${pad2(dd.getSeconds())}`;
      fixed++;
    }
  });
  return fixed;
}

let lastTsFixes = 0;
function getTsFixes() {
  return lastTsFixes;
}

function addFeatures(rows) {
  lastTsFixes = sanitizeTimestamps(rows);
  if (lastTsFixes) {
    console.log(`[featureEngineer] sanitized ${lastTsFixes} invalid timestamp(s)`);
  }

  return rows.map(row => {
    const { m: month, H, M, dow, isWeekend } = parseTimestamp(row.timestamp);
    const hour = H + M / 60;

    const hourSin = Math.sin((2 * Math.PI * hour) / 24);
    const hourCos = Math.cos((2 * Math.PI * hour) / 24);
    const dowSin = Math.sin((2 * Math.PI * dow) / 7);
    const dowCos = Math.cos((2 * Math.PI * dow) / 7);

    return {
      ...row,
      ambient_temp_c: Number(row.ambient_temp_c),
      humidity_pct: Number(row.humidity_pct),
      solar_irradiance_wm2: Number(row.solar_irradiance_wm2),
      hour_sin: hourSin,
      hour_cos: hourCos,
      dow_sin: dowSin,
      dow_cos: dowCos,
      is_weekend: isWeekend,
      month
    };
  });
}

function featureVectors(rows) {
  return addFeatures(rows).map(r => {
    const out = {};
    QUICKML_PAYLOAD.forEach(f => {
      out[f] = r[f];
    });
    return out;
  });
}

module.exports = { addFeatures, featureVectors, getTsFixes, sanitizeTimestamps, QUICKML_FEATURES, QUICKML_PAYLOAD };
