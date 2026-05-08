"""
RegIntel-AI - Zero-Cost Streamlit Cloud entry point.

This single file IS the application. It calls service functions directly
(no separate FastAPI), so it runs in one process - perfect for Streamlit
Community Cloud's free tier.
"""
from __future__ import annotations
import os
import sys
import time
from pathlib import Path

# Make `app` package importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="RegIntel-AI",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🛡️",
)

# Heavy imports after page_config so the spinner shows on cold start
with st.spinner("Loading RegIntel-AI... (first start may take ~30 seconds)"):
    from app.config import settings  # noqa: E402
    from app.services import database as db
    from app.services.analyzer import analyze
    from app.services.comparator import compare_documents
    from app.services.bootstrap import bootstrap_seed_data, is_bootstrapped
    from app.services.chunking import chunk_text
    from app.services.ingestion import load_document, extract_metadata
    from app.services.vectorstore import add_chunks, delete_doc
    from app.services.llm import call_llm_json
    from app.prompts import SIMULATION
    import shutil
    import re
    import uuid


# ============================================================
# One-time initialization
# ============================================================
@st.cache_resource(show_spinner=False)
def _init_app():
    """Initialize DB, restore from cloud if possible, else load seeds.
    Cached - runs once per session."""
    from app.services.bootstrap import bootstrap_with_cloud_restore
    db.init_db()
    return bootstrap_with_cloud_restore()


_init_result = _init_app()


# ============================================================
# Styling
# ============================================================
st.markdown("""
<style>
.main .block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
.kpi-card {
    background: linear-gradient(135deg, #0F2A47 0%, #028090 100%);
    padding: 18px; border-radius: 12px; color: white; height: 110px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
.kpi-card .label {font-size: 0.85rem; opacity: 0.9;}
.kpi-card .value {font-size: 2.1rem; font-weight: 700; margin-top: 4px;}
.priority-high {background:#fee2e2;color:#b91c1c;padding:2px 10px;border-radius:12px;font-size:0.78rem;font-weight:600;}
.priority-medium {background:#fef3c7;color:#92400e;padding:2px 10px;border-radius:12px;font-size:0.78rem;font-weight:600;}
.priority-low {background:#dcfce7;color:#166534;padding:2px 10px;border-radius:12px;font-size:0.78rem;font-weight:600;}
.diff-added {background:#dcfce7;border-left:3px solid #16a34a;padding:8px 10px;margin:4px 0;border-radius:4px;}
.diff-removed {background:#fee2e2;border-left:3px solid #dc2626;padding:8px 10px;margin:4px 0;border-radius:4px;text-decoration:line-through;}
.diff-modified {background:#fef9c3;border-left:3px solid #ca8a04;padding:8px 10px;margin:4px 0;border-radius:4px;}
.cite-snippet {background:#f1f5f9;padding:8px 10px;border-radius:6px;font-size:0.85rem;border-left:3px solid #64748b;}
.section-title {font-size:1.4rem;font-weight:700;color:#0f172a;margin:8px 0 4px 0;}
.demo-banner {background:linear-gradient(135deg, #02C39A 0%, #028090 100%); color:white; padding:10px 16px; border-radius:8px; margin-bottom:16px; font-size:0.9rem;}
</style>
""", unsafe_allow_html=True)


# ============================================================
# Sidebar
# ============================================================
st.sidebar.title("🛡️ RegIntel-AI")
st.sidebar.caption("Healthcare Regulatory Intelligence")

provider = (settings.llm_provider or "mock").lower()
has_key = bool(getattr(settings, f"{provider}_api_key", "")) if provider != "mock" else True
if provider == "gemini" and not settings.gemini_api_key:
    st.sidebar.warning("⚠️ Gemini key missing — running in **mock mode**.\n\nDemo will work but reasoning is canned.")
elif provider == "mock":
    st.sidebar.info("ℹ️ Running in **mock mode** (no API key configured).")
else:
    st.sidebar.success(f"✓ LLM provider: `{provider}`")

PAGE = st.sidebar.radio(
    "Navigate",
    ["📊 Dashboard", "🔍 Impact Analysis", "🔀 Version Comparison", "📤 Upload", "📜 Timeline"],
    label_visibility="collapsed",
)

st.sidebar.markdown("---")

# Bootstrap status (one-time message)
if _init_result and _init_result.get("cloud_pulled"):
    st.sidebar.caption("✓ Restored from cloud snapshot")
