import csv
import io

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.db import Action, Audit, Investigation, Source
from app.ingestion import parse_upload
from app.worker import process_one

RESET = {"confirm": "RESET"}


def source_named(client, name):
    return next(item for item in client.get("/api/sources").json() if item["name"] == name)


@pytest.fixture
def margin_workspace(workspace):
    client, _ = workspace
    assert client.post("/api/demo", json={"pack": "margin"}).status_code == 201
    return client


def test_reset_clears_evidence_reports_and_actions_but_keeps_the_audit_trail(seeded):
    client, factory = seeded
    client.post("/api/investigations", json={"question": "Why did our sales drop in the latest month?"})
    assert process_one(factory)
    response = client.post("/api/workspace/reset", json=RESET)
    assert response.status_code == 200, response.text
    assert response.json() == {"sources": 12, "investigations": 1, "actions": 1}
    with factory() as db:
        for model in (Source, Investigation, Action):
            assert db.scalar(select(func.count()).select_from(model)) == 0
        assert db.scalar(select(func.count()).select_from(Audit).where(Audit.event == "workspace.reset")) == 1
    assert client.post("/api/demo", json={"pack": "margin"}).status_code == 201, "demos can be switched"


def test_reset_needs_typed_confirmation_and_an_idle_worker(seeded):
    client, _ = seeded
    assert client.post("/api/workspace/reset", json={"confirm": "yes"}).status_code == 422
    assert client.post("/api/workspace/reset").status_code == 422
    client.post("/api/investigations", json={"question": "Why did our sales drop in the latest month?"})
    assert client.post("/api/workspace/reset", json=RESET).status_code == 409
    assert client.get("/api/sources").json(), "nothing was deleted"


def test_reset_is_unavailable_when_demo_loading_is_disabled(seeded, monkeypatch):
    client, _ = seeded
    monkeypatch.setattr(settings(), "demo_enabled", False)
    assert client.post("/api/workspace/reset", json=RESET).status_code == 404
    assert client.get("/api/sources").json()


def test_dataset_download_round_trips_the_stored_snapshot(margin_workspace):
    client = margin_workspace
    source = source_named(client, "himalayanmart_margin_deliveries.csv")
    response = client.get(f"/api/sources/{source['id']}/download")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'filename="himalayanmart_margin_deliveries.csv"' in response.headers["content-disposition"]
    header = next(csv.reader(io.StringIO(response.text)))
    assert header == ["order_id", "promised_date", "delivered_date", "route", "courier", "fee"]
    stored = client.get(f"/api/sources/{source['id']}").json()["rows"]
    reparsed, count = parse_upload(response.content, "deliveries.csv", "deliveries")
    assert count == source["row_count"] and reparsed["rows"][:100] == stored


def test_document_download_reassembles_overlapping_chunks(workspace):
    client, _ = workspace
    text = "".join(f"Line {i:04} of a long supplier report. " for i in range(80)).strip()
    assert len(text) > 2000
    upload = client.post("/api/sources", data={"kind": "document"}, files={"file": ("report.md", text.encode())})
    assert upload.status_code == 201 and upload.json()["row_count"] == 3
    response = client.get(f"/api/sources/{upload.json()['id']}/download")
    assert response.headers["content-type"].startswith("text/plain")
    assert 'filename="report.txt"' in response.headers["content-disposition"]
    assert response.text == text


def test_download_neutralises_spreadsheet_formulas(workspace):
    client, _ = workspace
    data = b'id,segment,location,signup_date\nC1,"=HYPERLINK(""http://x"")",Kathmandu,2026-01-01\n'
    source = client.post("/api/sources", data={"kind": "customers"}, files={"file": ("c.csv", data)}).json()
    rows = list(csv.reader(io.StringIO(client.get(f"/api/sources/{source['id']}/download").text)))
    assert rows[1][1] == '\'=HYPERLINK("http://x")'
    assert client.get("/api/sources/missing/download").status_code == 404


