const express = require("express");
const { getHistory } = require("../store/memoryStore");

const router = express.Router();

/**
 * GET /api/history?limit=20
 */
router.get("/", (req, res) => {
  const limit = Math.min(parseInt(req.query.limit, 10) || 20, 100);
  res.json({ history: getHistory(limit) });
});

module.exports = router;