elif _init_result and _init_result.get("had_local_data"):
    st.sidebar.caption("✓ Loaded existing data")
elif _init_result and _init_result.get("seeds_loaded", 0) > 0:
    st.sidebar.caption(f"✓ Loaded {_init_result['seeds_loaded']} sample documents")
else:
    st.sidebar.caption("✓ Sample documents pre-loaded")

if _init_result and _init_result.get("cloud_error"):
    st.sidebar.warning(f"⚠️ Cloud sync issue: {_init_result['cloud_error'][:60]}")

# Cloud sync status block
from app.services import persistence as _persist

st.sidebar.markdown("---")
st.sidebar.markdown("**Cloud Sync**")
_sync_status = _persist.get_status()

_state_emoji = {
    "synced": "🟢",
    "synced_pending": "🟡",
    "local_only": "⚪",
}.get(_sync_status["state"], "⚪")

st.sidebar.markdown(
    f"{_state_emoji} **{_sync_status['label']}**  \n"
    f"<span style='font-size:0.78rem; color:#64748B;'>{_sync_status['detail']}</span>",
    unsafe_allow_html=True,
)

if _persist.is_cloud_configured():
    if st.sidebar.button("⟳ Sync now", use_container_width=True, key="sync_now_btn"):
        with st.spinner("Pushing snapshot to cloud..."):
            res = _persist.push_to_cloud(reason="manual")
        if res.get("ok"):
            kb = (res.get("size_bytes", 0) // 1024)
            st.sidebar.success(f"✓ Synced ({kb} KB)")
            st.cache_resource.clear()  # invalidate so the badge refreshes
            st.rerun()
        else:
            st.sidebar.error(f"Sync failed: {res.get('error', 'unknown')[:80]}")


# ============================================================
# Helpers
# ============================================================
def _auto_sync(reason: str) -> None:
    """Fire a sync to cloud after a mutating operation.
    Silent on success; logs an error caption only if user-visible recovery is useful."""
    if not _persist.is_cloud_configured():
        return
    try:
        res = _persist.push_to_cloud(reason=reason)
        if not res.get("ok"):
            # Don't crash the user's flow — just note it once
            st.toast(f"⚠️ Cloud sync deferred: {res.get('error', 'unknown')[:60]}", icon="⚠️")
    except Exception as e:
        st.toast(f"⚠️ Cloud sync error: {str(e)[:60]}", icon="⚠️")


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


def ingest_uploaded_file(uploaded_file, kind: str, version: str, family_id: str | None = None):
    """Save uploaded file, parse, chunk, embed, and persist metadata."""
    kind = _normalize_kind(kind)
    safe_name = uploaded_file.name or "uploaded"
    save_path = settings.upload_dir / f"{uuid.uuid4().hex}_{safe_name}"
    with save_path.open("wb") as f:
        f.write(uploaded_file.getvalue())

    text = load_document(save_path)
    if not text.strip():
        return None, "Could not extract text from document."

    metadata: dict = {}
    if kind == "regulation":
        try:
            metadata = extract_metadata(text) or {}
        except Exception:
            metadata = {}

    final_title = metadata.get("title") or Path(safe_name).stem.replace("_", " ").title()
    fam = family_id or _slugify(metadata.get("regulation_id") or final_title)
    doc_id = f"{fam}__{version}__{uuid.uuid4().hex[:6]}"

    chunks = chunk_text(text, chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)
    chunk_records = [{
        "idx": i, "text": c.text, "section": c.section,
        "char_start": c.char_start, "char_end": c.char_end,
        "title": final_title, "version": version,
    } for i, c in enumerate(chunks)]

    add_chunks(kind, doc_id, chunk_records)
    db.insert_document({
        "doc_id": doc_id, "title": final_title, "kind": kind, "version": version,
        "family_id": fam,
        "effective_date": metadata.get("effective_date"),
        "regulatory_category": metadata.get("regulatory_category") or [],
        "change_type": metadata.get("change_type"),
        "issuing_body": metadata.get("issuing_body"),
        "regulation_id": metadata.get("regulation_id"),
        "num_chunks": len(chunks),
        "file_path": str(save_path),
        "full_text": text,
    })
    return doc_id, None


# ============================================================
# Pages
# ============================================================
def page_dashboard():
    st.markdown('<div class="section-title">Dashboard</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="demo-banner">📋 <b>Demo mode</b> — sample documents pre-loaded for demonstration. '
        'Three regulations and three internal artifacts are ready for analysis.</div>',
        unsafe_allow_html=True,
    )

    kpis = db.kpis()
    docs = db.list_documents()
    regs = [d for d in docs if d["kind"] == "regulation"]

    c1, c2, c3, c4, c5 = st.columns(5)
    cards = [
        (c1, "Regulations ingested", kpis.get("n_regulations", 0)),
        (c2, "Analyses run", kpis.get("n_analyses", 0)),
        (c3, "Total impacts", kpis.get("n_impacts", 0)),
        (c4, "High-risk impacts", kpis.get("n_high_risk", 0)),
        (c5, "Avg confidence", f"{kpis.get('avg_confidence', 0):.2f}"),
    ]
    for col, label, value in cards:
        with col:
            st.markdown(
                f'<div class="kpi-card"><div class="label">{label}</div>'
                f'<div class="value">{value}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown("&nbsp;")
    col_l, col_r = st.columns([2, 1])

    with col_l:
        st.subheader("Pre-loaded regulations")
        if not regs:
            st.info("Sample documents are loading. Refresh in a moment.")
        else:
            rows = []
            for r in regs[:25]:
                a = db.get_analysis(r["doc_id"])
                score = (a or {}).get("impact_score") if a else None
                rows.append({
                    "Title": r["title"],
                    "Version": r["version"],
                    "Effective": r.get("effective_date") or "—",
                    "Category": ", ".join(r.get("regulatory_category") or []) or "—",
                    "Chunks": r["num_chunks"],
                    "Impact score": score if score is not None else "—",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, height=240)

        st.subheader("Pre-loaded internal artifacts")
        internals = [d for d in docs if d["kind"] != "regulation"]
        if internals:
            irows = pd.DataFrame([{
                "Title": d["title"],
                "Type": d["kind"].upper(),
                "Version": d["version"],
                "Chunks": d["num_chunks"],
            } for d in internals])
            st.dataframe(irows, use_container_width=True, height=180)

    with col_r:
        st.subheader("Risk distribution")
        prio_counts = {"High": 0, "Medium": 0, "Low": 0}
        for r in regs:
            a = db.get_analysis(r["doc_id"])
            if not a:
                continue
            for ia in (a.get("result") or {}).get("impacted_areas", []):
                p = ia.get("priority", "Low")
                if p in prio_counts:
                    prio_counts[p] += 1
        if sum(prio_counts.values()) == 0:
            st.info("Run an impact analysis to populate this chart.")
        else:
            df = pd.DataFrame([{"Priority": k, "Count": v} for k, v in prio_counts.items()])
            fig = px.pie(
                df, names="Priority", values="Count", hole=0.55,
                color="Priority",
                color_discrete_map={"High": "#dc2626", "Medium": "#ea8f00", "Low": "#16a34a"},
            )
            fig.update_layout(margin=dict(t=10, b=0, l=0, r=0), height=280, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)


def page_impact():
    st.markdown('<div class="section-title">Impact Analysis</div>', unsafe_allow_html=True)

    docs = db.list_documents(kind="regulation")
    if not docs:
        st.info("No regulations available. Refresh the page or upload one.")
        return

    target = st.selectbox(
        "Select a regulation",
        docs,
        format_func=lambda d: f"{d['title']} ({d['version']})",
    )

    cols = st.columns([1, 1, 2])
    with cols[0]:
        run = st.button("▶ Run / refresh analysis", type="primary")

    cached = db.get_analysis(target["doc_id"])
    with cols[1]:
        if cached:
            st.caption("✓ Cached analysis available")

    if run:
        with st.spinner("Retrieving context and reasoning over impacts..."):
            try:
                result = analyze(target["doc_id"])
                cached = {"result": result.model_dump(), "impact_score": result.impact_score_overall}
            except Exception as e:
                st.error(f"Analysis failed: {e}")
                return
        _auto_sync(reason=f"analysis:{target['doc_id'][:24]}")

    if not cached:
        st.info("Click **Run / refresh analysis** to generate an impact report.")
        return

    existing = cached["result"]

    # Header
    score = existing.get("impact_score_overall", cached.get("impact_score", 0))
    score_color = "#dc2626" if score >= 70 else ("#ea8f00" if score >= 40 else "#16a34a")
    h1, h2 = st.columns([3, 1])
    with h1:
        st.markdown(f"### {target['title']}")
        st.caption(
            f"Effective date: {existing.get('effective_date') or '—'}  ·  "
            f"Category: {', '.join(existing.get('regulatory_category') or []) or '—'}"
        )
        st.write(existing.get("regulation_summary") or "")
    with h2:
        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=score,
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": score_color},
                "steps": [
                    {"range": [0, 40], "color": "#dcfce7"},
                    {"range": [40, 70], "color": "#fef9c3"},
                    {"range": [70, 100], "color": "#fee2e2"},
                ],
            },
            title={"text": "Overall impact"},
        ))
        fig.update_layout(height=240, margin=dict(t=30, b=0, l=20, r=20))
        st.plotly_chart(fig, use_container_width=True)

    # Filters
    f1, f2, f3 = st.columns(3)
    with f1:
        type_filter = st.multiselect("Type", ["Policy", "Workflow", "System"],
                                     default=["Policy", "Workflow", "System"])
    with f2:
        prio_filter = st.multiselect("Priority", ["High", "Medium", "Low"],
                                     default=["High", "Medium", "Low"])
    with f3:
        min_conf = st.slider("Min confidence", 0.0, 1.0, 0.0, 0.05)

    impacts = [
        ia for ia in existing.get("impacted_areas", [])
        if ia.get("type") in type_filter
        and ia.get("priority") in prio_filter
        and float(ia.get("confidence_score", 0)) >= min_conf
    ]

    st.markdown("#### Impacted artifacts")
    if not impacts:
        st.warning("No impacts match these filters.")
    for i, ia in enumerate(impacts):
        prio = ia.get("priority", "Low")
        cls = {"High": "priority-high", "Medium": "priority-medium", "Low": "priority-low"}[prio]
        with st.container(border=True):
            top = st.columns([3, 1, 1])
            with top[0]:
                st.markdown(f"**{ia['name']}** &nbsp; <span class='{cls}'>{prio}</span>",
                            unsafe_allow_html=True)
                st.caption(f"Type: {ia['type']}")
            with top[1]:
                st.metric("Confidence", f"{float(ia.get('confidence_score', 0)):.2f}")
            with top[2]:
                if st.button("Simulate", key=f"sim_{i}"):
                    st.session_state[f"sim_open_{i}"] = True

            st.write(f"**Why impacted:** {ia.get('impact_reason', '')}")
            st.write(f"**Recommended action:** {ia.get('recommended_action', '')}")
            st.write(f"**Risk if not implemented:** {ia.get('risk_if_not_implemented', '')}")

            cites = ia.get("supporting_citations") or []
            if cites:
                st.caption(f"Citations: {', '.join(cites)}")

            if st.session_state.get(f"sim_open_{i}"):
                with st.expander("What-if simulation: not implemented", expanded=True):
                    try:
                        from app.api.schemas import SimulationRequest, SimulationResult
                        raw = call_llm_json(
                            system="You are a healthcare risk officer. Return JSON only.",
                            user=SIMULATION.format(
                                reg_summary=existing.get("regulation_summary", ""),
                                effective_date=existing.get("effective_date") or "TBD",
                                artifact_name=ia["name"],
                                artifact_type=ia["type"],
                                gap_description=ia.get("impact_reason", ""),
                            ),
                            max_tokens=600,
                        )
                        sim = {
                            "financial_exposure": raw.get("financial_exposure") or {},
                            "regulatory_exposure": raw.get("regulatory_exposure") or "Unknown",
                            "member_impact": raw.get("member_impact") or "Unknown",
                            "operational_friction": raw.get("operational_friction") or "Unknown",
                            "reputational_impact": raw.get("reputational_impact") or "Unknown",
                            "likelihood_of_enforcement": raw.get("likelihood_of_enforcement") or "Medium",
                            "mitigation_window_days": int(raw.get("mitigation_window_days") or 90),
                        }
                        sc = st.columns(3)
                        fe = sim.get("financial_exposure", {}) or {}
                        sc[0].metric("Financial low",
                                     f"${fe.get('low_estimate_usd', 0):,}")
                        sc[1].metric("Financial high",
                                     f"${fe.get('high_estimate_usd', 0):,}")
                        sc[2].metric("Enforcement likelihood",
                                     sim.get("likelihood_of_enforcement", "—"))
                        st.write(f"**Basis:** {fe.get('basis', '')}")
                        st.write(f"**Regulatory exposure:** {sim.get('regulatory_exposure', '')}")
                        st.write(f"**Member impact:** {sim.get('member_impact', '')}")
                        st.write(f"**Operational friction:** {sim.get('operational_friction', '')}")
                        st.write(f"**Reputational impact:** {sim.get('reputational_impact', '')}")
                        st.caption(f"Mitigation window: {sim.get('mitigation_window_days')} days")
                    except Exception as e:
                        st.error(f"Simulation failed: {e}")

    # Explainability
    st.markdown("---")
    st.markdown("#### Explainability — retrieved context")
    cites = existing.get("citations") or []
    if not cites:
        st.caption("No citations recorded for this analysis.")
    for c in cites:
        with st.expander(
            f"[{c['citation_id']}] {c['source_title']} · "
            f"{c.get('section') or 'n/a'} · relevance {c['relevance']:.2f}"
        ):
            st.markdown(f"<div class='cite-snippet'>{c['snippet']}</div>",
                        unsafe_allow_html=True)


