import json

import pytest
from pydantic import ValidationError

from app import agent
from app.agent import SYSTEM, choose_scenario
from app.analysis import TOOL_NAMES
from app.config import settings
from app.demo import demo_pack
from app.ingestion import parse_upload, validate_rows
from app.schemas import AgentConclusion, AgentStep
from app.worker import process_one

QUESTION = "Revenue increased, so why is our margin falling?"


def run_investigation(client, factory, question=QUESTION, mode="question"):
    response = client.post("/api/investigations", json={"question": question, "mode": mode})
    assert response.status_code == 202, response.text
    assert process_one(factory)
    job = client.get(f"/api/investigations/{response.json()['id']}").json()
    assert job["status"] == "completed", job
    return job


def upload_margin_pack(client, skip=()):
    for kind, name, data in demo_pack("margin"):
        if kind in skip:
            continue
        response = client.post("/api/sources", data={"kind": kind}, files={"file": (name, data)})
        assert response.status_code == 201, response.text


@pytest.fixture
def margin(workspace):
    client, factory = workspace
    response = client.post("/api/demo", json={"pack": "margin"})
    assert response.status_code == 201, response.text
    assert response.json() | {"sources": 12} == {
        "sources": 12,
        "datasets": 9,
        "documents": 3,
        "pack": "margin",
        "company": "HimalayanMart",
        "synthetic": True,
    }
    return client, factory


def test_margin_demo_explains_decline_with_measured_and_documented_price_rises(margin):
    client, factory = margin
    job = run_investigation(client, factory)
    report = job["report"]
    assert report["scenario"] == "margin"
    assert report["engine"] == "deterministic"
    assert report["confidence"] == "medium" and report["actionable"]
    assert report["impact"]["observed_revenue_difference"] == 50400
    assert report["impact"]["observed_contribution_difference"] == -13360
    assert "Peakline Parcel" in report["root_cause"] and "Hillside Tea Traders" in report["root_cause"]
    statuses = {h["id"]: h["status"] for h in report["hypotheses"]}
    assert statuses == {"H1": "supported", "H2": "supported", "H3": "rejected", "H4": "rejected", "H5": "rejected"}

    evidence = {item["id"]: item for item in report["evidence"]}
    for h in report["hypotheses"][:2]:
        types = {evidence[eid]["type"] for eid in h["supporting_evidence"]}
        assert types == {"calculation", "fact"}, "a supported cause needs a measured change and a document"
    discount = report["hypotheses"][2]
    assert "discount" in evidence[discount["supporting_evidence"][0]]["claim"]
    assert evidence[discount["contradicting_evidence"][0]]["type"] == "calculation"
    assert {s["id"] for e in report["evidence"] for s in e["sources"]} <= set(job["source_ids"])

    bridge = report["margin_bridge"]
    assert round(sum(step["effect"] for step in bridge["steps"]), 2) == bridge["change"] == -13360
    contribution = next(m for m in report["metrics"] if m["key"] == "contribution")
    assert (contribution["current"], contribution["previous"]) == (bridge["current"], bridge["previous"])
    assert bridge["cost_basis"] == "purchases" and not bridge["missing"]

    action = job["actions"][0]
    assert action["metric"] == "contribution"
    assert (action["baseline"], action["target"]) == (60780, 74140)


def test_discover_mode_routes_a_contribution_anomaly_to_the_margin_scenario(margin):
    client, factory = margin
    dashboard = client.get("/api/dashboard").json()
    assert {m["key"] for m in dashboard["metrics"] if m["anomaly"]} == {"contribution"}
    report = run_investigation(client, factory, "Find what is going wrong", "discover")["report"]
    assert report["scenario"] == "margin" and report["confidence"] == "medium"


def test_measured_price_rises_without_documents_stay_inconclusive(workspace):
    client, factory = workspace
    upload_margin_pack(client, skip={"document"})
    report = run_investigation(client, factory)["report"]
    assert report["confidence"] == "low" and not report["actionable"]
    assert not client.get("/api/actions").json()
    h1, h2 = report["hypotheses"][:2]
    assert h1["status"] == h2["status"] == "inconclusive"
    assert "No retrieved document" in h1["explanation"] and "No retrieved document" in h2["explanation"]
    assert "does not isolate a documented cause" in report["root_cause"]
    assert "Peakline Parcel" in report["root_cause"], "measured signals are still reported"


def test_catalog_costs_hide_supplier_price_rises_and_say_so(workspace):
    client, factory = workspace
    upload_margin_pack(client, skip={"purchases"})
    report = run_investigation(client, factory)["report"]
    # The catalog holds only today's cost, so both windows are costed at NPR 1,150 and the decline disappears.
    assert report["margin_bridge"]["cost_basis"] == "catalog"
    assert report["confidence"] == "low" and not report["actionable"]
    assert report["hypotheses"][1]["status"] == "inconclusive"
    assert "Purchase costs are not recorded" in report["hypotheses"][1]["explanation"]
    assert "The estimate is incomplete" in report["root_cause"]


