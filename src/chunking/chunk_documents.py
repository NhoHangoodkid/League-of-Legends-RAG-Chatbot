"""
chunk_documents.py - Token-aware document chunker for the RAG pipeline.

Splits typed blocks into token-budgeted leaf chunks with sentence overlap,
table header repetition, and small chunk merging.

python src/chunking/chunk_documents.py output/structured.json output/leaf_chunks.jsonl
"""

import json
import hashlib
import argparse

from token_utils import count_tokens, split_into_sentences, chunk_config


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


def infer_domain(doc_path):
    """Infer document domain label from path."""
    path = doc_path.replace("\\", "/").lower()
    if "ielts" in path:
        return "IELTS"
    return "General English"


def chunk_document(data, config=None):
    """
    Chunk structured document blocks into token-budgeted leaf chunks.
    """
    cfg = {**chunk_config, **(config or {})}
    hard_cap = cfg["hard_cap"]
    overlap = cfg["overlap"]
    min_chunk = cfg["min_chunk"]

    doc_path = data.get("document_path", "")
    blocks = data.get("blocks", [])

    chunks = []
    chunk_index = 0

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

    for idx, ch in enumerate(chunks):
        ch["metadata"]["paragraph_id"] = idx

    return chunks


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
