"""
Token counting utilities for the chunking pipeline.

Uses BAAI/bge-m3 tokenizer if transformers is available, or falls back to
a regex-based word split approximation.
"""

import re
from typing import List

CHUNK_CONFIG = {
    "model_name": "BAAI/bge-m3",
    "hard_cap": 512,
    "soft_target": 300,
    "overlap": 50,
    "min_chunk": 30,
}

tokenizer = None
USE_FALLBACK = False


def init_tokenizer():
    """Lazy-load HuggingFace tokenizer or enable regex fallback."""
    global tokenizer, USE_FALLBACK

    if tokenizer is not None:
        return

    try:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(CHUNK_CONFIG["model_name"])
    except Exception:
        USE_FALLBACK = True
        tokenizer = "fallback"


def count_tokens(text: str) -> int:
    """
    Calculate the number of tokens in text.

    Parameters:
        text: Input string.

    Returns:
        Integer token count.
    """
    init_tokenizer()

    if USE_FALLBACK:
        words = text.split()
        return int(len(words) * 1.3)

    return len(tokenizer.encode(text, add_special_tokens=False))


SENT_RE = re.compile(r'(?<=[.!?])\s+(?=[A-Z"\'])')


def split_into_sentences(text: str) -> List[str]:
    """
    Split text into sentence units using regex lookahead.
    Falls back to line splits if no sentence delimiters are found.
    """
    sentences = [s.strip() for s in SENT_RE.split(text) if s.strip()]

    if len(sentences) <= 1 and "\n" in text:
        sentences = [s.strip() for s in text.split("\n") if s.strip()]

    return sentences if sentences else [text]


if __name__ == "__main__":
    samples = [
        "We use the present continuous for things happening now.",
        "Cho tôi collocation của từ mountain.",
        "mountain noun\nADJ. big, great, high, huge, towering\nVERB + MOUNTAIN ascend, climb, scale",
    ]
    print(f"Tokenizer: {'fallback (regex)' if USE_FALLBACK else CHUNK_CONFIG['model_name']}")
    print(f"Config: {CHUNK_CONFIG}\n")
    for s in samples:
        print(f"  {count_tokens(s):>4d} tokens | {s[:72]}{'...' if len(s) > 72 else ''}")
