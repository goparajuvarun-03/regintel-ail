"""SQLite metadata store. Tracks documents, versions, and analysis history."""
from __future__ import annotations
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from app.config import settings


_LOCK = threading.Lock()


@contextmanager
def get_conn():
    with _LOCK:
        conn = sqlite3.connect(str(settings.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def init_db():
    with get_conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            kind TEXT NOT NULL,                 -- regulation | policy | sop | system
            version TEXT NOT NULL,
            family_id TEXT NOT NULL,            -- groups versions of same doc
            effective_date TEXT,
            regulatory_category TEXT,           -- json list
            change_type TEXT,
            issuing_body TEXT,
            regulation_id TEXT,
            num_chunks INTEGER NOT NULL DEFAULT 0,
            file_path TEXT,
            full_text TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_docs_family ON documents(family_id);
        CREATE INDEX IF NOT EXISTS idx_docs_kind ON documents(kind);

        CREATE TABLE IF NOT EXISTS analyses (
            doc_id TEXT PRIMARY KEY,
            result_json TEXT NOT NULL,
            impact_score INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS comparisons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            old_doc_id TEXT NOT NULL,
            new_doc_id TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS timeline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family_id TEXT NOT NULL,
            doc_id TEXT NOT NULL,
            version TEXT NOT NULL,
            event_type TEXT NOT NULL,           -- ingested | analyzed | compared
            payload TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tl_family ON timeline(family_id);
        """)


def insert_document(d: dict) -> None:
    with get_conn() as c:
        c.execute("""
            INSERT OR REPLACE INTO documents
            (doc_id, title, kind, version, family_id, effective_date,
             regulatory_category, change_type, issuing_body, regulation_id,
             num_chunks, file_path, full_text, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            d["doc_id"], d["title"], d["kind"], d["version"], d["family_id"],
            d.get("effective_date"),
            json.dumps(d.get("regulatory_category", [])),
            d.get("change_type"),
            d.get("issuing_body"),
            d.get("regulation_id"),
            d.get("num_chunks", 0),
            d.get("file_path"),
            d.get("full_text"),
            datetime.utcnow().isoformat(timespec="seconds"),
        ))
    log_timeline(d["family_id"], d["doc_id"], d["version"], "ingested", {"title": d["title"]})


def list_documents(kind: Optional[str] = None) -> list[dict]:
    with get_conn() as c:
        if kind:
            rows = c.execute(
                "SELECT * FROM documents WHERE kind=? ORDER BY created_at DESC", (kind,)
            ).fetchall()
        else:
            rows = c.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
    return [_row_to_doc(r) for r in rows]


def get_document(doc_id: str) -> Optional[dict]:
    with get_conn() as c:
        row = c.execute("SELECT * FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
    return _row_to_doc(row) if row else None


def get_versions_in_family(family_id: str) -> list[dict]:
    with get_conn() as c:
        rows = c.execute(
            "SELECT * FROM documents WHERE family_id=? ORDER BY created_at ASC",
            (family_id,),
        ).fetchall()
    return [_row_to_doc(r) for r in rows]


def _row_to_doc(row: sqlite3.Row) -> dict:
    d = dict(row)
    try:
        d["regulatory_category"] = json.loads(d.get("regulatory_category") or "[]")
    except Exception:
        d["regulatory_category"] = []
    return d


def save_analysis(doc_id: str, result: dict, impact_score: int) -> None:
    with get_conn() as c:
        c.execute("""
            INSERT OR REPLACE INTO analyses (doc_id, result_json, impact_score, created_at)
            VALUES (?, ?, ?, ?)
        """, (doc_id, json.dumps(result), int(impact_score),
              datetime.utcnow().isoformat(timespec="seconds")))
    doc = get_document(doc_id)
    if doc:
        log_timeline(doc["family_id"], doc_id, doc["version"], "analyzed",
                     {"impact_score": int(impact_score)})


def get_analysis(doc_id: str) -> Optional[dict]:
    with get_conn() as c:
        row = c.execute("SELECT * FROM analyses WHERE doc_id=?", (doc_id,)).fetchone()
    if not row:
        return None
    out = dict(row)
    out["result"] = json.loads(out["result_json"])
    return out


def save_comparison(old_id: str, new_id: str, result: dict) -> int:
    with get_conn() as c:
        cur = c.execute("""
            INSERT INTO comparisons (old_doc_id, new_doc_id, result_json, created_at)
            VALUES (?, ?, ?, ?)
        """, (old_id, new_id, json.dumps(result),
              datetime.utcnow().isoformat(timespec="seconds")))
        cmp_id = cur.lastrowid
    new_doc = get_document(new_id)
    if new_doc:
        log_timeline(new_doc["family_id"], new_id, new_doc["version"], "compared",
                     {"vs": old_id})
    return cmp_id


def log_timeline(family_id: str, doc_id: str, version: str, event_type: str,
                 payload: dict | None = None) -> None:
    with get_conn() as c:
        c.execute("""
            INSERT INTO timeline (family_id, doc_id, version, event_type, payload, created_at)
            VALUES (?,?,?,?,?,?)
        """, (family_id, doc_id, version, event_type,
              json.dumps(payload or {}),
              datetime.utcnow().isoformat(timespec="seconds")))


def get_timeline(family_id: str | None = None) -> list[dict]:
    with get_conn() as c:
        if family_id:
            rows = c.execute(
                "SELECT * FROM timeline WHERE family_id=? ORDER BY created_at ASC",
                (family_id,),
            ).fetchall()
        else:
            rows = c.execute("SELECT * FROM timeline ORDER BY created_at DESC LIMIT 200").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["payload"] = json.loads(d.get("payload") or "{}")
        except Exception:
            d["payload"] = {}
        out.append(d)
    return out


def kpis() -> dict:
    with get_conn() as c:
        n_regs = c.execute("SELECT COUNT(*) FROM documents WHERE kind='regulation'").fetchone()[0]
        n_analyses = c.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        rows = c.execute("SELECT result_json, impact_score FROM analyses").fetchall()

    high_risk = 0
    avg_conf = 0.0
    n_imp = 0
    for r in rows:
        try:
            res = json.loads(r["result_json"])
            for ia in res.get("impacted_areas", []):
                n_imp += 1
                if ia.get("priority") == "High":
                    high_risk += 1
                avg_conf += float(ia.get("confidence_score", 0.0))
        except Exception:
            continue
    avg_conf = round(avg_conf / max(n_imp, 1), 2)
    return {
        "n_regulations": n_regs,
        "n_analyses": n_analyses,
        "n_impacts": n_imp,
        "n_high_risk": high_risk,
        "avg_confidence": avg_conf,
    }
