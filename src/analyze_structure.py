"""
Structure analyser for the RAG preprocessing pipeline.

Parses page text into typed blocks annotated with hierarchical metadata
(chapter, section, heading) and content-driven block types. Also links exercises
to answer keys.
"""

import json
import re
import argparse
from typing import Dict, Any, List, Optional

BLOCK_TYPES = (
    "rule",
    "exercise",
    "answer_key",
    "passage",
    "qa",
    "entry",
    "tips",
    "word_list",
    "table",
    "model_text",
    "definition",
    "paragraph",
)

CHAPTER_RE = re.compile(
    r"^(Unit|Chapter|Lesson|Part|Module)\s+([\dIVXivx]+)\b([:.\\-])?\s*(.*)$",
    re.IGNORECASE,
)

SECTION_RE = re.compile(
    r"^(Exercise|Practice|Section|Task|Activity)\s+[\d]+",
    re.IGNORECASE,
)

QUESTION_RE = re.compile(
    r"^(What|Who|When|Where|Why|How|Is|Are|Do|Does|Did|Can|Could|Should|"
    r"Would|Will|May|Might|Which|Has|Have|Had|Shall|Whom)\b.*\?$",
    re.IGNORECASE | re.DOTALL,
)

EXERCISE_PATTERNS = [
    re.compile(p, re.IGNORECASE | re.MULTILINE) for p in (
        r"(Fill in|Complete|Choose|Match|Circle|Underline|Correct|Rewrite)\s+(the|each|a|these)\b",
        r"Put\s+the\s+(verb|word|noun|adjective|phrase)",
        r"(Read|Listen|Look at)\s+.{5,40}\s+and\s+(answer|complete|decide|match|write|choose)",
        r"^\d+\.\s*_{2,}",
        r"^\d+\s+[A-D]\s+[A-D]\s+[A-D]",
        r"^(Exercise|Practice|Activity)\s+\d",
    )
]

ANSWER_KEY_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in (
        r"^(Answer\s+Key|Answers?|Key\s+to\s+(the\s+)?Exercises?)",
        r"^(Key|Answers?)\s*$",
    )
]

ENTRY_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in (
        r"[•▪]\s*(ADJ|VERB|ADV|PREP|QUANT|PHRASES)\.",
        r"^\w+\s+(noun|verb|adj|adv|adjective|adverb)\s*$",
    )
]

RULE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in (
        r"(We use|You use|Use)\s+(the\s+)?\w+\s+(when|for|to|if|in)",
        r"(is used|are used)\s+(to|for|when|in)",
        r"^(Compare|Note|Remember|Notice|Be careful)[:.!]",
    )
]

TIPS_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in (
        r"^\s*[▪•]\s*(Do|Don.t|Always|Never|Try to|Make sure|Remember)\b",
        r"^(Do|Don.t)\s*$",
    )
]

MODEL_TEXT_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in (
        r"^(Model|Sample|Example)\s+(Essay|Paragraph|Answer|Response|Letter)",
    )
]

CATEGORY_DEFAULTS = {
    "grammar": "rule",
    "dictionary": "entry",
    "vocabulary": "definition",
    "collocation": "entry",
    "phrasal_verb": "entry",
    "reading": "passage",
    "writing": "paragraph",
    "ielts_guide": "paragraph",
    "word_list": "word_list",
    "general": "paragraph",
}


def matches_any(text: str, patterns: list) -> bool:
    """Check if text matches any pattern in list."""
    return any(p.search(text) for p in patterns)


def detect_block_type(text: str,
                      heading: Optional[str],
                      is_table: bool,
                      doc_category: str) -> str:
    """
    Classify paragraph block type based on patterns, headings, or category defaults.
    """
    if matches_any(text, ANSWER_KEY_PATTERNS):
        return "answer_key"

    if matches_any(text, EXERCISE_PATTERNS):
        return "exercise"

    if matches_any(text, ENTRY_PATTERNS):
        return "entry"

    if is_table:
        return "table"

    if matches_any(text, TIPS_PATTERNS):
        return "tips"

    if matches_any(text, MODEL_TEXT_PATTERNS):
        return "model_text"

    if matches_any(text, RULE_PATTERNS):
        return "rule"

    if heading and QUESTION_RE.match(heading):
        return "qa"

    if heading and re.search(r"^(Answer|Key)", heading, re.IGNORECASE):
        return "answer_key"

    return CATEGORY_DEFAULTS.get(doc_category, "paragraph")


def is_heading(line: str) -> bool:
    """Determine if a line acts as a title/heading."""
    line = line.strip()
    if not line:
        return False

    if QUESTION_RE.match(line):
        return True

    if len(line) > 80:
        return False

    if line[-1] in ".!":
        return False

    words = line.split()
    if not words:
        return False

    cap_count = sum(1 for w in words if w.istitle() or w.isupper() or w.isdigit())
    return cap_count / len(words) >= 0.5


