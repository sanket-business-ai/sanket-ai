from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app import agent
from app.analysis import Tools
from app.config import Settings, settings
from app.db import Action, Audit, Investigation, Source, now
from app.demo import demo_pack
from app.ingestion import parse_upload, validate_rows
from app.schemas import AgentConclusion
from app.worker import monitor_due_actions, process_one


def run_investigation(client, factory, question="Why did our sales drop in the latest month?"):
    response = client.post("/api/investigations", json={"question": question})
    assert response.status_code == 202, response.text
    job_id = response.json()["id"]
    assert process_one(factory)
    job = client.get(f"/api/investigations/{job_id}").json()
    assert job["status"] == "completed", job
    return job


def test_complete_investigation_preserves_evidence_and_conservative_impact(seeded):
    client, factory = seeded
    job = run_investigation(client, factory)
    report = job["report"]
    assert report["engine"] == "deterministic"
    assert report["confidence"] == "medium"
    assert "Valley Electronics" in report["root_cause"]
    assert report["impact"]["observed_revenue_difference"] == -245000
    assert report["impact"]["attributable_loss"] is None
    assert len(report["hypotheses"]) >= 3
    assert report["hypotheses"][1]["status"] == "inconclusive"
    assert all(e["sources"] for e in report["evidence"])
    assert {s["id"] for e in report["evidence"] for s in e["sources"]} <= set(job["source_ids"])
    assert len(job["actions"]) == 1 and job["actions"][0]["status"] == "pending"
    assert any(event["stage"] == "challenge" for event in job["trail"])
    assert not process_one(factory)
    exported = client.get(f"/api/investigations/{job['id']}/export")
    assert exported.status_code == 200
    assert exported.json()["report"] == report


def test_challenge_keeps_source_snapshot_after_new_upload(seeded):
    client, factory = seeded
    original = run_investigation(client, factory)
    data = b"id,date,customer_id,product_id,quantity,revenue,status\nNEW,2026-10-12,C1,P1,1,4000,delivered\n"
    assert (
        client.post("/api/sources", data={"kind": "orders"}, files={"file": ("new_orders.csv", data)}).status_code
        == 201
    )
    response = client.post(f"/api/investigations/{original['id']}/challenge")
    assert response.status_code == 202
    assert process_one(factory)
    challenged = client.get(f"/api/investigations/{response.json()['id']}").json()
    assert challenged["source_ids"] == original["source_ids"]
    assert challenged["report"]["challenged"] is True
    assert len(challenged["report"]["evidence"]) > len(original["report"]["evidence"])
    assert client.get(f"/api/investigations/{original['id']}").json()["report"] == original["report"]


def test_approval_is_idempotent_and_monitoring_rejects_stale_data(seeded):
    client, factory = seeded
    action = run_investigation(client, factory)["actions"][0]
    path = f"/api/actions/{action['id']}"
    assert client.post(path + "/monitor").status_code == 409
    for _ in range(2):
        response = client.post(path + "/decision", json={"decision": "approve"})
        assert response.status_code == 200
        assert response.json()["status"] == "monitoring"
    assert client.post(path + "/decision", json={"decision": "reject"}).status_code == 409
    assert client.post(path + "/monitor").status_code == 409
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Audit).where(Audit.event == "action.approve")) == 1


def shift_outcome_sources(client, success):
    import csv
    import io

    for kind, filename, data in demo_pack():
        if kind not in {"orders", "deliveries", "inventory", "marketing", "suppliers", "expenses"}:
            continue
        rows = list(csv.DictReader(io.StringIO(data.decode())))
        for row in rows:
            for key in ("date", "promised_date", "delivered_date", "received_date"):
                if row.get(key):
                    row[key] = str(date.fromisoformat(row[key]) + timedelta(days=56))
            if kind == "deliveries" and success:
                row["delivered_date"] = row["promised_date"]
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        response = client.post(
            "/api/sources", data={"kind": kind}, files={"file": (filename, buffer.getvalue().encode())}
        )
        assert response.status_code == 201, response.text


@pytest.mark.parametrize("success", [True, False])
def test_fresh_outcome_records_success_or_queues_one_followup(seeded, success):
    client, factory = seeded
    action = run_investigation(client, factory)["actions"][0]
    path = f"/api/actions/{action['id']}"
    assert client.post(path + "/decision", json={"decision": "approve"}).status_code == 200
    shift_outcome_sources(client, success)
    response = client.post(path + "/monitor")
    assert response.status_code == 200, response.text
    outcome = response.json()
    assert outcome["status"] == ("succeeded" if success else "failed")
    assert bool(outcome["outcome"].get("followup_investigation_id")) is not success
    assert client.post(path + "/monitor").json()["outcome"] == outcome["outcome"]
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Investigation)) == (1 if success else 2)


