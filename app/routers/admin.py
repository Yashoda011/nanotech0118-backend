"""Admin panel: protected platform management.

Access: users whose email is in ADMIN_EMAILS, or is_admin flag.
All routes return 403 otherwise.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import current_user
from ..models import Activity, Enrollment, Purchase, SimRun, Ticket, User

router = APIRouter(prefix="/admin", tags=["admin"])


def admin_emails() -> list[str]:
    return [e.strip().lower() for e in settings.ADMIN_EMAILS.split(",") if e.strip()]


def require_admin(user: User = Depends(current_user)) -> User:
    if not (user.is_admin or user.email.lower() in admin_emails()):
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user


def _iso(dt) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class UserPatch(BaseModel):
    is_pro: bool | None = None
    is_admin: bool | None = None
    email_verified: bool | None = None


@router.get("/stats")
def stats(_admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "users": db.query(func.count(User.id)).scalar(),
        "pro_users": db.query(func.count(User.id)).filter((User.is_pro == True) | (User.is_team == True)).scalar(),  # noqa: E712
        "verified_users": db.query(func.count(User.id)).filter(User.email_verified == True).scalar(),  # noqa: E712
        "enrollments": db.query(func.count(Enrollment.id)).scalar(),
        "purchases": db.query(func.count(Purchase.id)).scalar(),
        "open_tickets": db.query(func.count(Ticket.id)).filter(Ticket.status == "open").scalar(),
        "sims_today": db.query(func.count(Activity.id)).filter(Activity.kind == "simulation", Activity.created_at >= today).scalar(),
    }


@router.get("/users")
def list_users(_admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(User).order_by(User.created_at.desc()).limit(200).all()
    return {"users": [
        {"id": u.id, "name": u.name, "email": u.email,
         "plan": "team" if u.is_team else ("pro" if u.is_pro else "starter"),
         "verified": bool(u.email_verified), "admin": bool(u.is_admin),
         "guest": bool(u.is_guest), "at": _iso(u.created_at)} for u in rows
    ]}


@router.patch("/users/{user_id}")
def patch_user(user_id: str, body: UserPatch, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    if u.id == admin.id and body.is_admin is False:
        raise HTTPException(status_code=400, detail="You cannot remove your own admin flag.")
    if body.is_pro is not None:
        u.is_pro = body.is_pro
    if body.is_admin is not None:
        u.is_admin = body.is_admin
    if body.email_verified is not None:
        u.email_verified = body.email_verified
    db.commit()
    return {"id": u.id, "plan": "team" if u.is_team else ("pro" if u.is_pro else "starter"),
            "verified": bool(u.email_verified), "admin": bool(u.is_admin)}


@router.get("/tickets")
def list_tickets(_admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(Ticket).order_by(Ticket.created_at.desc()).limit(200).all()
    return {"tickets": [
        {"id": t.id, "name": t.name, "email": t.email, "subject": t.subject,
         "message": t.message, "status": t.status, "at": _iso(t.created_at)} for t in rows
    ]}


@router.post("/tickets/{ticket_id}/close")
def close_ticket(ticket_id: str, _admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    t = db.get(Ticket, ticket_id)
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")
    t.status = "closed"
    db.commit()
    return {"id": t.id, "status": t.status}
