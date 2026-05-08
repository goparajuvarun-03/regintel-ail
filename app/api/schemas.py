"""Pydantic schemas for API I/O."""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field


# ============================================================
# Documents
# ============================================================
DocKind = Literal["regulation", "policy", "sop", "system"]


class IngestResponse(BaseModel):
    doc_id: str
    title: str
    kind: DocKind
    version: str
    num_chunks: int
    metadata: dict


class DocumentListItem(BaseModel):
    doc_id: str
    title: str
    kind: DocKind
    version: str
    effective_date: Optional[str] = None
    regulatory_category: list[str] = []
    change_type: Optional[str] = None
    num_chunks: int
    created_at: str


# ============================================================
# Impact analysis
# ============================================================
class ImpactedArea(BaseModel):
    type: Literal["Policy", "Workflow", "System"]
    name: str
    impact_reason: str
    supporting_citations: list[str] = []
    recommended_action: str
    priority: Literal["High", "Medium", "Low"]
    risk_if_not_implemented: str
    confidence_score: float = Field(ge=0.0, le=1.0)


class Citation(BaseModel):
    citation_id: str  # e.g. CHUNK_1
    source_doc_id: str
    source_title: str
    section: Optional[str] = None
    snippet: str
    relevance: float


class AnalysisResult(BaseModel):
    doc_id: str
    regulation_summary: str
    effective_date: Optional[str] = None
    regulatory_category: list[str] = []
    change_type: Optional[str] = None
    impacted_areas: list[ImpactedArea]
    impact_score_overall: int = Field(ge=0, le=100)
    citations: list[Citation] = []
    insufficient_context: list[str] = []


# ============================================================
# Comparison
# ============================================================
class Change(BaseModel):
    type: Literal["Added", "Removed", "Modified"]
    section: str
    description: str
    impact: str
    recommended_action: str
    compliance_risk_delta: Literal["Increased", "Decreased", "Unchanged"]
    operational_impact_delta: Literal["Higher", "Lower", "Unchanged"]
    old_text: Optional[str] = None
    new_text: Optional[str] = None


class DocumentComparison(BaseModel):
    summary: str
    old_version: str
    new_version: str
    changes: list[Change]


class CompareRequest(BaseModel):
    old_doc_id: str
    new_doc_id: str


# ============================================================
# Simulation
# ============================================================
class SimulationRequest(BaseModel):
    doc_id: str
    artifact_name: str
    artifact_type: Literal["Policy", "Workflow", "System"]
    gap_description: str


class SimulationResult(BaseModel):
    financial_exposure: dict
    regulatory_exposure: str
    member_impact: str
    operational_friction: str
    reputational_impact: str
    likelihood_of_enforcement: Literal["Low", "Medium", "High"]
    mitigation_window_days: int
