"""Industrial batches — backend-owned business data.

Reads: any authenticated user (own rows only).
Writes: members only (email accounts), like projects.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user, require_member
from ..models import Batch, User

router = APIRouter(prefix="/batches", tags=["batches"])


class BatchIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    material_id: str = Field(min_length=1, max_length=80)
    kg: float = Field(ge=0, le=100000)
    yield_pct: float = Field(ge=0, le=100)
    qc_pass: bool = False


def _iso(dt) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _out(b: Batch) -> dict:
    return {"id": b.id, "name": b.name, "material_id": b.material_id, "kg": b.kg,
            "yieldPct": b.yield_pct, "qcPass": b.qc_pass, "createdAt": _iso(b.created_at)}


@router.get("")
def list_batches(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Batch).filter(Batch.owner_id == user.id).order_by(Batch.created_at.desc()).all()
    return {"batches": [_out(b) for b in rows]}


@router.post("", status_code=201)
def create_batch(body: BatchIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    b = Batch(owner_id=user.id, name=body.name.strip(), material_id=body.material_id,
              kg=body.kg, yield_pct=body.yield_pct, qc_pass=body.qc_pass)
    db.add(b)
    db.commit()
    db.refresh(b)
    return _out(b)


@router.delete("/{batch_id}", status_code=204)
def delete_batch(batch_id: str, user: User = Depends(require_member), db: Session = Depends(get_db)):
    b = db.query(Batch).filter(Batch.id == batch_id, Batch.owner_id == user.id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Batch not found")
    db.delete(b)
    db.commit()
    return None
