# 🎤 RegIntel-AI — Demo Script

**Audience:** Senior leadership / management
**Duration:** 6–8 minutes of live demo (after the deck)
**Setting:** Live web app, projected or shared screen

---

## ⚡ 5 minutes before showtime

1. Open the app URL → let it fully load
2. Click **Impact Analysis** → select *Sample CMS-4201-F* → click **Run analysis** → wait for results (this caches the result so the live demo is instant)
3. Click **Version Comparison** → click **Compare** (this caches that result too)
4. Return to **Dashboard**
5. **Leave the tab open** — do NOT close it before the demo

If you skip this step, your audience will watch a 30-second cold-start spinner. Don't.

---

## 📜 The script

The script has stage directions in *italics* and your spoken words in regular text. Don't read it word-for-word — internalize it.

---

### Scene 1 — Open on the dashboard *(60 seconds)*

*Switch to the live app. The Dashboard page should be visible.*

> "What you're seeing is **RegIntel-AI** — running live in your browser, hosted on free infrastructure, deployed in two days.
>
> The system has already been pre-loaded with three sample regulations and three sample internal documents — a prior authorization policy, a claims SOP, and a system architecture doc. These are stand-ins for what your real internal artifacts would look like.
>
> *(point to the KPIs)*
>
> The dashboard gives leadership a one-glance view: regulations ingested, analyses run, total impacts identified, and a high-risk count. The risk distribution donut on the right shows how impacts split across priority levels."

*Optional: hover over a row in the regulations table.*

> "Each regulation tracks its effective date, category, chunk count, and overall impact score — once we run analysis."

---

### Scene 2 — Run an impact analysis *(2 minutes)*

*Click "Impact Analysis" in the left sidebar.*

> "Now the core capability. Let's pick the CMS Final Rule on continuity of care."

*Select **Sample CMS-4201-F — Continuity of Care (Final Rule)** from the dropdown.*

*Click **Run / refresh analysis**. Because you pre-warmed it, results appear in 1–2 seconds.*

> "In about ten seconds — first time around — the system has done the following:
>
> *(point to the regulation summary at the top)*
>
> One: read the regulation and produced a plain-English summary of what it requires.
>
> *(point to the impact gauge)*
>
> Two: scored the overall impact at *(read the number)* out of 100. This is a deterministic score combining severity, reach across artifacts, and urgency relative to the effective date.
>
> *(scroll to the impacted artifacts)*
>
> Three: identified specific impacted internal artifacts. Look at this — the Prior Authorization Continuity Policy, the Claims Adjudication SOP, and the MA Core Claims Engine. Each one comes with a priority badge, a confidence score, a recommended action, and a risk-if-not-implemented statement."

*Click into the first impact card if it's not already expanded.*

> "And critically — see these citation IDs at the bottom? Every recommendation traces back to specific paragraphs in specific source documents. No black-box AI. A compliance officer can audit every claim."

*Scroll down to the explainability section.*

> "Here at the bottom is the explainability panel. Each citation expands to show the actual retrieved snippet from the source document. This is what makes the system trustworthy — and makes it survive an audit."

---

### Scene 3 — What-if simulation *(60 seconds)*

*Scroll back up to the impact list. Click the **Simulate** button on a High-priority impact.*

> "One feature compliance officers love: what-if simulation. Pick any non-compliant artifact and ask: *what happens if we don't fix this?*"

*Wait 3–5 seconds for the result.*

> "The system projects a 12-month consequence: financial exposure with low and high estimates, regulatory exposure, member impact, operational friction, reputational impact, and the likelihood of enforcement. This converts compliance work from a cost center conversation into a quantified business case."

---

### Scene 4 — Version comparison *(2 minutes — the showstopper)*

*Click **Version Comparison** in the sidebar.*

> "Now the killer feature. Regulations evolve — proposed rules become final rules, often with material changes. We have two versions of CMS-4201 in the system: the proposed rule and the final rule."

*Confirm Old version = "v1.0-proposed", New version = "v2.0-final". Click **Compare**.*

*Result appears instantly because you pre-warmed it.*

> "Look at this. The system has produced a structured diff with three layers of analysis:
>
> *(point to the AI summary at the top)*
>
> One: an executive summary of what changed.
>
> *(point to the Added/Removed/Modified counters)*
>
> Two: a count of substantive changes — *added*, *removed*, or *modified* paragraphs.
>
> *(scroll to the change cards)*
>
> Three: a side-by-side diff. Each change card shows the old text in red, the new text in green, the regulatory section it came from, and — most importantly — an AI-generated description of what changed and what to do about it."

*Find the change card about the 30-day → 90-day window. Pause on it.*

> "Here's the change that matters most. Section 422.138(b) — the prior authorization honor period was extended from 30 days to 90 days. The system has flagged this as a Modified change with **Increased** compliance risk and **Higher** operational impact, and it's recommended a concrete action.
>
> Without this tool, that single sentence change is buried on page 47 of a 200-page document. Most compliance teams catch it weeks after the rule is finalized — sometimes after the effective date. With RegIntel-AI, you see it the moment the new version is ingested."

