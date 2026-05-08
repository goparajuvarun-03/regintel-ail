"""Chroma wrapper. One collection per document kind."""
from __future__ import annotations
import logging
from functools import lru_cache
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings
from app.services.embedding import embed_texts

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _client():
    return chromadb.PersistentClient(
        path=str(settings.chroma_dir),
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def _coll_name(kind: str) -> str:
    return f"regintel_{kind}"


def get_collection(kind: str):
    return _client().get_or_create_collection(name=_coll_name(kind), metadata={"hnsw:space": "cosine"})


def add_chunks(
    kind: str,
    doc_id: str,
    chunks: list[dict],
) -> None:
    """Embed and add chunks to the appropriate collection.

    Each chunk dict must have: text, section, char_start, char_end, idx.
    """
    if not chunks:
        return
    coll = get_collection(kind)
    ids = [f"{doc_id}::chunk_{c['idx']}" for c in chunks]
    docs = [c["text"] for c in chunks]
    metas = [{
        "doc_id": doc_id,
        "section": (c.get("section") or "")[:120],
        "char_start": c["char_start"],
        "char_end": c["char_end"],
        "idx": c["idx"],
        "title": (c.get("title") or "")[:200],
        "version": c.get("version") or "",
    } for c in chunks]
    embeddings = embed_texts(docs)
    coll.upsert(ids=ids, documents=docs, embeddings=embeddings, metadatas=metas)


def query_collection(
    kind: str,
    query_texts: list[str],
    n_results: int = 10,
    where: Optional[dict] = None,
) -> list[dict]:
    """Run a dense query. Returns flat list of hits across all queries, dedup by id."""
    coll = get_collection(kind)
    embeddings = embed_texts(query_texts)
    res = coll.query(
        query_embeddings=embeddings,
        n_results=n_results,
        where=where,
    )
    seen: set[str] = set()
    hits: list[dict] = []
    if not res or not res.get("ids"):
        return hits
    for q_i in range(len(res["ids"])):
        ids = res["ids"][q_i]
        docs = res["documents"][q_i]
        metas = res["metadatas"][q_i]
        dists = res["distances"][q_i]
        for k in range(len(ids)):
            cid = ids[k]
            if cid in seen:
                continue
            seen.add(cid)
            # cosine distance -> similarity
            sim = max(0.0, 1.0 - float(dists[k]))
            hits.append({
                "id": cid,
                "text": docs[k],
                "metadata": metas[k] or {},
                "score": sim,
            })
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits


def get_all_chunks_for_doc(kind: str, doc_id: str) -> list[dict]:
    """Fetch every chunk for a doc, ordered by idx."""
    coll = get_collection(kind)
    res = coll.get(where={"doc_id": doc_id})
    items = []
    for i, cid in enumerate(res.get("ids", [])):
        items.append({
            "id": cid,
            "text": res["documents"][i],
            "metadata": res["metadatas"][i] or {},
        })
    items.sort(key=lambda x: x["metadata"].get("idx", 0))
    return items


def delete_doc(kind: str, doc_id: str) -> None:
    coll = get_collection(kind)
    coll.delete(where={"doc_id": doc_id})
