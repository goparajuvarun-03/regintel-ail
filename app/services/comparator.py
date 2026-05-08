"""Version comparison engine: textual diff + semantic diff + LLM summarization."""
from __future__ import annotations
import difflib
import logging
import re
from typing import Optional

from app.api.schemas import Change, DocumentComparison
from app.prompts import CHANGE_SUMMARIZER, COMPARISON_SUMMARY
from app.services import database as db
from app.services.embedding import cosine, embed_text
from app.services.llm import call_llm, call_llm_json

logger = logging.getLogger(__name__)


# Regulatory section pattern (mirrors chunker)
_SECTION_RE = re.compile(
    r"(§\s*\d+(?:\.\d+)*[a-z]?(?:\([a-z0-9ivx]+\))*|Section\s+\d+(?:\.\d+)*)",
    re.IGNORECASE,
)


def _split_into_paragraphs(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    parts = re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if p.strip()]


def _detect_section(p: str) -> Optional[str]:
    m = _SECTION_RE.search(p[:200])
    return m.group(1).strip() if m else None


def _semantic_class(old: str, new: str) -> tuple[str, float]:
    """Classify a 'replace' block by embedding cosine similarity."""
    sim = cosine(embed_text(old), embed_text(new))
    if sim >= 0.95:
        return "cosmetic", sim
    if sim >= 0.85:
        return "minor", sim
    if sim >= 0.55:
        return "modified", sim
    return "rewritten", sim


def _summarize_change(section: str, old: str, new: str, kind: str) -> dict:
    """Ask the LLM for a structured change summary."""
    if kind == "added":
        old_for_prompt = "(no prior content)"
        new_for_prompt = new
    elif kind == "removed":
        old_for_prompt = old
        new_for_prompt = "(removed)"
    else:
        old_for_prompt, new_for_prompt = old, new
    try:
        return call_llm_json(
            system="You compare regulatory clauses and emit JSON only.",
            user=CHANGE_SUMMARIZER.format(
                section_path=section or "Unknown section",
                old_text=old_for_prompt[:1500],
                new_text=new_for_prompt[:1500],
            ),
            max_tokens=600,
        )
    except Exception as e:
        logger.warning("LLM change summarizer failed: %s", e)
        return {}


