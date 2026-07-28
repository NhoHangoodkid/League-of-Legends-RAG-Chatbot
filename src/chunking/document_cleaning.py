"""
document_cleaning.py - Document text cleaning routines for the RAG preprocessing pipeline.

Cleans pages in merged_document.json by removing repetitive headers/footers,
OCR artifacts, copyright boilerplate, URLs, watermarks, garbled text,
and detecting tabular text blocks.

Recommended execution command / CLI Usage Example:
    python src/chunking/document_cleaning.py EDA_raw_documents/doc_merged_document.json output/cleaned.json --category general
"""

import re
import json
import os
from collections import Counter

ocr_confidence_threshold = 0.5

watermark_domains = (
    "www.ellt.ir", "ellt.ir", "learnenglishteam.com",
    "tlm4all", "z-lib.org",
)

url_re = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)

roman_re = re.compile(r"^\s*[ivxlcdm]{1,6}\s*$", re.IGNORECASE)

publisher_fragments = (
    "cambridge university press", "oxford university press",
    "pearson", "longman", "macmillan", "harper collins",
)

cd_re = re.compile(r"\b(CD\s*(Track|Audio)|audio\s*CD|Track\s*\d)\b", re.IGNORECASE)

garble_thresholds = {
    "dictionary": 0.70,
    "vocabulary": 0.60,
    "collocation": 0.65,
    "grammar": 0.40,
    "reading": 0.40,
    "writing": 0.40,
    "ielts_guide": 0.40,
    "word_list": 0.50,
    "general": 0.50,
}

whitelist_re = re.compile(
    r"""
      /[^/]+/           |
      \[.{1,15}\]       |
      \*\w+             |
      \b(adj|adv|n|v|prep|conj|pron|sb|sth|etc|e\.g|i\.e)\b
    """,
    re.VERBOSE | re.IGNORECASE,
)

english_word_re = re.compile(r"^[a-zA-Z][a-zA-Z'-]{0,30}$")

ligature_map = {
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
}

pipe_re = re.compile(r"\|.*\|")
tabular_re = re.compile(r"^\s*\S+\s{2,}\S+\s{2,}\S+")


def filter_low_quality_ocr_pages(pages):
    """Flag pages with OCR confidence below threshold."""
    for page_data in pages.values():
        conf = page_data.get("confidence")
        if conf is not None and isinstance(conf, (int, float)) and conf < ocr_confidence_threshold:
            page_data["low_ocr_quality"] = True
    return pages


def detect_headers_footers(pages):
    """Identify lines repeating at page top/bottom across > 50% of pages."""
    num_pages = len(pages)
    if num_pages < 3:
        return set(), set()

    start_counter = Counter()
    end_counter = Counter()

    for page_data in pages.values():
        text = page_data.get("text", "")
        if not text:
            continue
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        if not lines:
            continue
        for ln in lines[:2]:
            start_counter[ln] += 1
        for ln in lines[-2:]:
            end_counter[ln] += 1

    threshold = num_pages * 0.5
    headers = {ln for ln, cnt in start_counter.items() if cnt > threshold}
    footers = {ln for ln, cnt in end_counter.items() if cnt > threshold}
    return headers, footers


def remove_headers_footers(text, headers, footers):
    """Strip detected header and footer lines from page text."""
    if not headers and not footers:
        return text

    lines = text.split("\n")
    non_empty = [i for i, ln in enumerate(lines) if ln.strip()]
    if not non_empty:
        return text

    header_zone = set(non_empty[:2])
    footer_zone = set(non_empty[-2:])

    out = []
    for i, ln in enumerate(lines):
        stripped = ln.strip()
        if not stripped:
            out.append(ln)
            continue
        if i in header_zone and stripped in headers:
            continue
        if i in footer_zone and stripped in footers:
            continue
        out.append(ln)
    return "\n".join(out)


def remove_page_number(text):
    """Remove standalone page numbers and short page footer lines."""
    out = []
    for ln in text.split("\n"):
        if re.match(r"^\s*\d{1,4}\s*$", ln):
            continue
        if re.search(r"\bPage\s+\d+(\s+of\s+\d+)?\b", ln, re.IGNORECASE) and len(ln.strip()) < 80:
            continue
        out.append(ln)
    return "\n".join(out)


def remove_copyright(text):
    """Remove copyright notice lines."""
    return "\n".join(
        ln for ln in text.split("\n")
        if not re.search(r"(Copyright\s*©|©|All rights reserved)", ln, re.IGNORECASE)
    )


def remove_isbn(text):
    """Remove ISBN lines."""
    isbn_re = r"ISBN\s*(?:-1[03])?:?\s*[0-9X-]{10,}"
    return "\n".join(
        ln for ln in text.split("\n")
        if not re.search(isbn_re, ln, re.IGNORECASE)
    )


