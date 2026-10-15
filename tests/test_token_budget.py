import json
from types import SimpleNamespace

from chatbot import response_generator as response_generator_module
from chatbot.prompts import (
    champion_synergy_prompt,
    champion_team_composition_prompt,
    counter_champion_prompt,
    general_response_prompt,
    intent_classification_prompt,
    team_building_prompt,
    team_counter_prompt,
)
from chatbot.response_generator import ResponseGenerator
from chatbot.response_prompts import select_response_prompt
from chatbot.token_budget import (
    estimate_tokens,
    fit_reference_context,
    format_recent_history,
    response_token_budget,
    truncate_to_token_budget,
)


def test_output_budget_is_intent_aware_and_respects_configured_maximum():
    assert response_token_budget("ITEM_INFO", 2048) == 256
    assert response_token_budget("TEAM_COMPOSITION_BUILDING", 2048) == 768
    assert response_token_budget("TEAM_COMPOSITION_BUILDING", 400) == 400
    assert response_token_budget("UNKNOWN", 2048) == 512


def test_truncate_to_token_budget_preserves_text_when_it_fits():
    text = "Short verified context."

    assert truncate_to_token_budget(text, estimate_tokens(text)) == text


def test_truncate_to_token_budget_caps_long_text():
    result = truncate_to_token_budget("verified " * 1000, 100)

    assert estimate_tokens(result) <= 100
    assert result.startswith("verified")
    assert result.endswith("[Context shortened to fit the token budget.]")


def test_reference_context_respects_model_window():
    context = "verified " * 10000
    result = fit_reference_context(
        context=context,
        question="Who counters Yasuo?",
        template=general_response_prompt,
        system_prompt="Answer using verified data.",
        context_window=1200,
        output_tokens=256,
        max_reference_tokens=2048,
    )

    assert estimate_tokens(result) <= 2048
    assert estimate_tokens(result) < estimate_tokens(context)


def test_recent_history_is_bounded_and_prioritizes_latest_messages():
    history = [
        {"role": "user", "content": "old question " * 500},
        {"role": "assistant", "content": "old answer " * 500},
        {"role": "user", "content": "new question"},
        {"role": "assistant", "content": "new answer"},
    ]

    result = format_recent_history(history, max_tokens=64)

    assert estimate_tokens(result) <= 64
    assert "new answer" in result


def test_composition_prompt_is_selected_for_composition_intent():
    selected = select_response_prompt(
        "CHAMPION_TEAM_COMPOSITION",
        {"is_champion_composition": True},
        "Build a team around Jinx",
    )

    assert selected is champion_team_composition_prompt


def test_response_prompts_render_without_placeholders_and_keep_grounding():
    templates = (
        general_response_prompt,
        counter_champion_prompt,
        team_counter_prompt,
        team_building_prompt,
        champion_synergy_prompt,
        champion_team_composition_prompt,
    )

    for template in templates:
        rendered = template.format(question="Who counters Yasuo?", data="Verified facts.")
        assert "Who counters Yasuo?" in rendered
        assert "Verified facts." in rendered
        assert "{question}" not in rendered
        assert "{data}" not in rendered
        assert "only" in template.lower() or "documented" in template.lower()


def test_intent_prompt_has_compact_json_schema_and_classifier_fits_token_cap():
    rendered = intent_classification_prompt.format(question="Jinx base stats")
    schema_text = rendered.split("null or [] for unknown lists:\n", maxsplit=1)[1]
    schema_text = schema_text.split("\n\nQuestion:", maxsplit=1)[0]
    schema = json.loads(schema_text)

    assert estimate_tokens(intent_classification_prompt) <= 310
    assert schema["intent"] == "INTENT_NAME"
    assert schema["champion_name"] is None
    assert schema["enemy_champions"] is None


def test_generator_passes_intent_specific_output_limit(monkeypatch):
    captured = {}

    def create_completion(**kwargs):
        captured.update(kwargs)
        message = SimpleNamespace(
            content="A concise, verified answer using only the available item facts and no unsupported details."
        )
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    generator = ResponseGenerator()
    monkeypatch.setattr(generator.client.chat.completions, "create", create_completion)
    monkeypatch.setattr(response_generator_module, "is_ollama_available", lambda _: True)

    answer = generator.generate(
        "What does this item do?",
        {"intent": "ITEM_INFO", "structured_data": {"name": "Test Item"}},
    )

    assert answer.startswith("A concise, verified answer")
    assert captured["max_tokens"] == 256
    assert captured["extra_body"]["num_predict"] == 256
