"""
Cloud persistence via GitHub API.

Bundles the local /data folder into a snapshot tarball, commits it to a
dedicated branch on the configured GitHub repo, and restores it on app
startup. Designed to fail gracefully — if GitHub is misconfigured or
unreachable, the app keeps working with local-only persistence and shows
a sidebar warning instead of crashing.

Approach 2B from the deployment plan: GitHub itself is the persistence
layer. Pros: zero new accounts/keys beyond what's already configured for
the repo. Cons: data is visible in the repo (mitigated by warning banner
+ guidance to keep repo private if real internal data ever flows).
"""
from __future__ import annotations

import base64
import io
import json
import logging
import tarfile
import time
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# Configuration
# ============================================================

# We use a dedicated branch (not main) to hold snapshots so the code branch
# stays clean. Branch is created on first push if it doesn't exist.
SNAPSHOT_BRANCH = "regintel-data-snapshots"
SNAPSHOT_PATH = "snapshot.tar.gz"
META_PATH = "snapshot.meta.json"

# Cap snapshot size to avoid hitting GitHub's per-file limit (100 MB hard cap;
# 50 MB soft warning). Demo workloads should be well under this.
MAX_SNAPSHOT_BYTES = 40 * 1024 * 1024  # 40 MB safety ceiling


# ============================================================
# Public API
# ============================================================

def is_cloud_configured() -> bool:
    """True iff all GitHub credentials are set."""
    return bool(
        getattr(settings, "github_token", "")
        and getattr(settings, "github_repo", "")
    )


def get_status() -> dict:
    """Returns a small dict describing current sync state.
    Used by the sidebar indicator."""
    if not is_cloud_configured():
        return {
            "state": "local_only",
            "label": "Local-only",
            "detail": "Cloud sync not configured. Data won't survive app restarts.",
            "last_sync_at": None,
        }
    meta = _read_local_meta()
    if meta is None:
        return {
            "state": "synced_pending",
            "label": "Sync pending",
            "detail": "No cloud snapshot yet — push to create one.",
            "last_sync_at": None,
        }
    return {
        "state": "synced",
        "label": "Synced",
        "detail": f"Last sync: {meta.get('pushed_at_human', 'unknown')}",
        "last_sync_at": meta.get("pushed_at"),
    }


def push_to_cloud(reason: str = "manual") -> dict:
    """
    Bundle local /data folder, push as snapshot to the data branch.
    Returns a result dict; never raises.
    """
    if not is_cloud_configured():
        return {"ok": False, "error": "not_configured"}

    try:
        tarball, size_bytes = _create_snapshot_tarball()
    except Exception as e:
        logger.exception("Failed to build snapshot tarball")
        return {"ok": False, "error": f"tarball: {e}"}

    if size_bytes > MAX_SNAPSHOT_BYTES:
        return {
            "ok": False,
            "error": f"snapshot too large ({size_bytes // 1024 // 1024} MB > "
                     f"{MAX_SNAPSHOT_BYTES // 1024 // 1024} MB)",
        }

    try:
        _ensure_branch_exists()
        _put_file(SNAPSHOT_PATH, tarball, message=f"snapshot: {reason}")
        meta = {
            "pushed_at": time.time(),
            "pushed_at_human": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "reason": reason,
            "size_bytes": size_bytes,
        }
        _put_file(
            META_PATH,
            json.dumps(meta, indent=2).encode("utf-8"),
            message=f"meta: {reason}",
        )
        _write_local_meta(meta)
        return {"ok": True, "size_bytes": size_bytes, "meta": meta}
    except Exception as e:
        logger.exception("GitHub push failed")
        return {"ok": False, "error": str(e)}


def pull_from_cloud() -> dict:
    """
    Pull latest snapshot from cloud and restore into local /data.
    Returns a result dict; never raises. Safe to call on every startup.
    """
    if not is_cloud_configured():
        return {"ok": False, "error": "not_configured", "restored": False}

    try:
        # Look for snapshot file on the snapshot branch
        meta_bytes = _get_file(META_PATH)
        if meta_bytes is None:
            return {"ok": True, "restored": False, "reason": "no_snapshot_yet"}

        snapshot_bytes = _get_file(SNAPSHOT_PATH)
        if snapshot_bytes is None:
            return {"ok": True, "restored": False, "reason": "snapshot_missing"}

        meta = json.loads(meta_bytes.decode("utf-8"))

        # Skip restore if local data is already fresher than cloud
        local_meta = _read_local_meta()
        if local_meta and local_meta.get("pushed_at", 0) >= meta.get("pushed_at", 0):
            return {"ok": True, "restored": False, "reason": "local_is_current"}

        _restore_snapshot_tarball(snapshot_bytes)
        _write_local_meta(meta)
        logger.info("Cloud snapshot restored: %s bytes", meta.get("size_bytes"))
        return {"ok": True, "restored": True, "meta": meta}

    except Exception as e:
        logger.exception("Cloud pull failed")
        return {"ok": False, "error": str(e), "restored": False}


# ============================================================
# Tarball helpers
# ============================================================