def remove_table_of_contents(text):
    """Remove dot-leader and OCR-style Table of Contents lines."""
    lines = text.split("\n")
    out = []
    toc_run = 0

    for ln in lines:
        stripped = ln.strip()
        if re.search(r"(\.{4,}|_{4,})\s*\d+$", stripped):
            toc_run += 1
            continue
        if re.match(r"^\s*(Table of Contents|Contents)\s*$", stripped, re.IGNORECASE):
            toc_run += 1
            continue
        if re.match(r"^.{3,50}\s+\d{1,4}$", stripped) and toc_run > 2:
            toc_run += 1
            continue

        toc_run = 0
        out.append(ln)
    return "\n".join(out)


def remove_url_and_watermark(text):
    """Remove standalone watermark domain links and URLs."""
    out = []
    for ln in text.split("\n"):
        stripped = ln.strip()
        if len(stripped) < 40 and any(d in stripped.lower() for d in watermark_domains):
            continue
        if len(stripped) < 60 and url_re.fullmatch(stripped):
            continue
        out.append(ln)
    return "\n".join(out)


def remove_page_artifacts(text):
    """Remove standalone roman numerals, publisher strings, and audio CD refs."""
    out = []
    for ln in text.split("\n"):
        stripped = ln.strip()
        if roman_re.match(stripped):
            continue
        if len(stripped) < 60 and any(p in stripped.lower() for p in publisher_fragments):
            continue
        if len(stripped) < 60 and cd_re.search(stripped):
            continue
        out.append(ln)
    return "\n".join(out)


def detect_global_duplicates(pages, threshold=20):
    """Rule 7: Identify lines that repeat globally more than threshold times."""
    counter = Counter()
    for page_data in pages.values():
        text = page_data.get("text", "")
        if not text:
            continue
        for ln in text.split("\n"):
            stripped = ln.strip()
            if len(stripped) > 10:
                counter[stripped] += 1
    return {ln for ln, cnt in counter.items() if cnt > threshold}


def remove_global_duplicates(text, global_dups):
    """Rule 7: Remove global duplicates."""
    if not global_dups:
        return text
    out = []
    for ln in text.split("\n"):
        if ln.strip() in global_dups:
            continue
        out.append(ln)
    return "\n".join(out)


def remove_symbol_only_lines(text):
    """Rule 12: Remove lines containing only symbols."""
    out = []
    for ln in text.split("\n"):
        if re.match(r"^\s*[-=*_#@]{3,}\s*$", ln):
            continue
        out.append(ln)
    return "\n".join(out)


def remove_repeated_characters(text):
    """Rule 14: Remove sequences of repeated characters."""
    return re.sub(r"(.)\1{4,}", "", text)


def remove_high_special_char_ratio(text):
    """Rule 13: Remove lines with high special character ratio (OCR errors)."""
    out = []
    for ln in text.split("\n"):
        stripped = ln.strip()
        if not stripped:
            out.append(ln)
            continue
        letters = sum(1 for c in stripped if c.isalnum() or c.isspace())
        if len(stripped) > 5 and letters / len(stripped) < 0.5:
            continue
        out.append(ln)
    return "\n".join(out)


def remove_specific_footers(text):
    """Rule 6: Remove specific known footers/headers."""
    known = ["cambridge ielts", "oxford word skills", "www."]
    out = []
    for ln in text.split("\n"):
        low_ln = ln.lower()
        if len(ln) < 60 and any(k in low_ln for k in known):
            continue
        if re.search(r"\bpage\s+\d+\b", low_ln) and len(ln) < 20:
            continue
        out.append(ln)
    return "\n".join(out)


def merge_broken_lines(text):
    """Rejoin lines broken across layout boundaries or soft hyphens."""
    text = text.replace("\u00ad", "")
    text = re.sub(r"-\n\s*", "", text)
    text = re.sub(r"(?<![.!?:;])\n([a-z])", r" \1", text)
    return text


def remove_duplicate_lines(text):
    """Remove consecutive duplicate lines."""
    lines = text.split("\n")
    out = []
    prev = None
    for ln in lines:
        s = ln.strip()
        if not s:
            out.append(ln)
            prev = None
            continue
        if s == prev:
            continue
        out.append(ln)
        prev = s
    return "\n".join(out)


