from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import cors_origins
from .database import Base, SessionLocal, engine
from .routers import admin, auth, batches, billing, community, datasets, learn, materials, projects, research, science, support, verify, workspace
from .schemas import HealthOut

Base.metadata.create_all(bind=engine)

# Lightweight migration for pre-existing dev databases (new columns/tables
# added after the first run). Safe to re-run: failures are ignored.
try:
    from sqlalchemy import text as _text
    with engine.begin() as _conn:
        _cols = [r[1] for r in _conn.execute(_text("PRAGMA table_info(users)")).all()] if "sqlite" in str(engine.url) else []
        if _cols and "is_guest" not in _cols:
            _conn.execute(_text("ALTER TABLE users ADD COLUMN is_guest BOOLEAN DEFAULT 0"))
            _conn.execute(_text("UPDATE users SET is_guest = 1 WHERE email LIKE '%@nanosphere.local'"))
        if _cols and "is_pro" not in _cols:
            _conn.execute(_text("ALTER TABLE users ADD COLUMN is_pro BOOLEAN DEFAULT 0"))
        if _cols and "pro_since" not in _cols:
            _conn.execute(_text("ALTER TABLE users ADD COLUMN pro_since DATETIME"))
        if _cols and "is_team" not in _cols:
            _conn.execute(_text("ALTER TABLE users ADD COLUMN is_team BOOLEAN DEFAULT 0"))
        for _col in ("email_verified", "is_admin"):
            if _cols and _col not in _cols:
                _conn.execute(_text(f"ALTER TABLE users ADD COLUMN {_col} BOOLEAN DEFAULT 0"))
        if _cols and "provider" not in _cols:
            _conn.execute(_text("ALTER TABLE users ADD COLUMN provider VARCHAR(20) DEFAULT 'email'"))
            _conn.execute(_text("UPDATE users SET provider = 'email' WHERE provider IS NULL"))
        if _cols and "phone" not in _cols:
            _conn.execute(_text("ALTER TABLE users ADD COLUMN phone VARCHAR(30) DEFAULT ''"))
except Exception:
    pass

# Seed shared catalogue content (materials, articles, lessons, glossary).
try:
    from .seed_content import seed_all as _seed_content
    _db = SessionLocal()
    try:
        _seed_content(_db)
    finally:
        _db.close()
except Exception:
    pass

app = FastAPI(title="NanoSphere API", version="1.0.0",
              description="FastAPI + PostgreSQL backend for NanoSphere. Demo science models are illustrative only.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(datasets.router)
app.include_router(workspace.router)
app.include_router(science.router)
app.include_router(learn.router)
app.include_router(billing.router)
app.include_router(verify.router)
app.include_router(materials.router)
app.include_router(research.router)
app.include_router(support.router)
app.include_router(admin.router)
app.include_router(batches.router)
app.include_router(community.router)


@app.get("/health", response_model=HealthOut)
def health():
    from .config import settings
    db_kind = "postgresql" if "postgres" in settings.DATABASE_URL else "sqlite"
    return {"status": "ok", "db": db_kind, "version": "1.0.0"}