def _create_snapshot_tarball() -> tuple[bytes, int]:
    """Pack settings.data_dir into an in-memory gzip tarball."""
    buf = io.BytesIO()
    data_dir = Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for child in data_dir.rglob("*"):
            if child.is_file():
                arcname = child.relative_to(data_dir)
                # Skip macOS metadata, lockfiles, and our own meta marker
                if str(arcname).startswith(("._", ".DS_Store", "_persist_meta.json")):
                    continue
                tar.add(child, arcname=str(arcname))

    blob = buf.getvalue()
    return blob, len(blob)


def _restore_snapshot_tarball(blob: bytes) -> None:
    """Extract a gzip tarball into settings.data_dir, replacing existing data."""
    data_dir = Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO(blob)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        # Safe extract — refuse anything escaping data_dir
        for member in tar.getmembers():
            target = (data_dir / member.name).resolve()
            if not str(target).startswith(str(data_dir.resolve())):
                logger.warning("Skipping unsafe path in snapshot: %s", member.name)
                continue
        tar.extractall(path=str(data_dir))


# ============================================================
# Local meta marker (so we can detect freshness without a round-trip)
# ============================================================

_META_FILE = "_persist_meta.json"


def _meta_path() -> Path:
    return Path(settings.data_dir) / _META_FILE


def _read_local_meta() -> Optional[dict]:
    p = _meta_path()
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception:
        return None


def _write_local_meta(meta: dict) -> None:
    p = _meta_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(meta, indent=2), encoding="utf-8")


# ============================================================
# GitHub HTTP plumbing — uses requests if available, else urllib
# ============================================================

def _gh_headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "regintel-ai-persistence",
    }


def _gh_url(path: str) -> str:
    repo = settings.github_repo.strip("/")
    return f"https://api.github.com/repos/{repo}/{path.lstrip('/')}"


def _http_request(method: str, url: str, headers: dict,
                  json_body: Optional[dict] = None) -> tuple[int, bytes]:
    """Tiny HTTP wrapper. Prefers `requests` (already installed transitively
    via streamlit/google-generativeai); falls back to urllib if not."""
    body_bytes = None
    if json_body is not None:
        body_bytes = json.dumps(json_body).encode("utf-8")
        headers = {**headers, "Content-Type": "application/json"}

    try:
        import requests
        resp = requests.request(method, url, headers=headers, data=body_bytes, timeout=30)
        return resp.status_code, resp.content
    except ImportError:
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError
        req = Request(url, data=body_bytes, headers=headers, method=method)
        try:
            with urlopen(req, timeout=30) as r:
                return r.status, r.read()
        except HTTPError as e:
            return e.code, e.read()


def _ensure_branch_exists() -> None:
    """If SNAPSHOT_BRANCH doesn't exist, create it from main."""
    code, _ = _http_request(
        "GET", _gh_url(f"git/refs/heads/{SNAPSHOT_BRANCH}"), _gh_headers()
    )
    if code == 200:
        return  # branch exists

    # Get sha of main (or master) to branch from
    for base in ("main", "master"):
        code, body = _http_request(
            "GET", _gh_url(f"git/refs/heads/{base}"), _gh_headers()
        )
        if code == 200:
            sha = json.loads(body.decode("utf-8"))["object"]["sha"]
            break
    else:
        raise RuntimeError("Neither 'main' nor 'master' branch found in repo.")

    code, body = _http_request(
        "POST", _gh_url("git/refs"), _gh_headers(),
        json_body={"ref": f"refs/heads/{SNAPSHOT_BRANCH}", "sha": sha},
    )
    if code not in (200, 201):
        raise RuntimeError(f"Failed to create branch: HTTP {code}: {body[:200]!r}")


def _get_file(path: str) -> Optional[bytes]:
    """Fetch a file from the snapshot branch; None if not found."""
    code, body = _http_request(
        "GET",
        _gh_url(f"contents/{path}?ref={SNAPSHOT_BRANCH}"),
        _gh_headers(),
    )
    if code == 404:
        return None
    if code != 200:
        raise RuntimeError(f"GitHub get_file HTTP {code}: {body[:200]!r}")
    payload = json.loads(body.decode("utf-8"))
    encoding = payload.get("encoding", "base64")
    content = payload.get("content", "")
    if encoding == "base64":
        return base64.b64decode(content)
    return content.encode("utf-8")


def _put_file(path: str, content: bytes, message: str) -> None:
    """Create or update a file on the snapshot branch."""
    # Need current sha if file exists (for update)
    existing_sha: Optional[str] = None
    code, body = _http_request(
        "GET",
        _gh_url(f"contents/{path}?ref={SNAPSHOT_BRANCH}"),
        _gh_headers(),
    )
    if code == 200:
        existing_sha = json.loads(body.decode("utf-8")).get("sha")

    payload = {
        "message": message,
        "content": base64.b64encode(content).decode("ascii"),
        "branch": SNAPSHOT_BRANCH,
    }
    if existing_sha:
        payload["sha"] = existing_sha

    code, body = _http_request(
        "PUT", _gh_url(f"contents/{path}"), _gh_headers(), json_body=payload
    )
    if code not in (200, 201):
        raise RuntimeError(f"GitHub put_file HTTP {code}: {body[:200]!r}")
