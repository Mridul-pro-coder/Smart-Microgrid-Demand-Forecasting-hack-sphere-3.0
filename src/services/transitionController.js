/**
 * Transition Controller — pure, stateless grid-switching logic.
 *
 * Rules:
 *   RENEWABLE_STORAGE:  predicted_kw > 160  OR  18 ≤ hour ≤ 22 (inclusive)
 *   MAIN_GRID:          predicted_kw ≤ 160  AND  outside 18–22 window
 *   CRITICAL_OVERLOAD:  predicted_kw ≥ 200 (independent of grid mode)
 *
 * Battery SoC simulation:
 *   - 100 kWh battery, max charge/discharge rate 50 kW
 *   - RENEWABLE_STORAGE hours: battery discharges to cover excess over grid base
 *   - MAIN_GRID hours: battery charges at available rate
 *   - Clamped to [0, 100]%
 */

const BATTERY_CAPACITY_KWH = 100;
const MAX_CHARGE_RATE_KW = 50;
const MAX_DISCHARGE_RATE_KW = 50;
const GRID_BASE_LOAD_KW = 100; // assumed minimum grid supply
const INITIAL_SOC_PCT = 80;

function classify(predictedKw, hour) {
  const evePeak = hour >= 18 && hour <= 22;
  const isRenewable = predictedKw > 160 || evePeak;
  const isOverload = predictedKw >= 200;

  const gridMode = isRenewable ? "RENEWABLE_STORAGE" : "MAIN_GRID";
  const alert = isOverload ? "CRITICAL_OVERLOAD" : null;

  return { gridMode, alert, isRenewable, isOverload };
}

/**
 * Runs the full 24-hour transition simulation.
 * @param {Array<{predicted_kw: number, hour: number, timestamp: string}>} rows
 * @returns {{predictions: Array, peakKw: number, overloadHours: number[], batterySoc: Array}}
 */
function runTransition(rows) {
  let soc = INITIAL_SOC_PCT; // percent
  const predictions = [];
  const batterySoc = [];
  let peakKw = 0;
  const overloadHours = [];

  for (const row of rows) {
    const { predicted_kw: kw, hour, timestamp } = row;
    const { gridMode, alert, isOverload } = classify(kw, hour);

    if (kw > peakKw) peakKw = kw;
    if (isOverload) overloadHours.push(hour);

    // Battery SoC update
    let socDeltaPct = 0;
    if (gridMode === "RENEWABLE_STORAGE") {
      // Battery discharges: covers demand above grid base
      const deficit = Math.max(0, kw - GRID_BASE_LOAD_KW);
      const dischargeKw = Math.min(deficit, MAX_DISCHARGE_RATE_KW);
      // Convert kW to % of capacity (1 hour = 1 kWh at 1 kW)
      socDeltaPct = -(dischargeKw / BATTERY_CAPACITY_KWH) * 100;
    } else {
      // Battery charges
      const chargeKw = Math.min(MAX_CHARGE_RATE_KW, GRID_BASE_LOAD_KW * 0.3);
      socDeltaPct = (chargeKw / BATTERY_CAPACITY_KWH) * 100;
    }

    soc = Math.max(0, Math.min(100, soc + socDeltaPct));

    predictions.push({
      timestamp,
      predicted_kw: Math.round(kw * 100) / 100,
      grid_mode: gridMode,
      alert,
      battery_soc_pct: Math.round(soc * 10) / 10
    });

    batterySoc.push(Math.round(soc * 10) / 10);
  }

  return {
    predictions,
    peakKw: Math.round(peakKw * 100) / 100,
    overloadHours,
    batterySoc
  };
}

module.exports = { classify, runTransition };
