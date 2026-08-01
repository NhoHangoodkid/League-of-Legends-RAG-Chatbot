"""
chunk_documents.py - Token-aware document chunker for the RAG pipeline.

Splits typed blocks into token-budgeted leaf chunks with sentence overlap,
table header repetition, and small chunk merging.

V2 changes:
  - Hardened is_valid_chunk(): publishing noise, template instructions,
    page-ref-only chunks, stricter minimum
  - Heading propagation: chunks inherit heading from predecessor when missing
  - Post-process dedup for near-identical template chunks across units

python src/chunking/chunk_documents.py output/structured.json output/leaf_chunks.jsonl
"""

import json
import hashlib
import argparse
import re

from token_utils import count_tokens, split_into_sentences, chunk_config


nlp = None

# ---------------------------------------------------------------------------
# Noise / boilerplate patterns (case-insensitive matching on text.lower())
# ---------------------------------------------------------------------------

# Publishing/copyright/metadata noise that slips through document_cleaning
_NOISE_SUBSTRINGS = (
    "all rights reserved",
    "this publication is in copyright",
    "printed in",
    "isbn",
    "published by",
    "ptg01.indd",
    "ptg01_hires",
    "acknowledgement",
    "acknowledgment",
    "about the author",
    "the publisher has used its best endeavors",
    "no part of this publication",
    "may be reproduced or distributed",
    "first published",
    "reprinted",
)

# Template instruction patterns that repeat across many units verbatim
_TEMPLATE_RE = [
    re.compile(p, re.IGNORECASE) for p in (
        r"^Do you remember the meanings of these words\?",
        r"^(?:A\. )?The table contains word families",
        r"^(?:A\. )?Choose the best answer for each question",
        r"^(?:A\. )?Read the target words\.",
        r"^(?:A\. )?Read the sentences and choose the word",
        r"^(?:A\. )?Match each target word",
        r"^Scope and Sequence",
    )
]

# Page-reference-only chunks (e.g. "➜ Unit 6 Past simple and present perfect ➜ Units 12–14")
_PAGE_REF_RE = re.compile(
    r"^[\d\s➜→►▶•,;/&\-–—()\[\]]+"
    r"(Unit|Page|Chapter|Section|Appendix|Exercise|Lesson)s?"
    r"[\d\s➜→►▶•,;/&\-–—()\[\]]*$",
    re.IGNORECASE,
)


def init_spacy():
    global nlp
    if nlp is None:
        try:
            import spacy
            nlp = spacy.load("en_core_web_sm", disable=["ner", "parser"])
        except Exception:
            nlp = "fallback"


def generate_chunk_id(text, doc_path=""):
    """Generate a deterministic short hash ID for a chunk."""
    key = f"{doc_path}::{text.strip()}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()[:12]


def force_split_chunk(text, max_tokens, overlap_tokens):
    """
    Split text exceeding max_tokens into sentence-aligned chunks with token overlap.
    """
    units = split_into_sentences(text)
    unit_tokens = [count_tokens(u) for u in units]

    chunks = []
    i = 0

    while i < len(units):
        current_units = []
        current_count = 0
        j = i

        while j < len(units):
            ut = unit_tokens[j]
            if current_count + ut > max_tokens and current_units:
                break
            current_units.append(units[j])
            current_count += ut
            j += 1

        chunks.append(" ".join(current_units))

        if j >= len(units):
            break

        overlap_acc = 0
        overlap_start = j
        for k in range(j - 1, i, -1):
            overlap_acc += unit_tokens[k]
            if overlap_acc >= overlap_tokens:
                overlap_start = k
                break

        i = overlap_start

    return chunks


def split_table_chunk(table_text, max_tokens):
    """
    Split a table into row-group chunks while repeating the table header row.
    """
    rows = table_text.strip().split("\n")
    if not rows:
        return [table_text]

    header = rows[0]
    header_tokens = count_tokens(header)
    data_rows = rows[1:] if len(rows) > 1 else []

    if count_tokens(table_text) <= max_tokens:
        return [table_text]

    chunks = []
    current_rows = [header]
    current_tokens = header_tokens

    for row in data_rows:
        row_tokens = count_tokens(row)
        if current_tokens + row_tokens + 1 > max_tokens and len(current_rows) > 1:
            chunks.append("\n".join(current_rows))
            current_rows = [header]
            current_tokens = header_tokens

        current_rows.append(row)
        current_tokens += row_tokens + 1

    if len(current_rows) > 1:
        chunks.append("\n".join(current_rows))

    return chunks if chunks else [table_text]


