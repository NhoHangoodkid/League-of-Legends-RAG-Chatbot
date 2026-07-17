"""
# 1 file
python final_analysis.py "path/to/file.pdf"

# Whole Folder
python final_analysis.py "path/to/documents/"

"""


import os
import sys
import json
from datetime import datetime, timezone

from analyse_document import analyze_document
from handle_scanned_pdf import ocr_flagged_pages, EngineOCR



def merge_document(document_path, analysis, ocr_results, language= "en", dpi=300, output_path = None):
    """Merge text-layer pages and OCR pages into a single per-page structure."""
    num_page = analysis["num_page"]
    text_pages = analysis.get("pages", {})
    ocr_pages = ocr_results.get("pages", {})

    merged_pages = {}
    for page_number in range(1, num_page + 1):
        page_key = str(page_number)
        if page_number in text_pages:
            info = text_pages[page_number]
            merged_pages[page_key] = {"source": "text", **info}
        elif page_number in ocr_pages:
            info = ocr_pages[page_number]
            merged_pages[page_key] = {"source": "ocr", **info}
        else:
            # Empty / unreadable page — placeholder so the pipeline never crashes.
            merged_pages[page_key] = {
                "source": "unknown",
                "text": "",
                "char_count": 0,
                "word_count": 0,
                "sentence_count": 0,
            }

    num_text = sum(1 for p in merged_pages.values() if p["source"] == "text")
    num_ocr = sum(1 for p in merged_pages.values() if p["source"] == "ocr")

    merged = {
        "document_path": document_path,
        "num_page": num_page,
        "pdf_type": analysis["pdf_type"],
        "num_text_pages": num_text,
        "num_scanned_pages": num_ocr,
        "metadata": {
            "ocr_backend": "PaddleOCR 3.x",
            "ocr_language": language,
            "ocr_dpi": dpi,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        "pages": merged_pages,
    }

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)

    return merged


def summarize_merged(merged):
    """Compute document-level summary stats from a merged document dict."""
    pages = merged["pages"]
    total_word = sum(p["word_count"] for p in pages.values())
    total_sentence = sum(p["sentence_count"] for p in pages.values())
    avg_word_per_sentence = round(total_word / total_sentence, 2) if total_sentence else 0

    ocr_confs = [p["confidence"] for p in pages.values()
                 if p["source"] == "ocr" and isinstance(p.get("confidence"), (int, float))]
    avg_ocr_confidence = round(sum(ocr_confs) / len(ocr_confs), 4) if ocr_confs else 0.0

    return {
        "document_path": merged["document_path"],
        "num_page": merged["num_page"],
        "pdf_type": merged["pdf_type"],
        "num_text_pages": merged["num_text_pages"],
        "num_scanned_pages": merged["num_scanned_pages"],
        "total_word": total_word,
        "total_sentence": total_sentence,
        "avg_word_per_sentence": avg_word_per_sentence,
        "avg_ocr_confidence": avg_ocr_confidence,
    }


def final_analysis(document_path, language="en", device="gpu", dpi=300, output_dir="output"):
    """Run the full pipeline: analyse -> OCR scanned pages -> merge -> JSON output."""
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(document_path))[0]

    merged_json_path = os.path.join(output_dir, f"{base_name} merged_document.json")

    # 1. Document-level statistics + per-page text (pdfplumber, one pass).
    analysis = analyze_document(document_path)

    # 2. OCR only the flagged scanned pages
    engine = EngineOCR(language=language, device=device)
    ocr_results = ocr_flagged_pages(document_path, analysis, engine=engine, dpi=dpi)

    # 3. Merge text-layer + OCR into one unified JSON per page.
    merged = merge_document(
        document_path, analysis, ocr_results,
        language = language, dpi = dpi,
        output_path = merged_json_path,
    )

    return {
        "merged_document": merged,
        "merged_json": merged_json_path,
    }


if __name__ == "__main__":
    import argparse
    import glob

    # Fix Windows console encoding: avoid UnicodeEncodeError for non-ASCII paths
    # (e.g. Vietnamese file names on cp1252 terminals).
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Run the full PDF analysis pipeline.")
    parser.add_argument("path", help="Path to a PDF file or a directory containing PDFs.")
    parser.add_argument("--language", default="en", help="OCR language (default: en).")
    parser.add_argument("--device", default="gpu", help="PaddleOCR device: gpu or cpu.")
    parser.add_argument("--dpi", type=int, default=300, help="DPI for rendering scanned pages (default: 300).")
    parser.add_argument("--output-dir", default="output", help="Directory for output files (default: output).")
    parser.add_argument("--force", action="store_true",
                        help="Re-process files even if output already exists.")
    args = parser.parse_args()

    # Collect PDF files: single file or recursive directory scan.
    if os.path.isfile(args.path):
        pdf_files = [args.path]
    elif os.path.isdir(args.path):
        pdf_files = sorted(glob.glob(os.path.join(args.path, "**", "*.pdf"), recursive=True))
    else:
        print(f"Error: '{args.path}' is not a valid file or directory.")
        exit(1)

    if not pdf_files:
        print(f"No PDF files found in '{args.path}'.")
        exit(1)

    print(f"Found {len(pdf_files)} PDF(s).\n")

    skipped = 0
    for i, pdf_path in enumerate(pdf_files, 1):
        # Incremental mode: skip files whose output already exists.
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        merged_json_path = os.path.join(args.output_dir, f"{base_name} merged_document.json")
        if not args.force and os.path.isfile(merged_json_path):
            print(f"[{i}/{len(pdf_files)}] SKIP (already exists): {pdf_path}")
            skipped += 1
            continue

        print(f"[{i}/{len(pdf_files)}] {pdf_path}")
        try:
            result = final_analysis(
                pdf_path,
                language = args.language,
                device = args.device,
                dpi = args.dpi,
                output_dir = args.output_dir,
            )
            print(f"  PDF type:    {result['merged_document']['pdf_type']}")
            print(f"  Merged JSON: {result['merged_json']}")
        except Exception as e:
            # Log error and continue processing remaining files.
            print(f"  ERROR: {e}")
        print()

    print(f"Done. {len(pdf_files) - skipped} processed, {skipped} skipped.")

    # 5. Consolidated summary: compute stats from all merged_document.json files.
    import csv
    merged_jsons = sorted(glob.glob(os.path.join(args.output_dir, "* merged_document.json")))
    if merged_jsons:
        all_summaries_path = os.path.join(args.output_dir, " all_summaries.csv")
        fieldnames = [
            "document_path", "num_page", "pdf_type", "num_text_pages",
            "num_scanned_pages", "total_word", "total_sentence",
            "avg_word_per_sentence", "avg_ocr_confidence",
        ]
        all_rows = []
        for json_path in merged_jsons:
            with open(json_path, "r", encoding="utf-8") as f:
                merged = json.load(f)
            all_rows.append(summarize_merged(merged))

        with open(all_summaries_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows)

        print(f"\nConsolidated summary: {all_summaries_path} ({len(all_rows)} documents)")
