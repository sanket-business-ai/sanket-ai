
import math
import re

import httpx

from .config import settings


def _embed_query(query: str) -> list[float] | None:
    """Create a query embedding using Ollama."""
    try:
        with httpx.Client(timeout=10, trust_env=False) as client:
            response = client.post(
                settings().ollama_url.rstrip("/") + "/api/embed",
                json={
                    "model": "bge-m3",
                    "input": query,
                },
            )
            response.raise_for_status()

            embeddings = response.json().get("embeddings", [])
            if embeddings and embeddings[0]:
                return embeddings[0]

    except (httpx.HTTPError, ValueError, KeyError, IndexError):
        pass

    return None


def _cosine_similarity(
    first: list[float],
    second: list[float],
) -> float:
    """Measure similarity between two embeddings."""
    if len(first) != len(second):
        return 0.0

    dot_product = sum(a * b for a, b in zip(first, second))
    first_norm = math.sqrt(sum(a * a for a in first))
    second_norm = math.sqrt(sum(b * b for b in second))

    if not first_norm or not second_norm:
        return 0.0

    return dot_product / (first_norm * second_norm)


def search(sources, query: str, limit: int = 5) -> dict:
    """
    Search document chunks using embeddings when available.
    Fall back to keyword matching when embeddings are unavailable.
    """
    query_embedding = _embed_query(query)
    chunks_to_search = []

    for source in sources:
        content = (
            source.content
            if hasattr(source, "content")
            else source.get("content", source)
        )

        if not isinstance(content, dict):
            continue

        for chunk in content.get("chunks", []):
            text = chunk.get("text", "")
            if not text:
                continue

            chunks_to_search.append({
                "source": source,
                "chunk": chunk,
                "text": text,
            })

    # Semantic search
    if query_embedding:
        embedded_chunks = [
            item for item in chunks_to_search
            if item["chunk"].get("embedding")
        ]

        if embedded_chunks:
            results = []

            for item in embedded_chunks:
                score = _cosine_similarity(
                    query_embedding,
                    item["chunk"]["embedding"],
                )
                results.append({**item, "score": score})

            results.sort(
                key=lambda item: item["score"],
                reverse=True,
            )

            return {
                "results": results[:limit],
                "method": "semantic",
            }

    # Keyword fallback
    query_words = set(re.findall(r"\w{3,}", query.lower()))
    results = []

    for item in chunks_to_search:
        text_words = set(re.findall(r"\w{3,}", item["text"].lower()))
        score = len(query_words & text_words)

        if score > 0:
            results.append({**item, "score": score})

    results.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return {
        "results": results[:limit],
        "method": "keyword",
    }
