"""
parent_chunks.py - Parent-chunk generator for the two-tier retrieval pattern.

Groups leaf chunks by chapter/section and creates parent-context chunks
stored separately for key-value lookup after retrieval.


python src/chunking/parent_chunks.py output/leaf_chunks.jsonl output/parent_chunks.jsonl
"""

import json
from collections import defaultdict

from token_utils import count_tokens

parent_max_tokens = 2000


def get_group_key(meta):
    """Return grouping key for leaf chunk metadata."""
    doc = meta.get("document", "")
    chapter = meta.get("chapter")
    section = meta.get("section")
    page = meta.get("page", "")

    if chapter and section:
        return f"{doc}||{chapter}||{section}"
    if chapter:
        return f"{doc}||{chapter}||"
    return f"{doc}||__page_{page}||"


def get_scope_label(meta):
    """Infer context scope label from metadata."""
    if meta.get("chapter") and meta.get("section"):
        return "section"
    if meta.get("chapter"):
        return "chapter"
    return "page"


def create_parent_chunks(leaf_chunks, max_tokens=parent_max_tokens):
    """
    Group leaf chunks into parent context units up to max_tokens.
    Populates parent_id on leaf chunks in-place.
    """
    groups = defaultdict(list)
    for idx, lc in enumerate(leaf_chunks):
        key = get_group_key(lc.get("metadata", {}))
        groups[key].append(idx)

    parents = []

    for group_key, child_indices in groups.items():
        if not child_indices:
            continue

        child_ids = []
        text_parts = []
        token_total = 0

        first_meta = leaf_chunks[child_indices[0]].get("metadata", {})

        for ci in child_indices:
            lc = leaf_chunks[ci]
            cid = lc.get("chunk_id", f"idx_{ci}")
            child_ids.append(cid)

            part = lc["text"].strip()
            part_tokens = count_tokens(part)
            if token_total + part_tokens <= max_tokens:
                text_parts.append(part)
                token_total += part_tokens

        parent_id = f"parent_{child_ids[0]}"
        parent_text = "\n\n".join(text_parts)

        parents.append({
            "chunk_id": parent_id,
            "text": parent_text,
            "child_ids": child_ids,
            "metadata": {
                "document": first_meta.get("document", ""),
                "scope": get_scope_label(first_meta),
                "chapter": first_meta.get("chapter"),
                "section": first_meta.get("section"),
            },
        })

        for ci in child_indices:
            leaf_chunks[ci]["parent_id"] = parent_id

    return parents


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate parent chunks from leaf chunks JSONL.")
    parser.add_argument("input_chunks", help="Path to leaf chunks JSONL.")
    parser.add_argument("output_parents", help="Path to output parents JSONL.")
    args = parser.parse_args()

    with open(args.input_chunks, "r", encoding="utf-8") as f:
        leaves = [json.loads(line) for line in f if line.strip()]

    parents = create_parent_chunks(leaves)

    with open(args.output_parents, "w", encoding="utf-8") as f:
        for p in parents:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    with open(args.input_chunks, "w", encoding="utf-8") as f:
        for lc in leaves:
            f.write(json.dumps(lc, ensure_ascii=False) + "\n")

    print(f"Created {len(parents)} parent chunks -> {args.output_parents}")
    print(f"Updated {len(leaves)} leaf chunks with parent_id -> {args.input_chunks}")
