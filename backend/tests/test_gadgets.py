import csv
import io
from collections import Counter
from datetime import date
from types import SimpleNamespace

import pytest

from app import agent, gadgets
from app.ingestion import CONTRACTS, parse_upload


@pytest.fixture(scope="module")
def dataset():
    return gadgets.generate()


def load(files):
    sources = []
    for name, data in files["csv"].items():
        kind = name.rsplit("_", 1)[1].removesuffix(".csv")
        content, _ = parse_upload(data, name, kind)  # raises if SanketAI would reject the upload
        sources.append(SimpleNamespace(id=name, name=name, kind=kind, content=content))
    for name, data in files["documents"].items():
        content, _ = parse_upload(data, name, "document")
        sources.append(SimpleNamespace(id=name, name=name, kind="document", content=content))
    return sources


def investigate(dataset, slug):
    pack = next(p for p in gadgets.PACKS if p["slug"] == slug)
    return agent.investigate(load(dataset[1][slug]), pack["question"], "question", lambda *_: None)


def metric(report, key):
    return next(m for m in report["metrics"] if m["key"] == key)


def test_every_pack_passes_upload_validation_within_limits(dataset):
    _, packs = dataset
    for files in packs.values():
        sources = load(files)
        assert {s.kind for s in sources} == set(CONTRACTS) | {"document"}
        assert all(len(data) < 10 * 1024 * 1024 for data in files["csv"].values())
        assert all(len(s.content["rows"]) <= 50_000 for s in sources if s.kind != "document")


def test_the_dashain_customs_delay_causes_the_only_stockouts(dataset):
    history, _ = dataset
    empty = {day for day, _, supplier, stock in history["inventory"] if stock <= 0}
    suppliers = {supplier for _, _, supplier, stock in history["inventory"] if stock <= 0}
    assert suppliers == {"S01"}
    assert date(2026, 9, 14) < min(empty) and max(empty) < gadgets.DASHAIN_RECEIVED


def test_exports_wait_for_deliveries_to_settle(dataset):
    _, packs = dataset
    rows = list(csv.DictReader(io.StringIO(packs["2_margin_squeeze"]["csv"]["hmg_2026-03-28_orders.csv"].decode())))
    statuses = Counter(row["status"] for row in rows)
    assert (statuses["pending"] + statuses["shipped"]) / len(rows) < 0.005


def test_margin_pack_names_the_courier_and_the_supplier(dataset):
    report = investigate(dataset, "2_margin_squeeze")
    statuses = {h["id"]: h["status"] for h in report["hypotheses"]}
    assert report["scenario"] == "margin" and report["confidence"] == "medium"
    assert statuses["H1"] == statuses["H2"] == "supported" and statuses["H3"] == "rejected"
    assert "Peakline Parcel" in report["root_cause"] and "Everest Tech Traders" in report["root_cause"]
    assert "products rose" in report["root_cause"], "a supplier's effect covers all of its repriced products"


def test_dashain_pack_traces_the_drop_to_the_delayed_shipment(dataset):
    report = investigate(dataset, "5_dashain_stockout")
    assert report["confidence"] == "medium" and "Everest Tech Traders" in report["root_cause"]
    assert metric(report, "revenue")["anomaly"]


def test_ai_only_packs_carry_their_signal_without_an_invented_cause(dataset):
    history, _ = dataset
    for slug in ("1_cod_refusals", "3_ad_campaign", "4_monsoon_delays"):
        report = investigate(dataset, slug)
        assert report["confidence"] == "low" and not report["actionable"]
    assert metric(investigate(dataset, "4_monsoon_delays"), "late_rate")["anomaly"]
    campaign = [o for o in history["orders"] if o["stream"] == "cod_campaign" and not o.get("cancelled")]
    assert sum(1 for o in campaign if o.get("refused")) / len(campaign) > 0.5
