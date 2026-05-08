"""All prompt templates for the system, kept in one place for tuning."""
from __future__ import annotations


METADATA_EXTRACTION = """\
You extract structured metadata from regulatory documents.
Return ONLY valid JSON. No prose, no markdown fences. If a field is unknown, use null.

From the document excerpt below, extract:
{{
  "issuing_body": "CMS | <state agency> | Other",
  "regulation_id": "e.g. 'CMS-4201-F' or null",
  "title": "...",
  "effective_date": "YYYY-MM-DD or null",
  "regulatory_category": ["claims" | "billing" | "compliance" | "enrollment" | "appeals" | "privacy" | "fraud_waste_abuse" | "other"],
  "change_type": "new | modification | removal | clarification"
}}

EXCERPT:
\"\"\"
{excerpt}
\"\"\"
"""


IMPACT_ANALYSIS_SYSTEM = """\
You are a senior healthcare compliance analyst at a U.S. payer.
You analyze regulatory text and map it to internal enterprise artifacts.
You ground EVERY claim in the provided context using [CHUNK_n] citations.
If the retrieved context is insufficient, say so explicitly in the "insufficient_context" array.
Output ONLY valid JSON matching the schema. No prose, no markdown fences.
"""


IMPACT_ANALYSIS_USER = """\
=== NEW / UPDATED REGULATION ===
Title: {reg_title}
Effective date: {effective_date}
Category: {category}

Regulation excerpt:
\"\"\"
{regulation_excerpt}
\"\"\"

=== RETRIEVED ENTERPRISE CONTEXT ===
{context_block}

=== TASK ===
1. Summarize what the regulation requires (2-3 sentences).
2. Identify every enterprise artifact (policy, workflow, or system) that is impacted, citing the supporting [CHUNK_n].
3. For each impacted artifact, recommend a concrete action.
4. Assign priority (High / Medium / Low) and a numeric confidence 0-1.
5. State the operational risk if the change is NOT implemented before the effective date.

Output JSON with this exact shape:
{{
  "regulation_summary": "...",
  "effective_date": "{effective_date}",
  "impacted_areas": [
    {{
      "type": "Policy | Workflow | System",
      "name": "...",
      "impact_reason": "...",
      "supporting_citations": ["CHUNK_1", "CHUNK_3"],
      "recommended_action": "...",
      "priority": "High | Medium | Low",
      "risk_if_not_implemented": "...",
      "confidence_score": 0.0
    }}
  ],
  "insufficient_context": []
}}
"""


CHANGE_SUMMARIZER = """\
You compare two versions of a regulatory clause and explain the substantive change for a healthcare compliance audience.
Be concise and factual. Do not speculate beyond the provided text.
Output ONLY valid JSON, no prose, no markdown fences.

=== OLD VERSION (section: {section_path}) ===
\"\"\"{old_text}\"\"\"

=== NEW VERSION (section: {section_path}) ===
\"\"\"{new_text}\"\"\"

Return JSON:
{{
  "type": "Added | Removed | Modified",
  "section": "{section_path}",
  "description": "Plain-English statement of what changed.",
  "impact": "How this affects payer operations.",
  "recommended_action": "Concrete action a compliance lead should take.",
  "compliance_risk_delta": "Increased | Decreased | Unchanged",
  "operational_impact_delta": "Higher | Lower | Unchanged"
}}
"""


COMPARISON_SUMMARY = """\
You write a 2-3 sentence executive summary of changes between two versions of a regulatory document.
Be factual, no speculation. Output PLAIN TEXT only (no JSON, no fences).

Number of substantive changes: {num_changes}
Change descriptions:
{change_list}
"""


SIMULATION = """\
You are a risk officer at a U.S. health plan. Given a regulatory requirement and the
enterprise artifact that is non-compliant, project the consequences over a 12-month horizon.
Output ONLY valid JSON, no prose, no markdown fences.

Regulation: {reg_summary}
Effective date: {effective_date}
Non-compliant artifact: {artifact_name} ({artifact_type})
Why non-compliant: {gap_description}

Return JSON:
{{
  "financial_exposure": {{"low_estimate_usd": 0, "high_estimate_usd": 0, "basis": "..."}},
  "regulatory_exposure": "CMP risk | CAP | suspension | other - explain",
  "member_impact": "...",
  "operational_friction": "...",
  "reputational_impact": "...",
  "likelihood_of_enforcement": "Low | Medium | High",
  "mitigation_window_days": 0
}}
"""
