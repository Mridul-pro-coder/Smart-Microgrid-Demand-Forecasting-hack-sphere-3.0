/**
 * In-memory store for hackathon — keeps last 100 forecast runs and logs.
 * Swap for Catalyst NoSQL later if persistence is needed.
 */

const MAX_FORECASTS = 100;
const MAX_LOGS = 500;

const forecasts = [];  // {id, timestamp, input_rows, result}
const logs = [];       // {level, message, timestamp}

function addForecast(entry) {
  forecasts.unshift({ id: Date.now(), ...entry });
  if (forecasts.length > MAX_FORECASTS) forecasts.pop();
}

function addLog(level, message) {
  logs.unshift({
    level,
    message,
    timestamp: new Date().toISOString()
  });
  if (logs.length > MAX_LOGS) logs.pop();
}

function getForecast(id) {
  return forecasts.find(f => f.id === id) || null;
}

function getHistory(limit = 20) {
  return forecasts.slice(0, limit).map(f => ({
    id: f.id,
    timestamp: f.timestamp,
    peak_kw: f.result?.peakKw,
    overload_hours: f.result?.overloadHours,
    renewable_hours: f.result?.predictions?.filter(p => p.grid_mode === "RENEWABLE_STORAGE").length
  }));
}

function getLogs() {
  return logs;
}

module.exports = { addForecast, addLog, getForecast, getHistory, getLogs };
