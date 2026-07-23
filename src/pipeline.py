"""
Pipeline orchestrator for the RAG preprocessing and chunking pipeline.

Chains processing stages:
    1. Classify document (document_classifier)
    2. Clean document (document_cleaning)
    3. Parse structure (analyze_structure)
    4. Chunk into leaf chunks (chunk_documents)
    5. Generate parent chunks (parent_chunks)
"""

import os
import sys
import glob
import json
import time
import argparse
from typing import List, Dict, Any, Optional

from document_classifier import classify_document
from document_cleaning import clean_document
from analyze_structure import parse_document
from chunk_documents import chunk_document
from parent_chunks import create_parent_chunks
from token_utils import count_tokens, CHUNK_CONFIG


def discover_files(path: str) -> List[str]:
    """Find all merged_document.json files under path."""
    if os.path.isfile(path):
        return [path]

    pattern = os.path.join(path, "**", "*merged_document.json")
    files = sorted(glob.glob(pattern, recursive=True))
    return files


def print_stats(doc_path: str,
                category: str,
                blocks: List[Dict[str, Any]],
                leaf_chunks: List[Dict[str, Any]],
                parent_chunks: List[Dict[str, Any]]):
    """Print per-document processing statistics."""
    from collections import Counter

    block_types = Counter(b["type"] for b in blocks)
    token_counts = [count_tokens(c["text"]) for c in leaf_chunks]

    if not token_counts:
        print("  [!] No chunks produced.")
        return

    token_counts.sort()
    n = len(token_counts)

    print(f"  Category: {category}")
    print(f"  Blocks:   {len(blocks):>5d}  ", end="")
    print("  ".join(f"{bt}={cnt}" for bt, cnt in block_types.most_common(5)))

    print(f"  Leaf chunks:   {n:>5d}")
    print(f"  Parent chunks: {len(parent_chunks):>5d}")
    print(f"  Token distribution:")
    print(f"      min={token_counts[0]}  "
          f"median={token_counts[n // 2]}  "
          f"max={token_counts[-1]}  "
          f"mean={sum(token_counts) // n}")

    small = sum(1 for t in token_counts if t < CHUNK_CONFIG["min_chunk"])
    large = sum(1 for t in token_counts if t > CHUNK_CONFIG["hard_cap"])
    if small:
        print(f"      [!] {small} chunks below min_chunk ({CHUNK_CONFIG['min_chunk']} tokens)")
    if large:
        print(f"      [!] {large} chunks above hard_cap ({CHUNK_CONFIG['hard_cap']} tokens)")

    chunk_types = Counter(c["metadata"].get("block_type", "?") for c in leaf_chunks)
    print("  Chunk block_types:")
    for bt, cnt in chunk_types.most_common():
        print(f"      {bt:<16s} {cnt:>5d}")


