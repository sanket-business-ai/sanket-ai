import csv
import logging
import re
import secrets
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import PurePath

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
from .connectors import import_sheet, sheet_export_url, sync_connection
from .db import (
    Action,
    Audit,
    AuthSession,
    Base,
    Connection,
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
from .ingestion import (
    CONTRACTS,
    OPTIONAL_COLUMNS,
    active_sources,
    detect_kind,
    export_csv,
    export_text,
    store_source,
)
from .jobs import enqueue
from .schemas import (
    ConnectionRequest,
    Decision,
    DeleteSourceRequest,
    DemoRequest,
    InvestigationRequest,
    Login,
    ResetRequest,
)

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


def unfinished():
    """Queued investigations, or running ones whose 30-minute lease is still live."""
    live_lease = now() - timedelta(minutes=30)
    return (Investigation.status == "queued") | (
        (Investigation.status == "running") & (Investigation.started_at > live_lease)
    )


def source_usage(db, source):
    ids = [job.id for job in db.scalars(select(Investigation)) if source.id in job.source_ids]
    if not ids:
        return ids, 0, False
    actions = db.scalar(select(func.count()).select_from(Action).where(Action.investigation_id.in_(ids)))
    busy = db.scalar(select(func.count()).select_from(Investigation).where(Investigation.id.in_(ids), unfinished()))
    return ids, actions, bool(busy)


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


def connection_dict(connection):
    return {column.name: getattr(connection, column.name) for column in Connection.__table__.columns}


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
        "model": settings().model_name,
        "llm_provider": settings().llm_provider,
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
    return {
        kind: {"required": list(columns), "optional": list(OPTIONAL_COLUMNS.get(kind, {}))}
        for kind, columns in CONTRACTS.items()
    }


@app.get("/api/sources/{source_id}")
def source_detail(source_id: str, offset: int = 0, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if offset < 0:
        raise HTTPException(422, "Offset must be non-negative")
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    key = "chunks" if source.kind == "document" else "rows"
    page = source.content[key][offset : offset + 100]
    if key == "chunks":
        page = [{k: v for k, v in chunk.items() if k != "embedding"} for chunk in page]
    return {
        **source_dict(source, {s.id for s in active_sources(db)}),
        key: page,
        "offset": offset,
    }


@app.get("/api/sources/{source_id}/download")
def download_source(source_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", PurePath(source.name).stem)[:120] or "source"
    if source.kind == "document":
        body, media, suffix = export_text(source.content["chunks"]), "text/plain", "txt"
    else:
        body, media, suffix = export_csv(source.kind, source.content["rows"]), "text/csv", "csv"
    return Response(
        body,
        media_type=f"{media}; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{stem}.{suffix}"'},
    )


@app.get("/api/sources/{source_id}/usage")
def usage(source_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    ids, actions, busy = source_usage(db, source)
    active = source.id in {s.id for s in active_sources(db)}
    replacement = None
    if active and source.kind != "document":
        older = db.scalar(
            select(Source)
            .where(Source.kind == source.kind, Source.id != source.id)
            .order_by(Source.created_at.desc(), Source.id.desc())
            .limit(1)
        )
        replacement = older.name if older else None
    return {
        "investigations": len(ids),
        "actions": actions,
        "running": busy,
        "active": active,
        "replacement": replacement,
        "connections": list(db.scalars(select(Connection.name).where(Connection.last_source_id == source.id))),
    }


@app.post("/api/sources/{source_id}/delete")
def delete_source(
    source_id: str,
    payload: DeleteSourceRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    ids, actions, busy = source_usage(db, source)
    if busy:
        raise HTTPException(409, "An investigation using this source is still running. Wait for it to finish.")
    if ids and not (payload and payload.delete_investigations):
        raise HTTPException(
            409,
            f"{len(ids)} investigation(s) used this source. Confirm deleting them too, or upload a corrected version instead.",
        )
    # A report never outlives its evidence: investigations that used the source go with it.
    if ids:
        db.execute(delete(Action).where(Action.investigation_id.in_(ids)))
        db.execute(update(Investigation).where(Investigation.parent_id.in_(ids)).values(parent_id=None))
        db.execute(delete(Investigation).where(Investigation.id.in_(ids)))
    details = {
        "name": source.name,
        "kind": source.kind,
        "rows": source.row_count,
        "checksum": source.checksum,
        "investigations": ids,
        "actions": actions,
    }
    db.delete(source)
    db.add(Audit(actor=user.id, event="source.deleted", entity_id=source_id, details=details))
    db.commit()
    return {"deleted": source_id, "investigations": len(ids), "actions": actions}


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
        if kind == "auto":
            kind = await run_in_threadpool(detect_kind, data, file.filename or "upload")
            if not kind:
                raise ValueError("Could not tell which type this file is. Choose its type and upload it again.")
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


@app.get("/api/connections")
def connections(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [connection_dict(c) for c in db.scalars(select(Connection).order_by(Connection.created_at.desc()))]


@app.post("/api/connections", status_code=201)
def create_connection(payload: ConnectionRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if payload.kind not in CONTRACTS:
        raise HTTPException(422, "Choose a dataset type. Documents cannot be connected from Google Sheets.")
    try:
        url = sheet_export_url(payload.url)
        if db.scalar(select(Connection).where(Connection.url == url, Connection.kind == payload.kind)):
            raise HTTPException(409, "This sheet is already connected for that dataset type.")
        name = payload.name.strip() or f"Google Sheet {payload.kind}"
        # Import before saving the connection so a private or invalid sheet is reported straight away.
        source, created = import_sheet(db, payload.kind, name, url)
    except (ValueError, UnicodeError, csv.Error) as error:
        db.rollback()
        raise HTTPException(422, str(error)) from error
    connection = Connection(
        provider=payload.provider,
        kind=payload.kind,
        name=name,
        url=url,
        refresh_hours=payload.refresh_hours,
        last_synced_at=now(),
        last_status="updated" if created else "unchanged",
        last_source_id=source.id,
        created_by=user.id,
    )
    db.add(connection)
    db.flush()
    db.add(
        Audit(
            actor=user.id,
            event="connection.created",
            entity_id=connection.id,
            details={"provider": payload.provider, "kind": payload.kind, "source_id": source.id},
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This data was imported concurrently. Refresh and try again.")
    return connection_dict(connection)


@app.post("/api/connections/{connection_id}/sync")
def sync_now(connection_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    connection = db.get(Connection, connection_id)
    if not connection:
        raise HTTPException(404, "Connection not found")
    sync_connection(db, connection, user.id)
    db.commit()
    return connection_dict(connection)


@app.post("/api/connections/{connection_id}/delete")
def disconnect(connection_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    connection = db.get(Connection, connection_id)
    if not connection:
        raise HTTPException(404, "Connection not found")
    details = {"name": connection.name, "kind": connection.kind, "provider": connection.provider}
    db.delete(connection)
    db.add(Audit(actor=user.id, event="connection.deleted", entity_id=connection_id, details=details))
    db.commit()
    return {"deleted": connection_id}


@app.post("/api/demo", status_code=201)
def demo(payload: DemoRequest | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    pack = payload.pack if payload else "supply"
    if not settings().demo_enabled:
        raise HTTPException(404, "Demo loading is disabled")
    if db.scalar(select(Source).limit(1)):
        raise HTTPException(409, "Demo data can only be loaded into an empty workspace")
    seeded = seed_demo(db, pack)
    documents = sum(source.kind == "document" for source in seeded)
    db.add(Audit(actor=user.id, event="demo.loaded", entity_id=user.id, details={"sources": len(seeded), "pack": pack}))
    db.commit()
    return {
        "sources": len(seeded),
        "datasets": len(seeded) - documents,
        "documents": documents,
        "pack": pack,
        "company": "HimalayanMart",
        "synthetic": True,
    }


@app.post("/api/workspace/reset")
def reset_workspace(payload: ResetRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
    # A testing aid: production rejects demo_enabled, so real business data cannot be wiped here.
    if not settings().demo_enabled:
        raise HTTPException(404, "Workspace reset is disabled")
    if db.scalar(select(func.count()).select_from(Investigation).where(unfinished())):
        raise HTTPException(409, "Wait for running investigations to finish before resetting the workspace")
    removed = {
        "connections": db.scalar(select(func.count()).select_from(Connection)),
        "sources": db.scalar(select(func.count()).select_from(Source)),
        "investigations": db.scalar(select(func.count()).select_from(Investigation)),
        "actions": db.scalar(select(func.count()).select_from(Action)),
    }
    # Reports, actions and their evidence go together, so no report outlives its sources. Connections go
    # too, or their next sync would refill the workspace.
    db.execute(delete(Connection))
    db.execute(delete(Action))
    db.execute(update(Investigation).values(parent_id=None))
    db.execute(delete(Investigation))
    db.execute(delete(Source))
    db.add(Audit(actor=user.id, event="workspace.reset", entity_id=user.id, details=removed))
    db.commit()
    return removed


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
