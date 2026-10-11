"""Research: verified catalogue from the DB + live external lookup.

Live lookup proxies the configured research API (Semantic Scholar by
default). If RESEARCH_API_URL is empty or the upstream fails, the endpoint
returns 502 and the frontend stays on the verified catalogue.
"""

import json
import urllib.parse
import urllib.request
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import current_user
from ..models import Article, User

router = APIRouter(prefix="/research", tags=["research"])


def _full(a: Article) -> dict:
    return {"id": a.id, "title": a.title, "source": a.source, "date": a.date,
            "readMinutes": a.read_minutes, "art": a.art, "accent": a.accent,
            "excerpt": a.excerpt, "tags": a.tags or [], "body": a.body or [], "verified": True}


@router.get("/articles")
def list_articles(
    q: str = Query(default="", max_length=120),
    tag: str = Query(default="", max_length=60),
    _user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    rows = db.query(Article).order_by(Article.date.desc()).all()
    items = [_full(a) for a in rows]
    needle = q.strip().lower()
    if needle:
        items = [a for a in items
                 if needle in a["title"].lower() or needle in a["excerpt"].lower()
                 or any(needle in t.lower() for t in a["tags"])]
    if tag and tag != "All":
        items = [a for a in items if tag in a["tags"]]
    return {"articles": items, "total": len(items), "source": "database-verified"}


@router.get("/articles/{article_id}")
def get_article(article_id: str, _user: User = Depends(current_user), db: Session = Depends(get_db)):
    a = db.get(Article, article_id)
    if not a:
        raise HTTPException(status_code=404, detail="Article not found")
    return _full(a)


@router.get("/live")
def live_lookup(
    q: str = Query(min_length=3, max_length=200),
    limit: int = Query(default=6, ge=1, le=20),
    _user: User = Depends(current_user),
):
    if not settings.RESEARCH_API_URL:
        raise HTTPException(status_code=502, detail="Live lookup is not configured on this server.")
    params = urllib.parse.urlencode({
        "query": q, "limit": limit,
        "fields": "title,authors,year,abstract,url,citationCount,venue",
    })
    req = urllib.request.Request(f"{settings.RESEARCH_API_URL}?{params}",
                                 headers={"User-Agent": "NanoSphere/1.0 (mailto:research@nanosphere.io)"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.load(resp)
    except Exception:
        raise HTTPException(status_code=502, detail="Upstream research API unreachable — try again shortly.")
    out = []
    for p in payload.get("data", [])[:limit]:
        authors = ", ".join(a.get("name", "") for a in (p.get("authors") or [])[:3])
        out.append({"paperId": p.get("paperId", ""), "title": p.get("title", "Untitled"),
                    "authors": authors, "year": p.get("year"), "venue": p.get("venue", ""),
                    "abstract": (p.get("abstract") or "")[:600],
                    "citations": p.get("citationCount", 0), "url": p.get("url", "")})
    return {"papers": out, "total": len(out), "source": "semantic-scholar"}
