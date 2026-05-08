"""FastAPI application for RegIntel-AI."""
from __future__ import annotations
import logging
import re
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.api.schemas import (
    AnalysisResult,
    CompareRequest,
    DocumentComparison,
    DocumentListItem,
    IngestResponse,
    SimulationRequest,
    SimulationResult,
)
from app.config import settings
from app.prompts import SIMULATION
from app.services import database as db
from app.services.analyzer import analyze
from app.services.chunking import chunk_text
from app.services.comparator import compare_documents
from app.services.ingestion import extract_metadata, load_document
from app.services.llm import call_llm_json
from app.services.vectorstore import add_chunks, delete_doc

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="RegIntel-AI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    db.init_db()


# ============================================================
# Health
# ============================================================
@app.get("/health")
def health():
    return {"ok": True, "llm_provider": settings.llm_provider}


# ============================================================
# Ingest
# ============================================================
def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_") or "doc"


def _normalize_kind(k: str) -> str:
    k = (k or "").lower()
    if k in {"regulation", "policy", "sop", "system"}:
        return k
    if "policy" in k:
        return "policy"
    if "sop" in k or "workflow" in k:
        return "sop"
    if "system" in k:
        return "system"
    return "regulation"


@app.post("/ingest", response_model=IngestResponse)
async def ingest(
    file: UploadFile = File(...),
    kind: str = Form("regulation"),
    title: str | None = Form(None),
    version: str = Form("v1"),
    family_id: str | None = Form(None),
):
    kind = _normalize_kind(kind)
    safe_name = file.filename or "uploaded"
    save_path = settings.upload_dir / f"{uuid.uuid4().hex}_{safe_name}"
    with save_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    text = load_document(save_path)
    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from document.")

    # Metadata via LLM (skipped for non-regulations to keep cost low)
    metadata: dict = {}
    if kind == "regulation":
        metadata = extract_metadata(text) or {}

    # Determine title
    final_title = (
        title
        or metadata.get("title")
        or Path(safe_name).stem.replace("_", " ").title()
    )
    fam = family_id or _slugify(metadata.get("regulation_id") or final_title)

    doc_id = f"{fam}__{version}__{uuid.uuid4().hex[:6]}"

    # Chunk
    chunks = chunk_text(text, chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)
    chunk_records = [
        {
            "idx": i,
            "text": c.text,
            "section": c.section,
            "char_start": c.char_start,
            "char_end": c.char_end,
            "title": final_title,
            "version": version,
        }
        for i, c in enumerate(chunks)
    ]

    # Add to vector store
    add_chunks(kind, doc_id, chunk_records)

    # Persist metadata
    record = {
        "doc_id": doc_id,
        "title": final_title,
        "kind": kind,
        "version": version,
        "family_id": fam,
        "effective_date": metadata.get("effective_date"),
        "regulatory_category": metadata.get("regulatory_category") or [],
        "change_type": metadata.get("change_type"),
        "issuing_body": metadata.get("issuing_body"),
        "regulation_id": metadata.get("regulation_id"),
        "num_chunks": len(chunks),
        "file_path": str(save_path),
        "full_text": text,
    }
    db.insert_document(record)

    return IngestResponse(
        doc_id=doc_id,
        title=final_title,
        kind=kind,  # type: ignore
        version=version,
        num_chunks=len(chunks),
        metadata=metadata,
    )


# ============================================================
# List / get
# ============================================================
@app.get("/documents", response_model=list[DocumentListItem])
def list_documents(kind: str | None = None):
    rows = db.list_documents(kind=kind) if kind else db.list_documents()
    return [
        DocumentListItem(
            doc_id=r["doc_id"],
            title=r["title"],
            kind=r["kind"],  # type: ignore
            version=r["version"],
            effective_date=r.get("effective_date"),
            regulatory_category=r.get("regulatory_category") or [],
            change_type=r.get("change_type"),
            num_chunks=r.get("num_chunks", 0),
            created_at=r["created_at"],
        )
        for r in rows
    ]


@app.delete("/documents/{doc_id}")
def remove_document(doc_id: str):
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="not found")
    delete_doc(doc["kind"], doc_id)
    # Soft-delete metadata via direct sql
    with db.get_conn() as c:
        c.execute("DELETE FROM documents WHERE doc_id=?", (doc_id,))
        c.execute("DELETE FROM analyses WHERE doc_id=?", (doc_id,))
    return {"ok": True}


# ============================================================
# Analyze / compare
# ============================================================
@app.post("/analyze/{doc_id}", response_model=AnalysisResult)
def analyze_endpoint(doc_id: str):
    try:
        return analyze(doc_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/analyze/{doc_id}", response_model=AnalysisResult | None)
def get_analysis_endpoint(doc_id: str):
    row = db.get_analysis(doc_id)
    if not row:
        return None
    return AnalysisResult(**row["result"])


@app.post("/compare", response_model=DocumentComparison)
def compare_endpoint(req: CompareRequest):
    try:
        return compare_documents(req.old_doc_id, req.new_doc_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================
# Simulation
# ============================================================
@app.post("/simulate", response_model=SimulationResult)
def simulate_endpoint(req: SimulationRequest):
    doc = db.get_document(req.doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="document not found")
    analysis_row = db.get_analysis(req.doc_id) or {}
    summary = (analysis_row.get("result") or {}).get("regulation_summary", "")
    raw = call_llm_json(
        system="You are a healthcare risk officer. Return JSON only.",
        user=SIMULATION.format(
            reg_summary=summary or doc["title"],
            effective_date=doc.get("effective_date") or "TBD",
            artifact_name=req.artifact_name,
            artifact_type=req.artifact_type,
            gap_description=req.gap_description,
        ),
        max_tokens=600,
    )
    return SimulationResult(
        financial_exposure=raw.get("financial_exposure") or {},
        regulatory_exposure=raw.get("regulatory_exposure") or "Unknown",
        member_impact=raw.get("member_impact") or "Unknown",
        operational_friction=raw.get("operational_friction") or "Unknown",
        reputational_impact=raw.get("reputational_impact") or "Unknown",
        likelihood_of_enforcement=raw.get("likelihood_of_enforcement") or "Medium",
        mitigation_window_days=int(raw.get("mitigation_window_days") or 90),
    )


# ============================================================
# KPIs / timeline
# ============================================================
@app.get("/kpis")
def kpis_endpoint():
    return db.kpis()


@app.get("/timeline")
def timeline_endpoint(family_id: str | None = None):
    return db.get_timeline(family_id=family_id)


@app.get("/families")
def families_endpoint():
    """Return distinct family_ids that have at least 2 versions."""
    with db.get_conn() as c:
        rows = c.execute("""
            SELECT family_id, COUNT(*) as n, MAX(title) as title
            FROM documents WHERE kind='regulation'
            GROUP BY family_id
            HAVING n >= 1
            ORDER BY title
        """).fetchall()
    return [{"family_id": r["family_id"], "title": r["title"], "versions": r["n"]} for r in rows]
