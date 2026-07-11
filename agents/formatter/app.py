import json
import logging
import os
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer


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
    logger = logging.getLogger("formatter")
    if not logger.handlers:
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


logger = configure_logging()

INPUT_FILE = "/data/prioritized.txt"
OUTPUT_FILE = "/output/daily_digest.md"
OUTPUT_DIR = "/output"
METRICS_FILE = os.path.join(OUTPUT_DIR, "metrics.json")
METRICS_PORT = int(os.getenv("METRICS_PORT", "8000"))
PROMETHEUS_METRICS = os.getenv("PROMETHEUS_METRICS", "false").lower() in {"1", "true", "yes", "on"}
METRICS_KEEPALIVE = os.getenv("METRICS_KEEPALIVE", "false").lower() in {"1", "true", "yes", "on"}


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in {"/", ""}:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            body = "<html><body><h1>Multi-agent digest metrics</h1><p><a href='/metrics'>View Prometheus metrics</a></p></body></html>"
            self.wfile.write(body.encode("utf-8"))
        elif self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(render_metrics().encode("utf-8"))
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        return


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
    metrics["agents"]["formatter"] = {
        **metrics["agents"].get("formatter", {}),
        **agent_updates,
    }

    with open(METRICS_FILE, "w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2)

    return metrics


def render_metrics():
    metrics = load_metrics()
    lines = [
        "# HELP multi_agent_digest_run_success Whether the latest run finished successfully",
        "# TYPE multi_agent_digest_run_success gauge",
    ]

    agents = metrics.get("agents", {})
    success = 1 if all(value.get("status") == "ok" for value in agents.values()) else 0
    lines.append(f"multi_agent_digest_run_success {success}")

    for name, values in sorted(agents.items()):
        for key, value in values.items():
            if key == "status":
                continue
            if isinstance(value, bool):
                value = int(value)
            if isinstance(value, (int, float)):
                lines.append(f"multi_agent_digest_{name}_{key} {value}")

    return "\n".join(lines) + "\n"


def start_metrics_server():
    if not PROMETHEUS_METRICS:
        return None

    server = HTTPServer(("0.0.0.0", METRICS_PORT), MetricsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Metrics endpoint available at http://0.0.0.0:{METRICS_PORT}/metrics")
    return server


def format_to_markdown():
    with open(INPUT_FILE, "r", encoding="utf-8") as handle:
        lines = [line.strip() for line in handle if line.strip()]

    today = datetime.now().strftime('%Y-%m-%d')

    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        out.write("# Your Daily AI Digest\n\n")
        out.write(f"**Date:** {today}\n\n")
        out.write("## Top Insights\n\n")
        for line in lines:
            if '] ' in line:
                score = line.split(']')[0][1:]
                content = line.split('] ', 1)[1]
                out.write(f"- **Priority {score}**: {content}\n")
            else:
                out.write(f"- {line}\n")

    logger.info(f"Digest written to {OUTPUT_FILE}")
    save_metrics({
        "digest_generated": True,
        "items_rendered": len(lines),
        "status": "ok",
    })


if __name__ == "__main__":
    server = start_metrics_server()
    try:
        format_to_markdown()
        if server is not None and METRICS_KEEPALIVE:
            while True:
                time.sleep(60)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()