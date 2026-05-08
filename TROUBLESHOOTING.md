# 🆘 RegIntel-AI — Troubleshooting

The 7 most likely problems you'll hit, in rough order of likelihood, with concrete fixes.

---

## 1. Deploy fails: "ModuleNotFoundError" or "ImportError"

**Symptom:** Streamlit Cloud's deploy log shows a red error like *"ModuleNotFoundError: No module named 'sentence_transformers'"* or similar.

**Cause:** A package didn't install correctly, usually because something is wrong with `requirements.txt` (file missing, in the wrong folder, or has typos).

**Fix:**
1. In your GitHub repo, verify `requirements.txt` is at the **top level** (same folder as `streamlit_app.py`), not nested inside `app/` or anywhere else.
2. Open it and confirm it's not empty — should have ~13 lines starting with `streamlit==1.40.2`.
3. If anything looks wrong, click the file in GitHub → click the pencil icon (Edit) → fix it → commit. Streamlit Cloud auto-redeploys on every commit.

---

## 2. App loads but shows "running in mock mode" warning

**Symptom:** The sidebar shows a yellow ⚠️ "Gemini key missing — running in mock mode" message.

**Cause:** The `GEMINI_API_KEY` secret isn't set, or has a typo, or has stray whitespace.

**Fix:**
1. In Streamlit Cloud, find your app → **"Manage app"** (bottom right) → **"Settings"** → **"Secrets"**
2. Verify the contents look exactly like this — spelling and quotes matter:
   ```toml
   LLM_PROVIDER = "gemini"
   GEMINI_API_KEY = "AIzaSy....your_real_key_here"
   GEMINI_MODEL = "gemini-2.5-flash-lite"
   EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
   ```
3. Common mistakes:
   - Missing quotes around the key
   - Extra spaces inside the quotes (`"AIzaSy.."` not `" AIzaSy..  "`)
   - Pasted with a hidden newline at the end (delete and retype the last char)
4. **Save** and reboot the app: **"Manage app"** → **"Reboot"**

> 💡 **Mock mode is not the end of the world.** The app will still demo correctly with canned but plausible AI output. Your Q&A will be more honest if you say "we're running on the deterministic fallback today because of an API issue, but here's the real LLM-powered version." Don't fake it.

---

## 3. First page load takes forever (>2 minutes)

**Symptom:** The browser shows a Streamlit spinner that never goes away on the very first visit.

**Cause:** First boot does three slow things in sequence: (1) install all Python packages, (2) download the embedding model (~80 MB), (3) ingest the 6 seed documents. Total is normally 3–5 minutes.

**Fix:**
1. **Wait the full 5 minutes** before assuming something's wrong. Check the Streamlit Cloud log (Manage app → Logs) — if you see lines scrolling, it's working.
2. If the log shows an actual error, scroll to the *first* error (red text). Copy it. The most common is a package version conflict — fix in `requirements.txt`.

> 💡 After the first load, every subsequent visit is fast. Only the first visit on a freshly deployed app is this slow.

---

## 4. Cold start during demo: 30-second wait when you click

**Symptom:** You're presenting, you click into the app URL, and it shows "Zzz... Wake me up" or just spins for 30 seconds.

**Cause:** Streamlit Community Cloud puts apps to sleep after 12 hours of no traffic. The first visitor wakes it.

**Fix (prevention):** **Open the app yourself 5 minutes before the demo starts.** Keep the tab open. The app will stay warm.

**Fix (live):** If you didn't pre-warm and you're already in front of management:
> "Streamlit's free tier puts demo apps to sleep after a day of inactivity — a real production deployment wouldn't do this. Give it 30 seconds to wake."

Don't try to hide it. Acknowledge and move on.

---

## 5. "Quota exceeded" or "Rate limit" error during analysis

**Symptom:** You click "Run analysis" and get a red error mentioning rate limits, 429, or quota.

**Cause:** Gemini's free tier allows 1,000 requests per day and 15 requests per minute. If you've been demo-rehearsing aggressively, you may have burned through the per-minute limit (the daily limit is hard to hit in a single session).

**Fix (immediate):**
1. **Wait 60 seconds** then try again — the per-minute limit resets quickly.
2. If still failing: **use a cached result instead.** Click into a regulation that already has a "✓ Cached analysis available" indicator, and that one will load without making a new LLM call.

**Fix (long-term):** Switch to Gemini paid Tier-1. Same key, same code — just enable billing in Google AI Studio. Pilot-volume usage costs $1–$5/month and lifts the rate limits dramatically.

---

## 6. Comparison shows "no changes detected" or fewer changes than expected

