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
