"""LLM gateway. Gemini-first for zero-cost deployments, with Anthropic/OpenAI/Mock fallbacks."""
from __future__ import annotations
import json
import re
import logging
import time
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# Public API
# ============================================================
def call_llm(system: str, user: str, json_mode: bool = True, max_tokens: int = 1500) -> str:
    """Call the configured LLM. Returns raw response text."""
    provider = (settings.llm_provider or "gemini").lower()

    if provider == "gemini" and settings.gemini_api_key:
        return _call_gemini(system, user, max_tokens, json_mode)
    if provider == "anthropic" and settings.anthropic_api_key:
        return _call_anthropic(system, user, max_tokens)
    if provider == "openai" and settings.openai_api_key:
        return _call_openai(system, user, max_tokens, json_mode)
    if provider not in {"gemini", "anthropic", "openai", "mock"}:
        logger.warning("Unknown LLM_PROVIDER=%s, falling back to mock", provider)
    return _call_mock(system, user)


def call_llm_json(system: str, user: str, max_tokens: int = 1500) -> dict:
    """Call LLM and parse JSON response. Strips markdown fences if present."""
    raw = call_llm(system, user, json_mode=True, max_tokens=max_tokens)
    return _safe_json_parse(raw)


# ============================================================
# Gemini provider (primary for zero-cost path)
# ============================================================
_GEMINI_LAST_CALL_TS = 0.0
_GEMINI_MIN_INTERVAL = 4.5  # seconds — Free tier is 15 RPM = one call per 4 seconds


def _call_gemini(system: str, user: str, max_tokens: int, json_mode: bool) -> str:
    """Gemini Flash-Lite via google-generativeai. Includes simple rate limiting."""
    global _GEMINI_LAST_CALL_TS
    import google.generativeai as genai

    # Rate-limit guard: enforce minimum interval between calls
    elapsed = time.time() - _GEMINI_LAST_CALL_TS
    if elapsed < _GEMINI_MIN_INTERVAL:
        time.sleep(_GEMINI_MIN_INTERVAL - elapsed)

    genai.configure(api_key=settings.gemini_api_key)

    generation_config = {
        "temperature": 0.2,
        "max_output_tokens": max_tokens,
    }
    if json_mode:
        generation_config["response_mime_type"] = "application/json"

    model = genai.GenerativeModel(
        model_name=settings.gemini_model,
        system_instruction=system,
        generation_config=generation_config,
    )

    try:
        response = model.generate_content(user)
        _GEMINI_LAST_CALL_TS = time.time()
        # Gemini sometimes returns empty if it hits a safety filter
        if not response.candidates or not response.candidates[0].content.parts:
            logger.warning("Gemini returned empty response; falling back to mock")
            return _call_mock(system, user)
        return response.text
    except Exception as e:
        logger.error("Gemini call failed: %s; falling back to mock", e)
        return _call_mock(system, user)


# ============================================================
# Anthropic / OpenAI providers (kept for swap-ability)
# ============================================================
def _call_anthropic(system: str, user: str, max_tokens: int) -> str:
    from anthropic import Anthropic
    client = Anthropic(api_key=settings.anthropic_api_key)
    msg = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in msg.content if hasattr(b, "text"))


