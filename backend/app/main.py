import csv
import logging
import secrets
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .actions import assess_action
from .analysis import Tools
from .auth import COOKIE, bootstrap_admin, current_user, hash_password, new_session, verify_password
from .config import settings
from .db import (
    Action,
    Audit,
    AuthSession,
    Base,
    Investigation,
    LoginAttempt,
    Runtime,
    SessionLocal,
    Source,
    User,
    engine,
    get_db,
    now,
)
from .demo import seed_demo
from .ingestion import CONTRACTS, active_sources, store_source
from .jobs import enqueue
from .schemas import Decision, InvestigationRequest, Login

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_):
    if settings().environment != "production":
        Base.metadata.create_all(engine)
    with SessionLocal() as db:
        bootstrap_admin(db)
    yield


app = FastAPI(title="SanketAI", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings().frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)


@app.middleware("http")
async def request_headers(request, call_next):
    request_id = secrets.token_hex(8)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(Exception)
async def unexpected_error(request, error):
    logger.exception("Unhandled request failure: %s", request.url.path, exc_info=error)
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred. Check server logs."})


def require_job(db, investigation_id):
    job = db.get(Investigation, investigation_id)
    if job is None:
        raise HTTPException(404, "Investigation not found")
    return job


def summary(job):
    return {
        "id": job.id,
        "question": job.question,
        "mode": job.mode,
        "status": job.status,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "parent_id": job.parent_id,
        "confidence": job.report.get("confidence") if job.report else None,
        "engine": job.report.get("engine") if job.report else None,
    }


def action_dict(action):
    return {column.name: getattr(action, column.name) for column in Action.__table__.columns}


def source_dict(source, active_ids):
    return {
        "id": source.id,
        "name": source.name,
        "kind": source.kind,
        "row_count": source.row_count,
        "created_at": source.created_at,
        "active": source.id in active_ids,
        "checksum": source.checksum,
    }


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post("/api/auth/login")
def login(payload: Login, request: Request, response: Response, db: Session = Depends(get_db)):
    origin = request.headers.get("origin")
    if origin and origin != settings().frontend_origin:
        raise HTTPException(403, "Untrusted request origin")
    ip = request.client.host if request.client else "unknown"
    cutoff = now() - timedelta(minutes=15)
    db.execute(delete(LoginAttempt).where(LoginAttempt.created_at < cutoff))
    count = db.scalar(
        select(func.count()).select_from(LoginAttempt).where(LoginAttempt.ip == ip, LoginAttempt.created_at >= cutoff)
    )
    if count >= 10:
        raise HTTPException(429, "Too many sign-in attempts. Try again in 15 minutes.")
    user = db.scalar(select(User).where(User.email == payload.email.lower().strip()))
    db.add(LoginAttempt(ip=ip))
    db.commit()
    # Match password work for unknown users to avoid a cheap account-existence probe.
    valid = (
        verify_password(payload.password, user.password_hash)
        if user
        else verify_password(payload.password, hash_password("unknown-account-password"))
    )
    if not user or not valid:
        raise HTTPException(401, "Invalid email or password")
    old = request.cookies.get(COOKIE)
    if old:
        from .auth import token_hash

        db.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash(old)))
    db.execute(delete(AuthSession).where(AuthSession.expires_at <= now()))
    token, session = new_session(db, user)
    db.add(Audit(actor=user.id, event="auth.login", entity_id=user.id, details={}))
    db.commit()
    response.set_cookie(
        COOKIE,
        token,
        max_age=settings().session_hours * 3600,
        httponly=True,
        secure=settings().secure_cookies,
        samesite="lax",
        path="/",
    )
    return {"email": user.email, "csrf_token": session.csrf}


@app.get("/api/auth/me")
def me(request: Request, user: User = Depends(current_user)):
    return {"email": user.email, "csrf_token": request.state.auth_session.csrf}


