import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from sqlalchemy.orm import Session

from app.db import SessionLocal, get_session, init_db
from app.routers import config, rosters
from app.seed import reset_demo, seed_if_empty
from app.static import mount_frontend


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    with SessionLocal() as s:
        seed_if_empty(s)
    yield


app = FastAPI(title="Smart Roster Management", lifespan=lifespan)
app.include_router(config.router)
app.include_router(rosters.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/demo/reset")
def demo_reset(s: Session = Depends(get_session), x_demo_token: str | None = Header(default=None)):
    token = os.environ.get("DEMO_RESET_TOKEN")
    if token and x_demo_token != token:
        raise HTTPException(403, "Demo reset is protected on this server")
    reset_demo(s)
    return {"status": "reset"}


# Serve the built frontend when it exists (production image, or after `npm run build`).
_dist = Path(os.environ.get("FRONTEND_DIST", Path(__file__).resolve().parents[2] / "frontend" / "dist"))
if (_dist / "index.html").exists():
    mount_frontend(app, _dist)
