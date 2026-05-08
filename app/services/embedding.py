"""Embedding wrapper. Uses sentence-transformers; caches by SHA1."""
from __future__ import annotations
import hashlib
import logging
from functools import lru_cache
from typing import Iterable

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _model():
    """Load model once, lazily."""
    from sentence_transformers import SentenceTransformer
    logger.info("Loading embedding model: %s", settings.embedding_model)
    return SentenceTransformer(settings.embedding_model)


# Simple in-process cache: sha1(text) -> np.ndarray
_VEC_CACHE: dict[str, np.ndarray] = {}


def _hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts. Returns list of float vectors. Cached."""
    if not texts:
        return []
    out: list[list[float]] = [None] * len(texts)  # type: ignore
    miss_idx: list[int] = []
    miss_texts: list[str] = []
    for i, t in enumerate(texts):
        key = _hash(t)
        if key in _VEC_CACHE:
            out[i] = _VEC_CACHE[key].tolist()
        else:
            miss_idx.append(i)
            miss_texts.append(t)
    if miss_texts:
        m = _model()
        vecs = m.encode(miss_texts, normalize_embeddings=True, show_progress_bar=False)
        vecs = np.asarray(vecs, dtype=np.float32)
        for j, i in enumerate(miss_idx):
            v = vecs[j]
            _VEC_CACHE[_hash(miss_texts[j])] = v
            out[i] = v.tolist()
    return out  # type: ignore


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]


def cosine(a: list[float] | np.ndarray, b: list[float] | np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))
