# 🛡️ RegIntel-AI — Zero-Cost Demo Package

**Healthcare Regulatory Intelligence — RAG-powered platform for payers**
**Built to demo for management on a $0 budget.**

---

## 📦 What's in this package

| File | What it's for |
|---|---|
| **`DEPLOYMENT.md`** | Step-by-step deployment checklist. **Start here.** |
| **`DEMO_SCRIPT.md`** | What to say and click during the live demo |
| **`TROUBLESHOOTING.md`** | The 7 most likely problems and their fixes |
| `streamlit_app.py` | The application entry point |
| `app/` | Service modules — chunker, retriever, analyzer, comparator, etc. |
| `seed/` | 6 sample documents auto-loaded on first run |
| `.streamlit/` | Streamlit theme + secrets template |
| `requirements.txt` | Python package dependencies |

---

## 🎯 What you're deploying

A live, public web application that:

1. **Pre-loads 6 sample documents** on first run — 3 sample CMS regulations and 3 sample internal artifacts (policy, SOP, system doc)
2. Runs **impact analysis** on any regulation: identifies impacted internal artifacts with priority, citations, and recommended actions
3. Performs **version comparison** between any two regulations: textual + semantic + impact-delta diff
4. Includes **what-if simulation**: project consequences if a gap isn't fixed
5. **Cross-machine persistence** via GitHub-backed snapshots — uploads survive app restarts and are visible from any device
5. Offers full **explainability**: every claim is cited

All powered by Google Gemini 2.5 Flash-Lite (free tier) + open-source embeddings + Chroma vector DB, hosted on Streamlit Community Cloud (free).

**Total cost: $0/month.**

---

## 🚀 Getting started

1. **Read `DEPLOYMENT.md`** end-to-end before you start clicking. It takes about 10 minutes to read but saves hours.
2. **Set aside 90 minutes** for the deployment itself (most of it is waiting for installs).
3. **24 hours before your demo**, run a full dress rehearsal — deploy, demo, and recover from one intentional failure.
4. **5 minutes before showtime**, pre-warm the app (see DEMO_SCRIPT.md "5 minutes before showtime").

---

## ⚠️ Important: about the sample documents

The 6 seed documents are **clearly marked as samples** in their titles. They are realistic but **not real CMS publications**. This is by design — using disguised fake documents in a management demo would be a credibility risk.

If asked about them: *"These are synthetic test documents we used to demonstrate the platform. The system works identically with real CMS documents — we just don't have permission to put real internal data into a free-tier demo system."*

For real data, switch to the paid Gemini Tier-1 ($1–$5/month) and the data privacy concerns go away.

---

## 🆘 If you're stuck

`TROUBLESHOOTING.md` covers the 7 most likely issues with concrete fixes. If you have time before the demo, do a full dress rehearsal end-to-end — that's the single most reliable way to catch problems while there's time to fix them.

Good luck with the demo. You've got this.
