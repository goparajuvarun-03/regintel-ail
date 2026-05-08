"""Hybrid retrieval: dense (Chroma) + sparse (BM25) fused with Reciprocal Rank Fusion."""
from __future__ import annotations
import logging
from typing import Optional

from rank_bm25 import BM25Okapi

from app.services.vectorstore import query_collection, get_collection

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    return [t for t in text.lower().split() if t.isalnum() or any(c.isalnum() for c in t)]


def _bm25_search(kind: str, query: str, n: int = 10, where: Optional[dict] = None) -> list[dict]:
    """Fetch all chunks (filtered) and rank by BM25. OK for dataset sizes up to ~50k chunks."""
    coll = get_collection(kind)
    res = coll.get(where=where) if where else coll.get()
    ids = res.get("ids") or []
    docs = res.get("documents") or []
    metas = res.get("metadatas") or []
    if not ids:
        return []
    tokenized = [_tokenize(d) for d in docs]
    bm25 = BM25Okapi(tokenized)
    scores = bm25.get_scores(_tokenize(query))
    ranked = sorted(zip(ids, docs, metas, scores), key=lambda x: x[3], reverse=True)[:n]
    out: list[dict] = []
    for cid, doc, meta, sc in ranked:
        out.append({
            "id": cid,
            "text": doc,
            "metadata": meta or {},
            "score": float(sc),
        })
    return out


def _rrf(ranked_lists: list[list[dict]], k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion. Each list is ordered best-first."""
    scores: dict[str, float] = {}
    payload: dict[str, dict] = {}
    for lst in ranked_lists:
        for rank, item in enumerate(lst):
            cid = item["id"]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
            payload.setdefault(cid, item)
    fused = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    out: list[dict] = []
    for cid, fused_score in fused:
        item = dict(payload[cid])
        item["score"] = fused_score
        out.append(item)
    return out


def hybrid_search(
    kind: str,
    query: str,
    n_dense: int = 10,
    n_sparse: int = 10,
    n_final: int = 5,
    where: Optional[dict] = None,
) -> list[dict]:
    """Run dense + sparse retrieval and fuse with RRF. Returns top n_final unique chunks."""
    dense = query_collection(kind, [query], n_results=n_dense, where=where)
    try:
        sparse = _bm25_search(kind, query, n=n_sparse, where=where)
    except Exception as e:
        logger.warning("BM25 failed: %s; using dense only", e)
        sparse = []
    fused = _rrf([dense, sparse]) if sparse else dense
    return fused[:n_final]
