require("dotenv").config();

const express = require("express");
const cors = require("cors");

const forecastRoutes = require("./routes/forecast");
const historyRoutes = require("./routes/history");
const logsRoutes = require("./routes/logs");

const app = express();

// Middleware
app.use(cors());
app.use(express.json({ limit: "10mb" }));
app.use(express.urlencoded({ extended: true }));

// Simple request logger
app.use((req, res, next) => {
  const start = Date.now();
  res.on("finish", () => {
    console.log(`${req.method} ${req.url} - ${res.statusCode} (${Date.now() - start}ms)`);
  });
  next();
});

// Serve the Slate dashboard (src/webapp/index.html) at the root URL —
// no-store so users always get the latest build after a redeploy
const path = require("path");
app.use(express.static(path.join(__dirname, "webapp"), { etag: false, lastModified: false }));
app.use((req, res, next) => {
  res.set("Cache-Control", "no-store");
  next();
});

// Routes
const BUILD_TAG = "chart-fix-v2"; // bumped on each fix; /api/health reports it
app.get("/api/health", (req, res) => {
  res.json({
    status: "ok",
    service: "HackSphere 3.0",
    build: BUILD_TAG,
    timestamp: new Date().toISOString()
  });
});

app.use("/api/forecast", forecastRoutes);
app.use("/api/history", historyRoutes);
app.use("/api/logs", logsRoutes);

// Dashboard at /
app.get("/", (req, res) => {
  res.sendFile(path.join(__dirname, "webapp", "index.html"));
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({ error: "Not found" });
});

// Error handler
app.use((err, req, res, next) => {
  console.error("Unhandled error:", err);
  res.status(500).json({ error: "Internal server error" });
});

// The Catalyst AppSail platform injects X_ZOHO_CATALYST_LISTEN_PORT and routes
// traffic to it. Locally we keep PORT=3000 via .env; fall back like the official
// appsail-nodejs sample (X_ZOHO_CATALYST_LISTEN_PORT || 9000).
const PORT = process.env.X_ZOHO_CATALYST_LISTEN_PORT || process.env.PORT || 9000;

app.listen(PORT, () => {
  console.log(`[HackSphere] Server running on port ${PORT}`);
  console.log(`[HackSphere] QuickML endpoint: ${process.env.QUICKML_ENDPOINT_URL || "(not configured)"}`);
});

module.exports = app;