def test_margin_question_on_supply_data_does_not_invent_cost_causes(seeded):
    client, factory = seeded
    report = run_investigation(client, factory, "Why is our profit margin falling?")["report"]
    assert report["scenario"] == "margin"
    assert report["confidence"] == "low" and not report["actionable"]
    statuses = {h["id"]: h["status"] for h in report["hypotheses"]}
    assert statuses["H1"] == statuses["H2"] == "inconclusive"
    assert statuses["H4"] == "supported", "the supply pack's revenue fell, so lower sales lead"
    assert any("Courier fees are not recorded" in item for item in report["unknowns"])


def test_supply_questions_keep_the_supply_scenario(seeded):
    client, factory = seeded
    report = run_investigation(client, factory, "Why did our sales drop in the latest month?")["report"]
    assert report["scenario"] == "supply" and report["margin_bridge"] is None
    assert choose_scenario("Why did deliveries become late?", "question", []) == "supply"
    assert choose_scenario("Why are courier costs rising?", "question", []) == "margin"


def test_courier_and_fee_columns_are_optional_but_validated():
    row = {"order_id": "O1", "promised_date": "2026-09-01", "delivered_date": "", "route": "Pokhara"}
    assert validate_rows([row], "deliveries") == [{**row, "delivered_date": None}]
    assert validate_rows([{**row, "courier": "", "fee": ""}], "deliveries")[0] | {"delivered_date": ""} == {
        **row,
        "courier": None,
        "fee": None,
    }
    with pytest.raises(ValueError, match="fee"):
        validate_rows([{**row, "courier": "Peakline Parcel", "fee": "-5"}], "deliveries")
    with pytest.raises(ValueError, match="Missing required columns: unit_cost"):
        parse_upload(b"date,supplier_id,product_id,quantity\n2026-09-01,S1,P1,5\n", "purchases.csv", "purchases")


def test_contracts_endpoint_lists_optional_columns(workspace):
    client, _ = workspace
    contracts = client.get("/api/sources/contracts").json()
    assert contracts["deliveries"]["optional"] == ["courier", "fee"]
    assert contracts["purchases"]["required"] == ["date", "supplier_id", "product_id", "quantity", "unit_cost"]


def test_unknown_demo_pack_is_rejected(workspace):
    client, _ = workspace
    assert client.post("/api/demo", json={"pack": "olist"}).status_code == 422


def test_model_plans_with_margin_tools_and_verification_completes(margin, monkeypatch):
    client, factory = margin
    monkeypatch.setattr(settings(), "agent_mode", "ollama")
    steps = iter(
        [
            AgentStep(rationale="Check courier fees before other costs.", tool="get_delivery_costs"),
            AgentStep(rationale="Enough evidence to conclude.", tool="finish"),
        ]
    )

    def model(schema, messages):
        if schema is AgentStep:
            return next(steps)
        results = [json.loads(m["content"]) for m in messages if m["content"].startswith('{"tool"')]
        courier = next(r for r in results if r["tool"] == "get_delivery_costs")["result"]["couriers"][0]
        return AgentConclusion.model_validate(
            {
                "root_cause": "Courier fees rose; the rate notice and fee records agree.",
                "causal_chain": ["Courier rate rise", "Lower contribution"],
                "evidence_ids": [courier["evidence_id"]],
                "confidence": "high",
                "hypotheses": [
                    {
                        "id": f"H{i}",
                        "claim": f"Competing cost explanation {i}",
                        "status": "inconclusive",
                        "supporting_evidence": [],
                        "contradicting_evidence": [],
                        "explanation": "Observational.",
                    }
                    for i in (1, 2)
                ],
                "unknowns": ["Invoices are not reconciled."],
                "recommended_action": "Compare courier rates before renewing the contract.",
            }
        )

    monkeypatch.setattr(agent, "model_json", model)
    job = run_investigation(client, factory)
    tools = [item["data"]["tool"] for item in job["trail"] if item["stage"] == "tool"]
    assert tools[:2] == ["detect_anomalies", "get_delivery_costs"]
    assert {"get_margin_bridge", "get_supplier_costs"} <= set(tools)
    assert job["report"]["engine"] == "ollama" and job["report"]["confidence"] == "medium"


def test_tool_allowlist_matches_schema_and_prompt():
    choices = set(AgentStep.model_fields["tool"].annotation.__args__)
    assert choices == set(TOOL_NAMES) | {"finish"}
    assert all(name in SYSTEM for name in TOOL_NAMES)
    with pytest.raises(ValidationError):
        AgentStep(rationale="Run arbitrary code.", tool="run_sql")
