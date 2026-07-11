import json
import logging
import os
from datetime import datetime


class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "agent": record.name,
            "message": record.getMessage(),
        })


def configure_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger = logging.getLogger("prioritizer")
    if not logger.handlers:
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


logger = configure_logging()

INPUT_FILE = "/data/summary.txt"
OUTPUT_FILE = "/data/prioritized.txt"
OUTPUT_DIR = "/output"
METRICS_FILE = os.path.join(OUTPUT_DIR, "metrics.json")

PRIORITY_KEYWORDS = [
    "urgent", "today", "asap", "important",
    "deadline", "critical", "action required"
]


def load_metrics():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if not os.path.exists(METRICS_FILE):
        return {"run_id": datetime.utcnow().isoformat(), "agents": {}}

    with open(METRICS_FILE, "r", encoding="utf-8") as handle:
        try:
            return json.load(handle)
        except json.JSONDecodeError:
            return {"run_id": datetime.utcnow().isoformat(), "agents": {}}


def save_metrics(agent_updates):
    metrics = load_metrics()
    metrics["updated_at"] = datetime.utcnow().isoformat()
    metrics.setdefault("agents", {})
    metrics["agents"]["prioritizer"] = {
        **metrics["agents"].get("prioritizer", {}),
        **agent_updates,
    }

    with open(METRICS_FILE, "w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2)

    return metrics


def score_line(line):
    """Count how many priority keywords appear in a line."""
    lower = line.lower()
    return sum(1 for kw in PRIORITY_KEYWORDS if kw in lower)


def prioritize():
    with open(INPUT_FILE, "r", encoding="utf-8") as handle:
        lines = [line.strip() for line in handle if line.strip()]

    scored = [(line, score_line(line)) for line in lines]
    scored.sort(key=lambda x: x[1], reverse=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        for line, score in scored:
            out.write(f"[{score}] {line}\n")

    logger.info(f"Prioritized {len(scored)} items -> {OUTPUT_FILE}")
    save_metrics({
        "items_prioritized": len(scored),
        "status": "ok",
    })


if __name__ == "__main__":
    prioritize()