@app.post("/api/auth/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db), user: User = Depends(current_user)):
    db.delete(request.state.auth_session)
    db.commit()
    response.delete_cookie(COOKIE, path="/", secure=settings().secure_cookies, httponly=True, samesite="lax")


@app.get("/api/system")
def system(db: Session = Depends(get_db), user: User = Depends(current_user)):
    heartbeat = db.get(Runtime, "worker")
    return {
        "agent_mode": settings().agent_mode,
        "model": settings().ollama_model,
        "worker_online": bool(
            heartbeat and heartbeat.heartbeat.replace(tzinfo=now().tzinfo) > now() - timedelta(minutes=20)
        ),
        "demo_enabled": settings().demo_enabled,
        "upload_max_bytes": settings().upload_max_bytes,
    }


@app.get("/api/sources")
def sources(db: Session = Depends(get_db), user: User = Depends(current_user)):
    active_ids = {s.id for s in active_sources(db)}
    return [
        source_dict(s, active_ids) for s in db.scalars(select(Source).order_by(Source.created_at.desc()).limit(200))
    ]


@app.get("/api/sources/contracts")
def contracts(user: User = Depends(current_user)):
    return CONTRACTS


@app.get("/api/sources/{source_id}")
def source_detail(source_id: str, offset: int = 0, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if offset < 0:
        raise HTTPException(422, "Offset must be non-negative")
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    key = "chunks" if source.kind == "document" else "rows"
    return {
        **source_dict(source, {s.id for s in active_sources(db)}),
        key: source.content[key][offset : offset + 100],
        "offset": offset,
    }


@app.post("/api/sources", status_code=201)
async def upload(
    file: UploadFile = File(...),
    kind: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    data = await file.read(settings().upload_max_bytes + 1)
    await file.close()
    if len(data) > settings().upload_max_bytes:
        raise HTTPException(413, "File exceeds the 10 MB upload limit")
    try:
        source, created = await run_in_threadpool(store_source, db, data, file.filename or "upload", kind)
        if created:
            db.add(
                Audit(
                    actor=user.id,
                    event="source.uploaded",
                    entity_id=source.id,
                    details={"kind": kind, "rows": source.row_count},
                )
            )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This source was uploaded concurrently. Refresh your sources.")
    except Exception as error:
        db.rollback()
        if isinstance(error, (ValueError, UnicodeError, csv.Error, KeyError, IndexError)):
            raise HTTPException(422, str(error)) from error
        logger.warning("Source parse rejected: %s", type(error).__name__)
        raise HTTPException(422, "Could not parse this file. Check the format and export it again.") from error
    return source_dict(source, {s.id for s in active_sources(db)})


@app.post("/api/demo", status_code=201)
def demo(db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not settings().demo_enabled:
        raise HTTPException(404, "Demo loading is disabled")
    if db.scalar(select(Source).limit(1)):
        raise HTTPException(409, "Demo data can only be loaded into an empty workspace")
    seeded = seed_demo(db)
    db.add(Audit(actor=user.id, event="demo.loaded", entity_id=user.id, details={"sources": len(seeded)}))
    db.commit()
    return {"sources": len(seeded), "company": "HimalayanMart", "synthetic": True}


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)):
    active = active_sources(db)
    signal = Tools(active).detect_anomalies() if active else {"metrics": [], "period": None, "coverage_issues": []}
    recent = list(db.scalars(select(Investigation).order_by(Investigation.created_at.desc()).limit(5)))
    return {
        **signal,
        "source_count": len(active),
        "investigation_count": db.scalar(select(func.count()).select_from(Investigation)),
        "pending_actions": db.scalar(select(func.count()).select_from(Action).where(Action.status == "pending")),
        "recent": [summary(job) for job in recent],
    }


@app.get("/api/investigations")
def investigations(offset: int = 0, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if offset < 0:
        raise HTTPException(422, "Offset must be non-negative")
    jobs = db.scalars(select(Investigation).order_by(Investigation.created_at.desc()).offset(offset).limit(50))
    return {
        "items": [summary(job) for job in jobs],
        "total": db.scalar(select(func.count()).select_from(Investigation)),
    }


@app.post("/api/investigations", status_code=202)
def create_investigation(
    payload: InvestigationRequest, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    job = enqueue(db, payload.question, payload.mode, user.id)
    db.commit()
    return summary(job)


@app.get("/api/investigations/{investigation_id}")
def investigation(investigation_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    job = require_job(db, investigation_id)
    actions = db.scalars(select(Action).where(Action.investigation_id == job.id))
    return {
        **summary(job),
        "source_ids": job.source_ids,
        "trail": job.trail,
        "report": job.report,
        "error": job.error,
        "actions": [action_dict(a) for a in actions],
    }


@app.post("/api/investigations/{investigation_id}/challenge", status_code=202)
def challenge(investigation_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    parent = require_job(db, investigation_id)
    if parent.status != "completed":
        raise HTTPException(409, "Only completed investigations can be challenged")
    job = enqueue(db, parent.question, "challenge", user.id, parent.source_ids, parent.id)
    db.commit()
    return summary(job)


@app.post("/api/investigations/{investigation_id}/retry", status_code=202)
def retry(investigation_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    parent = require_job(db, investigation_id)
    if parent.status != "failed":
        raise HTTPException(409, "Only failed investigations can be retried")
    job = enqueue(db, parent.question, parent.mode, user.id, parent.source_ids, parent.id)
    db.commit()
    return summary(job)


@app.get("/api/investigations/{investigation_id}/export")
def export_report(investigation_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    job = require_job(db, investigation_id)
    if not job.report:
        raise HTTPException(409, "Report is not ready")
    return JSONResponse(
        content={
            "id": job.id,
            "question": job.question,
            "source_ids": job.source_ids,
            "report": job.report,
            "trail": job.trail,
        },
        headers={"Content-Disposition": f'attachment; filename="sanketai-{job.id}.json"'},
    )


@app.get("/api/actions")
def actions(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [action_dict(a) for a in db.scalars(select(Action).order_by(Action.created_at.desc()).limit(200))]


@app.post("/api/actions/{action_id}/decision")
def decide(action_id: str, payload: Decision, db: Session = Depends(get_db), user: User = Depends(current_user)):
    action = db.get(Action, action_id)
    if not action:
        raise HTTPException(404, "Action not found")
    status = "monitoring" if payload.decision == "approve" else "rejected"
    if action.status == status:
        return action_dict(action)
    result = db.execute(
        update(Action)
        .where(Action.id == action_id, Action.status == "pending")
        .values(
            status=status,
            approved_by=user.id,
            approved_at=now(),
            due_at=now() + timedelta(days=7) if status == "monitoring" else None,
        )
    )
    if result.rowcount != 1:
        raise HTTPException(409, "This action has already been decided")
    db.add(
        Audit(
            actor=user.id,
            event=f"action.{payload.decision}",
            entity_id=action.id,
            details={"kind": action.kind, "effect": "Create an internal operations task and monitor the selected KPI"},
        )
    )
    db.commit()
    db.refresh(action)
    return action_dict(action)


@app.post("/api/actions/{action_id}/monitor")
def monitor(action_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return action_dict(assess_action(action_id, db, user.id))


@app.get("/api/audit")
def audit(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [
        {
            "id": a.id,
            "event": a.event,
            "actor": a.actor,
            "entity_id": a.entity_id,
            "details": a.details,
            "created_at": a.created_at,
        }
        for a in db.scalars(select(Audit).order_by(Audit.created_at.desc()).limit(100))
    ]