def compare_documents(old_doc_id: str, new_doc_id: str) -> DocumentComparison:
    old_doc = db.get_document(old_doc_id)
    new_doc = db.get_document(new_doc_id)
    if not old_doc or not new_doc:
        raise ValueError("One of the documents was not found.")

    old_text = old_doc.get("full_text") or ""
    new_text = new_doc.get("full_text") or ""

    old_paras = _split_into_paragraphs(old_text)
    new_paras = _split_into_paragraphs(new_text)

    sm = difflib.SequenceMatcher(a=old_paras, b=new_paras, autojunk=False)
    changes: list[Change] = []

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if tag == "insert":
            for j in range(j1, j2):
                p = new_paras[j]
                section = _detect_section(p) or _detect_section(
                    new_paras[max(0, j-1)] if j > 0 else ""
                ) or "Unknown section"
                summary = _summarize_change(section, "", p, "added")
                changes.append(Change(
                    type="Added",
                    section=summary.get("section") or section,
                    description=summary.get("description") or "New content was added.",
                    impact=summary.get("impact") or "May introduce new obligations.",
                    recommended_action=summary.get("recommended_action") or "Review and incorporate into operations.",
                    compliance_risk_delta=summary.get("compliance_risk_delta") or "Increased",
                    operational_impact_delta=summary.get("operational_impact_delta") or "Higher",
                    new_text=p,
                ))
        elif tag == "delete":
            for i in range(i1, i2):
                p = old_paras[i]
                section = _detect_section(p) or "Unknown section"
                summary = _summarize_change(section, p, "", "removed")
                changes.append(Change(
                    type="Removed",
                    section=summary.get("section") or section,
                    description=summary.get("description") or "Content was removed.",
                    impact=summary.get("impact") or "Obligation may no longer apply.",
                    recommended_action=summary.get("recommended_action") or "Confirm removal is intentional and update internal references.",
                    compliance_risk_delta=summary.get("compliance_risk_delta") or "Decreased",
                    operational_impact_delta=summary.get("operational_impact_delta") or "Lower",
                    old_text=p,
                ))
        elif tag == "replace":
            # Pair them up by index for semantic diff; if unequal counts, pair to shortest
            n = max(i2 - i1, j2 - j1)
            for k in range(n):
                old_p = old_paras[i1 + k] if i1 + k < i2 else ""
                new_p = new_paras[j1 + k] if j1 + k < j2 else ""
                if not old_p:
                    section = _detect_section(new_p) or "Unknown section"
                    summary = _summarize_change(section, "", new_p, "added")
                    changes.append(Change(
                        type="Added",
                        section=summary.get("section") or section,
                        description=summary.get("description") or "New paragraph introduced.",
                        impact=summary.get("impact") or "Possible new obligation.",
                        recommended_action=summary.get("recommended_action") or "Evaluate for impact.",
                        compliance_risk_delta=summary.get("compliance_risk_delta") or "Increased",
                        operational_impact_delta=summary.get("operational_impact_delta") or "Higher",
                        new_text=new_p,
                    ))
                    continue
                if not new_p:
                    section = _detect_section(old_p) or "Unknown section"
                    summary = _summarize_change(section, old_p, "", "removed")
                    changes.append(Change(
                        type="Removed",
                        section=summary.get("section") or section,
                        description=summary.get("description") or "Paragraph removed.",
                        impact=summary.get("impact") or "Obligation no longer present.",
                        recommended_action=summary.get("recommended_action") or "Confirm removal is intentional.",
                        compliance_risk_delta=summary.get("compliance_risk_delta") or "Decreased",
                        operational_impact_delta=summary.get("operational_impact_delta") or "Lower",
                        old_text=old_p,
                    ))
                    continue
                cls, sim = _semantic_class(old_p, new_p)
                if cls == "cosmetic":
                    continue
                section = _detect_section(new_p) or _detect_section(old_p) or "Unknown section"
                summary = _summarize_change(section, old_p, new_p, "modified")
                changes.append(Change(
                    type="Modified",
                    section=summary.get("section") or section,
                    description=summary.get("description") or f"Content modified (similarity={sim:.2f}).",
                    impact=summary.get("impact") or "Operational teams should review the updated language.",
                    recommended_action=summary.get("recommended_action") or "Update affected internal artifacts.",
                    compliance_risk_delta=summary.get("compliance_risk_delta") or ("Increased" if cls == "rewritten" else "Unchanged"),
                    operational_impact_delta=summary.get("operational_impact_delta") or ("Higher" if cls == "rewritten" else "Unchanged"),
                    old_text=old_p,
                    new_text=new_p,
                ))

    # Executive summary via LLM
    if changes:
        change_list = "\n".join(f"- [{c.type}] {c.section}: {c.description}" for c in changes[:20])
        try:
            exec_summary = call_llm(
                system="You write concise executive summaries.",
                user=COMPARISON_SUMMARY.format(num_changes=len(changes), change_list=change_list),
                json_mode=False,
                max_tokens=300,
            ).strip()
        except Exception as e:
            logger.warning("Exec summary failed: %s", e)
            exec_summary = f"{len(changes)} substantive changes detected between the two versions."
    else:
        exec_summary = "No substantive differences detected."

    result = DocumentComparison(
        summary=exec_summary,
        old_version=f"{old_doc['title']} (v{old_doc['version']})",
        new_version=f"{new_doc['title']} (v{new_doc['version']})",
        changes=changes,
    )
    db.save_comparison(old_doc_id, new_doc_id, result.model_dump())
    return result
