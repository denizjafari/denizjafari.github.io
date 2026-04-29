#!/usr/bin/env python3
"""
Build a small text corpus for the Cloudflare Worker chatbot.

Reads cleaned plaintext from `me/processed/` (produced by
`scripts/clean_me_for_chunking.py`), breaks it into ~400-token chunks, and
writes `worker/corpus.json` — a list of {id, source, text} records.

Why cleaned text and not raw PDFs:
  * raw `pypdf` extraction leaks page numbers, ToC dot-leaders, repeating
    headers, hyphenated line breaks, and giant data tables into chunks
  * scanned PDFs (the patent) come back empty
  * `.docx` files (research statement, etc.) need their own reader
The cleaning step (`scripts/clean_me_for_chunking.py`) handles all of the
above. This script just reads its output.

Embeddings are NOT computed here; they are computed on the Worker the first
time it boots, then cached in Workers KV. This way no API key is ever needed
locally and no embedding state lives in the repo.

Usage:
    # 1. (re)generate cleaned text   →  me/processed/*.txt
    python3 scripts/clean_me_for_chunking.py
    # 2. chunk it into the corpus     →  worker/corpus.json
    python3 scripts/build_chat_corpus.py

Set INCLUDE_BIG=1 to include the 78 MB MHSc thesis (slow + redundant with
the MSc thesis; off by default).

Excluded from the corpus by name/subdir, regardless of what's in processed/:
  * `applications/` — job-specific resumes/cover letters; the chatbot
    shouldn't quote employer-tailored phrasing back to visitors
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ME = ROOT / "me"
PROCESSED = ME / "processed"
# The Worker mounts ./public as a static asset binding (see worker/wrangler.toml
# `[assets] directory = "./public"`), so corpus.json must land there to be
# fetchable at runtime. Writing to worker/corpus.json silently does nothing.
OUT = ROOT / "worker" / "public" / "corpus.json"

# ~400 tokens ≈ 1600 chars (rough English heuristic). We chunk by paragraph and
# pack until we hit the cap, so chunk boundaries respect prose where possible.
TARGET_CHARS = 1600
OVERLAP_CHARS = 200

# Subdirectories under me/processed/ whose contents must NOT enter the corpus.
EXCLUDED_SUBDIRS = {"applications"}

# Map filename stems → stable source labels surfaced under chat answers as
# `// sources: <label>`. Anything not listed gets a slugified fallback.
LABEL_OVERRIDES = {
    "summary": "summary",
    "Profile": "profile",
    "DenizJafari_CV_2025": "cv-2025",
    "DenizJafari_CV_2026": "cv-2026",
    "Deniz Jafari Research Statement": "research-statement",
    "JSLHR-66-3151": "paper-jslhr-2023",
    "patent": "patent",
    "Jafari_Deniz_202211_MSc_thesis": "msc-thesis-2022",
    "Jafari_Deniz_ _201911_MHSc_thesis": "mhsc-thesis-2019",
    "RT_imu_article_v2": "paper-imu-rt",
    "ProgressReport-March1": "progress-report-2024",
    "DenizJafari_Resume_2024": "resume-2024",
    "DenizJafari_Resume_2022Medvention": "resume-2022",
    "DenizJafari_CoverLetter_AppliedResearchIntern": "cover-letter-applied-research",
}

# Stems excluded from the corpus even if present in processed/ (heavy file by
# default, redundant with msc-thesis-2022 unless you specifically want it).
SKIP_STEMS = set() if os.getenv("INCLUDE_BIG") == "1" else {"Jafari_Deniz_ _201911_MHSc_thesis"}


def slugify(stem: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()
    return s or "doc"


def discover_processed() -> list[tuple[str, Path]]:
    """Walk me/processed/ for *.txt, skipping excluded subdirs and the manifest."""
    if not PROCESSED.exists():
        sys.exit(
            f"missing {PROCESSED} — run `python3 scripts/clean_me_for_chunking.py` first"
        )
    docs: list[tuple[str, Path]] = []
    for p in sorted(PROCESSED.rglob("*.txt")):
        rel = p.relative_to(PROCESSED)
        # _manifest.tsv etc — not chat content
        if p.name.startswith("_"):
            continue
        # explicitly excluded subdirs (applications/)
        if rel.parts and rel.parts[0] in EXCLUDED_SUBDIRS:
            continue
        if p.stem in SKIP_STEMS:
            continue
        label = LABEL_OVERRIDES.get(p.stem, slugify(p.stem))
        docs.append((label, p))
    return docs


def read_processed_txt(path: Path) -> str:
    """
    Read a cleaned .txt file and strip the YAML-ish header inserted by
    clean_me_for_chunking.py (lines starting with `# ` up to and including
    the `---` separator). Everything below that is the chunkable body.
    """
    raw = path.read_text(encoding="utf-8", errors="ignore")
    lines = raw.splitlines()
    body_start = 0
    for i, ln in enumerate(lines[:20]):
        if ln.strip() == "---":
            body_start = i + 1
            break
    return "\n".join(lines[body_start:]).lstrip()


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

    docs = discover_processed()
    if not docs:
        sys.exit(
            f"no usable .txt files under {PROCESSED} — run "
            f"`python3 scripts/clean_me_for_chunking.py` first"
        )

    chunks: list[dict] = []
    for source, path in docs:
        raw = read_processed_txt(path)
        new = chunk_text(source, raw)
        chunks.extend(new)
        print(f"  {source}: {len(new)} chunks ({len(raw)} chars from {path.relative_to(ME)})")

    # Scrub contact-info shapes from chunks before they ship to the corpus.
    # Why each pattern matters:
    #   * EMAIL/PHONE — old standbys; CVs reliably print these at the top.
    #   * MAIL_LABEL_RE — older CVs include a labelled "Mailing Address" /
    #     "Home Address" block followed by the full street address. We
    #     greedily redact from the label through the trailing Canadian or US
    #     postal code so we don't leak a partial street.
    #   * STREET_RE — safety net for any street-address-shaped run that
    #     wasn't caught by a label (e.g., reflowed text where the label got
    #     separated from the address).
    #   * CA_POSTAL_RE / US_ZIP_RE — final belt-and-braces. The CA pattern
    #     (`A1A 1A1`) is very specific to Canadian postal codes, so false
    #     positives are negligible. The US ZIP pattern is intentionally
    #     limited to 5+4 form to avoid eating bare 5-digit numbers in
    #     academic prose (page IDs, equipment model numbers, years).
    EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
    PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
    # Order matters and is intentional:
    #   1. STREET_RE first  — kills a "<number> <Word> <StreetType>" run as
    #      one unit so the digits don't get mistaken for a US ZIP by the
    #      label pattern's lazy terminator.
    #   2. MAIL_LABEL_RE   — sweeps any remaining "Mailing Address: ..." run
    #      through to the closing postal code (or up to ~250 chars).
    #   3. CA_POSTAL / US_ZIP — final mop-up for bare postals.
    # The label-pattern terminator only accepts CA-style postal codes (six
    # alphanumerics in A#A #A# form) or strict 5+4 US ZIPs; bare 5-digit
    # numbers are too common in academic prose (page IDs, equipment models,
    # years) to be reliable end markers.
    STREET_RE = re.compile(
        r"\b\d{2,6}\s+"
        r"[A-Z][\w'-]+(?:\s+[A-Z][\w'-]+){0,3}\s+"
        r"(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Boulevard|Blvd|"
        r"Lane|Ln|Court|Ct|Way|Crescent|Cres|Place|Pl|Parkway|Pkwy|"
        r"Highway|Hwy|Trail|Tr|Square|Sq|Terrace|Ter)\.?"
        r"(?:\s+(?:N|S|E|W|NE|NW|SE|SW|North|South|East|West))?\b"
    )
    MAIL_LABEL_RE = re.compile(
        r"(?:Home|Mailing|Permanent|Residential|Postal)\s+Address"
        r"[:\s]+.{0,250}?"
        r"(?:\b[A-Z]\d[A-Z]\s?\d[A-Z]\d\b|\b\d{5}-\d{4}\b)",
        re.IGNORECASE | re.DOTALL,
    )
    CA_POSTAL_RE = re.compile(r"\b[A-Z]\d[A-Z]\s?\d[A-Z]\d\b")
    US_ZIP_RE = re.compile(r"\b\d{5}-\d{4}\b")
    for c in chunks:
        c["text"] = STREET_RE.sub("[address-redacted]", c["text"])
        c["text"] = MAIL_LABEL_RE.sub("[address-redacted]", c["text"])
        c["text"] = CA_POSTAL_RE.sub("[postal-redacted]", c["text"])
        c["text"] = US_ZIP_RE.sub("[postal-redacted]", c["text"])
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
