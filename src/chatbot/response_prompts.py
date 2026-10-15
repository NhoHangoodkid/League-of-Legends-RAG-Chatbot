"""Select the response prompt that best matches the classified question."""

from chatbot.prompts import (
    champion_synergy_prompt,
    champion_team_composition_prompt,
    counter_champion_prompt,
    general_response_prompt,
    team_building_prompt,
    team_counter_prompt,
)


def select_response_prompt(intent, structured_data, question):
    """Choose a specialized prompt when verified data supports one."""
    question_lower = question.lower()
    if (
        structured_data.get("is_champion_composition")
        or intent == "CHAMPION_TEAM_COMPOSITION"
        or (
            structured_data.get("best_team_compositions")
            and any(word in question_lower for word in ("đội hình", "team comp", "lineup", "composition"))
        )
    ):
        return champion_team_composition_prompt
    if structured_data.get("is_synergy_query") or intent == "SYNERGY_QUERY" or structured_data.get("best_duos"):
        return champion_synergy_prompt
    if structured_data.get("is_counter_query") or (intent == "COUNTER_QUERY" and structured_data.get("weak_against")):
        return counter_champion_prompt
    if (
        structured_data.get("is_team_counter_analysis")
        or intent == "TEAM_COUNTER_ANALYSIS"
        or (
            structured_data.get("is_composition_query")
            and any(word in question_lower for word in ("counter", "against", "beat", "deal with", "facing", "versus", "vs"))
        )
    ):
        return team_counter_prompt
    if structured_data.get("is_composition_building") or intent == "TEAM_COMPOSITION_BUILDING":
        return team_building_prompt
    return general_response_prompt
