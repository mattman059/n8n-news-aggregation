<div align="center">

# News Intelligence Pipeline

**Automated security news triage powered by Claude AI, n8n, and Google Sheets**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![n8n](https://img.shields.io/badge/n8n-Workflow-EA4B71?logo=n8n&logoColor=white)](https://n8n.io)
[![Claude](https://img.shields.io/badge/Claude-Opus_4.6-D97706?logo=anthropic&logoColor=white)](https://anthropic.com)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://python.org)

*Ingest 31 curated security feeds. Score every article with AI. Route signal from noise — automatically.*

</div>

---

## Overview

The News Intelligence Pipeline is a self-hosted, Docker-native automation stack that continuously monitors 31 cybersecurity RSS feeds, scores each article for relevance using Claude Opus, performs deep technical analysis on high-value content, and routes results to a structured Google Sheet — all without manual intervention.

Built for security practitioners, threat intel analysts, and offensive security teams who need to stay current without drowning in feed volume.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EVERY 2 HOURS                                       │
│                                                                             │
│  Feed Manager ──────► Split Articles ──► Scoring AI ──► Route Article      │
│  (31 feeds)           (per item)         (Claude)        (tier logic)       │
│                                                               │             │
│                                              ┌────────────────┤             │
│                                              │                │             │
│                                         Audit Log      Quality Filters      │
│                                         (JSONL)              │             │
│                                                    ┌─────────┼─────────┐   │
│                                                    │         │         │   │
│                                               score ≥ 7  score 4-6  score<4│
│                                                    │         │         │   │
│                                               Content AI  For Review  Archive│
│                                               (Claude)    Sheet       Sheet │
│                                                    │                        │
│                                             Published Sheet                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Features

- **31 curated feeds** across threat intelligence, offensive security, malware research, vulnerability disclosure, AI security, and exploit development
- **Two-stage AI pipeline** — lightweight scoring pass on every article, deep analysis only on high-signal content (minimizes API cost)
- **Configurable scoring thresholds** — adjust `SCORE_PUBLISH_MIN` and `SCORE_REVIEW_MIN` in `.env` without touching the workflow
- **Hot-reloadable feed config** — add, remove, or disable feeds in `config/feeds.yaml` with no container restart
- **Structured audit trail** — every scoring decision logged to JSONL with `/recent` and `/stats` REST endpoints
- **Full deduplication** — feed-manager deduplicates articles by URL hash across all sources within each poll cycle
- **Zero-maintenance operation** — cron-triggered, containerized, stateless except for audit logs and n8n workflow data

---

## Stack

| Service | Technology | Purpose |
|---|---|---|
| **n8n** | `n8nio/n8n:latest` | Workflow engine, credential management, scheduling |
| **feed-manager** | Python 3.11 / FastAPI | Aggregates all 31 feeds, normalizes, deduplicates |
| **score-logger** | Python 3.11 / Flask | Audit log REST API (`/log`, `/recent`, `/stats`) |
| **Redis** | `redis:7-alpine` | n8n queue state, AOF persistence |
| **Claude Opus 4.6** | Anthropic API | Article scoring (1–10) + deep technical analysis |
| **Google Sheets** | Sheets API v4 | Output destination — Published, For Review, Archive |

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) with Compose v2
- [Anthropic API key](https://console.anthropic.com/)
- Google Cloud service account with the **Sheets API** enabled

---

## Quick Start

```bash
git clone https://github.com/yourusername/news-intelligence-pipeline.git
cd news-intelligence-pipeline
bash setup.sh
```

`setup.sh` validates dependencies, builds images, starts the stack, and walks you through the remaining credential steps.

---

## Setup Guide

### 1. Environment

```bash
cp .env.example .env
# Edit .env — required: ANTHROPIC_API_KEY, GOOGLE_SPREADSHEET_ID
# Recommended: change N8N_PASSWORD and REDIS_PASSWORD
```

### 2. Google Sheets

1. [Google Cloud Console](https://console.cloud.google.com/) → create a project → enable **Google Sheets API**
2. IAM & Admin → Service Accounts → Create → download JSON key → save as `config/google-credentials.json`
3. Create a Google Sheet with three tabs: `Published`, `For Review`, `Archive`
4. Share the sheet with the service account email (`client_email` in the JSON) — **Editor** access
5. Copy the spreadsheet ID from the URL into `GOOGLE_SPREADSHEET_ID` in `.env`

**Sheet headers:**

| Tab | Columns |
|---|---|
| Published | Date, Score, Title, Headline, URL, Source, Category, Tags, TLDR, Analysis, So What, Action Items, Processed At |
| For Review | Date, Score, Title, URL, Source, Category, Tags, TLDR, Reason |
| Archive | Date, Score, Title, URL, Source, Category, Reason |

### 3. n8n Credentials

After `docker compose up -d`, open [http://localhost:5678](http://localhost:5678):

1. **Settings → Credentials → New → Anthropic** — paste your API key, name it `Anthropic API`
2. **Settings → Credentials → New → Google Sheets → Service Account** — paste the contents of `config/google-credentials.json`, name it `Google Sheets`
3. **Workflows → Import from File → `workflow.json`** → Activate

---

## Configuration

All tuneable parameters live in `.env`:

| Variable | Default | Description |
|---|---|---|
| `N8N_USER` | `admin` | n8n UI login username |
| `N8N_PASSWORD` | — | n8n UI login password |
| `ANTHROPIC_API_KEY` | — | Anthropic secret key |
| `CLAUDE_MODEL` | `claude-opus-4-6` | Claude model for scoring and analysis |
| `GOOGLE_SPREADSHEET_ID` | — | Target spreadsheet ID (from URL) |
| `SHEET_PUBLISHED` | `Published` | Tab name for high-score articles |
| `SHEET_REVIEW` | `For Review` | Tab name for mid-score articles |
| `SHEET_ARCHIVE` | `Archive` | Tab name for low-score articles |
| `SCORE_PUBLISH_MIN` | `7` | Min score → full analysis + Published tab |
| `SCORE_REVIEW_MIN` | `4` | Min score → For Review tab |
| `FEED_LIMIT` | `100` | Max articles fetched per poll cycle |
| `RSS_POLL_CRON` | `0 */2 * * *` | Cron expression for polling interval |
| `REDIS_PASSWORD` | — | Redis auth password |
| `TIMEZONE` | `America/Chicago` | n8n scheduler timezone |

---

## Feed Management

Feeds are defined in `config/feeds.yaml` and **hot-reload on every request** — no container restart required.

```yaml
feeds:
  - name: "Krebs on Security"
    url: "https://krebsonsecurity.com/feed/"
    category: "threat-intelligence"
    enabled: true
```

**Built-in categories:**

| Category | Example Sources |
|---|---|
| `threat-intelligence` | Krebs, BleepingComputer, Dark Reading, Recorded Future |
| `offensive-security` | SpecterOps, ired.team, MDSec, NCC Group, OffSec |
| `malware-research` | Unit 42, Talos, Elastic Security Labs, Project Zero |
| `vulnerability` | CISA Advisories, Rapid7, Tenable |
| `ai-security` | Trail of Bits, AI Village |
| `exploit-dev` | j00ru, Hex-Rays, modexp |

To add a feed: append an entry to `feeds.yaml`. To pause a feed: set `enabled: false`.

---

## AI Scoring Rubric

Claude scores each article 1–10 against this rubric:

| Score | Category |
|---|---|
| **8–10** | Breaking CVEs, novel attack techniques, APT activity, significant tool releases, nation-state operations |
| **5–7** | General security news, patch roundups, substantive industry commentary |
| **3–4** | Vendor marketing, vague op-eds, low-information pieces |
| **1–2** | Off-topic, clickbait, duplicate coverage |

Articles scoring at or above `SCORE_PUBLISH_MIN` (default: 7) receive a second Claude pass that generates a rewritten headline, 3–5 sentence technical analysis, practical "so what", and actionable items.

---

## Monitoring

```bash
# Recent scoring decisions
curl -s http://localhost:5001/recent | jq '.[] | {title, score, event}'

# Pipeline statistics — counts by tier and by day
curl -s http://localhost:5001/stats

# Live n8n logs
docker compose logs -f n8n

# Live feed-manager logs
docker compose logs -f feed-manager
```

---

## Operations

```bash
# Start
docker compose up -d

# Stop
docker compose down

# Rebuild after code changes
docker compose build --no-cache feed-manager score-logger
docker compose up -d

# Full wipe — removes all persistent data
docker compose down -v && rm -rf n8n-data logs
```

---

## Project Structure

```
.
├── docker-compose.yml           # 4-service stack definition
├── workflow.json                # n8n workflow — import this into n8n
├── .env.example                 # Environment template — copy to .env
├── setup.sh                     # First-run setup script
│
├── feed-manager/
│   ├── feed_manager.py          # FastAPI aggregator — fetches, normalizes, deduplicates
│   └── Dockerfile
│
├── scripts/
│   ├── logger_api.py            # Flask audit API — /log, /recent, /stats
│   └── Dockerfile.logger
│
└── config/
    ├── feeds.yaml               # 31 RSS feed definitions (hot-reloads)
    └── google-credentials.json  # Service account key — NOT committed to git
```

---

## Extending

**Cross-run deduplication**
Add a Redis node in the n8n workflow after Split Articles. Check `dedup:<article_id>` — skip if exists, set with 7-day TTL if new.

**Alerts**
Add an HTTP Request node after "Log to Published Sheet" posting to a Slack webhook or Telegram bot.

**Different domain**
Change the scoring system prompt in the workflow to any niche — finance, legal, biotech, policy. The rest of the pipeline is domain-agnostic.

**Local model**
Replace the Anthropic credential nodes with HTTP Request nodes pointing to `http://host.docker.internal:11434` (Ollama).

**Higher volume**
Replace Google Sheets nodes with n8n PostgreSQL nodes. Keep Sheets as a reporting export target.

---

## License

MIT — see [LICENSE](LICENSE)

---

<div align="center">
Built with <a href="https://n8n.io">n8n</a> · <a href="https://anthropic.com">Claude</a> · <a href="https://fastapi.tiangolo.com">FastAPI</a> · <a href="https://flask.palletsprojects.com">Flask</a>
</div>