---

### Scene 5 — Close *(45 seconds)*

*Return to the Dashboard.*

> "Three things to remember:
>
> One — this is **running today**. It's not a slide deck of what we could build; it's a working system you can use right now.
>
> Two — it cost **zero dollars** to develop and runs at **zero to five dollars a month**. We chose open-source where it matters and free tiers where they're safe.
>
> Three — every recommendation is **cited and auditable**. The platform's design philosophy is trust by construction, not bolt-on compliance theater.
>
> What I'd like to ask leadership for is a two-week pilot. Pick one CMS rule and three real internal documents. We'll show measurable impact — quantified analyst hours saved, citations to validate, and a clear remediation plan you can take to your team."

---

## 🎯 Q&A preparation

The 8 questions you're most likely to get, with crisp answers ready.

### Q1: "Is this real?"
> "Yes. The platform is real and running. The documents you saw are clearly marked synthetic samples because we don't have permission to put real internal data into a free-tier system yet. The platform itself works identically with real data — and we'd switch to a privacy-protected paid tier the day we connect anything sensitive."

### Q2: "How much does this cost at scale?"
> "Today's free-tier setup handles roughly thirty to fifty users. To support a full payer team of 200+ users, we'd move to paid tiers — about fifty dollars a month for compute, plus token costs that scale with usage. A realistic production budget is two-to-five hundred dollars a month — still trivial compared to what consultants charge for the same work."

### Q3: "Will it hallucinate?"
> "Every recommendation is grounded in retrieved source paragraphs and shows its citations. We use a technique called Retrieval-Augmented Generation — RAG — where the AI must answer based on retrieved context, not from training memory. It can still occasionally misrank or misclassify, which is why every output also carries a transparent confidence score. Below 0.6 confidence, the UI flags 'review recommended.'"

### Q4: "Who owns the data?"
> "Today, on the free demo, the data lives on Streamlit Cloud's instance and the LLM is Google Gemini's free tier. Both are subject to the providers' free-tier terms. For real data, the configuration switches — same code — to a paid tier where Google contractually doesn't train on inputs. We'd recommend that switch on day one of any real pilot."

### Q5: "What about HIPAA?"
> "The current zero-cost setup is **not** HIPAA-compliant — that's why we use synthetic samples. For HIPAA, we'd deploy on a Business Associate Agreement-covered cloud environment — AWS, Azure, or GCP with BAAs in place — and use a HIPAA-eligible model API. The application code is unchanged; the deployment target changes. Roughly $200–$400/month for a HIPAA-compliant production setup."

### Q6: "Can it integrate with our existing systems?"
> "Yes — three ways. One: the system has a clean REST API for any internal tool to call. Two: it can pull regulations automatically from CMS RSS feeds and state portals. Three: outputs can flow into Salesforce, ServiceNow, or any work-tracking system as tickets. None of this is built today — it's the next-phase roadmap."

### Q7: "How long would full production deployment take?"
> "Pilot today, hardened pilot in 30 days — SSO, role-based access, persistent storage. Full production in 90 days — enterprise UI, managed infrastructure, audit logging. We have a phased roadmap that scales without rewrites."

### Q8: "What if Gemini changes pricing or shuts down their free tier?"
> "The application is provider-agnostic by design. The LLM is one configuration setting — `LLM_PROVIDER` — that can flip between Google Gemini, Anthropic Claude, or OpenAI without code changes. If any provider changes terms unfavorably, we switch in fifteen minutes."

---

## 🛡️ If something breaks live

**Stay calm. Here's the recovery script:**

If the page won't load:
> *"Looks like the demo environment is waking up — give it a moment."* *(reload the page; takes 30 seconds max)*

If an analysis fails or hangs:
> *"The free-tier rate limit kicked in. Let me show you the version comparison instead — that's the more impressive feature anyway."* *(click into Version Comparison, which has a cached result)*

If everything is broken:
> *"Rather than wrestle with the live system, let me walk you through the pre-recorded screenshots in the deck — they show the same flow."* *(switch to the slide deck)*

**Pro tip:** Take screenshots of every page **the night before the demo** and keep them in a backup folder. If the live demo breaks beyond recovery, you can flip to "look, here's what it does" mode without missing a beat.

---

## ⏱️ Pacing

| Scene | Time | Cumulative |
|---|---|---|
| 1. Dashboard | 1:00 | 1:00 |
| 2. Impact analysis | 2:00 | 3:00 |
| 3. Simulation | 1:00 | 4:00 |
| 4. Version comparison | 2:00 | 6:00 |
| 5. Close | 0:45 | 6:45 |
| **Demo total** | | **~7 min** |

Plus your slide deck (~12 min) and Q&A (~10 min) = **~30 min total session**.
