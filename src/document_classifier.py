"""
Document-level classifier for the RAG preprocessing pipeline.

Classifies a merged_document.json into a broad category based on its folder path and filename.
This category serves as a fallback default when content patterns do not match.
"""

import os
import glob
import json
from typing import Tuple

CATEGORIES = (
    "dictionary",
    "collocation",
    "phrasal_verb",
    "grammar",
    "vocabulary",
    "reading",
    "writing",
    "ielts_guide",
    "word_list",
    "general",
)

WORD_LIST_KEYWORDS = (
    "word list", "wordlist", "100 most", "common-opposites",
    "pet-vocabulary-list", "super từ", "super vocab",
)


def normalise_path(path: str) -> str:
    """Lower-case and unify separators for reliable matching."""
    return path.replace("\\", "/").lower()


def folder_match(path: str, keywords: Tuple[str, ...]) -> bool:
    """Check if any keyword appears in any folder segment of the path."""
    segments = path.split("/")
    return any(kw in seg for seg in segments for kw in keywords)


def is_word_list(path: str) -> bool:
    """Check if the filename matches known word-list patterns."""
    filename = path.split("/")[-1]
    return any(kw in filename for kw in WORD_LIST_KEYWORDS)


def classify_document(doc_path: str) -> str:
    """
    Classify a document path into a curriculum category.

    Parameters:
        doc_path: Document file path string.

    Returns:
        One of the categories defined in CATEGORIES.
    """
    path = normalise_path(doc_path)

    if is_word_list(path):
        return "word_list"

    if "dictionary" in path and "collocation" in path:
        return "dictionary"

    if folder_match(path, ("phrasal verb", "phrasal_verb", "phrasal-verb")):
        return "phrasal_verb"

    if folder_match(path, ("collocation",)):
        return "collocation"

    if folder_match(path, ("reading",)):
        return "reading"

    if folder_match(path, ("writing",)):
        return "writing"

    if folder_match(path, ("grammar",)):
        return "grammar"

    if folder_match(path, ("vocabulary", "vocab")):
        return "vocabulary"

    if folder_match(path, ("ielts",)):
        return "ielts_guide"

    return "general"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Classify merged_document.json files into curriculum categories."
    )
    parser.add_argument("path", help="Path to a single JSON file or directory.")
    args = parser.parse_args()

    if os.path.isfile(args.path):
        files = [args.path]
    else:
        files = sorted(glob.glob(os.path.join(args.path, "**", "*merged_document.json"), recursive=True))

    if not files:
        print(f"No merged_document.json found in '{args.path}'.")
        exit(1)

    for fp in files:
        with open(fp, "r", encoding="utf-8") as f:
            doc = json.load(f)
        doc_path = doc.get("document_path", fp)
        cat = classify_document(doc_path)
        try:
            print(f"  [{cat:<14s}]  {doc_path}")
        except UnicodeEncodeError:
            safe_path = doc_path.encode("ascii", errors="replace").decode("ascii")
            print(f"  [{cat:<14s}]  {safe_path}")