**Symptom:** You compare the two CMS-4201 versions and the output looks empty or thin.

**Cause:** Either the two documents got assigned to different `family_id` values (so the system doesn't see them as related), or the diff threshold filtered out edits as cosmetic.

**Fix:**
1. Go to the **Upload** page → see the document list at the bottom
2. Look at the two CMS-4201 versions. They should both have `family_id` ending in `cms_sample_4201`.
3. If the bootstrap loaded correctly, this should "just work." If it doesn't:
   - In Streamlit Cloud: **"Manage app"** → **"Reboot"**
   - Wait for the app to come back. The seed documents will reload.

> 💡 **Pre-flight check:** Run the comparison once during pre-warm. If it works in pre-warm, it'll work in the demo.

---

## 7. Cloud sync stuck on "Sync pending" or "Local-only"

**Symptom:** Sidebar shows ⚪ Local-only or 🟡 Sync pending, never 🟢 Synced. Files don't appear on other machines.

**Cause:** GitHub credentials are missing, wrong, or the token doesn't have the right permissions.

**Fix:**
1. **Confirm both secrets are set.** In Streamlit Cloud → Manage app → Settings → Secrets, verify both `GITHUB_TOKEN` and `GITHUB_REPO` exist and are filled in. `GITHUB_REPO` must be in `owner/repo` format (no `https://` prefix, no `.git` suffix).
2. **Check the token's permissions.** Go to https://github.com/settings/tokens?type=beta → click your `regintel-ai-snapshots` token → confirm:
   - Repository access includes your `regintel-ai` repo
   - Repository permissions includes **Contents: Read and write**
3. **Token may have expired.** GitHub fine-grained tokens default to 90-day expiry. If expired, generate a new one and update the Streamlit secret.
4. **Click ⟳ Sync now in the sidebar.** Watch for an error message — it will tell you exactly what failed (404 = repo not found / no access; 401 = bad token; 403 = wrong permissions).

> 💡 Cloud sync is OPTIONAL. If it never works, the app still functions — it just won't persist uploads across restarts. For an emergency demo, you can run with sync disabled and manually re-upload files in advance.

## 8. Uploaded files visible to anyone — privacy concern

**Symptom:** Public GitHub repo, real internal documents got uploaded.

**Cause:** Public repos make all repo contents visible — including the `regintel-data-snapshots` branch where the app stores snapshots.

**Fix (immediate):**
1. **Delete the snapshot branch.** Go to your GitHub repo → branches → find `regintel-data-snapshots` → delete it.
2. **Make the repo private.** Go to repo Settings → bottom → "Change repository visibility" → Private.
3. **Restart the app** so it re-creates a fresh empty snapshot branch.

**Fix (long-term):** Either keep the repo private, or only upload synthetic / public regulatory documents. The Upload page shows a warning banner when the repo is configured for cloud sync — heed it.

## 9. App crashed and won't restart

**Cause:** Memory exhaustion (rare on this app), a runaway error loop, or Streamlit Cloud platform issues.

**Fix:**
1. In Streamlit Cloud: **"Manage app"** → **"Reboot app"**
2. Wait 2–3 minutes. The app reboots and re-bootstraps.
3. If reboot doesn't help: check **https://streamlit.statuspage.io** for platform-wide issues.
4. If the platform is fine but your app is broken, scroll the **Logs** for clues. Most likely culprit: a recent commit broke something. **Revert in GitHub** by clicking the offending commit → "Revert."

---

## 🚨 Last-resort recovery (the demo is in 5 minutes and nothing works)

If you can't get the live app running and the clock is ticking:

1. **Open the slide deck in PowerPoint and start there.** The deck stands on its own — it tells the story without the live demo.
2. **For the demo section,** say: *"I have screenshots of each page. Let me walk you through them"* — and either click through your pre-recorded screenshots or describe each page from memory.
3. **Don't try to fix the app live.** Trying to debug while presenting destroys credibility. Acknowledge the issue once, then move on.

This is why I recommend:
- ✅ Pre-warming 5 minutes before
- ✅ Taking screenshots of every page the night before
- ✅ Having the deck open in a second tab as a fallback

---

## 📞 If you need help between now and the demo

- **GitHub issues** (broken file, can't upload) → search Stack Overflow for *"github upload file"*
- **Streamlit Cloud issues** (deploy fails, app won't load) → forums.streamlit.io
- **Gemini API issues** (key not working) → ai.google.dev/support

If you have time before the demo, **do a full dress rehearsal end-to-end** — it's the single most reliable way to catch problems while there's still time to fix them.
