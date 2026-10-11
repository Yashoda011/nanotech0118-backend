from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Activity, Notification, User
from ..schemas import ActivityOut, NotificationOut
from ..deps import current_user

router = APIRouter(prefix="/auth", tags=["auth"])

from ..schemas import LoginIn, SignupIn, TokenOut, UserOut  # noqa: E402
from ..security import create_token, hash_password, verify_password  # noqa: E402
from ..config import settings as _settings  # noqa: E402


def _admin_emails() -> list[str]:
    return [e.strip().lower() for e in _settings.ADMIN_EMAILS.split(",") if e.strip()]


def _out(u: User) -> dict:
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role,
            "density": u.density, "default_metric": u.default_metric, "email_digest": u.email_digest,
            "email_verified": bool(getattr(u, "email_verified", False)),
            "is_admin": bool(getattr(u, "is_admin", False) or u.email.lower() in _admin_emails())}


def _create_member(db: Session, name: str, email: str, password: str, provider: str, phone: str = "") -> User:
    """Shared member creation: unique email, hashed password, seeded workspace."""
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="An account with this email already exists — sign in instead")
    user = User(name=name.strip(), email=email, password_hash=hash_password(password), provider=provider, phone=phone.strip()[:30])
    if email in _admin_emails():
        user.is_admin = True
    db.add(user)
    db.flush()
    from ..seed import seed_user
    seed_user(db, user)
    db.refresh(user)
    return user


def _token_for(user: User) -> dict:
    return {"access_token": create_token(user.id), "token_type": "bearer", "user": _out(user)}


class GoogleIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    phone: str = Field(default="", max_length=30)


@router.post("/signup", response_model=TokenOut, status_code=201)
def signup(body: SignupIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name is required.")
    return _token_for(_create_member(db, body.name.strip(), email, body.password, "email"))


@router.post("/google", response_model=TokenOut, status_code=201)
def google(body: GoogleIn, db: Session = Depends(get_db)):
    """Continue with Google: creates a REAL member account (never a guest).
    Email ownership is proven through the verification-code step afterwards."""
    email = body.email.strip().lower()
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name is required.")
    return _token_for(_create_member(db, body.name.strip(), email, body.password, "google", body.phone or ""))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if email in _admin_emails() and not user.is_admin:
        user.is_admin = True
        db.commit()
        db.refresh(user)
    return {"access_token": create_token(user.id), "token_type": "bearer", "user": _out(user)}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return _out(user)


@router.post("/guest", response_model=TokenOut)
def guest(db: Session = Depends(get_db)):
    import uuid
    email = f"guest-{uuid.uuid4().hex[:8]}@nanosphere.local"
    user = User(name="Guest", email=email, password_hash=hash_password(uuid.uuid4().hex), is_guest=True)
    db.add(user)
    db.flush()
    from ..seed import seed_user
    seed_user(db, user)
    db.refresh(user)
    return {"access_token": create_token(user.id), "token_type": "bearer", "user": _out(user)}