def page_compare():
    st.markdown('<div class="section-title">Version Comparison</div>', unsafe_allow_html=True)

    docs = db.list_documents()
    regs = [d for d in docs if d["kind"] == "regulation"]
    if len(regs) < 2:
        st.info("Need at least two regulation documents to compare.")
        return

    families: dict[str, list[dict]] = {}
    for d in regs:
        families.setdefault(d["family_id"], []).append(d)

    family_options = [f for f, docs_in in families.items() if len(docs_in) >= 2]
    if family_options:
        family = st.selectbox(
            "Select a regulation family",
            family_options,
            format_func=lambda f: f"{families[f][0]['title']} ({len(families[f])} versions)",
        )
        options = families[family]
    else:
        st.warning("No families with 2+ versions.")
        options = regs
        family = None

    c1, c2 = st.columns(2)
    with c1:
        old = st.selectbox("Old version", options,
                           format_func=lambda d: f"{d['version']} — {d['title']}")
    with c2:
        new = st.selectbox("New version",
                           [o for o in options if o["doc_id"] != old["doc_id"]],
                           format_func=lambda d: f"{d['version']} — {d['title']}")

    if st.button("Compare", type="primary"):
        with st.spinner("Computing textual + semantic diff..."):
            try:
                res = compare_documents(old["doc_id"], new["doc_id"])
                st.session_state["last_compare"] = res.model_dump()
            except Exception as e:
                st.error(f"Comparison failed: {e}")
                return
        _auto_sync(reason=f"compare:{old['doc_id'][:16]}->{new['doc_id'][:16]}")

    res = st.session_state.get("last_compare")
    if not res:
        return

    st.success(res["summary"])
    st.caption(f"{res['old_version']}  ⇄  {res['new_version']}")

    a = sum(1 for c in res["changes"] if c["type"] == "Added")
    r = sum(1 for c in res["changes"] if c["type"] == "Removed")
    m = sum(1 for c in res["changes"] if c["type"] == "Modified")
    sc = st.columns(3)
    sc[0].metric("Added", a)
    sc[1].metric("Removed", r)
    sc[2].metric("Modified", m)

    st.markdown("#### Changes")
    for c in res["changes"]:
        with st.container(border=True):
            badge_class = {
                "Added": "diff-added",
                "Removed": "diff-removed",
                "Modified": "diff-modified",
            }[c["type"]]
            st.markdown(
                f"<div class='{badge_class}'><b>{c['type']}</b> · {c['section']}<br>"
                f"{c['description']}</div>",
                unsafe_allow_html=True,
            )
            cols = st.columns(2)
            with cols[0]:
                st.caption("OLD")
                if c.get("old_text"):
                    st.markdown(f"<div class='diff-removed'>{c['old_text']}</div>",
                                unsafe_allow_html=True)
                else:
                    st.caption("—")
            with cols[1]:
                st.caption("NEW")
                if c.get("new_text"):
                    st.markdown(f"<div class='diff-added'>{c['new_text']}</div>",
                                unsafe_allow_html=True)
                else:
                    st.caption("—")
            st.write(f"**Impact:** {c['impact']}")
            st.write(f"**Recommended action:** {c['recommended_action']}")
            st.caption(
                f"Compliance risk: {c['compliance_risk_delta']} · "
                f"Operational impact: {c['operational_impact_delta']}"
            )


