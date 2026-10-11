"""Contact / support tickets: validated public submission, owner + admin views."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user
from ..models import Ticket, User

router = APIRouter(prefix="/support", tags=["support"])


class TicketIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    subject: str = Field(min_length=4, max_length=200)
    message: str = Field(min_length=10, max_length=5000)


def _iso(dt) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _out(t: Ticket) -> dict:
    return {"id": t.id, "name": t.name, "email": t.email, "subject": t.subject,
            "message": t.message, "status": t.status, "at": _iso(t.created_at)}


@router.post("/tickets", status_code=201)
def create_ticket(body: TicketIn, db: Session = Depends(get_db)):
    t = Ticket(name=body.name.strip(), email=body.email.strip().lower(),
               subject=body.subject.strip(), message=body.message.strip())
    db.add(t)
    db.commit()
    db.refresh(t)
    return _out(t)


@router.get("/tickets/mine")
def my_tickets(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Ticket)
        .filter((Ticket.owner_id == user.id) | (Ticket.email == user.email))
        .order_by(Ticket.created_at.desc())
        .all()
    )
    # Backfill ownership for tickets submitted pre-login with the same email.
    for t in rows:
        if not t.owner_id:
            t.owner_id = user.id
    db.commit()
    return {"tickets": [_out(t) for t in rows]}


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = db.get(Ticket, ticket_id)
    if not t or (t.owner_id != user.id and t.email != user.email and not user.is_admin):
        raise HTTPException(status_code=404, detail="Ticket not found")
    return _out(t)
