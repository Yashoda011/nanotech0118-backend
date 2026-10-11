"""Email verification + password reset: 6-digit codes with expiry.

Production delivery is SMTP (configure); with DEV_MAILBOX=true (local demo)
codes are returned/fetchable so the flows are testable end-to-end
without a mail server.
"""

import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import current_user, require_member
from ..mailer import send_code
from ..models import EmailToken, User
from ..security import hash_password

router = APIRouter(prefix="/auth", tags=["auth-verify"])

CODE_TTL_MIN = 15


class ConfirmIn(BaseModel):
    code: str = Field(min_length=4, max_length=10)


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=10)
    new_password: str = Field(min_length=6, max_length=128)


def _issue(db: Session, user: User) -> EmailToken:
    db.query(EmailToken).filter(EmailToken.owner_id == user.id, EmailToken.used == False).update({"used": True})  # noqa: E712
    code = f"{secrets.randbelow(900000) + 100000}"
    tok = EmailToken(owner_id=user.id, code=code,
                     expires_at=datetime.now(timezone.utc) + timedelta(minutes=CODE_TTL_MIN))
    db.add(tok)
    db.commit()
    db.refresh(tok)
    return tok


def _check(db: Session, user: User, code: str) -> EmailToken | None:
    tok = (
        db.query(EmailToken)
        .filter(EmailToken.owner_id == user.id, EmailToken.used == False)  # noqa: E712
        .order_by(EmailToken.created_at.desc())
        .first()
    )
    if not tok:
        return None
    exp = tok.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        return None
    if tok.code != code.strip():
        return None
    return tok


@router.post("/request-code")
def request_code(user: User = Depends(require_member), db: Session = Depends(get_db)):
    if user.email_verified:
        return {"sent": False, "verified": True}
    tok = _issue(db, user)
    mailed = send_code(user.email, tok.code, "verification")
    out: dict = {"sent": True, "expires_minutes": CODE_TTL_MIN, "mailed": mailed}
    if not mailed and settings.DEV_MAILBOX:
        out["dev_code"] = tok.code
    return out


@router.post("/confirm-code")
def confirm_code(body: ConfirmIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    tok = _check(db, user, body.code)
    if not tok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code.")
    tok.used = True
    user.email_verified = True
    db.commit()
    return {"verified": True}


@router.get("/dev-inbox")
def dev_inbox(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not settings.DEV_MAILBOX:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dev mailbox disabled.")
    tok = (
        db.query(EmailToken)
        .filter(EmailToken.owner_id == user.id, EmailToken.used == False)  # noqa: E712
        .order_by(EmailToken.created_at.desc())
        .first()
    )
    if not tok:
        raise HTTPException(status_code=404, detail="No active code — request one first.")
    return {"code": tok.code, "expires_at": tok.expires_at.isoformat(), "email": user.email}


@router.post("/forgot")
def forgot(body: ForgotIn, db: Session = Depends(get_db)):
    """Issue a password-reset code. Always returns sent:true (no enumeration)."""
    email = body.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    out: dict = {"sent": True}
    if user and not user.is_guest:
        tok = _issue(db, user)
        mailed = send_code(user.email, tok.code, "password reset")
        out["mailed"] = mailed
        if not mailed and settings.DEV_MAILBOX:
            out["dev_code"] = tok.code
    return out


@router.post("/reset")
def reset_password(body: ResetIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters.")
    user = db.query(User).filter(User.email == email).first()
    if not user or user.is_guest:
        raise HTTPException(status_code=400, detail="Invalid email or code.")
    if not _check(db, user, body.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code.")
    # _check only reads; mark consumed + set new hash here.
    tok = (
        db.query(EmailToken)
        .filter(EmailToken.owner_id == user.id, EmailToken.used == False)  # noqa: E712
        .order_by(EmailToken.created_at.desc())
        .first()
    )
    if tok:
        tok.used = True
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"reset": True}