def page_upload():
    st.markdown('<div class="section-title">Upload Documents</div>', unsafe_allow_html=True)
    st.caption("Upload regulatory mandates or internal documents. PDF / DOCX / TXT / HTML / MD supported.")

    # Privacy warning when cloud sync is enabled
    if _persist.is_cloud_configured():
        st.warning(
            "⚠️ **Files uploaded here are persisted to the configured GitHub repository.** "
            "If your repo is **public**, uploaded files will be visible to anyone. "
            "Do not upload real internal payer documents to a public repo. "
            "For real internal data, use a private GitHub repo or switch to a HIPAA-compliant deployment."
        )

    with st.form("upload_form"):
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            files = st.file_uploader(
                "Drag and drop files",
                type=["pdf", "docx", "txt", "md", "html", "htm"],
                accept_multiple_files=True,
            )
        with c2:
            kind = st.selectbox("Kind",
                                ["regulation", "policy", "sop", "system"],
                                format_func=lambda x: {
                                    "regulation": "Regulation",
                                    "policy": "Internal Policy",
                                    "sop": "SOP / Workflow",
                                    "system": "System Doc",
                                }[x])
        with c3:
            version = st.text_input("Version", value="v1")
        family_id = st.text_input("Family ID (optional)",
                                  help="Use the same Family ID for versions of the same document.")
        submitted = st.form_submit_button("Ingest", type="primary")

    if submitted and files:
        progress = st.progress(0.0)
        status = st.empty()
        any_success = False
        for i, f in enumerate(files, start=1):
            status.write(f"Ingesting **{f.name}** ...")
            doc_id, err = ingest_uploaded_file(f, kind, version, family_id or None)
            if err:
                st.error(f"❌ {f.name}: {err}")
            else:
                st.success(f"✓ Ingested **{f.name}** (doc_id: `{doc_id}`)")
                any_success = True
            progress.progress(i / len(files))
        status.write("Done.")
        if any_success:
            with st.spinner("Syncing to cloud..."):
                _auto_sync(reason=f"upload:{len(files)}_files")

    st.markdown("---")
    st.subheader("All documents in system")
    all_docs = db.list_documents()
    if not all_docs:
        st.info("Nothing indexed yet.")
        return
    rows = pd.DataFrame([{
        "doc_id": d["doc_id"], "Title": d["title"], "Kind": d["kind"],
        "Version": d["version"], "Effective": d.get("effective_date") or "—",
        "Chunks": d["num_chunks"], "Created": d["created_at"],
    } for d in all_docs])
    st.dataframe(rows, use_container_width=True, height=260)