def process_document(input_path: str,
                     output_dir: str,
                     dry_run: bool = False,
                     show_stats: bool = False,
                     config: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    """
    Run full preprocessing and chunking pipeline on a single merged JSON file.
    """
    t0 = time.time()

    with open(input_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    doc_path = raw_data.get("document_path", input_path)
    category = classify_document(doc_path)
    cleaned_data = clean_document(raw_data, category=category)
    structured = parse_document(cleaned_data, doc_category=category)
    blocks = structured.get("blocks", [])

    leaf_chunks = chunk_document(structured, config=config)
    parents = create_parent_chunks(leaf_chunks)

    elapsed = time.time() - t0

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    base_name = base_name.replace(" merged_document", "")

    if not dry_run:
        os.makedirs(output_dir, exist_ok=True)

        chunks_path = os.path.join(output_dir, f"{base_name}_chunks.jsonl")
        parents_path = os.path.join(output_dir, f"{base_name}_parents.jsonl")

        with open(chunks_path, "w", encoding="utf-8") as f:
            for ch in leaf_chunks:
                f.write(json.dumps(ch, ensure_ascii=False) + "\n")

        with open(parents_path, "w", encoding="utf-8") as f:
            for p in parents:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")

    if show_stats:
        print(f"\n{'-' * 70}")
        try:
            print(f"  {doc_path}")
        except UnicodeEncodeError:
            safe_path = doc_path.encode("ascii", errors="replace").decode("ascii")
            print(f"  {safe_path}")
        print(f"  Processed in {elapsed:.1f}s")
        print_stats(doc_path, category, blocks, leaf_chunks, parents)

    return {
        "input": input_path,
        "category": category,
        "num_blocks": len(blocks),
        "num_leaf_chunks": len(leaf_chunks),
        "num_parent_chunks": len(parents),
        "elapsed_seconds": round(elapsed, 2),
    }


def run_pipeline(input_path: str,
                 output_dir: str,
                 dry_run: bool = False,
                 show_stats: bool = False,
                 config: Optional[Dict[str, int]] = None):
    """
    Execute pipeline on a single file or directory of merged_document.json files.
    """
    files = discover_files(input_path)
    if not files:
        print(f"No merged_document.json files found at: {input_path}")
        sys.exit(1)

    print(f"Pipeline: processing {len(files)} document(s)")
    print(f"  Input:  {input_path}")
    print(f"  Output: {output_dir}{'  [DRY RUN]' if dry_run else ''}")
    print(f"  Config: hard_cap={CHUNK_CONFIG['hard_cap']} "
          f"soft_target={CHUNK_CONFIG['soft_target']} "
          f"overlap={CHUNK_CONFIG['overlap']} "
          f"min_chunk={CHUNK_CONFIG['min_chunk']}")
    summaries = []
    for i, fp in enumerate(files, 1):
        try:
            print(f"\n[{i}/{len(files)}] {os.path.basename(fp)}")
        except UnicodeEncodeError:
            safe_name = os.path.basename(fp).encode("ascii", errors="replace").decode("ascii")
            print(f"\n[{i}/{len(files)}] {safe_name}")
        try:
            summary = process_document(
                fp, output_dir,
                dry_run=dry_run,
                show_stats=show_stats,
                config=config,
            )
            summaries.append(summary)
        except Exception as e:
            try:
                print(f"  [X] ERROR: {e}")
            except UnicodeEncodeError:
                safe_err = str(e).encode("ascii", errors="replace").decode("ascii")
                print(f"  [X] ERROR: {safe_err}")
            summaries.append({"input": fp, "error": str(e)})

    ok = [s for s in summaries if "error" not in s]
    err = [s for s in summaries if "error" in s]

    total_chunks = sum(s.get("num_leaf_chunks", 0) for s in ok)
    total_parents = sum(s.get("num_parent_chunks", 0) for s in ok)
    total_time = sum(s.get("elapsed_seconds", 0) for s in ok)

    print(f"\n{'=' * 70}")
    print("  PIPELINE COMPLETE")
    print(f"  Documents: {len(ok)} OK, {len(err)} errors")
    print(f"  Total leaf chunks:   {total_chunks}")
    print(f"  Total parent chunks: {total_parents}")
    print(f"  Total time: {total_time:.1f}s")
    if err:
        print("\n  Failed documents:")
        for s in err:
            try:
                print(f"    [X] {s['input']}: {s['error']}")
            except UnicodeEncodeError:
                safe_inp = s['input'].encode("ascii", errors="replace").decode("ascii")
                safe_err = str(s['error']).encode("ascii", errors="replace").decode("ascii")
                print(f"    [X] {safe_inp}: {safe_err}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="RAG preprocessing pipeline: classify -> clean -> parse -> chunk -> parent."
    )
    parser.add_argument("input_path", help="Path to merged_document.json or directory.")
    parser.add_argument("output_dir", help="Directory to write chunk JSONL files.")
    parser.add_argument("--dry-run", action="store_true", help="Process without writing files.")
    parser.add_argument("--stats", action="store_true", help="Print per-document statistics.")
    parser.add_argument("--hard_cap", type=int, default=None)
    parser.add_argument("--soft_target", type=int, default=None)
    parser.add_argument("--overlap", type=int, default=None)
    parser.add_argument("--min_chunk", type=int, default=None)
    args = parser.parse_args()

    config = {}
    for key in ("hard_cap", "soft_target", "overlap", "min_chunk"):
        val = getattr(args, key, None)
        if val is not None:
            config[key] = val

    run_pipeline(
        input_path=args.input_path,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
        show_stats=args.stats,
        config=config or None,
    )
