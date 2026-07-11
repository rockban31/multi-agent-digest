# Multi-Agent Digest

This repository runs a small multi-agent pipeline that ingests text files, summarizes them, prioritizes the content, and formats a daily digest.

## What the pipeline does

- Ingestor: reads files from `data/input` and writes `data/ingested.txt`
- Summarizer: calls the Kimchi Inference API (OpenAI-compatible) to produce a summary in `data/summary.txt`
- Prioritizer: ranks lines by priority into `data/prioritized.txt`
- Formatter: writes the final digest to `output/daily_digest.md`

## Prerequisites

- Docker Desktop installed and running
- A Kimchi account and API key — sign up at [app.kimchi.dev](https://app.kimchi.dev) and create one under Settings → API Keys

You do NOT need Ollama or any local model. The summarizer talks to Kimchi's hosted inference API over HTTPS.

## Run locally with Docker

```powershell
docker compose up --build
```

This will build and run all four agents.

## Kimchi configuration

The summarizer uses the Kimchi Inference API (OpenAI-compatible):

- Default URL: `https://llm.kimchi.dev/openai/v1/chat/completions`
- Default model: `kimi-k2.7`

Set the API key in `.env` (or your shell environment):

```powershell
$env:KIMCHI_API_KEY="your-kimchi-api-key-here"
$env:KIMCHI_MODEL="kimi-k2.7"
```

You can override the endpoint or model with `KIMCHI_API_URL` and `KIMCHI_MODEL` respectively. Other available models include `minimax-m2.7` and `nemotron-3-super-fp4`.

## Observability

The project also includes basic observability support:

- Structured JSON logs from each agent
- A metrics JSON file written to `output/metrics.json`
- A Prometheus-style metrics endpoint at `http://localhost:8000/metrics`
- A Prometheus container and Grafana setup via `docker-compose.grafana.yml`

## Monitoring stack

Start the monitoring containers:

```powershell
docker compose -f docker-compose.grafana.yml up -d
```

Then open:

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

Grafana login:

- Username: `admin`
- Password: `admin`

## Next steps

- Make sure your `KIMCHI_API_KEY` is set and valid
- Add alert rules in Prometheus for failed runs or missing digest output
- Expand the metrics endpoint with more business-level KPIs
