"""Dataset upload + CSV/JSON parsing with pandas/numpy stats."""

import csv
import io
import json
import os
import uuid
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import current_user
from ..models import Activity, Dataset, Notification, User
from ..schemas import DatasetOut
from ..science import dataset_stats

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _iso(dt) -> str:
    return dt.isoformat() if dt else ""


def _out(d: Dataset) -> dict:
    return {"id": d.id, "name": d.name, "source": d.source, "uploadedAt": _iso(d.uploaded_at),
            "series": d.series or [], "stats": d.stats or {}}


def parse_content(name: str, content: str) -> list[dict]:
    trimmed = content.strip()
    if not trimmed:
        raise ValueError("File appears to be empty.")
    if trimmed[0] in "[{":
        data = json.loads(trimmed)
        records = data if isinstance(data, list) else [data]
        if not records or not isinstance(records[0], dict):
            raise ValueError("JSON must be an array of objects with numeric fields.")
        keys = list(records[0].keys())
        value_keys = [k for k in keys if all(_num_or_empty(r.get(k)) for r in records)]
        value_keys = [k for k in value_keys if any(_is_num(r.get(k)) for r in records)]
        if not value_keys:
            raise ValueError("No numeric fields found in JSON.")
        series = []
        for k in value_keys[:4]:
            pts = [{"label": str(r.get("label", r.get("name", f"#{i+1}"))), "value": float(r[k])}
                   for i, r in enumerate(records) if _is_num(r.get(k))]
            series.append({"name": k, "unit": "", "points": pts})
        return series
    # CSV / TSV
    first_line = trimmed.splitlines()[0]
    delimiter = "\t" if "\t" in first_line else ","
    reader = csv.reader(io.StringIO(trimmed), delimiter=delimiter)
    rows = [r for r in reader if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise ValueError("File appears to be empty.")
    columns, data_rows = rows[0], rows[1:]
    series = []
    for c in range(1, len(columns)):
        pts = []
        for i, r in enumerate(data_rows):
            if c >= len(r):
                continue
            try:
                v = float(r[c])
            except ValueError:
                continue
            pts.append({"label": r[0] if r else f"#{i+1}", "value": v})
        if pts:
            series.append({"name": columns[c] or f"Column {c+1}", "unit": "", "points": pts})
    if not series:
        raise ValueError("No numeric columns found.")
    return series[:4]


def _num_or_empty(v) -> bool:
    return v is None or v == "" or _is_num(v)


def _is_num(v) -> bool:
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


@router.get("", response_model=list[DatasetOut])
def list_datasets(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ds = db.query(Dataset).filter(Dataset.owner_id == user.id).order_by(Dataset.uploaded_at.desc()).all()
    return [_out(d) for d in ds]


@router.post("/upload", response_model=DatasetOut, status_code=201)
async def upload_dataset(file: UploadFile = File(...), user: User = Depends(current_user),
                         db: Session = Depends(get_db)):
    fname = (file.filename or "dataset").lower()
    if not fname.endswith((".csv", ".tsv", ".json", ".txt")):
        raise HTTPException(status_code=400, detail="Only .csv, .tsv, .json or .txt files are accepted.")
    raw = await file.read()
    if len(raw) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File too large (max {settings.MAX_UPLOAD_MB} MB)")
    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not decode file as text")
    try:
        series = parse_content(file.filename or "dataset", text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    stats = {}
    try:
        stats = dataset_stats(series)
    except Exception:
        stats = {}
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    fname = f"{uuid.uuid4().hex}_{(file.filename or 'dataset')[:80]}"
    fpath = os.path.join(settings.UPLOAD_DIR, fname)
    with open(fpath, "wb") as f:
        f.write(raw)
    d = Dataset(owner_id=user.id, name=file.filename or "dataset", source="upload",
              file_path=fpath, series=series, stats=stats)
    db.add(d)
    db.add(Activity(owner_id=user.id, kind="dataset", title="New dataset uploaded", meta=d.name))
    db.add(Notification(owner_id=user.id, title="Dataset processed",
                        body=f"{d.name} parsed successfully — {sum(len(s['points']) for s in series)} rows."))
    db.commit()
    db.refresh(d)
    return _out(d)


@router.delete("/{dataset_id}", status_code=204)
def delete_dataset(dataset_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = db.query(Dataset).filter(Dataset.id == dataset_id, Dataset.owner_id == user.id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if d.file_path and os.path.exists(d.file_path):
        try:
            os.remove(d.file_path)
        except OSError:
            pass
    db.delete(d)
    db.commit()
    return None
