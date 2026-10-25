from types import SimpleNamespace

import pytest
from sqlalchemy import select
from test_investigations import run_investigation

from app import ingestion, retrieval
from app.analysis import Tools
from app.config import settings
from app.db import Source

# A tiny stand-in for bge-m3: one dimension per idea, recognising English and Romanized Nepali words.
IDEAS = [
    {"late", "delay", "dhilo", "slow"},
    {"price", "prices", "cost", "mahango"},
    {"stock", "sold", "sakiyo"},
    {"monsoon", "rain", "barsat"},
]


def fake_embed(texts):
    return [[1.0 if retrieval.words(text) & idea else 0.0 for idea in IDEAS] + [0.1] for text in texts]


def document(name, *texts):
    chunks = [{"page": 1, "chunk": i + 1, "text": t, "embedding": fake_embed([t])[0]} for i, t in enumerate(texts)]
    return SimpleNamespace(id=name, name=name, kind="document", content={"chunks": chunks})


@pytest.fixture
def semantic(monkeypatch):
    monkeypatch.setattr(settings(), "embedding_model", "bge-m3")
    monkeypatch.setattr(retrieval, "embed", fake_embed)


def test_meaning_matches_without_shared_words(semantic):
    sources = [
        document("complaints.md", "Saman ekdam dhilo aayo, courier le phone uthaudaina."),
        document("letter.md", "Everest Tech Traders will raise wholesale prices by 10%."),
    ]
    result = Tools(sources).search_documents("Why are parcels arriving late?")
    assert result["method"] == "semantic (bge-m3)"
    assert [m["source"] for m in result["matches"]] == ["complaints.md"], "the unrelated letter is not a match"


def test_evidence_records_how_each_document_was_found(semantic):
    tools = Tools([document("complaints.md", "Saman dhilo aayo.")])
    tools.search_documents("late deliveries")
    assert tools.evidence[0]["calculation"].startswith("Semantic similarity")


def test_chunks_without_embeddings_still_match_by_keyword(semantic):
    old = SimpleNamespace(
        id="old.md",
        name="old.md",
        kind="document",
        content={"chunks": [{"page": 1, "chunk": 1, "text": "Courier delays in Pokhara."}]},
    )
    result = Tools([document("new.md", "Parcels were slow."), old]).search_documents("courier delays late")
    assert [m["source"] for m in result["matches"]] == ["new.md", "old.md"]
    assert result["method"] == "semantic (bge-m3) and keyword"


def test_search_falls_back_to_keywords_when_the_model_is_unavailable(semantic, monkeypatch):
    monkeypatch.setattr(retrieval, "embed", lambda texts: None)
    sources = [document("complaints.md", "Courier delays in Pokhara."), document("letter.md", "Prices rose.")]
    result = Tools(sources).search_documents("courier delays")
    assert result["method"] == "lexical keyword retrieval"
    assert [m["source"] for m in result["matches"]] == ["complaints.md"]


def test_uploads_store_embeddings_and_the_preview_hides_them(workspace, monkeypatch):
    client, factory = workspace
    monkeypatch.setattr(ingestion, "embed", fake_embed)
    upload = client.post("/api/sources", data={"kind": "document"}, files={"file": ("note.md", b"Saman dhilo aayo.")})
    assert upload.status_code == 201
    with factory() as db:
        chunk = db.scalar(select(Source)).content["chunks"][0]
        assert len(chunk["embedding"]) == len(IDEAS) + 1
    preview = client.get(f"/api/sources/{upload.json()['id']}").json()
    assert "embedding" not in preview["chunks"][0] and preview["chunks"][0]["text"] == "Saman dhilo aayo."


def test_uploads_still_work_without_the_embedding_model(workspace):
    client, factory = workspace
    upload = client.post("/api/sources", data={"kind": "document"}, files={"file": ("note.md", b"Plain note.")})
    assert upload.status_code == 201
    with factory() as db:
        assert "embedding" not in db.scalar(select(Source)).content["chunks"][0]


def test_uploading_a_document_again_embeds_it_once_the_model_is_available(workspace, monkeypatch):
    client, factory = workspace
    first = client.post("/api/sources", data={"kind": "document"}, files={"file": ("note.md", b"Saman dhilo aayo.")})
    monkeypatch.setattr(ingestion, "embed", fake_embed)
    again = client.post("/api/sources", data={"kind": "document"}, files={"file": ("note.md", b"Saman dhilo aayo.")})
    assert again.json()["id"] == first.json()["id"], "the duplicate still reuses the stored source"
    with factory() as db:
        assert db.scalar(select(Source)).content["chunks"][0]["embedding"] == fake_embed(["Saman dhilo aayo."])[0]


def test_several_queries_cite_each_chunk_once_with_its_best_score(semantic):
    sources = [document("complaints.md", "Saman dhilo aayo."), document("letter.md", "Prices rose by 10%.")]
    result = Tools(sources).search_documents(["Why are parcels late?", "price increase"])
    assert sorted(m["source"] for m in result["matches"]) == ["complaints.md", "letter.md"]
    assert all(m["score"] > 0.9 for m in result["matches"])


def test_the_verification_search_also_uses_the_question(seeded, monkeypatch):
    client, factory = seeded
    monkeypatch.setattr(settings(), "embedding_model", "bge-m3")
    monkeypatch.setattr(retrieval, "embed", fake_embed)
    monkeypatch.setattr(ingestion, "embed", fake_embed)
    note = ("roads.md", b"Barsat le pahad ko bato bandh.")
    assert client.post("/api/sources", data={"kind": "document"}, files={"file": note}).status_code == 201
    # Only the question shares an idea with the note; no built-in search terms would find it.
    job = run_investigation(client, factory, "Why did our sales drop in the monsoon rain?")
    assert "roads.md" in {s["name"] for e in job["report"]["evidence"] for s in e["sources"]}
