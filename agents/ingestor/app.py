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
    logger = logging.getLogger("ingestor")
    if not logger.handlers:
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


logger = configure_logging()

INPUT_DIR = "/data/input"
OUTPUT_FILE = "/data/ingested.txt"
OUTPUT_DIR = "/output"
METRICS_FILE = os.path.join(OUTPUT_DIR, "metrics.json")


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
    metrics["agents"]["ingestor"] = {
        **metrics["agents"].get("ingestor", {}),
        **agent_updates,
    }

    with open(METRICS_FILE, "w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2)

    return metrics


def ingest():
    content = ""
    files_processed = 0
    errors = 0
    for filename in sorted(os.listdir(INPUT_DIR)):
        filepath = os.path.join(INPUT_DIR, filename)
        if os.path.isfile(filepath):
            try:
                # Detect UTF-16 BOM (\xff\xfe or \xfe\xff) and decode accordingly
                with open(filepath, "rb") as raw:
                    raw_bytes = raw.read()
                if raw_bytes.startswith(b'\xff\xfe'):
                    text = raw_bytes.decode("utf-16-le")
                elif raw_bytes.startswith(b'\xfe\xff'):
                    text = raw_bytes.decode("utf-16-be")
                else:
                    text = raw_bytes.decode("utf-8")
                content += f"\n--- {filename} ---\n"
                content += text
                content += "\n"
                files_processed += 1
            except Exception as exc:
                errors += 1
                logger.error(f"Failed to read {filename}: {exc}")

    if files_processed == 0:
        logger.warning("No input files found in /data/input/")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        out.write(content)

    logger.info(f"Ingested {files_processed} files -> {OUTPUT_FILE}")
    save_metrics({
        "files_processed": files_processed,
        "errors": errors,
        "status": "ok" if errors == 0 else "error",
    })


if __name__ == "__main__":
    ingest()