"""Document loaders and metadata extraction."""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Optional

from app.prompts import METADATA_EXTRACTION
from app.services.llm import call_llm_json

logger = logging.getLogger(__name__)


# ============================================================
# Loaders
# ============================================================
def load_document(path: Path) -> str:
    """Detect type by extension and return plain text."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _load_pdf(path)
    if suffix in {".html", ".htm"}:
        return _load_html(path)
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix in {".docx"}:
        return _load_docx(path)
    # Default: try as text
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.error("Could not read %s: %s", path, e)
        return ""


def _load_pdf(path: Path) -> str:
    import pdfplumber
    pages: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for p in pdf.pages:
            pages.append(p.extract_text() or "")
    return "\n\n".join(pages)


def _load_html(path: Path) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "lxml")
    for s in soup(["script", "style"]):
        s.decompose()
    return soup.get_text(separator="\n")


def _load_docx(path: Path) -> str:
    """Best-effort .docx reader without adding python-docx dependency."""
    import zipfile
    from xml.etree import ElementTree as ET
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    try:
        with zipfile.ZipFile(str(path)) as z:
            xml = z.read("word/document.xml").decode("utf-8", errors="replace")
        root = ET.fromstring(xml)
        paragraphs: list[str] = []
        for p in root.iter(f"{ns}p"):
            text = "".join(t.text or "" for t in p.iter(f"{ns}t"))
            if text.strip():
                paragraphs.append(text)
        return "\n\n".join(paragraphs)
    except Exception as e:
        logger.warning("docx parse failed for %s: %s", path, e)
        return ""


# ============================================================
# Metadata extraction
# ============================================================
def extract_metadata(text: str, max_chars: int = 6000) -> dict:
    """Use the LLM to extract metadata from the first part of the document."""
    excerpt = text[:max_chars]
    if not excerpt.strip():
        return {}
    try:
        return call_llm_json(
            system="You extract metadata. Respond with JSON only.",
            user=METADATA_EXTRACTION.format(excerpt=excerpt),
            max_tokens=400,
        )
    except Exception as e:
        logger.error("Metadata extraction failed: %s", e)
        return {}
