#!/usr/bin/env python3
"""
Clean PDFs (and DOCX files) in me/ into chunk-friendly plaintext.

Pipeline (per file):

  1. Detect document type
       * native-text PDF  -> pdfplumber for layout-aware extraction
       * scanned PDF      -> pdftoppm + tesseract OCR (300dpi, eng)
       * .docx            -> python-docx, paragraphs + tables in reading order

  2. Per-page (PDFs)
       * Pull tables via pdfplumber.extract_tables() and render them compactly:
           - small tables (<= 6 rows & <= 6 cols & <800 chars total)  -> markdown rows
           - bigger tables                                            -> [TABLE omitted: rows x cols on p.N]
         The table area is *masked out* of the page bbox before text extraction
         so the same content does not appear twice.
       * Drop figures (image regions); they are not in extract_text() anyway,
         but figure CAPTIONS like "Figure 3 ..." are kept (one paragraph max).
       * Strip page numbers (lines that are only digits or "Page X of Y").
       * Strip ToC dot-leader lines:  "Some Heading ............ 23"
       * Strip repeating headers/footers: any line that appears on >=40% of pages
         is treated as boilerplate and removed.

  3. Document-level cleanup
       * Fix soft hyphenation at line-end:  "rehabili-\ntation" -> "rehabilitation"
       * Re-flow paragraphs: join lines inside a paragraph, keep blank lines
         as paragraph breaks.
       * Unicode normalize (NFKC), drop control chars, normalize quotes/dashes.
       * Detect heading-like lines (numbered "1.2.3 Foo", ALL-CAPS short lines,
         "Chapter N") and prefix with "## " so chunkers can split on them.
       * Collapse runs of >2 blank lines.

  4. Output
       * One .txt per source under me/text_clean/<same-name>.txt
       * Each file starts with a small YAML-ish header: source file, page count,
         char count, extraction mode (text/ocr/docx).
       * Major sections separated by  "\n\n---\n\n"  so a naive chunker can split.
"""

from __future__ import annotations

import os
import re
import sys
import shutil
import subprocess
import tempfile
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Iterable

import pdfplumber
from docx import Document

ME_DIR = Path(__file__).resolve().parent.parent / "me"
# `me/processed/` is the canonical home for the cleaned text. The chatbot's
# corpus builder reads from here, so anything dropped (or excluded) below
# directly shapes what the LLM can answer about.
OUT_DIR = ME_DIR / "processed"
# Subdirectories under me/ that we deliberately do NOT feed to the LLM.
# `applications/` is job-application-specific cover letters and tailored
# resumes — they are noisy duplicates of the canonical CV with employer-
# specific phrasing that biases retrieval. Keep them out.
EXCLUDED_SUBDIRS = {"applications"}
# OCR resolution. 200 dpi is a sweet spot: legible enough for tesseract,
# fast enough for the patent (19 pages) to fit in a single bash call.
OCR_DPI = 200
# Comma-separated filename stems to skip on this run, via env var. Useful when
# you want to split a slow OCR pass off into its own invocation.
SKIP_STEMS_ENV = {s.strip() for s in os.environ.get("CLEAN_SKIP", "").split(",") if s.strip()}
# Comma-separated filename stems to ONLY process on this run (everything else
# is skipped). Inverse of CLEAN_SKIP. Empty = process everything.
ONLY_STEMS_ENV = {s.strip() for s in os.environ.get("CLEAN_ONLY", "").split(",") if s.strip()}
OUT_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

