import json
import logging
import os
import time
from datetime import datetime

import requests


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
    logger = logging.getLogger("summarizer")
    if not logger.handlers:
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


logger = configure_logging()

INPUT_FILE = "/data/ingested.txt"
OUTPUT_FILE = "/data/summary.txt"
OUTPUT_DIR = "/output"
METRICS_FILE = os.path.join(OUTPUT_DIR, "metrics.json")

KIMCHI_API_URL = os.getenv("KIMCHI_API_URL", "https://llm.kimchi.dev/openai/v1/chat/completions")
KIMCHI_API_KEY = os.getenv("KIMCHI_API_KEY", "")
KIMCHI_MODEL = os.getenv("KIMCHI_MODEL", "kimi-k2.7")

MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


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
    metrics["agents"]["summarizer"] = {
        **metrics["agents"].get("summarizer", {}),
        **agent_updates,
    }

    with open(METRICS_FILE, "w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2)

    return metrics


def summarize(text, retries=MAX_RETRIES, model=KIMCHI_MODEL):
    """Call the Kimchi Inference API (OpenAI-compatible) with retry logic."""
    if not KIMCHI_API_KEY:
        raise RuntimeError("KIMCHI_API_KEY is not set. Set it in your environment or .env file.")

    for attempt in range(retries):
        try:
            started = time.monotonic()
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Summarize the following text into key bullet points:\n\n"
                            f"{text[:8000]}"
                        ),
                    }
                ],
            }
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {KIMCHI_API_KEY}",
            }
            response = requests.post(KIMCHI_API_URL, json=payload, headers=headers, timeout=120)
            latency = time.monotonic() - started
            data = response.json()

            # Handle model_not_found ("410 Gone") — extract replacement and retry
            if response.status_code == 410 and data.get("error", {}).get("type") == "model_not_found":
                replacement = data["error"].get("replacement", "")
                if replacement and model != replacement:
                    logger.warning(f"Model {model!r} is deprecated, retrying with {replacement!r}")
                    return summarize(text, retries=retries - attempt - 1, model=replacement)
                raise RuntimeError(f"Model {model!r} is no longer available") from None

            response.raise_for_status()

            summary = data["choices"][0]["message"]["content"]
            usage = data.get("usage")
            logger.info("Summarization completed")
            return summary, latency, usage
        except requests.exceptions.RequestException as exc:
            wait = RETRY_DELAY * (attempt + 1)
            logger.warning(f"Kimchi API request failed: {exc}. Retrying in {wait}s...")
            time.sleep(wait)
        except (KeyError, IndexError, ValueError) as exc:
            raise RuntimeError(f"Unexpected Kimchi API response: {exc}") from exc
    raise RuntimeError("Max retries exceeded for Kimchi API call")


def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as handle:
        raw_text = handle.read()

    metrics = {
        "latency_seconds": None,
        "prompt_tokens": None,
        "completion_tokens": None,
        "retries": 0,
        "errors": 0,
        "used_fallback": False,
        "status": "ok",
    }

    if not raw_text.strip():
        logger.warning("Empty input. Writing fallback summary.")
        summary = "No content to summarize."
        metrics["used_fallback"] = True
    else:
        try:
            summary, latency, usage = summarize(raw_text)
            metrics["latency_seconds"] = round(latency, 3)
            if usage is not None:
                metrics["prompt_tokens"] = usage.get("prompt_tokens")
                metrics["completion_tokens"] = usage.get("completion_tokens")
        except Exception as exc:
            logger.error(f"Summarization failed: {exc}")
            summary = f"Summarization failed: {exc}"
            metrics["errors"] = 1
            metrics["status"] = "error"

    with open(OUTPUT_FILE, "w", encoding="utf-8") as handle:
        handle.write(summary)

    logger.info(f"Summary written to {OUTPUT_FILE}")
    save_metrics(metrics)


if __name__ == "__main__":
    main()