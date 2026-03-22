# News Intelligence Pipeline

n8n + Claude (Anthropic) + Google Sheets — automated news scoring, analysis, and triage across 31 curated security feeds.

## Architecture

```
Schedule Trigger (every 2h)
    │
    ▼
Feed Manager (FastAPI)    ← fetches all 31 feeds, deduplicates by URL hash
    │
    ▼
Split Articles            ← one n8n item per article
    │
    ▼
Scoring AI (Claude)       ← scores 1–10 for cybersecurity relevance
    │
    ▼
Parse Score               ← extracts JSON, fallback on parse error
    │
    ▼
Route Article             ← assigns tier via env var thresholds
    │
    ├──── Audit Log ───────→ score-logger (JSONL + /stats endpoint)
    │
    ▼
Quality Filter 1 (tier == published?)
    │ YES                      NO
    ▼                           ▼
Content AI (Claude)       Quality Filter 2 (tier == review?)
full analysis report           │ YES           NO
    │                          ▼               ▼
    ▼                     For Review        Archive
Published Sheet           Sheet             Sheet
```

## Stack

| Service        | Build                     | Port | Purpose                        |
|----------------|---------------------------|------|--------------------------------|
| `n8n`          | n8nio/n8n:latest          | 5678 | Workflow engine + UI           |
| `feed-manager` | feed-manager/Dockerfile   | 8080 | FastAPI multi-feed aggregator  |
| `redis`        | redis:7-alpine            | —    | n8n state + dedup cache        |
| `score-logger` | scripts/Dockerfile.logger | 5001 | Audit log REST API             |

---

## Prerequisites

- Docker + Docker Compose v2
- Anthropic API key: https://console.anthropic.com/
- Google Cloud service account with Sheets API enabled

---

## Quick Start

```bash
bash setup.sh
```

The script validates dependencies, builds images, and starts the stack. Follow the prompts.

---

## File Structure

```
n8n_News_Aggregator/
├── docker-compose.yml           # 4-service stack
├── workflow.json                # n8n workflow (import this)
├── .env.example                 # copy to .env and fill in values
├── setup.sh                     # first-run automation
├── pipeline-README.md           # this file
│
├── feed-manager/
│   ├── feed_manager.py          # FastAPI feed aggregator
│   └── Dockerfile
│
├── scripts/
│   ├── logger_api.py            # Flask audit logger
│   └── Dockerfile.logger
│
├── config/
│   ├── feeds.yaml               # 31 configurable RSS feeds (hot-reloads)
│   └── google-credentials.json  # service account key (NOT in git)
│
├── n8n-data/                    # n8n state (created at runtime, NOT in git)
└── logs/                        # audit JSONL (created at runtime, NOT in git)
```

---

## Google Sheets Setup

### 1. Service Account

1. https://console.cloud.google.com/ → create/select a project
2. Enable **Google Sheets API**
3. IAM & Admin → Service Accounts → Create → download JSON key
4. Save as `config/google-credentials.json`

### 2. Spreadsheet

Create a Google Sheet with three tabs and add headers in Row 1:

**Published:**
```
Date | Score | Title | Headline | URL | Source | Category | Tags | TLDR | Analysis | So What | Action Items | Processed At
```

**For Review:**
```
Date | Score | Title | URL | Source | Category | Tags | TLDR | Reason
```

**Archive:**
```
Date | Score | Title | URL | Source | Category | Reason
```

Share the spreadsheet with the service account `client_email` (Editor access).
Copy the spreadsheet ID from the URL → set as `GOOGLE_SPREADSHEET_ID` in `.env`.

---

## n8n Credential Setup

After the stack starts, go to http://localhost:5678.

**Anthropic:**
Settings → Credentials → New → Anthropic → paste API key → name it `Anthropic API`

**Google Sheets:**
Settings → Credentials → New → Google Sheets → Service Account → paste JSON → name it `Google Sheets`

**Import workflow:**
Workflows → Import from File → select `workflow.json` → activate

---

## Configuration (.env)

| Variable              | Default              | Description                                  |
|-----------------------|----------------------|----------------------------------------------|
| `N8N_USER`            | admin                | n8n UI username                              |
| `N8N_PASSWORD`        | —                    | n8n UI password (change this)                |
| `ANTHROPIC_API_KEY`   | —                    | Anthropic secret key                         |
| `CLAUDE_MODEL`        | claude-opus-4-6      | Claude model for scoring and analysis        |
| `GOOGLE_SPREADSHEET_ID` | —                  | Target spreadsheet ID (from URL)             |
| `SHEET_PUBLISHED`     | Published            | Tab name for high-score articles             |
| `SHEET_REVIEW`        | For Review           | Tab name for mid-score articles              |
| `SHEET_ARCHIVE`       | Archive              | Tab name for low-score articles              |
| `SCORE_PUBLISH_MIN`   | 7                    | Min score for full analysis + Published tab  |
| `SCORE_REVIEW_MIN`    | 4                    | Min score for For Review tab                 |
| `FEED_LIMIT`          | 100                  | Max articles fetched per poll cycle          |
| `RSS_POLL_CRON`       | 0 */2 * * *          | Cron expression for polling interval         |
| `REDIS_PASSWORD`      | —                    | Redis auth password (change this)            |
| `TIMEZONE`            | America/Chicago      | Timezone for n8n                             |

---

## Managing Feeds

Edit `config/feeds.yaml` to add, remove, or toggle feeds. The feed-manager hot-reloads this file on every request — **no container restart needed**.

```yaml
feeds:
  - name: "Krebs on Security"
    url: "https://krebsonsecurity.com/feed/"
    category: "threat-intelligence"
    enabled: true
```

Available categories: `threat-intelligence`, `offensive-security`, `malware-research`, `vulnerability`, `ai-security`, `exploit-dev`

---

## Useful Commands

```bash
# Start stack
docker compose up -d

# View recent scoring decisions
curl -s http://localhost:5001/recent | jq '.[] | {title, score, event}'

# View pipeline statistics (by tier, by day)
curl -s http://localhost:5001/stats

# Stream n8n logs
docker compose logs -f n8n

# Stream feed-manager logs
docker compose logs -f feed-manager

# Rebuild after code changes
docker compose build --no-cache feed-manager score-logger && docker compose up -d

# Stop
docker compose down

# Full wipe (removes all data)
docker compose down -v && rm -rf n8n-data logs
```

---

## Extending

**Cross-run deduplication:** Add a Redis SET node in n8n after Split Articles — check/set `dedup:<article_id>` with 7-day TTL using the n8n Redis credential node.

**Slack/Telegram alerts:** Add an HTTP Request node after "Log to Published Sheet" POSTing to your webhook.

**Local model:** Replace Anthropic credential with an Ollama HTTP Request node at `http://host.docker.internal:11434`.

**PostgreSQL backend:** Replace Google Sheets nodes with n8n PostgreSQL nodes for higher volume and full-text search.

**Different niche:** Change the scoring system prompt in the workflow to target any domain (finance, biotech, legal, etc.).
