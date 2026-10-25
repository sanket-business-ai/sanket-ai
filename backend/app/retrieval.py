"""Document retrieval with local embeddings and keyword fallback."""

import math
import re

import httpx

from .config import settings

STOP_WORDS = {"the", "and", "why", "our", "this", "what"}
MIN_SIMILARITY = 0.5
BATCH = 32


def embed(texts):
    """Embed texts with the configured local model; None when embeddings are off or unavailable."""
    model = settings().embedding_model
    if not model or not texts:
        return None
    vectors = []
    try:
        with httpx.Client(timeout=120, trust_env=False) as client:
            for start in range(0, len(texts), BATCH):
                response = client.post(
                    settings().ollama_url.rstrip("/") + "/api/embed",
                    json={"model": model, "input": texts[start : start + BATCH]},
                )
                response.raise_for_status()
                vectors += response.json()["embeddings"]
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None
    return vectors if len(vectors) == len(texts) and all(vectors) else None


def _embed_query(query: str) -> list[float] | None:
    """Compatibility helper for callers that embed one query at a time."""
    vectors = embed([query])
    return vectors[0] if vectors else None


def cosine(first, second):
    if len(first) != len(second):
        return 0.0
    dot = sum(a * b for a, b in zip(first, second))
    norms = math.sqrt(sum(a * a for a in first)) * math.sqrt(sum(b * b for b in second))
    return dot / norms if norms else 0.0


def _cosine_similarity(first: list[float], second: list[float]) -> float:
    """Compatibility alias for the original retrieval API."""
    return cosine(first, second)


def words(text):
    return set(re.findall(r"\w{3,}", text.lower()))


def rank(query, chunks, limit=5):
    """Rank source/chunk pairs semantically, with keyword fallback for unembedded chunks."""
    queries = [query] if isinstance(query, str) else query
    tokens = [words(item) - STOP_WORDS for item in queries]
    query_vectors = None
    if any(chunk.get("embedding") for _, chunk in chunks):
        query_vectors = embed(queries)
    semantic, keyword = [], []
    for source, chunk in chunks:
        text = words(chunk["text"])
        overlap = max((len(token_set & text) for token_set in tokens), default=0)
        if query_vectors and chunk.get("embedding"):
            similarity = max(cosine(vector, chunk["embedding"]) for vector in query_vectors)
            if similarity >= MIN_SIMILARITY:
                semantic.append(
                    {"source": source, "chunk": chunk, "similarity": similarity, "overlap": overlap}
                )
        elif overlap:
            keyword.append({"source": source, "chunk": chunk, "overlap": overlap})
    semantic.sort(key=lambda match: (-match["similarity"], match["source"].name, match["chunk"]["chunk"]))
    keyword.sort(key=lambda match: (-match["overlap"], match["source"].name, match["chunk"]["chunk"]))
    matches = (semantic + keyword)[:limit]
    used = {"semantic" if "similarity" in match else "keyword" for match in matches}
    method = (
        f"semantic ({settings().embedding_model}) and keyword"
        if used == {"semantic", "keyword"}
        else f"semantic ({settings().embedding_model})"
        if used == {"semantic"}
        else "lexical keyword retrieval"
    )
    return matches, method


def search(sources, query: str, limit: int = 5) -> dict:
    """Compatibility API for direct document search and the /sources/search endpoint."""
    chunks_to_search = []
    for source in sources:
        content = source.content if hasattr(source, "content") else source.get("content", source)
        if not isinstance(content, dict):
            continue
        for chunk in content.get("chunks", []):
            text = chunk.get("text", "")
            if text:
                chunks_to_search.append({"source": source, "chunk": chunk, "text": text})

    query_embedding = _embed_query(query)
    embedded_chunks = [item for item in chunks_to_search if item["chunk"].get("embedding")]
    if query_embedding and embedded_chunks:
        results = [
            {
                **item,
                "score": cosine(query_embedding, item["chunk"]["embedding"]),
            }
            for item in embedded_chunks
        ]
        results.sort(key=lambda item: item["score"], reverse=True)
        return {"results": results[:limit], "method": "semantic"}

    query_words = words(query)
    results = []
    for item in chunks_to_search:
        score = len(query_words & words(item["text"]))
        if score:
            results.append({**item, "score": score})
    results.sort(key=lambda item: item["score"], reverse=True)
    return {"results": results[:limit], "method": "keyword"}
