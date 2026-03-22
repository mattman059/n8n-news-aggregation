#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# setup.sh — first-run setup for news-pipeline
# Run once before `docker compose up`
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; NC='\033[0m'

info()  { echo -e "${GREEN}[+]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*" >&2; exit 1; }

# ── 1. Check dependencies ─────────────────────────────────────────────────────
command -v docker &>/dev/null || error "docker not found — install Docker Desktop first"
docker compose version &>/dev/null || \
  command -v docker-compose &>/dev/null || error "docker compose plugin not found"

# ── 2. Copy env template ──────────────────────────────────────────────────────
if [[ ! -f .env ]]; then
  cp .env.example .env
  warn ".env created from template — edit it before continuing"
  warn "  Required: ANTHROPIC_API_KEY, GOOGLE_SPREADSHEET_ID"
  warn "  Recommended: change N8N_PASSWORD and REDIS_PASSWORD"
  echo ""
  read -rp "Press ENTER after editing .env to continue, or Ctrl+C to abort..." _
fi

source .env

# ── 3. Validate required vars ─────────────────────────────────────────────────
[[ -z "${ANTHROPIC_API_KEY:-}" ]]     && error "ANTHROPIC_API_KEY is not set in .env"
[[ -z "${GOOGLE_SPREADSHEET_ID:-}" ]] && error "GOOGLE_SPREADSHEET_ID is not set in .env"

[[ "${N8N_PASSWORD:-changeme}" == "changeme" ]] && \
  warn "N8N_PASSWORD is still the default — change it in .env for production"
[[ "${REDIS_PASSWORD:-redis_secret}" == "redis_secret" ]] && \
  warn "REDIS_PASSWORD is still the default — change it in .env for production"

# ── 4. Check Google credentials ───────────────────────────────────────────────
if [[ ! -f config/google-credentials.json ]]; then
  warn "config/google-credentials.json not found"
  warn "Create a Google Cloud service account, enable Sheets API, download the key JSON,"
  warn "save it as config/google-credentials.json, and share your spreadsheet with the"
  warn "service account email (Editor access)."
  warn "See pipeline-README.md for step-by-step instructions."
  echo ""
  read -rp "Press ENTER once credentials are in place, or Ctrl+C to abort..." _
fi

# ── 5. Create runtime directories ─────────────────────────────────────────────
info "Creating runtime directories..."
mkdir -p n8n-data logs config

# ── 6. Set n8n data permissions (n8n runs as UID 1000) ────────────────────────
if [[ "$(id -u)" != "0" ]]; then
  warn "Not running as root — if n8n has permission errors, run:"
  warn "  sudo chown -R 1000:1000 n8n-data"
fi
chmod -R 777 n8n-data 2>/dev/null || true

# ── 7. Build images ───────────────────────────────────────────────────────────
info "Building feed-manager and score-logger images..."
docker compose build --no-cache feed-manager score-logger

# ── 8. Pull remaining images ──────────────────────────────────────────────────
info "Pulling n8n and Redis images..."
docker compose pull n8n redis

# ── 9. Start stack ────────────────────────────────────────────────────────────
info "Starting stack..."
docker compose up -d

# ── 10. Wait for services ─────────────────────────────────────────────────────
info "Waiting for feed-manager health check..."
for i in {1..12}; do
  if docker compose exec feed-manager python -c \
      "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" \
      &>/dev/null 2>&1; then
    info "Feed-manager is healthy"
    break
  fi
  [[ $i -eq 12 ]] && warn "Feed-manager health check timed out — check logs with: docker compose logs feed-manager"
  sleep 5
done

echo ""
info "Stack is up!"
echo ""
echo "  n8n UI:         http://localhost:5678"
echo "  Score logger:   http://localhost:5001/recent"
echo "  Logger stats:   http://localhost:5001/stats"
echo "  Feed list:      (internal) http://feed-manager:8080/feeds"
echo ""
echo "Next steps:"
echo "  1. Log into n8n at http://localhost:5678"
echo "  2. Go to Settings > Credentials and add:"
echo "     - Anthropic API (paste your ANTHROPIC_API_KEY)"
echo "     - Google Sheets OAuth2 (service account JSON)"
echo "  3. Import workflow: Workflows > Import from file > workflow.json"
echo "  4. Activate the workflow"
echo ""
echo "Useful commands:"
echo "  docker compose logs -f n8n            # stream n8n logs"
echo "  docker compose logs -f feed-manager   # stream feed-manager logs"
echo "  docker compose restart feed-manager   # reload after editing feeds.yaml"
echo "  curl http://localhost:5001/stats       # view pipeline statistics"
echo ""
info "Done."
