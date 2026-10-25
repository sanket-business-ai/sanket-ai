"""Durable database queue. Run separately from the API: python -m app.worker."""

import logging
import signal
import time
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import or_, select, update

from .actions import assess_action
from .agent import investigate
from .connectors import sync_due_connections
from .db import Action, Investigation, Runtime, SessionLocal, Source, now, uid

logger = logging.getLogger(__name__)


def process_one(session_factory=SessionLocal):
    config_lease = now() - timedelta(minutes=30)
    with session_factory() as db:
        # Atomic compare-and-swap works on SQLite and PostgreSQL without a queue broker.
        eligible = or_(
            Investigation.status == "queued",
            (Investigation.status == "running") & (Investigation.started_at < config_lease),
        )
        job = db.scalar(select(Investigation).where(eligible).order_by(Investigation.created_at).limit(1))
        if job is None:
            return False
        token = uid()
        claimed = db.execute(
            update(Investigation)
            .where(Investigation.id == job.id, eligible)
            .values(
                status="running",
                started_at=now(),
                lease_token=token,
                attempts=Investigation.attempts + 1,
                trail=[],
                error=None,
            )
            .execution_options(synchronize_session=False)
        )
        db.commit()
        if claimed.rowcount != 1:
            return False
        db.refresh(job)
        job_id = job.id
        if job.attempts > 3:
            job.status = "failed"
            job.error = "Investigation exceeded its recovery limit. Start a new investigation."
            db.commit()
            return True
        sources = list(db.scalars(select(Source).where(Source.id.in_(job.source_ids))))
        if len(sources) != len(job.source_ids):
            job.status = "failed"
            job.error = "An investigation source is missing."
            db.commit()
            return True
        question, mode, challenged = job.question, job.mode, bool(job.parent_id and job.mode == "challenge")

    def emit(stage, message, data):
        with session_factory() as db:
            job = db.get(Investigation, job_id)
            if job is None or job.lease_token != token or job.status != "running":
                raise RuntimeError("Investigation lease lost")
            job.trail = job.trail + [
                {
                    "sequence": len(job.trail) + 1,
                    "stage": stage,
                    "message": message,
                    "data": data,
                    "timestamp": now().isoformat(),
                }
            ]
            db.commit()

    try:
        report = investigate(sources, question, mode, emit, challenged)
        with session_factory() as db:
            job = db.get(Investigation, job_id)
            if job is None or job.lease_token != token or job.status != "running":
                return True
            job.report, job.status, job.completed_at = report, "completed", now()
            if report["actionable"]:
                metric = None
                if report.get("scenario") == "margin":
                    metric = next((m for m in report["metrics"] if m["key"] == "contribution"), None)
                metric = metric or next(
                    (m for m in report["metrics"] if m["key"] == "late_rate" and m["anomaly"]), None
                )
                metric = metric or next(m for m in report["metrics"] if m["key"] == "revenue")
                db.add(
                    Action(
                        investigation_id=job.id,
                        title=report["recommended_action"],
                        metric=metric["key"],
                        baseline=metric["current"],
                        target=metric["previous"],
                        direction=metric["direction"],
                    )
                )
            db.commit()
    except Exception:
        logger.exception("Investigation %s failed", job_id)
        with session_factory() as db:
            job = db.get(Investigation, job_id)
            if job is not None and job.lease_token == token:
                job.status = "failed"
                job.error = "Investigation could not finish. Check model availability and worker logs, then retry."
                job.completed_at = now()
                db.commit()
    return True


def monitor_due_actions(session_factory=SessionLocal):
    with session_factory() as db:
        actions = list(
            db.scalars(select(Action).where(Action.status == "monitoring", Action.due_at <= now()).limit(20))
        )
        for action in actions:
            action_id = action.id
            try:
                assess_action(action_id, db, action.approved_by)
            except HTTPException as error:
                db.rollback()
                if error.status_code == 409:
                    action = db.get(Action, action_id)
                    if action.status == "monitoring":
                        action.due_at = now() + timedelta(days=1)
                        db.commit()
                else:
                    raise


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    logger.info("SanketAI worker started")
    last_monitor = 0
    while not stopping:
        try:
            with SessionLocal() as db:
                heartbeat = db.get(Runtime, "worker")
                if heartbeat:
                    heartbeat.heartbeat = now()
                else:
                    db.add(Runtime(key="worker", heartbeat=now()))
                db.commit()
            if time.monotonic() - last_monitor >= 60:
                monitor_due_actions()
                sync_due_connections()
                last_monitor = time.monotonic()
            if not process_one():
                time.sleep(2)
        except Exception:
            logger.exception("Worker polling failed")
            time.sleep(5)


if __name__ == "__main__":
    main()