def merge_small_chunks(chunks, min_tokens, hard_cap):
    """
    Merge small adjacent chunks sharing block_type and chapter up to hard_cap.
    """
    if not chunks:
        return chunks

    merged = []
    i = 0

    while i < len(chunks):
        chunk = chunks[i]
        chunk_tok = count_tokens(chunk["text"])

        if chunk_tok < min_tokens and i + 1 < len(chunks):
            nxt = chunks[i + 1]
            same_type = chunk["metadata"].get("block_type") == nxt["metadata"].get("block_type")
            same_chapter = chunk["metadata"].get("chapter") == nxt["metadata"].get("chapter")
            combined_tok = chunk_tok + count_tokens(nxt["text"])

            if same_type and same_chapter and combined_tok <= hard_cap:
                merged_chunk = {
                    **chunk,
                    "text": chunk["text"].strip() + "\n\n" + nxt["text"].strip(),
                    "chunk_id": generate_chunk_id(
                        chunk["text"] + nxt["text"],
                        chunk["metadata"].get("document", ""),
                    ),
                }
                merged.append(merged_chunk)
                i += 2
                continue

        merged.append(chunk)
        i += 1

    return merged


def _is_noise_text(text_lower):
    """Return True if text is publishing/copyright noise."""
    return any(frag in text_lower for frag in _NOISE_SUBSTRINGS)


def _is_template_instruction(text):
    """Return True if text matches a known repeated template instruction."""
    return any(p.search(text) for p in _TEMPLATE_RE)


def _is_page_ref_only(text):
    """Return True if chunk is just cross-references to other units/pages."""
    # Must be short and match the pattern
    if len(text.split()) > 30:
        return False
    return bool(_PAGE_REF_RE.match(text.strip()))


def is_valid_chunk(text, metadata, drop_answers=False):
    """Filter out low-quality chunks based on various heuristics.
    
    V2 hardened: blocks publishing noise, template duplicates,
    page-ref-only chunks, and applies stricter word minimums.
    """
    block_type = metadata.get("block_type", "")

    # --- answer key filtering ---
    if drop_answers and block_type == "answer_key":
        return False

    stripped = text.strip()

    # --- trivial single-token chunks ---
    if re.match(r"^[A-Da-d][.)]?$", stripped):
        return False
    if re.match(r"^\d+[.)]?$", stripped):
        return False

    words = text.split()
    word_count = len(words)

    # --- V2: stricter minimum word count ---
    # Short-form types (table, qa, entry) get a lower bar
    short_form_types = ("table", "qa", "entry")
    min_words = 8 if block_type in short_form_types else 15
    if word_count < min_words:
        return False

    # --- character composition checks ---
    letters = sum(1 for c in text if c.isalpha())
    digits = sum(1 for c in text if c.isdigit())
    chars = len(text)
    if chars > 0:
        if letters / chars < 0.4:
            return False
        if digits / chars > 0.5:
            return False

    # --- word uniqueness (catches repetitive noise) ---
    if word_count > 0:
        unique_ratio = len(set(w.lower() for w in words)) / word_count
        if unique_ratio < 0.3:
            return False

    # --- V2: publishing/copyright noise ---
    text_lower = text.lower()
    if _is_noise_text(text_lower):
        return False

    # --- V2: repeated template instructions ---
    if _is_template_instruction(text):
        return False

    # --- V2: page-reference-only chunks ---
    if _is_page_ref_only(text):
        return False

    # --- spaCy POS check (verb+noun requirement) ---
    init_spacy()
    if nlp and nlp != "fallback":
        doc = nlp(text)
        has_verb = any(token.pos_ in ("VERB", "AUX") for token in doc)
        has_noun = any(token.pos_ in ("NOUN", "PROPN") for token in doc)
        if not (has_verb and has_noun):
            if block_type not in ("table", "entry", "qa", "exercise"):
                return False

    return True


def infer_domain(doc_path):
    """Infer document domain label from path."""
    path = doc_path.replace("\\", "/").lower()
    if "ielts" in path:
        return "IELTS"
    return "General English"


def _propagate_headings(chunks):
    """V2: Propagate heading from predecessor when a chunk has no heading.
    
    Many chunks end up with heading=None because the structural parser only
    assigns a heading when a heading line immediately precedes the paragraph.
    For consecutive chunks in the same chapter/document, we carry the last
    known heading forward so that downstream tasks (query generation,
    retrieval) have richer context.
    """
    last_heading = None
    last_doc = None
    last_chapter = None

    for ch in chunks:
        meta = ch["metadata"]
        doc = meta.get("document")
        chapter = meta.get("chapter")

        # Reset when document or chapter changes
        if doc != last_doc or chapter != last_chapter:
            last_heading = None
            last_doc = doc
            last_chapter = chapter

        if meta.get("heading"):
            last_heading = meta["heading"]
        elif last_heading:
            meta["heading"] = last_heading

    return chunks


