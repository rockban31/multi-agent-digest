# Session Plan

## Goal
Create a local plan file in the repository root to track session tasks.

## Tasks
- Create `plan.md` at the repository root.
- Note the current objective and any next steps.

## Notes
This plan file is specific to the current repo and can be used to track work during this session.

## How to Use a Local LLM for Full Privacy (Ollama)
If you want to keep all data on your machine and avoid sending anything to external APIs, you can swap the OpenAI API for a local model running through **Ollama**. Ollama lets you run open-source LLMs locally, handling model weight downloads, memory management, and serving an API.

To set up Ollama:

```
# Install Ollama (macOS or Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model (llama3 is a good general-purpose choice)
ollama pull llama3

# Verify it is running
ollama list
```

Replace the OpenAI API call in the Summarizer with a request to Ollama's local API:

```
import requests

def summarize_locally(text):
    """Call a local Ollama instance from inside a Docker container."""
    url = "http://host.docker.internal:11434/api/generate"
    payload = {
        "model": "llama3",
        "prompt": (
            "Summarize the following text into key "
            f"bullet points:\n\n{text}"
        ),
        "stream": False
    }
    try:
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json().get('response', 'No response')
    except requests.exceptions.RequestException as e:
        return f"Ollama error: {e}"
```

The `host.docker.internal` hostname lets a container communicate with services running on the host machine. Ollama runs on your host (not inside a container), so this is how the Summarizer reaches it.

> **Note:** On Linux, `host.docker.internal` may not resolve by default. Add this to your `docker-compose.yml` under the summarizer service: `extra_hosts: ["host.docker.internal:host-gateway"]`

Local models are slower than cloud APIs and require decent hardware (at least 8 GB of RAM for smaller models, 16 GB or more for larger ones). But they are free, fully private, and work without an internet connection.

## Example Seed Data and Expected Output
To test the full pipeline without real newsletters, create these sample input files:

`data/input/newsletter_ai.txt`

```
AI Weekly Roundup - January 2025
OpenAI released a new reasoning model this week.
URGENT: New EU AI Act regulations take effect in March.
Google announced updates to their Gemini model family.
A startup raised $50M for AI-powered code review tools.
```
`data/input/meeting_notes.txt`:

```
Team Standup Notes - Monday
IMPORTANT: Deadline for Q1 report is this Friday.
Action required: Review the updated API documentation.
Sprint velocity is on track. No blockers reported.
```
Expected output in `output/daily_digest.md`:

```
# Your Daily AI Digest

**Date:** 2025-01-20

## Top Insights

- **Priority 3**: IMPORTANT: Deadline for Q1 report due Friday
- **Priority 2**: URGENT: New EU AI Act regulations in March
- **Priority 1**: Action required: Review the updated API docs
- **Priority 0**: OpenAI released a new reasoning model
- **Priority 0**: Sprint velocity is on track
```

The exact summary text will vary depending on your LLM model and settings, but the structure and priority ordering should remain consistent.

## How to Automate Daily Execution
Now that the pipeline works end-to-end with a single command, you can schedule it to run automatically every morning.

### How to Use Cron on Linux or macOS
Open your crontab with `crontab -e` and add this line to run the pipeline every day at 7:00 AM:

```
0 7 * * * cd /path/to/multi-agent-digest && docker compose up --build >> cron.log 2>&1
```

The `>> cron.log 2>&1` part redirects all output (including errors) to a log file so you can check it later. Make sure your machine is running at the scheduled time and Docker Desktop is started.

### How to Use Task Scheduler on Windows
Open Task Scheduler and create a new task. Under "Actions," set the program to:

```
wsl -e bash -c 'cd /mnt/c/path/to/multi-agent-digest && docker compose up --build'
```

Set the trigger to fire every morning at your preferred time.

### How to Add Delivery Notifications
For the digest to be truly useful, you want it delivered to you rather than sitting in a folder. Here are three options:

**Email** — Extend the Formatter to send the digest via Python's `smtplib` module. You will need SMTP credentials for a service like Gmail, SendGrid, or Amazon SES.

**Slack** — Create an incoming webhook in your Slack workspace and POST the digest as a message. This takes about 10 lines of code.

**Notion or Obsidian** — Use their APIs to create a new page or note with the digest content each morning.

## Troubleshooting Common Errors
**Container exits with OOM error** — Large files or LLM processing are exceeding memory. Increase the memory limit in `docker-compose.yml` under `deploy > resources > limits > memory`. Try `1G`.

**Rate limit errors from OpenAI** — The retry logic handles temporary rate limits automatically. Check your OpenAI dashboard for usage caps.

`depends_on` **does not wait for completion** — Make sure you are using `condition: service_completed_successfully`, which requires Docker Compose v2.

**Permission denied on** `/output` — Volume mount permissions mismatch. Run `chmod -R 777 ./output` on the host, or add a `USER` directive to your Dockerfiles.

`OPENAI_API_KEY` **not found** — The `.env` file may be missing or not in the right directory. Create `.env` in the same folder as `docker-compose.yml` and verify with `docker compose config`.

**Cannot reach Ollama from container** — `host.docker.internal` may not be resolving on Linux. Add `extra_hosts: ["host.docker.internal:host-gateway"]` to the service in `docker-compose.yml`.

## Production Deployment Options
The `docker compose up` approach works well for personal use and development. When you are ready to deploy to a server or the cloud, here are your main options.

### Docker Swarm
Docker Swarm is the simplest step up from Compose. It lets you deploy across multiple machines with minimal changes to your existing Compose file:

```
docker swarm init
docker stack deploy -c docker-compose.yml morning-brief
```

### Kubernetes
For production at scale, Kubernetes gives you more control over scheduling, scaling, and fault tolerance. Use Kubernetes **Jobs** (not Deployments) for batch agents that run once and exit. Set resource requests and limits on each container so the cluster scheduler can allocate resources efficiently. Store API keys in **Kubernetes Secrets**, and use **CronJobs** for scheduled daily execution — they work like cron but are managed by the cluster.

### Cloud Platforms
All major cloud providers offer managed container services that can run this pipeline:

**AWS** — ECS Fargate with scheduled tasks for serverless execution, or EKS for managed Kubernetes.

**Azure** — Azure Container Instances for simple runs, or AKS for managed Kubernetes.

**GCP** — Cloud Run Jobs for serverless batch processing, or GKE for managed Kubernetes.

## Conclusion and Next Steps
In this handbook, you built a multi-agent AI system from scratch. You created four specialized Python agents, containerized each one with Docker, orchestrated them with Docker Compose, and added secrets handling, structured logging, retry logic, and graceful fallbacks.

The core patterns you learned — separation of concerns, containerized agents, shared-volume communication, and defensive coding against external APIs — apply far beyond this specific use case. Any time you need a reliable, modular, and reproducible AI workflow, these patterns are a solid foundation.

Here are some directions to explore next:

**Agent collaboration frameworks** — Tools like CrewAI and LangGraph let you build agents that delegate tasks to each other, negotiate priorities, and collaborate in more sophisticated ways.

**Local and fine-tuned models** — Experiment with Ollama or vLLM to run models locally. Fine-tune a small model specifically for summarization to get better results at lower cost.

**Event-driven architectures** — Replace the shared volume with Redis or RabbitMQ so agents react to events in real time rather than running on a schedule.

**Feedback loops** — Add an agent that evaluates the quality of the daily digest and adjusts the Summarizer's prompts over time. This is how production agent systems learn and improve.