def parse_document(data: Dict[str, Any], doc_category: str = "general") -> Dict[str, Any]:
    """
    Extract structured blocks with hierarchical metadata from cleaned document JSON.
    """
    doc_path = data.get("document_path", "")
    pages_dict = data.get("pages", {})

    blocks: List[Dict[str, Any]] = []

    current_chapter: Optional[str] = None
    current_section: Optional[str] = None
    current_heading: Optional[str] = None
    expecting_chapter_title = False
    in_answer_key_region = False

    try:
        sorted_pages = sorted(pages_dict.items(), key=lambda x: int(x[0]))
    except ValueError:
        sorted_pages = sorted(pages_dict.items())

    for page_num_str, page_data in sorted_pages:
        page_num = page_num_str
        text = page_data.get("text", "")
        page_source = page_data.get("source", "unknown")
        page_conf = page_data.get("confidence", None)
        table_regions = page_data.get("table_regions", [])

        if not text:
            continue

        table_lines = set()
        for tr in table_regions:
            for li in range(tr["start_line"], tr["end_line"] + 1):
                table_lines.add(li)

        lines = text.split("\n")
        paragraph_buffer: List[str] = []

        def commit_paragraph():
            if not paragraph_buffer:
                return
            para_text = " ".join(paragraph_buffer).strip()
            if not para_text:
                paragraph_buffer.clear()
                return

            btype = detect_block_type(
                para_text,
                heading=current_heading,
                is_table=False,
                doc_category=doc_category,
            )

            if in_answer_key_region and btype == CATEGORY_DEFAULTS.get(doc_category, "paragraph"):
                btype = "answer_key"

            blocks.append({
                "type": btype,
                "text": para_text,
                "metadata": {
                    "page": page_num,
                    "chapter": current_chapter,
                    "section": current_section,
                    "heading": current_heading,
                    "source": page_source,
                    "ocr_confidence": page_conf,
                    "document_category": doc_category,
                },
            })
            paragraph_buffer.clear()

        for line_idx, line in enumerate(lines):
            stripped = line.strip()

            if not stripped:
                commit_paragraph()
                continue

            if line_idx in table_lines:
                commit_paragraph()
                if blocks and blocks[-1]["type"] == "table" and blocks[-1]["metadata"]["page"] == page_num:
                    blocks[-1]["text"] += "\n" + stripped
                else:
                    blocks.append({
                        "type": "table",
                        "text": stripped,
                        "metadata": {
                            "page": page_num,
                            "chapter": current_chapter,
                            "section": current_section,
                            "heading": current_heading,
                            "source": page_source,
                            "ocr_confidence": page_conf,
                            "document_category": doc_category,
                        },
                    })
                continue

            if QUESTION_RE.match(stripped):
                commit_paragraph()
                current_heading = stripped
                in_answer_key_region = False
                continue

            chapter_m = CHAPTER_RE.match(stripped)
            if chapter_m:
                commit_paragraph()
                if chapter_m.group(4) and chapter_m.group(4).strip():
                    current_chapter = stripped
                    expecting_chapter_title = False
                else:
                    current_chapter = stripped
                    expecting_chapter_title = True
                current_section = None
                current_heading = None
                in_answer_key_region = False
                continue

            if expecting_chapter_title:
                commit_paragraph()
                if len(stripped) < 120:
                    current_chapter = f"{current_chapter} - {stripped}"
                expecting_chapter_title = False
                continue

            section_m = SECTION_RE.match(stripped)
            if section_m:
                commit_paragraph()
                current_section = stripped
                current_heading = None
                in_answer_key_region = False
                continue

            if matches_any(stripped, ANSWER_KEY_PATTERNS):
                commit_paragraph()
                current_heading = stripped
                in_answer_key_region = True
                continue

            if is_heading(stripped) and not paragraph_buffer:
                current_heading = stripped
                if re.match(r"^(Answer|Key)", stripped, re.IGNORECASE):
                    in_answer_key_region = True
                else:
                    in_answer_key_region = False
                continue

            paragraph_buffer.append(stripped)

        commit_paragraph()

    blocks = link_exercises_to_answers(blocks)

    return {
        "document_path": doc_path,
        "document_category": doc_category,
        "blocks": blocks,
    }


def make_exercise_key(chapter: Optional[str], section: Optional[str]) -> Optional[str]:
    """Create key for exercise to answer key matching."""
    if not chapter:
        return None
    return f"{chapter}||{section or ''}"


def link_exercises_to_answers(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Link exercise blocks to corresponding answer key blocks."""
    exercise_index: Dict[str, int] = {}
    for i, blk in enumerate(blocks):
        if blk["type"] == "exercise":
            key = make_exercise_key(
                blk["metadata"].get("chapter"),
                blk["metadata"].get("section"),
            )
            if key:
                exercise_index[key] = i

    for i, blk in enumerate(blocks):
        if blk["type"] != "answer_key":
            continue

        key = make_exercise_key(
            blk["metadata"].get("chapter"),
            blk["metadata"].get("section"),
        )
        if not key:
            key = make_exercise_key(blk["metadata"].get("chapter"), "")

        if key and key in exercise_index:
            ex_idx = exercise_index[key]
            ex_id = f"block_{ex_idx}"
            ans_id = f"block_{i}"
            blocks[ex_idx]["metadata"]["linked_answer_id"] = ans_id
            blk["metadata"]["linked_exercise_id"] = ex_id

        blk["metadata"]["retrieval_priority"] = "low"

    return blocks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyse document structure into typed blocks.")
    parser.add_argument("input_file", help="Path to cleaned JSON file.")
    parser.add_argument("output_file", help="Path to output structured JSON file.")
    parser.add_argument("--category", default="general", help="Document category.")
    args = parser.parse_args()

    with open(args.input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    structured = parse_document(data, doc_category=args.category)

    with open(args.output_file, "w", encoding="utf-8") as f:
        json.dump(structured, f, ensure_ascii=False, indent=2)

    from collections import Counter
    type_counts = Counter(b["type"] for b in structured["blocks"])
    total = len(structured["blocks"])
    print(f"Parsed {total} blocks from {structured['document_path']}")
    for bt, cnt in type_counts.most_common():
        print(f"  {bt:<16s} {cnt:>5d}")
