"""
feed_manager.py
---------------
Lightweight FastAPI service that:
  1. Reads feeds.yaml (hot-reloaded on each request)
  2. Fetches & parses RSS/Atom feeds
  3. Returns normalized article objects for n8n to consume

Endpoints:
  GET /feeds          — list all configured feed sources
  GET /articles       — fetch + parse all feeds, return article list
  GET /articles?limit=N  — cap results
  GET /health         — liveness probe
"""

import yaml
import httpx
import feedparser
import hashlib
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel

app = FastAPI(title="News Pipeline Feed Manager", version="1.0.0")

FEEDS_FILE = "/app/feeds.yaml"


# ── Models ─────────────────────────────────────────────────────

class FeedSource(BaseModel):
    name: str
    url: str
    category: str
    enabled: bool = True


class Article(BaseModel):
    id: str                    # SHA256 of URL (dedup key)
    title: str
    url: str
    summary: str
    published: Optional[str]
    source_name: str
    source_category: str


# ── Helpers ────────────────────────────────────────────────────

def load_feeds() -> list[FeedSource]:
    with open(FEEDS_FILE, "r") as f:
        data = yaml.safe_load(f)
    return [FeedSource(**feed) for feed in data.get("feeds", [])]


def article_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def parse_feed(source: FeedSource) -> list[Article]:
    try:
        resp = httpx.get(source.url, timeout=10, follow_redirects=True)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.text)
        articles = []
        for entry in parsed.entries:
            url = entry.get("link", "")
            if not url:
                continue
            summary = entry.get("summary", entry.get("description", ""))
            # Strip basic HTML tags from summary
            import re
            summary = re.sub(r"<[^>]+>", "", summary).strip()[:1000]
            published = None
            if hasattr(entry, "published"):
                published = entry.published
            articles.append(Article(
                id=article_id(url),
                title=entry.get("title", "Untitled"),
                url=url,
                summary=summary,
                published=published,
                source_name=source.name,
                source_category=source.category,
            ))
        return articles
    except Exception as e:
        print(f"[WARN] Failed to fetch {source.name} ({source.url}): {e}")
        return []


# ── Routes ─────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/feeds", response_model=list[FeedSource])
def list_feeds():
    return load_feeds()


@app.get("/articles", response_model=list[Article])
def get_articles(limit: Optional[int] = Query(default=None, ge=1, le=500)):
    feeds = [f for f in load_feeds() if f.enabled]
    if not feeds:
        raise HTTPException(status_code=404, detail="No enabled feeds configured")

    all_articles: list[Article] = []
    for feed in feeds:
        all_articles.extend(parse_feed(feed))

    # Deduplicate by ID
    seen = set()
    unique = []
    for a in all_articles:
        if a.id not in seen:
            seen.add(a.id)
            unique.append(a)

    if limit:
        unique = unique[:limit]

    return unique