NEW_ORDERS = b"id,date,customer_id,product_id,quantity,revenue,status\nNEW,2026-10-12,C1,P1,1,4000,delivered\n"


def run(client, factory, question="Why did our sales drop in the latest month?"):
    job = client.post("/api/investigations", json={"question": question}).json()
    assert process_one(factory)
    return job["id"]


def active_names(client):
    return {item["name"] for item in client.get("/api/sources").json() if item["active"]}


def test_deleting_an_unused_current_version_restores_the_previous_one(seeded):
    client, factory = seeded
    new = client.post("/api/sources", data={"kind": "orders"}, files={"file": ("orders_v2.csv", NEW_ORDERS)}).json()
    assert "orders_v2.csv" in active_names(client)
    assert client.get(f"/api/sources/{new['id']}/usage").json() == {
        "investigations": 0,
        "actions": 0,
        "running": False,
        "active": True,
        "replacement": "himalayanmart_orders.csv",
    }
    response = client.post(f"/api/sources/{new['id']}/delete")
    assert response.status_code == 200 and response.json()["investigations"] == 0
    assert "himalayanmart_orders.csv" in active_names(client)
    assert client.get(f"/api/sources/{new['id']}").status_code == 404
    with factory() as db:
        event = db.scalar(select(Audit).where(Audit.event == "source.deleted"))
        assert event.details["name"] == "orders_v2.csv" and event.details["rows"] == 1
    upload = client.post("/api/sources", data={"kind": "orders"}, files={"file": ("orders_v2.csv", NEW_ORDERS)})
    assert upload.status_code == 201, "the same file can be uploaded again"


def test_deleting_a_used_source_needs_confirmation_and_removes_its_reports(seeded):
    client, factory = seeded
    first = run(client, factory)
    assert client.post(f"/api/investigations/{first}/challenge").status_code == 202
    assert process_one(factory)
    orders = source_named(client, "himalayanmart_orders.csv")
    usage = client.get(f"/api/sources/{orders['id']}/usage").json()
    assert usage["investigations"] == 2 and usage["actions"] >= 1 and usage["replacement"] is None
    refused = client.post(f"/api/sources/{orders['id']}/delete")
    assert refused.status_code == 409 and "2 investigation(s)" in refused.json()["detail"]
    assert client.get("/api/investigations").json()["total"] == 2, "a refused delete changes nothing"
    response = client.post(f"/api/sources/{orders['id']}/delete", json={"delete_investigations": True})
    assert response.json() == {"deleted": orders["id"], "investigations": 2, "actions": usage["actions"]}
    assert client.get("/api/investigations").json()["total"] == 0
    assert client.get("/api/actions").json() == []


def test_surviving_follow_ups_only_lose_their_parent_link(seeded):
    client, factory = seeded
    parent = run(client, factory)
    client.post("/api/sources", data={"kind": "orders"}, files={"file": ("orders_v2.csv", NEW_ORDERS)})
    child = run(client, factory)
    with factory() as db:
        db.get(Investigation, child).parent_id = parent
        db.commit()
    old = source_named(client, "himalayanmart_orders.csv")
    response = client.post(f"/api/sources/{old['id']}/delete", json={"delete_investigations": True})
    assert response.status_code == 200 and response.json()["investigations"] == 1
    survivor = client.get(f"/api/investigations/{child}").json()
    assert survivor["status"] == "completed" and survivor["parent_id"] is None


def test_sources_used_by_unfinished_investigations_cannot_be_deleted(seeded):
    client, _ = seeded
    client.post("/api/investigations", json={"question": "Why did our sales drop in the latest month?"})
    orders = source_named(client, "himalayanmart_orders.csv")
    assert client.get(f"/api/sources/{orders['id']}/usage").json()["running"] is True
    response = client.post(f"/api/sources/{orders['id']}/delete", json={"delete_investigations": True})
    assert response.status_code == 409 and "still running" in response.json()["detail"]
    assert client.get("/api/sources/missing/usage").status_code == 404
    assert client.post("/api/sources/missing/delete").status_code == 404