def test_authentication_csrf_origin_and_logout(workspace):
    client, _ = workspace
    csrf = client.headers.pop("X-CSRF-Token")
    assert client.post("/api/demo").status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    assert client.post("/api/demo", headers={"Origin": "https://attacker.example"}).status_code == 403
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/sources").status_code == 401


def test_invalid_upload_is_atomic_and_duplicate_upload_is_reused(seeded):
    client, _ = seeded
    count = len(client.get("/api/sources").json())
    bad = b"id,date,customer_id,product_id,quantity,revenue,status\nO1,not-a-date,C1,P1,1,NaN,delivered\n"
    assert client.post("/api/sources", data={"kind": "orders"}, files={"file": ("bad.csv", bad)}).status_code == 422
    kind, name, data = demo_pack()[0]
    assert client.post("/api/sources", data={"kind": kind}, files={"file": (name, data)}).status_code == 201
    assert len(client.get("/api/sources").json()) == count
    assert client.post("/api/demo").status_code == 409


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-1", "1e9999"])
def test_nonfinite_or_negative_money_is_rejected(amount):
    with pytest.raises(ValueError):
        validate_rows([{"id": "P1", "name": "Product", "category": "Test", "price": amount, "cost": "1"}], "products")


def test_duplicate_keys_and_missing_headers_are_rejected():
    row = {"id": "C1", "segment": "New", "location": "Kathmandu", "signup_date": "2026-01-01"}
    with pytest.raises(ValueError, match="duplicate"):
        validate_rows([row, row], "customers")
    with pytest.raises(ValueError, match="Missing required"):
        parse_upload(b"id,name\nP1,Phone\n", "products.csv", "products")


def test_document_only_investigation_does_not_invent_a_cause(workspace):
    client, factory = workspace
    assert (
        client.post(
            "/api/sources",
            data={"kind": "document"},
            files={
                "file": (
                    "notes.txt",
                    b"Supplier claims that a route delay caused lower sales. This claim is unverified.",
                )
            },
        ).status_code
        == 201
    )
    report = run_investigation(client, factory)["report"]
    assert report["confidence"] == "low"
    assert report["actionable"] is False
    assert report["impact"]["observed_revenue_difference"] is None


def test_model_failure_is_visible_in_auto_mode(seeded, monkeypatch):
    client, factory = seeded
    monkeypatch.setattr(settings(), "agent_mode", "auto")

    def unavailable(*args):
        raise ValueError("invalid model JSON")

    monkeypatch.setattr(agent, "model_json", unavailable)
    report = run_investigation(client, factory)["report"]
    assert report["engine"] == "deterministic"
    assert report["model_notice"]


def test_model_cannot_cite_invented_evidence():
    payload = {
        "root_cause": "A supplier delay could explain the observed change.",
        "causal_chain": ["Supplier delay"],
        "evidence_ids": ["E999"],
        "confidence": "high",
        "hypotheses": [
            {
                "id": f"H{i}",
                "claim": "A supplier delay caused the decline",
                "status": "inconclusive",
                "supporting_evidence": [],
                "contradicting_evidence": [],
                "explanation": "Unknown",
            }
            for i in (1, 2)
        ],
        "unknowns": ["Demand is not measured"],
        "recommended_action": "Check supplier shipment records.",
    }
    with pytest.raises(ValueError, match="not collected"):
        agent.validate_conclusion(AgentConclusion.model_validate(payload), [{"id": "E1", "sources": [{"id": "s"}]}])


def test_lease_recovery_cannot_duplicate_actions(seeded):
    client, factory = seeded
    job = client.post("/api/investigations", json={"question": "Why did deliveries become late?"}).json()
    with factory() as db:
        record = db.get(Investigation, job["id"])
        record.status = "running"
        record.started_at = now() - timedelta(hours=1)
        record.lease_token = "crashed-worker"
        db.commit()
    assert process_one(factory)
    assert not process_one(factory)
    with factory() as db:
        assert db.get(Investigation, job["id"]).attempts == 1
        assert db.scalar(select(func.count()).select_from(Action)) == 1


def test_production_configuration_rejects_insecure_defaults():
    with pytest.raises(ValueError, match="Production requires"):
        Settings(
            environment="production", secure_cookies=False, frontend_origin="http://localhost:5173", demo_enabled=False
        )


