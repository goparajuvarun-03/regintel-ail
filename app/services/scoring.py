"""Impact and confidence scoring."""
from __future__ import annotations
import math
from datetime import datetime
from typing import Optional


_PRIORITY_TO_SEVERITY = {"High": 9.0, "Medium": 6.0, "Low": 3.0}


def days_until(date_str: Optional[str]) -> Optional[int]:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            d = datetime.strptime(date_str, fmt)
            return (d.date() - datetime.utcnow().date()).days
        except ValueError:
            continue
    return None


def overall_impact_score(impacted_areas: list[dict], effective_date: Optional[str]) -> int:
    """0-100 deterministic score based on severity x reach x urgency."""
    if not impacted_areas:
        return 0

    # Severity = max priority across areas (mapped to 0-10)
    severity = max(_PRIORITY_TO_SEVERITY.get(ia.get("priority", "Low"), 3.0)
                   for ia in impacted_areas)

    # Reach = log scale of number of impacted artifacts (1->0, 2->3.3, 5->7, 10->10)
    n = len(impacted_areas)
    reach = min(10.0, math.log2(n + 1) * 3.3) if n > 0 else 0.0

    # Urgency = closer effective date -> more urgent
    days = days_until(effective_date)
    if days is None:
        urgency = 5.0  # neutral when unknown
    else:
        urgency = max(0.0, min(10.0, 10.0 - (days / 30.0)))

    score = 0.4 * severity + 0.3 * reach + 0.3 * urgency
    return int(round(score * 10))  # 0-100


def confidence_breakdown(retrieval_top_score: float,
                         model_self_rated: float,
                         num_citations: int,
                         num_areas: int) -> dict:
    """Decompose a 0-1 confidence value with transparency."""
    retrieval_strength = max(0.0, min(1.0, retrieval_top_score))
    model_self = max(0.0, min(1.0, model_self_rated))
    citation_density = max(0.0, min(1.0, num_citations / max(num_areas, 1)))
    overall = 0.4 * retrieval_strength + 0.3 * model_self + 0.3 * citation_density
    return {
        "retrieval_strength": round(retrieval_strength, 2),
        "model_self_rating": round(model_self, 2),
        "citation_density": round(citation_density, 2),
        "overall": round(overall, 2),
    }
