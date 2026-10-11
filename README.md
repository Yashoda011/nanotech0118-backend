# NanoSphere Backend — FastAPI + PostgreSQL + SQLAlchemy

Full backend for the NanoSphere nanotech dashboard.

## Stack
- **FastAPI** + **Uvicorn** (REST API, OpenAPI at `/docs`)
- **PostgreSQL** via **SQLAlchemy 2.0** (+ `psycopg2`). Falls back to SQLite for local dev.
- **Auth & security**: bcrypt password hashing (`passlib`), JWT (`python-jose`), Bearer auth, CORS allowlist, file-size limits, email validation.
- **Scientific Python**: `numpy`, `scipy`, `pandas`, `scikit-learn`
  - `POST /science/simulate` — deterministic demo transport model (port of `src/lib/science.ts`)
  - `POST /science/lab-calc` — Scherrer / dilution / photon-energy calculators
  - `POST /datasets/upload` — CSV/TSV/JSON parsing + `pandas.describe()` stats per series

## Quick start (Windows PowerShell)

```powershell
cd C:\Users\acer\nanosphere-site
pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env   # edit DATABASE_URL for Postgres
python -m uvicorn backend.app.main:app --port 8000 --host 127.0.0.1
# health: http://127.0.0.1:8000/health
# docs:   http://127.0.0.1:8000/docs
```

Postgres example:
```
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/nanosphere
```
Create the DB once: `createdb nanosphere` (or via pgAdmin). Tables auto-create on startup.

## Endpoints
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/signup` | no | Create account + seed demo workspace |
| POST | `/auth/login` | no | Login, returns JWT |
| POST | `/auth/guest` | no | Ephemeral guest account |
| GET | `/auth/me` | yes | Current user |
| GET/POST | `/projects`, `/projects/{id}` | yes | Project CRUD |
| POST/PATCH/DELETE | `/projects/{pid}/tasks...` | yes | Tasks |
| GET/POST/DELETE | `/datasets`, `/datasets/upload` | yes | CSV/JSON upload with stats |
| GET/POST/DELETE | `/workspace/activities`, `/notifications`, `/saved`, `/search-history`, `/settings`, `/reset` | yes | All former localStorage data |
| POST | `/science/simulate`, `/science/lab-calc` | yes | Compute |

Frontend uses `VITE_API_URL` (see `src/lib/api.ts`) and falls back to localStorage when the backend is offline.
