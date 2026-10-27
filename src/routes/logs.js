const express = require("express");
const { getLogs } = require("../store/memoryStore");

const router = express.Router();

/**
 * GET /api/logs?limit=50&level=alert
 */
router.get("/", (req, res) => {
  const limit = Math.min(parseInt(req.query.limit, 10) || 50, 500);
  let logs = getLogs();
  if (req.query.level) {
    logs = logs.filter(l => l.level === req.query.level);
  }
  res.json({ logs: logs.slice(0, limit) });
});

module.exports = router;
