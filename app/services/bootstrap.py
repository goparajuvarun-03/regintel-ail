"""Auto-bootstrap: ingests seed documents on first run so the demo opens with content."""
from __future__ import annotations
import logging
from pathlib import Path

from app.config import settings
from app.services import database as db
from app.services.chunking import chunk_text
from app.services.ingestion import load_document, extract_metadata
from app.services.vectorstore import add_chunks

logger = logging.getLogger(__name__)


# Manifest: filename -> (kind, version, family_id, override_title, override_metadata)
SEED_MANIFEST = [
    {
        "filename": "01_cms_4201_proposed.txt",
        "kind": "regulation",
        "version": "v1.0-proposed",
        "family_id": "cms_sample_4201",
        "title": "Sample CMS-4201-P — Continuity of Care (Proposed Rule)",
        "metadata": {
            "issuing_body": "CMS",
            "regulation_id": "CMS-SAMPLE-4201-P",
            "effective_date": "2026-01-15",
            "regulatory_category": ["compliance", "claims"],
            "change_type": "new",
        },
    },
    {
        "filename": "02_cms_4201_final.txt",
        "kind": "regulation",
        "version": "v2.0-final",
        "family_id": "cms_sample_4201",
        "title": "Sample CMS-4201-F — Continuity of Care (Final Rule)",
        "metadata": {
            "issuing_body": "CMS",
            "regulation_id": "CMS-SAMPLE-4201-F",
            "effective_date": "2026-01-15",
            "regulatory_category": ["compliance", "claims"],
            "change_type": "modification",
        },
    },
    {
        "filename": "03_cms_mln_billing.txt",
        "kind": "regulation",
        "version": "v1.0",
        "family_id": "cms_sample_mln_12345",
        "title": "Sample CMS-MLN-12345 — ICD-10 Validation Edits",
        "metadata": {
            "issuing_body": "CMS",
            "regulation_id": "CMS-SAMPLE-MLN-12345",
            "effective_date": "2026-07-01",
            "regulatory_category": ["billing", "claims"],
            "change_type": "modification",
        },
    },
    {
        "filename": "04_internal_pa_policy.txt",
        "kind": "policy",
        "version": "v3.2",
        "family_id": "internal_pa_cont_001",
        "title": "Sample Internal Policy — Prior Authorization Continuity (PA-CONT-001)",
        "metadata": {},
    },
    {
        "filename": "05_internal_claims_sop.txt",
        "kind": "sop",
        "version": "v2.4",
        "family_id": "internal_sop_clm_014",
        "title": "Sample Internal SOP — Claims Adjudication New-Member Triage",
        "metadata": {},
    },
    {
        "filename": "06_internal_system_arch.txt",
        "kind": "system",
        "version": "v1.7",
        "family_id": "internal_sys_ma_101",
        "title": "Sample System Architecture — MA Core Claims Engine",
        "metadata": {},
    },
]


def is_bootstrapped() -> bool:
    """Check if seed documents have already been ingested."""
    docs = db.list_documents()
    seed_titles = {item["title"] for item in SEED_MANIFEST}
    existing_titles = {d["title"] for d in docs}
    # Consider bootstrapped if at least 4 of the 6 seeds are present (resilience to manual deletion)
    overlap = len(seed_titles & existing_titles)
    return overlap >= 4


def has_any_documents() -> bool:
    """True if the database has any documents at all (seeds or user uploads)."""
    try:
        return len(db.list_documents()) > 0
    except Exception:
        return False


def bootstrap_with_cloud_restore() -> dict:
    """
    Top-level startup logic. Tries in order:
      1. Pull cloud snapshot (if configured + newer than local)
      2. If after pull there are documents, we're done
      3. Otherwise load seed documents
    Returns a dict the UI can use to show what happened.
    """
    from app.services import persistence

    db.init_db()
    result = {
        "cloud_pulled": False,
        "seeds_loaded": 0,
        "had_local_data": False,
        "cloud_error": None,
    }

    # Try cloud restore first
    if persistence.is_cloud_configured():
        pull = persistence.pull_from_cloud()
        if pull.get("ok") and pull.get("restored"):
            result["cloud_pulled"] = True
            db.init_db()  # re-init in case the pulled DB needs schema verification
            logger.info("Bootstrap: restored from cloud snapshot.")
            return result
        if not pull.get("ok"):
            result["cloud_error"] = pull.get("error")
            logger.warning("Bootstrap: cloud pull failed: %s", pull.get("error"))

    # Cloud unavailable or no snapshot — check what's local
    if has_any_documents():
        result["had_local_data"] = True
        logger.info("Bootstrap: using existing local data.")
        return result

    # Nothing local, nothing in cloud — load the seeds
    seed_result = bootstrap_seed_data()
    result["seeds_loaded"] = seed_result.get("loaded", 0)
    logger.info("Bootstrap: loaded %d seed documents.", result["seeds_loaded"])
    return result


def bootstrap_seed_data(force: bool = False) -> dict:
    """Ingest the seed documents. Returns a summary dict."""
    if not force and is_bootstrapped():
        logger.info("Bootstrap: seed data already present; skipping.")
        return {"loaded": 0, "skipped": True}

    db.init_db()
    seed_dir: Path = settings.seed_dir
    if not seed_dir.exists():
        logger.warning("Seed directory not found at %s", seed_dir)
        return {"loaded": 0, "skipped": True, "error": "no_seed_dir"}

    loaded = 0
    errors: list[str] = []

    for item in SEED_MANIFEST:
        path = seed_dir / item["filename"]
        if not path.exists():
            errors.append(f"missing: {item['filename']}")
            continue
        try:
            text = load_document(path)
            if not text.strip():
                errors.append(f"empty: {item['filename']}")
                continue

            chunks = chunk_text(
                text,
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
            )
            chunk_records = [
                {
                    "idx": i,
                    "text": c.text,
                    "section": c.section,
                    "char_start": c.char_start,
                    "char_end": c.char_end,
                    "title": item["title"],
                    "version": item["version"],
                }
                for i, c in enumerate(chunks)
            ]

            doc_id = f"{item['family_id']}__{item['version']}__seed"

            add_chunks(item["kind"], doc_id, chunk_records)

            md = item.get("metadata", {}) or {}
            db.insert_document({
                "doc_id": doc_id,
                "title": item["title"],
                "kind": item["kind"],
                "version": item["version"],
                "family_id": item["family_id"],
                "effective_date": md.get("effective_date"),
                "regulatory_category": md.get("regulatory_category", []),
                "change_type": md.get("change_type"),
                "issuing_body": md.get("issuing_body"),
                "regulation_id": md.get("regulation_id"),
                "num_chunks": len(chunks),
                "file_path": str(path),
                "full_text": text,
            })
            loaded += 1
            logger.info("Bootstrap loaded: %s (%d chunks)", item["title"], len(chunks))
        except Exception as e:
            logger.error("Bootstrap failed for %s: %s", item["filename"], e)
            errors.append(f"{item['filename']}: {e}")

    return {"loaded": loaded, "skipped": False, "errors": errors}
