"""Live data connections. Only Google's sheet export hosts can be fetched; any other address is refused."""

import csv
import logging
import re
from datetime import timedelta, timezone

import httpx
from sqlalchemy import select

from .config import settings
from .db import Audit, Connection, SessionLocal, now
from .ingestion import active_sources, store_source

logger = logging.getLogger(__name__)
SHEET_LINK = re.compile(r"^https://docs\.google\.com/spreadsheets/d/(e/)?([A-Za-z0-9_-]{20,})(?:[/?#]|$)")
REFRESH_HOURS = (0, 1, 6, 24)
PRIVATE = "The sheet is private. In Google Sheets choose Share → General access → Anyone with the link (Viewer)."


def sheet_export_url(link):
    """Turn a Google Sheets share or publish link into the CSV export URL for the same tab."""
    match = SHEET_LINK.match(link.strip())
    if not match:
        raise ValueError("Paste a Google Sheets link that starts with https://docs.google.com/spreadsheets/d/")
    published, key = match.groups()
    gid = re.search(r"[#?&]gid=(\d+)", link)
    tab = f"&gid={gid.group(1)}" if gid else ""
    if published:
        return f"https://docs.google.com/spreadsheets/d/e/{key}/pub?output=csv{tab}"
    return f"https://docs.google.com/spreadsheets/d/{key}/export?format=csv{tab}"


def allowed(url):
    return url.scheme == "https" and (url.host == "docs.google.com" or url.host.endswith(".googleusercontent.com"))


def fetch_sheet(export_url):
    limit = settings().upload_max_bytes
    url = httpx.URL(export_url)
    try:
        with httpx.Client(timeout=30, trust_env=False, follow_redirects=False) as client:
            # Google answers with a redirect to a googleusercontent.com host; each hop is re-checked.
            for _ in range(5):
                if not allowed(url):
                    raise ValueError(
                        PRIVATE if url.host == "accounts.google.com" else "Google redirected to an unexpected address."
                    )
                with client.stream("GET", url) as response:
                    if response.is_redirect:
                        url = url.join(response.headers["location"])
                        continue
                    if response.status_code == 404:
                        raise ValueError("Google Sheets could not find that sheet or tab. Check the link.")
                    if response.status_code in {401, 403}:
                        raise ValueError(PRIVATE)
                    if response.status_code != 200:
                        raise ValueError(f"Google Sheets answered HTTP {response.status_code}. Try again later.")
                    if "text/csv" not in response.headers.get("content-type", ""):
                        raise ValueError("The link did not return sheet data. " + PRIVATE)
                    data = bytearray()
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        if len(data) > limit:
                            raise ValueError(f"The sheet exceeds the {limit // 1024 // 1024} MB upload limit.")
                    return bytes(data)
            raise ValueError("Google Sheets redirected too many times.")
    except httpx.HTTPError as error:
        raise ValueError("Could not reach Google Sheets. Check the internet connection and try again.") from error


def import_sheet(db, kind, name, export_url):
    """Fetch and store a sheet; returns the source and whether it is a new or re-activated version."""
    source, created = store_source(db, fetch_sheet(export_url), f"{name}.csv", kind)
    if not created and source.id not in {s.id for s in active_sources(db)}:
        # The sheet matches an older stored version: make that version current again.
        source.created_at = now()
        created = True
    return source, created


def sync_connection(db, connection, actor):
    try:
        source, created = import_sheet(db, connection.kind, connection.name, connection.url)
    except (ValueError, UnicodeError, csv.Error) as error:
        connection.last_status, connection.last_error = "error", str(error)[:500]
    else:
        connection.last_status = "updated" if created else "unchanged"
        connection.last_error, connection.last_source_id = None, source.id
        if created:
            db.add(
                Audit(
                    actor=actor,
                    event="connection.synced",
                    entity_id=connection.id,
                    details={"source_id": source.id, "rows": source.row_count},
                )
            )
    connection.last_synced_at = now()
    return connection


def as_utc(value):
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def sync_due_connections(session_factory=SessionLocal):
    with session_factory() as db:
        for connection in db.scalars(select(Connection).where(Connection.refresh_hours > 0)):
            last = connection.last_synced_at
            if last is None or as_utc(last) + timedelta(hours=connection.refresh_hours) <= now():
                sync_connection(db, connection, connection.created_by)
                db.commit()
                if connection.last_status == "error":
                    logger.warning("Connection %s failed to sync: %s", connection.id, connection.last_error)