def test_partial_period_cannot_produce_confident_impact():
    content, _ = parse_upload(
        b"id,date,customer_id,product_id,quantity,revenue,status\nO1,2026-09-30,C1,P1,1,100,delivered\n",
        "orders.csv",
        "orders",
    )
    source = SimpleNamespace(id="source", name="orders.csv", kind="orders", content=content)
    report = agent.investigate([source], "Why did sales change?", "question", lambda *_: None)
    assert report["confidence"] == "low" and not report["actionable"]
    assert report["impact"]["observed_revenue_difference"] is None


def test_tools_use_decimal_for_money():
    rows = [
        {
            "id": str(i),
            "date": "2026-09-30",
            "customer_id": "C1",
            "product_id": "P1",
            "quantity": "1",
            "revenue": "0.1",
            "status": "delivered",
        }
        for i in range(3)
    ]
    source = SimpleNamespace(id="s", name="orders.csv", kind="orders", content={"rows": rows})
    assert Tools([source]).detect_anomalies()["metrics"][0]["current"] == 0.3


def test_due_monitor_waits_for_data_then_checks_automatically(seeded):
    client, factory = seeded
    action = run_investigation(client, factory)["actions"][0]
    client.post(f"/api/actions/{action['id']}/decision", json={"decision": "approve"})
    with factory() as db:
        db.get(Action, action["id"]).due_at = now() - timedelta(days=1)
        db.commit()
    monitor_due_actions(factory)
    with factory() as db:
        assert db.get(Action, action["id"]).status == "monitoring"
        assert db.get(Action, action["id"]).due_at.replace(tzinfo=now().tzinfo) > now()
    shift_outcome_sources(client, True)
    with factory() as db:
        db.get(Action, action["id"]).due_at = now() - timedelta(days=1)
        db.commit()
    monitor_due_actions(factory)
    with factory() as db:
        assert db.get(Action, action["id"]).status == "succeeded"


def test_counter_evidence_reduces_confidence(seeded):
    client, factory = seeded
    with factory() as db:
        source = db.scalar(select(Source).where(Source.kind == "marketing"))
        data = source.content.copy()
        data["rows"] = [
            dict(row, clicks="10", impressions="100") if row["date"] >= "2026-09-03" else row for row in data["rows"]
        ]
        # Test fixture changes are intentional; application sources are immutable.
        source.content = data
        db.commit()
    report = run_investigation(client, factory)["report"]
    assert report["confidence"] == "low"
    assert not report["actionable"]
    assert report["hypotheses"][1]["supporting_evidence"]


def test_model_selects_tools_and_validates_final_report(seeded, monkeypatch):
    from app.schemas import AgentStep

    client, factory = seeded
    monkeypatch.setattr(settings(), "agent_mode", "ollama")
    steps = iter(
        [
            AgentStep(
                rationale="Inspect fulfillment as a competing explanation.",
                tool="get_deliveries",
                hypotheses=[
                    {"id": "H1", "claim": "Supplier delays constrained deliveries"},
                    {"id": "H2", "claim": "Demand weakened across the business"},
                ],
            ),
            AgentStep(rationale="Conclude after mandatory counter-evidence verification.", tool="finish"),
        ]
    )

    def model(schema, messages):
        if schema is AgentStep:
            return next(steps)
        return AgentConclusion.model_validate(
            {
                "root_cause": "Supplier constraints are a possible explanation requiring further validation.",
                "causal_chain": ["Supplier constraint", "Fulfillment impact"],
                "evidence_ids": ["E1"],
                "confidence": "high",
                "hypotheses": [
                    {
                        "id": f"H{i}",
                        "claim": f"Competing explanation number {i}",
                        "status": "inconclusive",
                        "supporting_evidence": [],
                        "contradicting_evidence": [],
                        "explanation": "Evidence is observational.",
                    }
                    for i in (1, 2)
                ],
                "unknowns": ["The counterfactual is unknown."],
                "recommended_action": "Review supplier delivery commitments.",
            }
        )

    monkeypatch.setattr(agent, "model_json", model)
    job = run_investigation(client, factory)
    assert job["report"]["engine"] == "ollama"
    assert job["report"]["confidence"] == "medium"
    assert any(item["stage"] == "hypotheses" for item in job["trail"])


def test_malformed_pdf_and_oversize_upload_are_rejected(workspace, monkeypatch):
    client, _ = workspace
    response = client.post("/api/sources", data={"kind": "document"}, files={"file": ("broken.pdf", b"not a PDF")})
    assert response.status_code == 422
    monkeypatch.setattr(settings(), "upload_max_bytes", 10)
    assert (
        client.post("/api/sources", data={"kind": "document"}, files={"file": ("big.txt", b"x" * 11)}).status_code
        == 413
    )
