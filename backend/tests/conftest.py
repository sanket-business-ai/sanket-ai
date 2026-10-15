import os
from pathlib import Path

os.environ["SANKET_ADMIN_PASSWORD"] = "test-only-password-12345"
os.environ["SANKET_AGENT_MODE"] = "deterministic"
os.environ["SANKET_DATABASE_URL"] = "sqlite:///" + str(
    Path(__file__).resolve().parents[2] / ".cache/test-bootstrap.db"
).replace("\\", "/")
os.environ["SANKET_ENVIRONMENT"] = "development"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app import ingestion, retrieval
from app import main
from app.db import get_db, make_engine, uid


@pytest.fixture(autouse=True)
def disable_external_embeddings(monkeypatch):
    monkeypatch.setattr(ingestion, "embed_text", lambda _: None)
    monkeypatch.setattr(retrieval, "_embed_query", lambda _: None)


@pytest.fixture
def workspace(monkeypatch):
    directory = Path(__file__).resolve().parents[2] / ".cache/test-dbs"
    directory.mkdir(parents=True, exist_ok=True)
    engine = make_engine("sqlite:///" + str(directory / f"{uid()}.db"))
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "SessionLocal", factory)

    def override():
        with factory() as db:
            yield db

    main.app.dependency_overrides[get_db] = override
    with TestClient(main.app) as client:
        response = client.post(
            "/api/auth/login", json={"email": "founder@sanketai.local", "password": "test-only-password-12345"}
        )
        assert response.status_code == 200
        client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        yield client, factory
    main.app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def seeded(workspace):
    client, factory = workspace
    response = client.post("/api/demo")
    assert response.status_code == 201
    assert response.json()["scenario"] == "supply"
    return client, factory
