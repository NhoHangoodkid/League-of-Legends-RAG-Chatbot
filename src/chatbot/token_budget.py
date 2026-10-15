"""Token-budget helpers for LLM prompts and responses."""

from math import ceil


SHORT_RESPONSE_INTENTS = frozenset({
    "ARAM_QUERY",
    "CHAMPION_BASE_STATS",
    "CHAMPION_STATS_AT_LEVEL",
    "ITEM_INFO",
    "RUNE_INFO",
    "SKILL_COOLDOWN",
    "SKILL_DAMAGE_AT_LEVEL",
    "SKILL_INFO",
    "SKILL_MANA_COST",
})

LONG_RESPONSE_INTENTS = frozenset({
    "COUNTER_QUERY",
    "ROLE_COUNTER_PICK",
    "TEAM_COMPOSITION_BUILDING",
    "TEAM_COUNTER_ANALYSIS",
})


def estimate_tokens(text):
    """Conservatively estimate token count without loading a model tokenizer."""
    return ceil(len(text.encode("utf-8")) / 3)


def truncate_to_token_budget(text, max_tokens, marker="\n[Context shortened to fit the token budget.]"):
    """Trim text to a conservative token estimate while preserving its beginning."""
    if max_tokens <= 0:
        return ""
    if estimate_tokens(text) <= max_tokens:
        return text

    marker_tokens = estimate_tokens(marker)
    if marker_tokens < max_tokens:
        content_budget = max_tokens - marker_tokens
    else:
        marker = ""
        content_budget = max_tokens
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if estimate_tokens(text[:middle]) <= content_budget:
            low = middle
        else:
            high = middle - 1
    return text[:low].rstrip() + marker


def response_token_budget(intent, configured_max):
    """Return a per-intent output cap, bounded by the configured model maximum."""
    configured_max = max(1, int(configured_max))
    if intent in SHORT_RESPONSE_INTENTS:
        target = 256
    elif intent in LONG_RESPONSE_INTENTS:
        target = 768
    else:
        target = 512
    return min(configured_max, target)


def format_recent_history(history, max_tokens=256, max_messages=4):
    """Keep compact recent turns for follow-up classification, not full answers."""
    if not history:
        return ""

    recent_messages = history[-max_messages:]
    message_budget = max(1, max_tokens // (len(recent_messages) + 1))
    lines = []
    for message in recent_messages:
        role = "User" if message.get("role") == "user" else "Assistant"
        content = str(message.get("content") or "").strip()
        if content:
            content = truncate_to_token_budget(content, message_budget, marker="...")
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def fit_reference_context(
    context,
    question,
    template,
    system_prompt,
    context_window,
    output_tokens,
    max_reference_tokens=2048,
    safety_margin=256,
):
    """Fit reference data to a bounded share of the model's input context."""
    fixed_prompt = template.format(question=question, data="")
    fixed_tokens = estimate_tokens(f"{system_prompt}\n{fixed_prompt}")
    available_tokens = min(
        max_reference_tokens,
        context_window - output_tokens - safety_margin - fixed_tokens,
    )
    return truncate_to_token_budget(context, available_tokens)