def normalize_whitespace(text):
    """Collapse excess inline whitespace and empty line sequences."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def english_ratio(text):
    """Calculate ratio of English-like words in paragraph block."""
    cleaned = whitelist_re.sub("", text)
    tokens = cleaned.split()
    if len(tokens) < 5:
        return 1.0

    english_count = 0
    for t in tokens:
        word = t.strip(".,;:!?()[]\"'•+*-\\/" )
        if word and english_word_re.match(word):
            english_count += 1

    return english_count / len(tokens)


def is_scrambled_layout(text):
    """Detect scrambled PDF layout text (e.g. single-character letter spacing)."""
    cleaned = whitelist_re.sub("", text)
    tokens = cleaned.split()
    if len(tokens) < 15:
        return False

    single_letters = sum(
        1 for t in tokens
        if len(t.strip(".,;:!?()[]\"'•+*-\\/" )) == 1
        and t.lower() not in ("a", "i")
    )
    ratio = single_letters / len(tokens)
    if ratio > 0.25:
        return True

    words = [t.strip(".,;:!?()[]\"'•+*-\\/" ) for t in tokens]
    words = [w for w in words if w]
    if words:
        mean_len = sum(len(w) for w in words) / len(words)
        if mean_len < 2.0:
            return True

    return False


def remove_garbled_text(text, category="general"):
    """Remove garbled text blocks exceeding non-English word threshold."""
    threshold = garble_thresholds.get(category, 0.50)
    blocks = re.split(r"\n\s*\n", text)
    kept = []
    for block in blocks:
        if len(block.strip()) < 60:
            kept.append(block)
            continue
        if is_scrambled_layout(block):
            continue
        ratio = english_ratio(block)
        if ratio >= (1.0 - threshold):
            kept.append(block)
    return "\n\n".join(kept)


def normalize_ocr_artifacts(text):
    """Replace Unicode ligatures and weird punctuation with plain ASCII characters."""
    for lig, replacement in ligature_map.items():
        text = text.replace(lig, replacement)
    
    # Replace guillemets and weird quotes
    text = text.replace("«", '"').replace("»", '"')
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("‘", "'").replace("’", "'")
    
    # Replace weird PDF bullets
    text = text.replace("", "-").replace("◗", "-")
    
    return text


def detect_table_regions(text):
    """Locate tabular text lines based on alignment or pipe separators."""
    lines = text.split("\n")
    regions = []
    run_start = None

    for i, ln in enumerate(lines):
        is_table_line = bool(pipe_re.search(ln) or tabular_re.match(ln))
        if is_table_line:
            if run_start is None:
                run_start = i
        else:
            if run_start is not None and (i - run_start) >= 3:
                table_lines = lines[run_start:i]
                regions.append({
                    "start_line": run_start,
                    "end_line": i - 1,
                    "header_row": table_lines[0],
                    "text": "\n".join(table_lines),
                })
            run_start = None

    if run_start is not None and (len(lines) - run_start) >= 3:
        table_lines = lines[run_start:]
        regions.append({
            "start_line": run_start,
            "end_line": len(lines) - 1,
            "header_row": table_lines[0],
            "text": "\n".join(table_lines),
        })

    return regions


def clean_page_text(text, category="general", global_dups=None):
    """Apply all page-level text cleaning filters sequentially."""
    if not text:
        return ""

    text = remove_page_number(text)
    text = remove_copyright(text)
    text = remove_isbn(text)
    text = remove_table_of_contents(text)
    text = remove_url_and_watermark(text)
    text = remove_page_artifacts(text)
    
    # Custom Rules
    text = remove_specific_footers(text)
    text = remove_symbol_only_lines(text)
    text = remove_repeated_characters(text)
    text = remove_high_special_char_ratio(text)
    if global_dups:
        text = remove_global_duplicates(text, global_dups)
        
    text = remove_garbled_text(text, category)
    text = normalize_ocr_artifacts(text)
    text = merge_broken_lines(text)
    text = remove_duplicate_lines(text)
    text = normalize_whitespace(text)

    return text


def clean_document(input_data, category="general"):
    """
    Clean merged_document JSON data structure.

    Parameters:
        input_data: Merged document dictionary.
        category: Curriculum category string.

    Returns:
        Cleaned document dictionary copy.
    """
    output = input_data.copy()
    pages = output.get("pages", {})
    if not pages:
        return output

    pages = filter_low_quality_ocr_pages(pages)
    header_set, footer_set = detect_headers_footers(pages)
    global_dups = detect_global_duplicates(pages, threshold=20)

    for page_data in pages.values():
        text = page_data.get("text", "")
        if not text:
            continue

        text = remove_headers_footers(text, header_set, footer_set)
        tables = detect_table_regions(text)
        if tables:
            page_data["table_regions"] = tables

        page_data["text"] = clean_page_text(text, category, global_dups)

    output["pages"] = pages
    return output


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Clean merged_document.json.")
    parser.add_argument("input_file", help="Path to input merged JSON file.")
    parser.add_argument("output_file", help="Path to output cleaned JSON file.")
    parser.add_argument("--category", default="general", help="Document category.")
    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"Error: {args.input_file} does not exist.")
        exit(1)

    with open(args.input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    cleaned = clean_document(data, category=args.category)

    with open(args.output_file, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    total = len(cleaned.get("pages", {}))
    flagged = sum(1 for p in cleaned.get("pages", {}).values() if p.get("low_ocr_quality"))
    tables = sum(len(p.get("table_regions", [])) for p in cleaned.get("pages", {}).values())
    print(f"Cleaned {total} pages ({flagged} low-OCR, {tables} table regions) -> {args.output_file}")
