const express = require("express");
const { getPredictions } = require("../services/quickmlClient");
const { getTsFixes } = require("../services/featureEngineer");
const { runTransition } = require("../services/transitionController");
const { addForecast, addLog } = require("../store/memoryStore");

const router = express.Router();

const REQUIRED_COLS = ["timestamp", "ambient_temp_c", "humidity_pct", "solar_irradiance_wm2"];

/**
 * POST /api/forecast
 * Body: { telemetry: [ {timestamp, ambient_temp_c, humidity_pct, solar_irradiance_wm2}, ... ] }
 */
router.post("/", async (req, res) => {
  try {
    const telemetry = req.body.telemetry;

    // --- Validate input ---
    if (!Array.isArray(telemetry) || telemetry.length === 0) {
      return res.status(400).json({ error: "Body must include a non-empty 'telemetry' array" });
    }

    const missingCols = REQUIRED_COLS.filter(c => !(c in telemetry[0]));
    if (missingCols.length) {
      return res.status(400).json({
        error: `Missing required columns: ${missingCols.join(", ")}`,
        expected: REQUIRED_COLS
      });
    }

    addLog("info", `Forecast request received — ${telemetry.length} rows`);

    // --- Get predictions from QuickML (or local model) ---
    const predictedKw = await getPredictions(telemetry);

    if (predictedKw.length !== telemetry.length) {
      return res.status(500).json({
        error: `Prediction count mismatch: expected ${telemetry.length}, got ${predictedKw.length}`
      });
    }

    // --- Combine predictions with input + run transition logic ---
    const enriched = telemetry.map((row, i) => ({
      ...row,
      hour: parseInt(row.timestamp.split(" ")[1].split(":")[0], 10),
      predicted_kw: predictedKw[i]
    }));

    const result = runTransition(enriched);

    // --- Persist ---
    const entry = { timestamp: new Date().toISOString(), input_rows: telemetry.length, result };
    addForecast(entry);
    addLog("info", `Forecast complete — peak ${result.peakKw} kW, overload hours: [${result.overloadHours}]`);

    if (result.overloadHours.length > 0) {
      addLog("alert", `Critical overload detected at hours: ${result.overloadHours.join(", ")}`);
    }

    res.json({
      forecast_id: entry.id,
      predictions: result.predictions,
      peak_kw: result.peakKw,
      overload_hours: result.overloadHours,
      battery_soc_series: result.batterySoc,
      initial_soc_pct: 80,
      timestamps_fixed: getTsFixes(),
      system_log: result.predictions.map(p => {
        const parts = [`${p.timestamp.slice(11, 16)}`, p.grid_mode, `SOC ${p.battery_soc_pct}%`];
        if (p.alert) parts.push(`⚠ ${p.alert}`);
        return parts.join(" — ");
      })
    });

  } catch (err) {
    console.error("Forecast error:", err);
    addLog("error", `Forecast failed: ${err.message}`);
    res.status(500).json({ error: err.message });
  }
});

/**
 * GET /api/forecast/:id — retrieve a stored forecast run
 */
router.get("/:id", (req, res) => {
  const store = require("../store/memoryStore");
  const entry = store.getForecast(parseInt(req.params.id, 10));
  if (!entry) return res.status(404).json({ error: "Forecast not found" });
  res.json(entry);
});

module.exports = router;