def _call_openai(system: str, user: str, max_tokens: int, json_mode: bool) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=settings.openai_api_key)
    kwargs = dict(
        model=settings.openai_model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


# ============================================================
# Mock provider — fallback for when no key configured or quota hit
# ============================================================
def _call_mock(system: str, user: str) -> str:
    """A deterministic stand-in. Lets the app run end-to-end with no API key."""
    s = (system + "\n" + user).lower()

    if "extract structured metadata" in s or "issuing_body" in s:
        title = _grep_first(user, r"(?:title[:=]\s*)([^\n]+)") or "Regulatory Document"
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", user) or re.search(
            r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}",
            user,
        )
        eff = date_match.group(0) if date_match else None
        if eff and not re.match(r"\d{4}-\d{2}-\d{2}", eff):
            eff = _norm_date(eff)
        body = "CMS" if "cms" in s else ("State Agency" if "state" in s else "Other")
        cat = []
        for k in ("claims", "billing", "compliance", "enrollment", "appeals", "privacy"):
            if k in s:
                cat.append(k)
        if not cat:
            cat = ["compliance"]
        return json.dumps({
            "issuing_body": body,
            "regulation_id": _grep_first(user, r"(CMS-\d+-[A-Z]+|[A-Z]{2}\s*SB-?\d+)"),
            "title": title.strip()[:120],
            "effective_date": eff,
            "regulatory_category": cat,
            "change_type": "modification",
        })

    if "impacted_areas" in s and "regulation_summary" in s:
        chunk_ids = re.findall(r"\[CHUNK_(\d+)\]", user)[:5]
        if not chunk_ids:
            chunk_ids = ["1", "2", "3"]
        names = re.findall(r"(?:source|policy|sop|system):\s*([^,\n)]+)", user, flags=re.I)
        names = [n.strip().strip(")") for n in names][:3]
        while len(names) < 3:
            names.append(f"Internal Artifact {len(names)+1}")
        eff = _grep_first(user, r"Effective date:\s*([^\n]+)") or "TBD"
        return json.dumps({
            "regulation_summary": "The regulation introduces new payer obligations affecting downstream policy, workflow and system behavior.",
            "effective_date": eff,
            "impacted_areas": [
                {"type": "Policy", "name": names[0],
                 "impact_reason": "Existing policy language does not reflect the updated regulatory requirement.",
                 "supporting_citations": [f"CHUNK_{chunk_ids[0]}"],
                 "recommended_action": "Revise the relevant section, route through compliance review, and republish to staff.",
                 "priority": "High",
                 "risk_if_not_implemented": "Civil monetary penalties and audit findings.",
                 "confidence_score": 0.86},
                {"type": "Workflow", "name": names[1],
                 "impact_reason": "Current workflow lacks the decision step required by the new rule.",
                 "supporting_citations": [f"CHUNK_{chunk_ids[min(1, len(chunk_ids)-1)]}"],
                 "recommended_action": "Insert a triage decision node and update SOP runbook.",
                 "priority": "Medium",
                 "risk_if_not_implemented": "Inappropriate denials; appeals volume increase.",
                 "confidence_score": 0.79},
                {"type": "System", "name": names[2],
                 "impact_reason": "Core system module needs a new edit/check to enforce the regulation.",
                 "supporting_citations": [f"CHUNK_{chunk_ids[min(2, len(chunk_ids)-1)]}"],
                 "recommended_action": "Add a configuration flag and edit rule; plan a release for next sprint.",
                 "priority": "Medium",
                 "risk_if_not_implemented": "Manual workarounds; audit findings.",
                 "confidence_score": 0.74},
            ],
            "insufficient_context": [],
        })

    if "compliance_risk_delta" in s and "operational_impact_delta" in s:
        section = _grep_first(user, r"section:\s*([^\)\n]+)") or "Unknown section"
        return json.dumps({
            "type": "Modified",
            "section": section.strip(),
            "description": "Substantive language change altering an obligation or threshold.",
            "impact": "Operational teams must update procedures and reflect the change in supporting systems.",
            "recommended_action": "Update the corresponding internal policy and notify affected workflow owners.",
            "compliance_risk_delta": "Increased",
            "operational_impact_delta": "Higher",
        })

    if "executive summary of changes" in s:
        return "Several substantive changes were detected between the two versions. Most edits expand or clarify payer obligations, with a net increase in operational and compliance burden."

    if "financial_exposure" in s and "mitigation_window_days" in s:
        return json.dumps({
            "financial_exposure": {
                "low_estimate_usd": 250000,
                "high_estimate_usd": 1500000,
                "basis": "Estimated CMP exposure plus rework/appeals cost over 12 months.",
            },
            "regulatory_exposure": "CMP risk and possible CAP if non-compliance is found during audit.",
            "member_impact": "Members may experience inappropriate denials or coverage gaps.",
            "operational_friction": "Manual workarounds, increased call volume, appeals backlog.",
            "reputational_impact": "Negative member feedback and possible press coverage if widespread.",
            "likelihood_of_enforcement": "Medium",
            "mitigation_window_days": 90,
        })

    return json.dumps({"note": "mock_llm: no rule matched", "echo": user[:200]})


# ============================================================
# Helpers
# ============================================================
def _safe_json_parse(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", t, flags=re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    logger.error("LLM JSON parse failed. Raw: %s", text[:300])
    return {}


def _grep_first(text: str, pattern: str) -> Optional[str]:
    m = re.search(pattern, text, flags=re.IGNORECASE)
    return m.group(1) if m else None


_MONTHS = {m.lower(): i+1 for i, m in enumerate(
    ["January","February","March","April","May","June","July","August","September","October","November","December"]
)}

def _norm_date(s: str) -> Optional[str]:
    m = re.match(r"(\w+)\s+(\d{1,2}),\s+(\d{4})", s)
    if not m:
        return None
    mo = _MONTHS.get(m.group(1).lower())
    if not mo:
        return None
    return f"{m.group(3)}-{mo:02d}-{int(m.group(2)):02d}"