def _dedup_near_identical(chunks, similarity_threshold=0.95):
    """V2: Remove near-identical template chunks that repeat across units.
    
    Keeps the first occurrence and drops subsequent chunks whose text is
    almost identical (by character-level set overlap). This catches the
    "Do you remember the meanings..." pattern (49 copies) and similar.
    """
    seen_texts = {}  # normalized_prefix -> index of first occurrence
    keep = []

    for ch in chunks:
        text = ch["text"].strip()
        # Use first 200 chars as dedup key (enough to catch templates)
        prefix = text[:200].lower()
        word_count = len(text.split())

        # Only dedup short template-like chunks (< 40 words)
        if word_count < 40 and prefix in seen_texts:
            continue

        if word_count < 40:
            seen_texts[prefix] = True

        keep.append(ch)

    removed = len(chunks) - len(keep)
    if removed > 0:
        print(f"  [dedup] Removed {removed} near-identical template chunks")

    return keep


def chunk_document(data, config=None):
    """
    Chunk structured document blocks into token-budgeted leaf chunks.
    
    V2: adds heading propagation and near-duplicate dedup.
    """
    cfg = {**chunk_config, **(config or {})}
    hard_cap = cfg["hard_cap"]
    overlap = cfg["overlap"]
    min_chunk = cfg["min_chunk"]

    doc_path = data.get("document_path", "")
    blocks = data.get("blocks", [])

    chunks = []
    chunk_index = 0

    dep_markers_re = re.compile(r"^(because|since|although|and|or|but)\b", re.IGNORECASE)

    for block_idx, block in enumerate(blocks):
        btype = block["type"]
        text = block["text"]
        metadata = block.get("metadata", {})

        block_tokens = count_tokens(text)

        if btype == "table":
            sub_texts = split_table_chunk(text, hard_cap)
        elif block_tokens <= hard_cap:
            sub_texts = [text]
        else:
            sub_texts = force_split_chunk(text, hard_cap, overlap)

        for sub_idx, sub_text in enumerate(sub_texts):
            sub_text = sub_text.strip()
            if not sub_text:
                continue

            # --- Rule 16: Merge dependent chunks ---
            if dep_markers_re.match(sub_text) and chunks:
                prev = chunks[-1]
                prev_text = prev["text"]
                combined_text = prev_text + " " + sub_text
                if count_tokens(combined_text) <= hard_cap:
                    prev["text"] = combined_text
                    prev["chunk_id"] = generate_chunk_id(combined_text, doc_path)
                    continue

            meta = dict(metadata)
            meta["block_type"] = btype
            meta["document"] = doc_path
            meta["domain"] = infer_domain(doc_path)

            if meta.get("heading") and meta["heading"].strip().endswith("?"):
                meta["question"] = meta["heading"]
                meta["heading"] = None

            meta["paragraph_id"] = chunk_index
            meta["block_index"] = block_idx
            meta["sub_chunk_index"] = sub_idx if len(sub_texts) > 1 else None

            chunk_id = generate_chunk_id(sub_text, doc_path)

            chunks.append({
                "chunk_id": chunk_id,
                "text": sub_text,
                "parent_id": None,
                "metadata": meta,
            })
            chunk_index += 1

    chunks = merge_small_chunks(chunks, min_chunk, hard_cap)

    # --- V2: Heading propagation (before filtering so heading info is available) ---
    chunks = _propagate_headings(chunks)

    drop_answers = cfg.get("drop_answers", False)
    valid_chunks = []
    for ch in chunks:
        if is_valid_chunk(ch["text"], ch["metadata"], drop_answers):
            valid_chunks.append(ch)

    # --- V2: Dedup near-identical template chunks ---
    valid_chunks = _dedup_near_identical(valid_chunks)

    for idx, ch in enumerate(valid_chunks):
        ch["metadata"]["paragraph_id"] = idx

    return valid_chunks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chunk structured document blocks into JSONL.")
    parser.add_argument("input_file", help="Path to structured JSON file.")
    parser.add_argument("output_file", help="Path to output chunks JSONL file.")
    parser.add_argument("--hard_cap", type=int, default=chunk_config["hard_cap"])
    parser.add_argument("--soft_target", type=int, default=chunk_config["soft_target"])
    parser.add_argument("--overlap", type=int, default=chunk_config["overlap"])
    parser.add_argument("--min_chunk", type=int, default=chunk_config["min_chunk"])
    args = parser.parse_args()

    with open(args.input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    cfg = {
        "hard_cap": args.hard_cap,
        "soft_target": args.soft_target,
        "overlap": args.overlap,
        "min_chunk": args.min_chunk,
    }

    chunks = chunk_document(data, config=cfg)

    with open(args.output_file, "w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")

    from collections import Counter
    token_counts = [count_tokens(ch["text"]) for ch in chunks]
    type_counts = Counter(ch["metadata"].get("block_type", "?") for ch in chunks)

    print(f"Generated {len(chunks)} chunks -> {args.output_file}")
    print(f"  Token stats: min={min(token_counts)} "
          f"median={sorted(token_counts)[len(token_counts)//2]} "
          f"max={max(token_counts)} "
          f"mean={sum(token_counts)//len(token_counts)}")
    print(f"  Block types:")
    for bt, cnt in type_counts.most_common():
        print(f"    {bt:<16s} {cnt:>5d}")
