"""Document retrieval: bge-m3 embeddings through the local Ollama when available, keyword overlap otherwise.

Builds on the retriever from the document-retriever branch (shanky-1234): chunks get an embedding at
upload, the question is embedded at search time, and anything without an embedding falls back to keywords.
"""

import math
import re

import httpx

from .config import settings

STOP_WORDS = {"the", "and", "why", "our", "this", "what"}
# bge-m3 scores unrelated business text around 0.3-0.4; below this a chunk is not treated as a match.
MIN_SIMILARITY = 0.45
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
    except httpx.HTTPError, ValueError, KeyError:
        return None
    return vectors if len(vectors) == len(texts) and all(vectors) else None


def cosine(first, second):
    if len(first) != len(second):
        return 0.0
    dot = sum(a * b for a, b in zip(first, second))
    norms = math.sqrt(sum(a * a for a in first)) * math.sqrt(sum(b * b for b in second))
    return dot / norms if norms else 0.0


def words(text):
    return set(re.findall(r"\w{3,}", text.lower()))


def rank(query, chunks, limit=5):
    """Best (source, chunk) pairs for the query.

    Chunks with embeddings are ranked by meaning; chunks without one (uploaded while embeddings were off)
    are ranked by shared words after them. Returns matches as dicts with `similarity` or `overlap`.
    """
    tokens = words(query) - STOP_WORDS
    query_vector = None
    if any(chunk.get("embedding") for _, chunk in chunks):
        vectors = embed([query])
        query_vector = vectors[0] if vectors else None
    semantic, keyword = [], []
    for source, chunk in chunks:
        overlap = len(tokens & words(chunk["text"]))
        if query_vector and chunk.get("embedding"):
            similarity = cosine(query_vector, chunk["embedding"])
            if similarity >= MIN_SIMILARITY:
                semantic.append({"source": source, "chunk": chunk, "similarity": similarity, "overlap": overlap})
        elif overlap:
            keyword.append({"source": source, "chunk": chunk, "overlap": overlap})
    semantic.sort(key=lambda m: (-m["similarity"], m["source"].name, m["chunk"]["chunk"]))
    keyword.sort(key=lambda m: (-m["overlap"], m["source"].name, m["chunk"]["chunk"]))
    matches = (semantic + keyword)[:limit]
    used = {"semantic" if "similarity" in m else "keyword" for m in matches}
    method = (
        f"semantic ({settings().embedding_model}) and keyword"
        if used == {"semantic", "keyword"}
        else f"semantic ({settings().embedding_model})"
        if used == {"semantic"}
        else "lexical keyword retrieval"
    )
    return matches, method
