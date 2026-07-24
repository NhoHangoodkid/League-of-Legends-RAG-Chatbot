"""
token_utils.py - Token counting utilities for the chunking pipeline.

Uses BAAI/bge-m3 tokenizer if transformers is available, or falls back to
a regex-based word split approximation.

Recommended execution command / CLI Usage Example:
    python src/chunking/token_utils.py
"""

import re

chunk_config = {
    "model_name": "BAAI/bge-m3",
    "hard_cap": 512,
    "soft_target": 300,
    "overlap": 50,
    "min_chunk": 30,
}

tokenizer = None
use_fallback = False


def init_tokenizer():
    """Lazy-load HuggingFace tokenizer or enable regex fallback."""
    global tokenizer, use_fallback

    if tokenizer is not None:
        return

    try:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(chunk_config["model_name"])
    except Exception:
        use_fallback = True
        tokenizer = "fallback"


def count_tokens(text):
    """
    Calculate the number of tokens in text.

    Parameters:
        text: Input string.

    Returns:
        Integer token count.
    """
    init_tokenizer()

    if use_fallback:
        words = text.split()
        return int(len(words) * 1.3)

    return len(tokenizer.encode(text, add_special_tokens=False))


sent_re = re.compile(r'(?<=[.!?])\s+(?=[A-Z"\'])')


def split_into_sentences(text):
    """
    Split text into sentence units using regex lookahead.
    Falls back to line splits if no sentence delimiters are found.
    """
    sentences = [s.strip() for s in sent_re.split(text) if s.strip()]

    if len(sentences) <= 1 and "\n" in text:
        sentences = [s.strip() for s in text.split("\n") if s.strip()]

    return sentences if sentences else [text]


if __name__ == "__main__":
    samples = [
        "We use the present continuous for things happening now.",
        "Get collocations for the word mountain.",
        "mountain noun\nADJ. big, great, high, huge, towering\nVERB + MOUNTAIN ascend, climb, scale",
    ]
    print(f"Tokenizer: {'fallback (regex)' if use_fallback else chunk_config['model_name']}")
    print(f"Config: {chunk_config}")
    for s in samples:
        print(f"{count_tokens(s)} tokens | {s[:72]}{'...' if len(s) > 72 else ''}")
