"""
score-logger — lightweight audit API
Receives POST requests from n8n with article scoring events and writes
structured logs to disk. Useful for debugging scoring thresholds and
reviewing what Claude decided about each article.

Endpoints:
  POST /log      — log a scoring/routing event
  GET  /recent   — return last N log entries as JSON
  GET  /stats    — summary counts by tier and date
  GET  /health   — liveness check
"""

import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from flask import Flask, request, jsonify

app = Flask(__name__)
LOG_DIR = os.environ.get("LOG_DIR", "/app/logs")
LOG_FILE = os.path.join(LOG_DIR, "pipeline.jsonl")

os.makedirs(LOG_DIR, exist_ok=True)


def _write(entry: dict):
    entry["ts"] = datetime.now(timezone.utc).isoformat()
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _read_all() -> list[dict]:
    if not os.path.exists(LOG_FILE):
        return []
    entries = []
    with open(LOG_FILE) as f:
        for line in f:
            try:
                entries.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                pass
    return entries


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}), 200


@app.route("/log", methods=["POST"])
def log_event():
    """
    Expected payload:
    {
        "event":    "published" | "review" | "archived",
        "title":    "Article title",
        "url":      "https://...",
        "score":    8,
        "reason":   "Claude's scoring rationale",
        "source":   "Feed source name",
        "category": "threat-intelligence"
    }
    """
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"error": "empty payload"}), 400
    _write(data)
    return jsonify({"logged": True}), 200


@app.route("/recent", methods=["GET"])
def recent():
    n = int(request.args.get("n", 50))
    entries = _read_all()
    return jsonify(list(reversed(entries[-n:]))), 200


@app.route("/stats", methods=["GET"])
def stats():
    """Return aggregate counts: total processed, per-tier, per-day."""
    entries = _read_all()
    tier_counts: dict[str, int] = defaultdict(int)
    daily_counts: dict[str, int] = defaultdict(int)

    for e in entries:
        tier_counts[e.get("event", "unknown")] += 1
        ts = e.get("ts", "")
        if ts:
            day = ts[:10]  # YYYY-MM-DD
            daily_counts[day] += 1

    return jsonify({
        "total": len(entries),
        "by_tier": dict(tier_counts),
        "by_day": dict(sorted(daily_counts.items(), reverse=True)[:30]),
    }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
