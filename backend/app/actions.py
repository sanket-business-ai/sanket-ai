from fastapi import HTTPException
from sqlalchemy import select, update

from .analysis import Tools
from .db import Action, Audit, Investigation, now
from .ingestion import active_sources
from .jobs import enqueue


def assess_action(action_id, db, user_id):
    action = db.scalar(select(Action).where(Action.id == action_id).with_for_update())
    if not action:
        raise HTTPException(404, "Action not found")
    if action.status in {"succeeded", "failed"}:
        return action
    if action.status != "monitoring":
        raise HTTPException(409, "Approve the action before monitoring its result")
    original = db.get(Investigation, action.investigation_id)
    active = active_sources(db)
    tools = Tools(active)
    metrics = tools.detect_anomalies()
    metric = next((m for m in metrics["metrics"] if m["key"] == action.metric), None)
    old_end = original.report["period"]["current_end"]
    fresh_period = metrics["period"]["current_start"] > old_end
    coverage_valid = not any("baseline" in issue for issue in tools.coverage())
    if action.metric == "late_rate":
        deliveries = tools.delivery_summary()["current"]
        coverage_valid = (
            coverage_valid and deliveries["count"] == deliveries["matched_orders"] and deliveries["count"] > 0
        )
        source = tools.tables.get("deliveries")
        coverage_valid = coverage_valid and source is not None and source.id not in original.source_ids
    if not metric or not fresh_period or not coverage_valid:
        raise HTTPException(
            409,
            "Upload a complete, newer 28-day outcome period after the original report before assessing success or failure",
        )
    succeeded = metric["current"] >= action.target if action.direction == "up" else metric["current"] <= action.target
    status = "succeeded" if succeeded else "failed"
    outcome = {
        "value": metric["current"],
        "target": action.target,
        "baseline": action.baseline,
        "checked_at": now().isoformat(),
        "period": metrics["period"],
        "source_ids": [s.id for s in active],
        "note": "KPI outcome is observational; it does not establish that this task caused the change.",
    }
    # Reserve the transition before creating a follow-up so concurrent checks cannot duplicate it.
    result = db.execute(
        update(Action).where(Action.id == action_id, Action.status == "monitoring").values(status=status)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Another request already assessed this action")
    if not succeeded:
        followup = enqueue(db, original.question, "followup", user_id, parent_id=original.id)
        outcome["followup_investigation_id"] = followup.id
    action.outcome = outcome
    db.add(Audit(actor=user_id, event="action.monitored", entity_id=action.id, details=outcome))
    db.commit()
    db.refresh(action)
    return action
