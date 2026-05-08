"""Impact analyzer: orchestrates retrieval + LLM reasoning to produce AnalysisResult."""
from __future__ import annotations
import logging
from typing import Optional

from app.api.schemas import AnalysisResult, ImpactedArea, Citation
from app.prompts import IMPACT_ANALYSIS_SYSTEM, IMPACT_ANALYSIS_USER
from app.services import database as db
from app.services.llm import call_llm_json
from app.services.retrieval import hybrid_search
from app.services.scoring import overall_impact_score
from app.services.vectorstore import get_all_chunks_for_doc

logger = logging.getLogger(__name__)


def _select_query_chunks(reg_chunks: list[dict], k: int = 3) -> list[dict]:
    """Pick the most informative chunks of the regulation as retrieval queries.
    Heuristic: longest chunks tend to carry the most regulatory substance."""
    return sorted(reg_chunks, key=lambda c: len(c["text"]), reverse=True)[:k]


def analyze(doc_id: str, top_k_final: int = 5) -> AnalysisResult:
    """Full impact analysis flow for one regulation doc."""
    doc = db.get_document(doc_id)
    if not doc:
        raise ValueError(f"Unknown doc_id {doc_id}")
    if doc["kind"] != "regulation":
        raise ValueError(f"analyze() expects a regulation, got kind={doc['kind']}")

    # 1) Pull regulation chunks; pick query chunks
    reg_chunks = get_all_chunks_for_doc("regulation", doc_id)
    if not reg_chunks:
        raise ValueError("Regulation has no chunks indexed.")
    query_chunks = _select_query_chunks(reg_chunks, k=3)

    # 2) For each query chunk, run hybrid retrieval against enterprise collections
    aggregated: dict[str, dict] = {}
    for qc in query_chunks:
        for kind in ("policy", "sop", "system"):
            try:
                hits = hybrid_search(kind, qc["text"], n_final=top_k_final)
            except Exception as e:
                logger.warning("Retrieval against %s failed: %s", kind, e)
                hits = []
            for h in hits:
                if h["id"] not in aggregated or h["score"] > aggregated[h["id"]]["score"]:
                    h2 = dict(h)
                    h2["kind"] = kind
                    aggregated[h["id"]] = h2

    top_hits = sorted(aggregated.values(), key=lambda x: x["score"], reverse=True)[:top_k_final]

    # 3) Build citation block
    context_lines = []
    citations: list[Citation] = []
    for i, h in enumerate(top_hits, start=1):
        cid = f"CHUNK_{i}"
        meta = h.get("metadata", {})
        src_doc_id = meta.get("doc_id", "unknown")
        src_doc = db.get_document(src_doc_id) or {}
        title = src_doc.get("title", meta.get("title", "Unknown"))
        section = meta.get("section") or "n/a"
        snippet = h["text"]
        context_lines.append(
            f"[{cid}] (source: {title}, section: {section}, kind: {h.get('kind')})\n{snippet}\n"
        )
        citations.append(Citation(
            citation_id=cid,
            source_doc_id=src_doc_id,
            source_title=title,
            section=section if section and section != "n/a" else None,
            snippet=snippet[:600],
            relevance=round(float(h.get("score", 0.0)), 3),
        ))

    if not context_lines:
        context_lines.append("[CHUNK_1] (no enterprise context indexed yet)\nNo internal documents available for retrieval.\n")

    # 4) Compose the regulation excerpt (concatenate the query chunks)
    reg_excerpt = "\n\n".join(qc["text"] for qc in query_chunks)[:6000]

    user_prompt = IMPACT_ANALYSIS_USER.format(
        reg_title=doc["title"],
        effective_date=doc.get("effective_date") or "unknown",
        category=", ".join(doc.get("regulatory_category") or []) or "general",
        regulation_excerpt=reg_excerpt,
        context_block="\n".join(context_lines),
    )

    # 5) Call LLM
    raw = call_llm_json(IMPACT_ANALYSIS_SYSTEM, user_prompt, max_tokens=1800)

    # 6) Validate / coerce
    impacted_raw = raw.get("impacted_areas", []) or []
    impacted: list[ImpactedArea] = []
    for ia in impacted_raw:
        try:
            impacted.append(ImpactedArea(
                type=ia.get("type", "Policy"),
                name=ia.get("name", "Unknown artifact"),
                impact_reason=ia.get("impact_reason", ""),
                supporting_citations=ia.get("supporting_citations", []) or [],
                recommended_action=ia.get("recommended_action", ""),
                priority=ia.get("priority", "Medium"),
                risk_if_not_implemented=ia.get("risk_if_not_implemented", ""),
                confidence_score=float(ia.get("confidence_score", 0.6)),
            ))
        except Exception as e:
            logger.warning("Skipping malformed impacted_area: %s (%s)", ia, e)

    score = overall_impact_score(
        [ia.model_dump() for ia in impacted],
        doc.get("effective_date"),
    )

    result = AnalysisResult(
        doc_id=doc_id,
        regulation_summary=raw.get("regulation_summary", ""),
        effective_date=doc.get("effective_date"),
        regulatory_category=doc.get("regulatory_category") or [],
        change_type=doc.get("change_type"),
        impacted_areas=impacted,
        impact_score_overall=score,
        citations=citations,
        insufficient_context=raw.get("insufficient_context", []) or [],
    )

    db.save_analysis(doc_id, result.model_dump(), score)
    return result
