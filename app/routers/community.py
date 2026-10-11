"""Community forum — threads, replies and likes in the database.

Reads: any authenticated user (guests can browse).
Writes (threads, replies, likes): members only, so every post links to a
real email account. All rows are owner-scoped where it matters.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user, require_member
from ..models import Reply, Thread, ThreadLike, User

router = APIRouter(prefix="/community", tags=["community"])

VALID_TAGS = {"Formulation", "Characterization", "Showcase", "Safety", "Business", "General"}


class ThreadIn(BaseModel):
    title: str = Field(min_length=4, max_length=300)
    body: str = Field(min_length=4, max_length=5000)
    tag: str = Field(default="General", max_length=60)


class ReplyIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


def _iso(dt) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _thread_out(t: Thread, db: Session, user_id: str | None = None) -> dict:
    replies = db.query(Reply).filter(Reply.thread_id == t.id).order_by(Reply.created_at).all()
    liked = False
    if user_id:
        liked = db.query(ThreadLike).filter(
            ThreadLike.owner_id == user_id, ThreadLike.thread_id == t.id).first() is not None
    return {"id": t.id, "title": t.title, "body": t.body, "tag": t.tag, "author": t.author,
            "likes": t.likes_count, "liked": liked, "at": _iso(t.created_at),
            "replies": [{"id": r.id, "author": r.author, "text": r.text, "at": _iso(r.created_at)} for r in replies]}


@router.get("/threads")
def list_threads(tag: str = "", q: str = "", user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Thread).order_by(Thread.created_at.desc()).limit(100).all()
    items = [_thread_out(t, db, user.id) for t in rows]
    if tag and tag != "All":
        items = [t for t in items if t["tag"] == tag]
    needle = (q or "").strip().lower()
    if needle:
        items = [t for t in items if needle in t["title"].lower() or needle in t["body"].lower()]
    return {"threads": items, "total": len(items), "source": "database"}


@router.post("/threads", status_code=201)
def create_thread(body: ThreadIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    t = Thread(owner_id=user.id, title=body.title.strip(), body=body.body.strip(),
               tag=body.tag if body.tag in VALID_TAGS else "General", author=user.name)
    db.add(t)
    db.commit()
    db.refresh(t)
    return _thread_out(t, db, user.id)


@router.post("/threads/{thread_id}/replies", status_code=201)
def add_reply(thread_id: str, body: ReplyIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    t = db.get(Thread, thread_id)
    if not t:
        raise HTTPException(status_code=404, detail="Thread not found")
    r = Reply(thread_id=t.id, owner_id=user.id, author=user.name, text=body.text.strip())
    db.add(r)
    db.commit()
    return {"id": r.id, "author": r.author, "text": r.text, "at": _iso(r.created_at)}


@router.post("/threads/{thread_id}/like")
def toggle_like(thread_id: str, user: User = Depends(require_member), db: Session = Depends(get_db)):
    t = db.get(Thread, thread_id)
    if not t:
        raise HTTPException(status_code=404, detail="Thread not found")
    existing = db.query(ThreadLike).filter(
        ThreadLike.owner_id == user.id, ThreadLike.thread_id == thread_id).first()
    if existing:
        db.delete(existing)
        t.likes_count = max(0, (t.likes_count or 0) - 1)
        liked = False
    else:
        db.add(ThreadLike(owner_id=user.id, thread_id=thread_id))
        t.likes_count = (t.likes_count or 0) + 1
        liked = True
    db.commit()
    db.refresh(t)
    return {"likes": t.likes_count, "liked": liked}
