from datetime import timedelta

import httpx
import pytest
from sqlalchemy import func, select

from app import connectors
from app.config import settings
from app.connectors import as_utc, sheet_export_url, sync_due_connections
from app.db import Audit, Connection, Source, now

SHEET = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit#gid=7"
EXPORT = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/export?format=csv&gid=7"
PRODUCTS = b"id,name,category,price,cost\nP1,Ilam tea gift box,Gifts,1800,1000\n"
REPRICED = b"id,name,category,price,cost\nP1,Ilam tea gift box,Gifts,1800,1150\n"


@pytest.fixture
def google(monkeypatch):
    """A fake Google: docs.google.com redirects to a googleusercontent.com host that serves the CSV."""
    state = {"csv": PRODUCTS, "requests": [], "reply": None}

    def handler(request):
        state["requests"].append(str(request.url))
        if state["reply"]:
            return state["reply"](request)
        if request.url.host == "docs.google.com":
            return httpx.Response(307, headers={"location": "https://doc-0s-sheets.googleusercontent.com/export/abc"})
        return httpx.Response(200, headers={"content-type": "text/csv; charset=utf-8"}, content=state["csv"])

    real = httpx.Client
    monkeypatch.setattr(
        connectors.httpx, "Client", lambda **kwargs: real(transport=httpx.MockTransport(handler), **kwargs)
    )
    return state


def connect(client, **overrides):
    body = {"kind": "products", "url": SHEET, "name": "Product list", "refresh_hours": 6} | overrides
    return client.post("/api/connections", json=body)


def active(client, kind):
    return next(s for s in client.get("/api/sources").json() if s["kind"] == kind and s["active"])


def test_sheet_links_become_export_urls_and_other_hosts_are_refused():
    assert sheet_export_url(SHEET) == EXPORT
    assert sheet_export_url(SHEET.split("#")[0]).endswith("/export?format=csv")
    published = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQabcdefghijklmnopqrstuvwxyz/pubhtml?gid=3"
    assert sheet_export_url(published).endswith("/pub?output=csv&gid=3")
    for link in (
        "http://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
        "https://docs.google.com.evil.example/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
        "https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
    ):
        with pytest.raises(ValueError, match="Google Sheets link"):
            sheet_export_url(link)


def test_connecting_imports_the_sheet_through_googles_redirect(workspace, google):
    client, _ = workspace
    response = connect(client)
    assert response.status_code == 201, response.text
    connection = response.json()
    assert google["requests"] == [EXPORT, "https://doc-0s-sheets.googleusercontent.com/export/abc"]
    assert connection["last_status"] == "updated" and connection["refresh_hours"] == 6
    source = active(client, "products")
    assert source["name"] == "Product list.csv" and connection["last_source_id"] == source["id"]
    assert [c["id"] for c in client.get("/api/connections").json()] == [connection["id"]]
    assert connect(client).status_code == 409, "the same sheet cannot be connected twice for one type"


def test_sync_adds_versions_only_for_changes_and_restores_reverted_sheets(workspace, google):
    client, _ = workspace
    connection = connect(client).json()
    first = active(client, "products")["id"]
    sync = f"/api/connections/{connection['id']}/sync"
    assert client.post(sync).json()["last_status"] == "unchanged"
    google["csv"] = REPRICED
    assert client.post(sync).json()["last_status"] == "updated"
    second = active(client, "products")["id"]
    assert second != first and len(client.get("/api/sources").json()) == 2
    google["csv"] = PRODUCTS
    assert client.post(sync).json()["last_status"] == "updated"
    assert active(client, "products")["id"] == first, "a reverted sheet makes its earlier version current again"


@pytest.mark.parametrize(
    "reply, message",
    [
        (lambda r: httpx.Response(302, headers={"location": "https://accounts.google.com/ServiceLogin"}), "private"),
        (lambda r: httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html>"), "private"),
        (lambda r: httpx.Response(404), "could not find"),
        (lambda r: httpx.Response(307, headers={"location": "https://169.254.169.254/latest"}), "unexpected address"),
        (lambda r: httpx.Response(200, headers={"content-type": "text/csv"}, content=b"id,name\nP1,x\n"), "Missing"),
    ],
)
def test_unusable_sheets_are_reported_and_nothing_is_saved(workspace, google, reply, message):
    client, factory = workspace
    google["reply"] = reply
    response = connect(client)
    assert response.status_code == 422 and message in response.json()["detail"]
    assert not any("169.254" in url for url in google["requests"]), "redirects outside Google are never followed"
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Connection)) == 0
        assert db.scalar(select(func.count()).select_from(Source)) == 0


def test_oversized_sheets_and_documents_are_rejected(workspace, google, monkeypatch):
    client, _ = workspace
    assert connect(client, kind="document").status_code == 422
    assert (
        connect(client, url="https://example.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74").status_code == 422
    )
    monkeypatch.setattr(settings(), "upload_max_bytes", 20)
    response = connect(client)
    assert response.status_code == 422 and "exceeds" in response.json()["detail"]


def test_due_connections_sync_in_the_worker(workspace, google):
    client, factory = workspace
    hourly = connect(client, refresh_hours=1).json()
    manual = connect(client, url=SHEET.replace("gid=7", "gid=8"), refresh_hours=0, name="Manual copy").json()
    stale = now() - timedelta(hours=2)
    with factory() as db:
        for connection in db.scalars(select(Connection)):
            connection.last_synced_at = stale
        db.commit()
    google["csv"] = REPRICED
    sync_due_connections(factory)
    with factory() as db:
        assert as_utc(db.get(Connection, hourly["id"]).last_synced_at) > stale
        assert as_utc(db.get(Connection, manual["id"]).last_synced_at) == stale, "manual-only waits for Sync now"
        assert db.scalar(select(func.count()).select_from(Audit).where(Audit.event == "connection.synced")) == 1
    assert active(client, "products")["id"] != hourly["last_source_id"]


def test_failed_syncs_are_recorded_and_disconnecting_keeps_the_data(workspace, google):
    client, factory = workspace
    connection = connect(client).json()
    google["reply"] = lambda request: httpx.Response(404)
    synced = client.post(f"/api/connections/{connection['id']}/sync").json()
    assert synced["last_status"] == "error" and "could not find" in synced["last_error"]
    assert client.post(f"/api/connections/{connection['id']}/delete").status_code == 200
    assert client.get("/api/connections").json() == []
    assert active(client, "products")["name"] == "Product list.csv"
    with factory() as db:
        events = set(db.scalars(select(Audit.event)))
        assert {"connection.created", "connection.deleted"} <= events
    assert client.post("/api/connections/missing/sync").status_code == 404


def test_deleting_an_imported_source_warns_and_reset_removes_connections(workspace, google):
    client, _ = workspace
    connect(client)
    source = active(client, "products")
    assert client.get(f"/api/sources/{source['id']}/usage").json()["connections"] == ["Product list"]
    reset = client.post("/api/workspace/reset", json={"confirm": "RESET"}).json()
    assert reset["connections"] == 1 and client.get("/api/connections").json() == []
