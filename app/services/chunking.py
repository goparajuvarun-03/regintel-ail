"""Section-aware recursive chunker tuned for regulatory text."""
from __future__ import annotations
import re
from dataclasses import dataclass


# Ordered separators — try the strongest semantic boundary first.
# Each entry is (regex, keep_with_next). If keep_with_next is True the separator
# is glued onto the start of the next chunk (so '§ 422.166' stays attached).
SEPARATOR_PATTERNS: list[tuple[str, bool]] = [
    (r"\n§\s+\d+(?:\.\d+)*[a-z]?", True),       # CFR sections
    (r"\nSection\s+\d+", True),                  # Section numbering
    (r"\n[A-Z][A-Z\s]{4,}\n", False),            # ALL CAPS HEADER lines
    (r"\n\(\d+\)\s", True),                      # (1), (2) ...
    (r"\n\([a-z]\)\s", True),                    # (a), (b) ...
    (r"\n\([ivx]+\)\s", True),                   # (i), (ii) ...
    (r"\n\n", False),                            # paragraph break
    (r"(?<=[.!?])\s+(?=[A-Z])", False),          # sentence boundary
    (r"\n", False),
    (r"\s", False),                              # last resort
]


@dataclass
class Chunk:
    text: str
    section: str | None
    char_start: int
    char_end: int


def _split_with_pattern(text: str, pattern: str, keep_with_next: bool) -> list[str]:
    """Split text by regex, optionally keeping the separator attached to the following piece."""
    if keep_with_next:
        # Use lookahead to retain the separator at the start of each piece
        parts = re.split(f"(?={pattern})", text)
    else:
        parts = re.split(pattern, text)
    return [p for p in parts if p]


def _recursive_split(text: str, max_chars: int, sep_idx: int = 0) -> list[str]:
    """Recursively split until each piece is <= max_chars."""
    if len(text) <= max_chars:
        return [text]
    if sep_idx >= len(SEPARATOR_PATTERNS):
        # Hard cut
        return [text[i:i + max_chars] for i in range(0, len(text), max_chars)]
    pattern, keep = SEPARATOR_PATTERNS[sep_idx]
    parts = _split_with_pattern(text, pattern, keep)
    if len(parts) == 1:
        return _recursive_split(text, max_chars, sep_idx + 1)
    out: list[str] = []
    for p in parts:
        if len(p) <= max_chars:
            out.append(p)
        else:
            out.extend(_recursive_split(p, max_chars, sep_idx + 1))
    return out


def _merge_small(parts: list[str], target: int, overlap: int) -> list[str]:
    """Greedy merge adjacent small parts up to target size, with character overlap."""
    merged: list[str] = []
    buf = ""
    for p in parts:
        if len(buf) + len(p) <= target or not buf:
            buf += p
        else:
            merged.append(buf.strip())
            tail = buf[-overlap:] if overlap > 0 and len(buf) > overlap else ""
            buf = tail + p
    if buf.strip():
        merged.append(buf.strip())
    return merged


_SECTION_RE = re.compile(r"(§\s*\d+(?:\.\d+)*[a-z]?(?:\([a-z0-9ivx]+\))*|Section\s+\d+(?:\.\d+)*)", re.IGNORECASE)


def _detect_section(text: str) -> str | None:
    m = _SECTION_RE.search(text[:200])
    return m.group(1).strip() if m else None


def chunk_text(text: str, chunk_size: int = 700, chunk_overlap: int = 80) -> list[Chunk]:
    """
    Section-aware chunker. We use *characters* as the size unit (roughly ~1 char ≈ 0.25 tokens).
    chunk_size=700 chars ≈ 175 tokens, which is comfortable.
    For larger chunks, raise chunk_size.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Approx 4 chars per token, so allow a bigger char budget
    char_budget = chunk_size * 4
    char_overlap = chunk_overlap * 4
    parts = _recursive_split(text, char_budget)
    merged = _merge_small(parts, char_budget, char_overlap)

    chunks: list[Chunk] = []
    cursor = 0
    for piece in merged:
        # Locate piece in original text from cursor onward (best effort)
        idx = text.find(piece[:60], cursor) if len(piece) >= 60 else text.find(piece, cursor)
        if idx == -1:
            idx = cursor
        end = idx + len(piece)
        chunks.append(Chunk(
            text=piece,
            section=_detect_section(piece),
            char_start=idx,
            char_end=end,
        ))
        cursor = end
    return chunks