def page_timeline():
    st.markdown('<div class="section-title">Regulatory Timeline</div>', unsafe_allow_html=True)
    st.caption("History of ingestion, analysis and comparison events.")

    events = db.get_timeline() or []
    if not events:
        st.info("No events yet.")
        return
    df = pd.DataFrame([{
        "When": e["created_at"],
        "Family": e["family_id"],
        "Version": e["version"],
        "Event": e["event_type"],
        "doc_id": e["doc_id"],
    } for e in events])
    st.dataframe(df, use_container_width=True, height=300)

    docs = db.list_documents(kind="regulation")
    by_date = [d for d in docs if d.get("effective_date")]
    if by_date:
        st.markdown("#### Effective dates")
        df2 = pd.DataFrame([{
            "Title": d["title"], "Effective": d["effective_date"],
            "Category": ", ".join(d.get("regulatory_category") or []) or "—",
        } for d in by_date])
        df2["Effective_dt"] = pd.to_datetime(df2["Effective"], errors="coerce")
        df2 = df2.dropna(subset=["Effective_dt"]).sort_values("Effective_dt")
        if len(df2):
            fig = px.scatter(df2, x="Effective_dt", y="Title", color="Category", height=380)
            fig.update_traces(marker=dict(size=14))
            fig.update_layout(margin=dict(t=20, b=20, l=10, r=10),
                              xaxis_title="Effective date", yaxis_title=None)
            st.plotly_chart(fig, use_container_width=True)


# ============================================================
# Router
# ============================================================
if PAGE.endswith("Dashboard"):
    page_dashboard()
elif PAGE.endswith("Impact Analysis"):
    page_impact()
elif PAGE.endswith("Version Comparison"):
    page_compare()
elif PAGE.endswith("Upload"):
    page_upload()
elif PAGE.endswith("Timeline"):
    page_timeline()