DOTS_LEADER_RE = re.compile(r"\.{4,}\s*\d+\s*$")
PAGE_NUM_RE = re.compile(r"^\s*(?:page\s+)?\d+(?:\s*/\s*\d+)?\s*$", re.IGNORECASE)
PAGE_OF_RE = re.compile(r"^\s*page\s+\d+\s+of\s+\d+\s*$", re.IGNORECASE)
NUMBERED_HEADING_RE = re.compile(r"^(?:chapter\s+\d+|\d+(?:\.\d+){0,4})\.?\s+\S.{0,120}$", re.IGNORECASE)
ALLCAPS_HEADING_RE = re.compile(r"^[A-Z][A-Z0-9 \-:&,'/]{3,80}$")
SOFT_HYPHEN_RE = re.compile(r"(\w)-\n(\w)")
MULTI_BLANK_RE = re.compile(r"\n{3,}")
WS_INSIDE_LINE = re.compile(r"[ \t]{2,}")


def nfkc(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    # tame curly quotes and exotic dashes for downstream LLM tokenization
    repl = {
        "‘": "'", "’": "'", "“": '"', "”": '"',
        "–": "-", "—": "-", "−": "-",
        " ": " ", " ": " ", "​": "",
        "ﬁ": "fi", "ﬂ": "fl",
    }
    for k, v in repl.items():
        text = text.replace(k, v)
    # strip control chars except \n and \t
    return "".join(c for c in text if c == "\n" or c == "\t" or unicodedata.category(c)[0] != "C")


def strip_dotleaders(text: str) -> str:
    out = []
    for line in text.splitlines():
        if DOTS_LEADER_RE.search(line):
            continue
        out.append(line)
    return "\n".join(out)


def strip_page_numbers(text: str) -> str:
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            out.append(line)
            continue
        if PAGE_NUM_RE.match(s) or PAGE_OF_RE.match(s):
            continue
        out.append(line)
    return "\n".join(out)


def remove_repeating_lines(pages: list[str], threshold: float = 0.4) -> list[str]:
    """
    Lines (stripped) that appear on >= threshold fraction of pages are headers/footers.
    Drop them everywhere.
    """
    if len(pages) < 4:
        return pages
    counter: Counter = Counter()
    for p in pages:
        seen_on_page = set()
        for raw in p.splitlines():
            s = raw.strip()
            if 3 <= len(s) <= 120 and s not in seen_on_page:
                seen_on_page.add(s)
                counter[s] += 1
    cutoff = max(2, int(threshold * len(pages)))
    boilerplate = {s for s, n in counter.items() if n >= cutoff}
    if not boilerplate:
        return pages
    cleaned = []
    for p in pages:
        kept = [ln for ln in p.splitlines() if ln.strip() not in boilerplate]
        cleaned.append("\n".join(kept))
    return cleaned


def fix_hyphenation(text: str) -> str:
    return SOFT_HYPHEN_RE.sub(r"\1\2", text)


def reflow_paragraphs(text: str) -> str:
    """Join wrapped lines inside paragraphs while preserving blank-line breaks."""
    paragraphs = re.split(r"\n\s*\n", text)
    out = []
    for p in paragraphs:
        lines = [ln.rstrip() for ln in p.splitlines() if ln.strip()]
        if not lines:
            continue
        # Don't reflow heading-like single lines or list items
        if len(lines) == 1:
            out.append(lines[0])
            continue
        merged = []
        for ln in lines:
            if merged and not (
                ln.startswith(("- ", "* ", "• ", "·  ", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9."))
                or NUMBERED_HEADING_RE.match(ln)
                or ALLCAPS_HEADING_RE.match(ln)
            ):
                merged[-1] = merged[-1] + " " + ln
            else:
                merged.append(ln)
        out.append("\n".join(merged))
    return "\n\n".join(out)


def mark_headings(text: str) -> str:
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            out.append(line)
            continue
        if NUMBERED_HEADING_RE.match(s) or (ALLCAPS_HEADING_RE.match(s) and len(s) <= 80 and len(s.split()) <= 12):
            out.append(f"## {s}")
        else:
            out.append(line)
    return "\n".join(out)


def collapse_blanks(text: str) -> str:
    text = MULTI_BLANK_RE.sub("\n\n", text)
    text = "\n".join(WS_INSIDE_LINE.sub(" ", ln) for ln in text.splitlines())
    return text.strip() + "\n"


def render_table(table: list[list[str]]) -> str:
    if not table or not any(any(c for c in row if c) for row in table):
        return ""
    rows = [[(c or "").strip() for c in row] for row in table]
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    rendered = "\n".join("| " + " | ".join(r) + " |" for r in rows)
    too_big = len(rows) > 6 or width > 6 or len(rendered) > 800
    if too_big:
        return f"[TABLE omitted: {len(rows)} rows x {width} cols]"
    return rendered


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

def extract_pdf_with_pdfplumber(path: Path) -> tuple[list[str], int]:
    pages_text: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            try:
                tables = page.find_tables()
            except Exception:
                tables = []
            table_bboxes = [t.bbox for t in tables] if tables else []
            # Mask out table regions for text extraction
            try:
                if table_bboxes:
                    crop = page
                    not_table = crop.filter(
                        lambda obj: not any(
                            obj["x0"] >= bb[0] and obj["x1"] <= bb[2]
                            and obj["top"] >= bb[1] and obj["bottom"] <= bb[3]
                            for bb in table_bboxes
                        )
                    )
                    text = not_table.extract_text(x_tolerance=2, y_tolerance=3) or ""
                else:
                    text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
            except Exception:
                text = page.extract_text() or ""
            # Append table renderings after the prose
            chunks = [text.strip()]
            for t in tables:
                try:
                    rows = t.extract()
                except Exception:
                    rows = None
                if rows:
                    rendered = render_table(rows)
                    if rendered:
                        chunks.append(rendered)
            pages_text.append("\n\n".join(c for c in chunks if c))
    return pages_text, len(pages_text)


def ocr_pdf(path: Path) -> tuple[list[str], int]:
    pages_text: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        # render at OCR_DPI as PNG
        prefix = Path(td) / "p"
        subprocess.run(
            ["pdftoppm", "-r", str(OCR_DPI), "-png", str(path), str(prefix)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        pngs = sorted(Path(td).glob("p-*.png"))
        for png in pngs:
            res = subprocess.run(
                ["tesseract", str(png), "-", "-l", "eng", "--psm", "1"],
                capture_output=True, text=True,
            )
            pages_text.append(res.stdout)
    return pages_text, len(pages_text)


def is_scanned_pdf(path: Path) -> bool:
    """Sample first few pages; if essentially no text, treat as scanned."""
    try:
        out = subprocess.run(
            ["pdftotext", "-f", "1", "-l", "3", str(path), "-"],
            capture_output=True, text=True, check=True,
        ).stdout
    except Exception:
        return True
    return len(re.sub(r"\s", "", out)) < 50


# ---------------------------------------------------------------------------
# DOCX extraction
# ---------------------------------------------------------------------------

def extract_docx(path: Path) -> tuple[list[str], int]:
    doc = Document(str(path))
    out_chunks: list[str] = []
    # python-docx doesn't keep paragraphs+tables interleaved natively without
    # walking the body, so we walk the underlying XML for reading order.
    body = doc.element.body
    for child in body.iterchildren():
        tag = child.tag.split("}")[-1]
        if tag == "p":
            text = "".join(node.text or "" for node in child.iter() if node.tag.endswith("}t"))
            text = text.strip()
            if text:
                out_chunks.append(text)
        elif tag == "tbl":
            rows = []
            for tr in child.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tr"):
                cells = []
                for tc in tr.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc"):
                    cell_text = "".join(
                        n.text or "" for n in tc.iter() if n.tag.endswith("}t")
                    ).strip()
                    cells.append(cell_text)
                if cells:
                    rows.append(cells)
            rendered = render_table(rows)
            if rendered:
                out_chunks.append(rendered)
    # Treat the whole docx as one virtual "page" for downstream cleanup
    return ["\n\n".join(out_chunks)], 1


# ---------------------------------------------------------------------------
# top-level driver
# ---------------------------------------------------------------------------

def clean_pages(pages: list[str]) -> str:
    pages = [nfkc(p) for p in pages]
    pages = [strip_page_numbers(strip_dotleaders(p)) for p in pages]
    pages = remove_repeating_lines(pages)
    full = "\n\n".join(pages)
    full = fix_hyphenation(full)
    full = reflow_paragraphs(full)
    full = mark_headings(full)
    full = collapse_blanks(full)
    return full


def process_file(src: Path, out_root: Path, force: bool = False) -> dict:
    rel = src.relative_to(ME_DIR)
    out_path = out_root / rel.with_suffix(".txt")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Idempotent re-runs: skip if output is fresher than source. Lets us
    # invoke the script multiple times without redoing slow OCR work.
    if not force and out_path.exists() and out_path.stat().st_mtime >= src.stat().st_mtime:
        return {
            "src": str(rel),
            "out": str(out_path),
            "mode": "cached",
            "pages": "?",
            "chars": out_path.stat().st_size,
        }

    if src.suffix.lower() == ".pdf":
        if is_scanned_pdf(src):
            mode = "ocr"
            pages, n = ocr_pdf(src)
        else:
            mode = "text"
            pages, n = extract_pdf_with_pdfplumber(src)
    elif src.suffix.lower() == ".docx":
        mode = "docx"
        pages, n = extract_docx(src)
    else:
        return {"src": str(src), "skipped": True}

    cleaned = clean_pages(pages)
    header = (
        f"# source: {rel}\n"
        f"# pages: {n}\n"
        f"# extraction: {mode}\n"
        f"# chars: {len(cleaned)}\n"
        f"---\n\n"
    )
    out_path.write_text(header + cleaned, encoding="utf-8")
    return {
        "src": str(rel),
        "out": str(out_path),
        "mode": mode,
        "pages": n,
        "chars": len(cleaned),
    }


def all_targets() -> Iterable[Path]:
    """
    Walk me/ for PDFs and DOCX files, skipping:
      * the OUT_DIR itself (avoid recursive re-cleaning)
      * any subdir listed in EXCLUDED_SUBDIRS (currently `applications/`,
        which holds job-specific cover letters/resumes the chatbot
        shouldn't quote from)
      * Word lock files like `~$foo.docx`
    """
    for ext in ("*.pdf", "*.docx"):
        for p in sorted(ME_DIR.rglob(ext)):
            if p.name.startswith("~$"):
                continue
            try:
                rel = p.relative_to(ME_DIR)
            except ValueError:
                continue
            top = rel.parts[0] if rel.parts else ""
            if top in EXCLUDED_SUBDIRS:
                continue
            if top == OUT_DIR.name:
                continue
            if SKIP_STEMS_ENV and p.stem in SKIP_STEMS_ENV:
                continue
            if ONLY_STEMS_ENV and p.stem not in ONLY_STEMS_ENV:
                continue
            yield p


def main() -> None:
    results = []
    for src in all_targets():
        try:
            print(f"[+] processing {src.relative_to(ME_DIR)}", flush=True)
            r = process_file(src, OUT_DIR)
            print(f"    -> {r}", flush=True)
            results.append(r)
        except Exception as e:
            print(f"    !! failed: {e}", flush=True)
            results.append({"src": str(src), "error": str(e)})
    # write a manifest
    manifest = OUT_DIR / "_manifest.txt"
    with manifest.open("w", encoding="utf-8") as f:
        f.write("source\tmode\tpages\tchars\toutput\n")
        for r in results:
            if "error" in r:
                f.write(f"{r.get('src')}\tERROR\t-\t-\t{r.get('error')}\n")
            elif r.get("skipped"):
                continue
            else:
                f.write(f"{r['src']}\t{r['mode']}\t{r['pages']}\t{r['chars']}\t{r['out']}\n")
    print(f"\nManifest: {manifest}")


if __name__ == "__main__":
    main()
