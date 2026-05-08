# 🛡️ RegIntel-AI — Deployment Checklist

**Goal:** Take the app from a folder of files to a live, public URL. Total time ≈ **45–90 minutes** (most of it waiting for installs).

> 💡 **Tip:** Print this checklist or keep it open in a separate window. Tick boxes as you go.

---

## ☐ Step 1: Create the three free accounts (15 min)

You need three free accounts. Open each in a separate browser tab.

### 1A. GitHub
1. Go to **https://github.com/signup**
2. Sign up with your work email (or any email you'll remember)
3. Verify your email when GitHub sends the link
4. ✅ When you can see github.com/yourusername, you're done

### 1B. Streamlit Community Cloud
1. Go to **https://streamlit.io/cloud**
2. Click **"Sign up"** (top right)
3. Choose **"Continue with GitHub"** — this links the two accounts (required)
4. Authorize Streamlit to access your GitHub
5. ✅ When you land on the Streamlit dashboard ("My apps"), you're done

### 1C. Google AI Studio (for the Gemini API key)
1. Go to **https://aistudio.google.com/apikey**
2. Sign in with any Google account (Gmail works fine)
3. Click **"Create API key"** (blue button)
4. Choose **"Create API key in new project"** if prompted
5. **Copy the key** — it starts with `AIza...`
6. **Paste it somewhere safe temporarily** (a notepad). You'll need it in Step 4.
7. ✅ When you have the key copied, you're done

> ⚠️ **Treat the API key like a password.** Don't paste it into emails, screenshots, or public docs.

---

## ☐ Step 2: Upload the code to GitHub (15 min)

You're going to copy the code package I provided into a new GitHub repository.

### 2A. Create the repository
1. Go to **https://github.com/new**
2. Repository name: **`regintel-ai`** (lowercase, exact spelling)
3. Description: *RegIntel-AI demo*
4. Set to **Public** (Streamlit Cloud free tier requires public repos)
5. **Check** ✅ "Add a README file" (just so the repo isn't empty)
6. Click **"Create repository"**

### 2B. Upload the files
You'll do this through the GitHub web UI — no Git needed.

1. On your new repo page, click **"Add file"** → **"Upload files"**
2. Open the unzipped `regintel-zero` folder on your computer
3. **Select ALL the contents** of that folder (not the folder itself):
   - `streamlit_app.py`
   - `requirements.txt`
   - `.gitignore`
   - The `app/` folder
   - The `seed/` folder
   - The `.streamlit/` folder
4. **Drag them all** into the GitHub upload area
5. Wait until every file shows uploaded (green checkmark)
6. Scroll down. In the "Commit changes" box: type *"Initial RegIntel-AI commit"*
7. Click **"Commit changes"** (green button)

> ⚠️ **Hidden folders:** If you don't see `.streamlit` or `.gitignore` in your file picker, your operating system is hiding dotfiles. On Mac press **Cmd+Shift+.** in Finder; on Windows enable **"Hidden items"** in File Explorer's View menu.

> ✅ **Verify:** Your repo should show `streamlit_app.py` at the top level. If it doesn't, something didn't upload right.

---

## ☐ Step 3: Deploy to Streamlit Cloud (10 min)

1. Go back to your Streamlit dashboard: **https://share.streamlit.io**
2. Click **"Create app"** (top right)
3. Choose **"Deploy a public app from GitHub"**
4. Fill in:
   - **Repository:** `yourusername/regintel-ai`
   - **Branch:** `main`
   - **Main file path:** `streamlit_app.py`
   - **App URL** (custom subdomain): e.g., `regintel-ai-yourname` (your choice)
5. **Don't click Deploy yet** — go to Step 4 and Step 5 first to set up the secrets.

---

## ☐ Step 4: Get a GitHub Personal Access Token (5 min) — REQUIRED for cloud sync

The app uses a PAT to save uploaded files back to GitHub so they survive across app restarts and across machines.

1. Go to **https://github.com/settings/tokens?type=beta** (Fine-grained tokens)
2. Click **"Generate new token"**
3. Set:
   - **Token name:** `regintel-ai-snapshots`
   - **Expiration:** 90 days (or longer if you prefer)
   - **Repository access:** Only select repositories → pick your `regintel-ai` repo
   - **Repository permissions:** Set **"Contents"** to **"Read and write"** (this is the only one needed)
4. Click **Generate token**
5. **Copy the token — it starts with `github_pat_`**. You won't see it again.
6. **Paste it somewhere safe temporarily** (a notepad). You'll use it in Step 5.

> ⚠️ Treat this token like a password. It can write to your repo.

---

## ☐ Step 5: Add your secrets to Streamlit Cloud (5 min)

1. In the Streamlit deployment screen, click **"Advanced settings"** (just above the Deploy button)
2. In the **Secrets** box, paste this exactly (replace both placeholders with your real values):

```toml
LLM_PROVIDER = "gemini"
GEMINI_API_KEY = "AIza...your-real-gemini-key..."
GEMINI_MODEL = "gemini-2.5-flash-lite"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Cloud persistence (cross-machine demo support)
GITHUB_TOKEN = "github_pat_...your-real-token..."
GITHUB_REPO = "yourusername/regintel-ai"
```

> ⚠️ `GITHUB_REPO` is in the format `owner/repo` (e.g., `sarah-reyes/regintel-ai`). It's the same name as your repository.

3. Click **"Save"** to confirm the secrets
4. Now click **"Deploy!"**

---

## ☐ Step 6: Wait for first deploy (~10 min)

Streamlit Cloud is now installing every Python package and downloading the embedding model. This is the longest single wait in the whole process.

You'll see a log scrolling on the right side. Watch for:

- ✅ `Cloning repository...` → done in seconds
- ✅ `Processing dependencies...` → 3–5 minutes (lots of packages)
- ✅ `Downloading sentence-transformers/all-MiniLM-L6-v2` → 1–2 minutes
- ✅ `You can now view your Streamlit app in your browser.` → success!

When ready, the app loads automatically.

> ⚠️ **First load takes another ~30 seconds** because the embedding model loads into memory and the seed documents get ingested. This only happens once.

---

## ☐ Step 7: Verify the demo works (10 min)

In the live app:

- ☐ **Dashboard** loads with KPIs showing **3 regulations** and **3 internal artifacts**
- ☐ Sidebar says ✓ Loaded 6 sample documents (or "✓ Sample documents pre-loaded" on later visits)
- ☐ Sidebar shows **🟢 Synced** under "Cloud Sync" (or 🟡 Sync pending if first run — click "⟳ Sync now")
- ☐ Click **Impact Analysis** → select *"Sample CMS-4201-F"* → click **Run analysis** → wait ~10s → impacts appear
- ☐ Click **Version Comparison** → keep the default family → click **Compare** → side-by-side diff appears
- ☐ Click **Upload** → upload one small test PDF → confirm "✓ Ingested" appears → confirm "Syncing to cloud..." appears
- ☐ **Cross-machine test**: Open the same URL on a second machine (phone, another laptop) → confirm the test PDF is visible there. **This is the key test.**

If all four checkmarks pass: **you're done.** The app is live.

---

## ☐ Step 8: Pre-warm before your demo (CRITICAL — 5 min before showtime)

Streamlit Community Cloud puts apps to sleep after 12 hours of no traffic. **A cold app takes ~30 seconds to wake up** — you don't want that happening in front of management.

**5 minutes before the demo:**

1. Open your app URL in your browser
2. Wait until the dashboard fully loads
3. Click into Impact Analysis once and run an analysis (this warms up the model and caches an analysis)
4. Click Version Comparison and run one comparison (this caches the diff result)
5. **Leave the tab open.** The app will stay warm.

---

## 🆘 If something goes wrong

See `TROUBLESHOOTING.md` for the 7 most common issues and fixes.

If you're stuck and the demo is approaching, the quickest recovery is usually:

1. In Streamlit Cloud, click **"Manage app"** → **"Reboot app"**
2. Wait 2 minutes
3. Re-test
