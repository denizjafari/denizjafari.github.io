#!/usr/bin/env python3
"""
Build a small text corpus for the Cloudflare Worker chatbot.

Reads the private docs in ./me/ (CV, summary, theses, journal article, patent),
extracts text, breaks it into ~400-token chunks, and writes
worker/corpus.json — a list of {id, source, text} records.

Embeddings are NOT computed here; they are computed on the Worker the first
time it boots, then cached in Workers KV. This way no API key is ever needed
locally and no embedding state lives in the repo.

Usage:
    python3 scripts/build_chat_corpus.py

Reads:
    me/summary.txt
    me/DenizJafari_CV_2025.pdf
    me/JSLHR-66-3151.pdf
    me/Profile.pdf
    me/Jafari_Deniz_202211_MSc_thesis.pdf
    me/patent.pdf
    (skips the 78 MB MHSc thesis by default — set INCLUDE_BIG=1 to include it)

Writes:
    worker/corpus.json
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ME = ROOT / "me"
OUT = ROOT / "worker" / "corpus.json"

# ~400 tokens ≈ 1600 chars (rough English heuristic). We chunk by paragraph and
# pack until we hit the cap, so chunk boundaries respect prose where possible.
TARGET_CHARS = 1600
OVERLAP_CHARS = 200

# Files to ingest. Order matters: earlier files are more "canonical".
DOCS = [
    ("summary", ME / "summary.txt"),
    ("cv", ME / "DenizJafari_CV_2025.pdf"),
    ("profile", ME / "Profile.pdf"),
    ("paper-jslhr-2023", ME / "JSLHR-66-3151.pdf"),
    ("patent", ME / "patent.pdf"),
    ("msc-thesis-2022", ME / "Jafari_Deniz_202211_MSc_thesis.pdf"),
]

if os.getenv("INCLUDE_BIG") == "1":
    DOCS.append(("mhsc-thesis-2019", ME / "Jafari_Deniz_ _201911_MHSc_thesis.pdf"))


def read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        sys.exit("Missing dependency: pip install pypdf")

    text_chunks: list[str] = []
    reader = PdfReader(str(path))
    for page in reader.pages:
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        text_chunks.append(t)
    return "\n".join(text_chunks)


def read_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def normalize(text: str) -> str:
    # Collapse hard-wraps and excessive whitespace; keep paragraph breaks.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Join lines that are clearly hard-wrapped within a sentence.
    text = re.sub(r"-\n", "", text)              # hyphen-broken words
    text = re.sub(r"(?<![.\n])\n(?!\n)", " ", text)  # mid-sentence newlines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip()


def chunk_text(source: str, text: str) -> list[dict]:
    text = normalize(text)
    if not text:
        return []

    # Split into paragraphs first; pack into chunks under TARGET_CHARS.
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    out: list[dict] = []
    buf = ""
    cid = 0
    for para in paragraphs:
        if not buf:
            buf = para
            continue
        if len(buf) + len(para) + 2 <= TARGET_CHARS:
            buf = f"{buf}\n\n{para}"
        else:
            out.append({"id": f"{source}-{cid:03d}", "source": source, "text": buf})
            cid += 1
            # carry overlap from end of previous chunk to keep continuity
            tail = buf[-OVERLAP_CHARS:]
            buf = (tail + "\n\n" + para).strip()
    if buf:
        out.append({"id": f"{source}-{cid:03d}", "source": source, "text": buf})

    # Hard-cap any single chunk that's still too big (e.g., one giant paragraph).
    capped: list[dict] = []
    for c in out:
        t = c["text"]
        if len(t) <= TARGET_CHARS * 1.5:
            capped.append(c)
            continue
        # split on sentence boundary
        parts = re.split(r"(?<=[.!?])\s+", t)
        sub_buf = ""
        sub_cid = 0
        for s in parts:
            if len(sub_buf) + len(s) + 1 <= TARGET_CHARS:
                sub_buf = (sub_buf + " " + s).strip()
            else:
                if sub_buf:
                    capped.append({
                        "id": f"{c['id']}-s{sub_cid:02d}",
                        "source": c["source"],
                        "text": sub_buf,
                    })
                    sub_cid += 1
                sub_buf = s
        if sub_buf:
            capped.append({
                "id": f"{c['id']}-s{sub_cid:02d}",
                "source": c["source"],
                "text": sub_buf,
            })
    return capped


def main() -> None:
    if not ME.exists():
        sys.exit(f"missing {ME} — nothing to index")

    OUT.parent.mkdir(parents=True, exist_ok=True)

    chunks: list[dict] = []
    for source, path in DOCS:
        if not path.exists():
            print(f"  skip (missing): {path}", file=sys.stderr)
            continue
        if path.suffix.lower() == ".pdf":
            raw = read_pdf(path)
        else:
            raw = read_txt(path)
        new = chunk_text(source, raw)
        chunks.extend(new)
        print(f"  {source}: {len(new)} chunks ({len(raw)} chars from {path.name})")

    # Light scrubbing: remove email addresses + phone numbers from chunks
    # so the corpus never accidentally exposes contact details to the LLM.
    EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
    PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
    for c in chunks:
        c["text"] = EMAIL_RE.sub("[email-redacted]", c["text"])
        c["text"] = PHONE_RE.sub("[phone-redacted]", c["text"])

    OUT.write_text(json.dumps({"chunks": chunks}, ensure_ascii=False, indent=2))
    total_chars = sum(len(c["text"]) for c in chunks)
    print(
        f"\nwrote {OUT.relative_to(ROOT)}  "
        f"({len(chunks)} chunks, {total_chars:,} chars, "
        f"{OUT.stat().st_size/1024:.0f} KB)"
    )


if __name__ == "__main__":
    main()
