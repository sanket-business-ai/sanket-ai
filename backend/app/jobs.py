from fastapi import HTTPException
from sqlalchemy import func, select

from .db import Audit, Investigation
from .ingestion import active_sources


def enqueue(db, question, mode, user_id, source_ids=None, parent_id=None):
    ids = source_ids if source_ids is not None else [s.id for s in active_sources(db)]
    if not ids:
        raise HTTPException(409, "Upload business data or load the demo evidence pack first")
    queued = db.scalar(
        select(func.count()).select_from(Investigation).where(Investigation.status.in_(["queued", "running"]))
    )
    if queued >= 20:
        raise HTTPException(429, "Investigation queue is full. Try again after a job completes.")
    job = Investigation(question=question, mode=mode, source_ids=ids, created_by=user_id, parent_id=parent_id)
    db.add(job)
    db.flush()
    db.add(Audit(actor=user_id, event="investigation.created", entity_id=job.id, details={"mode": mode}))
    return job
