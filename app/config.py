"""Central configuration. Reads from Streamlit secrets first, then env, then defaults."""
from __future__ import annotations
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _from_streamlit_secrets() -> dict:
    """Try to load Streamlit secrets if running inside a Streamlit context."""
    try:
        import streamlit as st
        # st.secrets behaves like a dict; convert keys to lowercase env-style
        return {k.lower(): v for k, v in dict(st.secrets).items()}
    except Exception:
        return {}


# Inject Streamlit secrets into env so pydantic picks them up
for k, v in _from_streamlit_secrets().items():
    if k.upper() not in os.environ:
        os.environ[k.upper()] = str(v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Paths ----
    data_dir: Path = PROJECT_ROOT / "data"
    chroma_dir: Path = PROJECT_ROOT / "data" / "chroma"
    upload_dir: Path = PROJECT_ROOT / "data" / "uploads"
    db_path: Path = PROJECT_ROOT / "data" / "regintel.db"
    seed_dir: Path = PROJECT_ROOT / "seed"

    # ---- LLM ----
    llm_provider: str = "gemini"  # gemini | mock | anthropic | openai
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # ---- Embeddings ----
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # ---- Cloud persistence (GitHub-backed snapshots) ----
    github_token: str = ""
    github_repo: str = ""  # format: "owner/repo"

    # ---- Retrieval ----
    chunk_size: int = 700
    chunk_overlap: int = 80
    top_k_dense: int = 10
    top_k_sparse: int = 10
    top_k_final: int = 5

    def ensure_dirs(self) -> None:
        for p in (self.data_dir, self.chroma_dir, self.upload_dir):
            p.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
