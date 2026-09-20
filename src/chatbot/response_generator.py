"""
Response Generator for LoL Knowledge Bot.

Converts retrieved game knowledge (Graph Knowledge Base + FAISS Vector Passages)
into natural, fluent, and accurate answers in English using local LLM via Ollama.
Includes a clean direct fallback formatter if the LLM is offline or times out.
"""

import json
import re

import httpx
from openai import OpenAI

from chatbot.config import llm_model, llm_num_ctx, llm_num_predict, llm_temperature, ollama_base_url
from chatbot.intent_classifier import is_ollama_available
from chatbot.prompts import (
    champion_synergy_prompt,
    champion_team_composition_prompt,
    conversation_system_prompt,
    counter_champion_prompt,
    general_response_prompt,
    response_generation_prompt,
    team_building_prompt,
    team_counter_prompt,
)


class ResponseGenerator:
    """Generate natural language responses in English from retrieved Graph and Vector data."""

    def __init__(self, base_url = ollama_base_url, model = llm_model):
        self.base_url = base_url
        self.model = model
        self.client = OpenAI(
            base_url = base_url,
            api_key = "ollama",
            timeout = httpx.Timeout(600.0, connect = 10.0),
            max_retries = 0,
        )

    def serialize_for_llm(self, data, question = ""):
        """
        Assemble high-density context from RAG passages (Graph + Vector) and telemetry for the LLM.
        """
        sections = []
        # 1. Specific Structured Facts (Highest priority, verified ground-truth from MongoDB)
        s_data = data.get("structured_data", {})
        intent = data.get("intent", "")
        fact_lines = []
        if isinstance(s_data, dict) and s_data:
            champ = s_data.get("champion") or s_data.get("name")
            if champ:
                title = s_data.get("title", "")
                fact_lines.append(f"Champion: {champ} ({title})" if title else f"Champion: {champ}")

            # Mechanics / wind wall / spell shield
            if s_data.get("wind_wall_verdict"):
                fact_lines.append(f"Wind Wall Interaction: {s_data['wind_wall_verdict']}")
            if s_data.get("spellshield_verdict"):
                fact_lines.append(f"Spell Shield Interaction: {s_data['spellshield_verdict']}")

            # Skin catalog query
            if s_data.get("is_skin_query") or s_data.get("unique_skin_count"):
                u_cnt = s_data.get("unique_skin_count", len(s_data.get("actual_skins", [])))
                c_cnt = s_data.get("chroma_count", 0)
                fact_lines.append(f"Unique Champion Skins: {u_cnt} standalone skins (plus {c_cnt} chromas/cosmetic variants).")
                actual_skins = s_data.get("actual_skins", [])
                if actual_skins:
                    fact_lines.append(f"Actual Unique Skins: {', '.join(actual_skins)}")
                leg_prest = s_data.get("legendary_prestige", [])
                if leg_prest:
                    fact_lines.append(f"Legendary and Prestige Releases: {', '.join(leg_prest)}")
                themes = s_data.get("thematic_groups", {})
                if themes:
                    theme_summary = "; ".join(f"{t}: {', '.join(sk_list)}" for t, sk_list in themes.items())
                    fact_lines.append(f"Key Thematic Universes: {theme_summary}")

            # Lore and narrative relationships
            if s_data.get("is_lore_query"):
                c1 = s_data.get("champion")
                c2 = s_data.get("interaction_champion")
                if c2 and s_data.get("is_conflict_lore_query"):
                    fact_lines.append(f"Canon Lore Conflict & Relationship: {c1} and {c2}")
                    fact_lines.append(f"Region: {s_data.get('region') or s_data.get('interaction_region', 'Ionia')}")
                    fact_lines.append(f"{c1} ({s_data.get('title', '')}) Background: {s_data.get('shortLore', '')}")
                    fact_lines.append(f"{c2} ({s_data.get('interaction_title', '')}) Background: {s_data.get('interaction_shortLore', '')}")
                    names_lower = {str(c1).lower(), str(c2).lower()}
                    if "zed" in names_lower and "shen" in names_lower:
                        fact_lines.append("Core Canon Conflict Elements:")
                        fact_lines.append("  - Brothers in the Kinkou Order: Raised together under Master Kusho, closest friends and top acolytes.")
                        fact_lines.append("  - Hunt for Jhin: Zed demanded Jhin's execution; Master Kusho only imprisoned him, planting resentment.")
                        fact_lines.append("  - Noxian Invasion & Shadow Magic: Kinkou remained neutral; Zed broke into temple, took shadow magic, founded Order of Shadow.")
                        fact_lines.append("  - Slaying of Master Kusho: Zed returned, Kusho was slain, temple seized; Shen became Eye of Twilight.")
                else:
                    fact_lines.append(f"Champion Lore: {s_data.get('shortLore', '')}")
                rel = s_data.get("related_champions", [])
                if rel and not s_data.get("is_conflict_lore_query"):
                    rel_names = [r.get("name") if isinstance(r, dict) else str(r) for r in rel if r]
                    fact_lines.append(f"Related Lore Characters: {', '.join(rel_names)}")

            # ARAM balance
            if s_data.get("is_aram_query") or s_data.get("aram_modifiers"):
                fact_lines.append(f"ARAM Modifiers: {s_data.get('aram_modifiers', {})}")

            # Specific stat calculations
            if s_data.get("is_stat_calculation") or s_data.get("stats_at_level"):
                lvl = s_data.get("level") or s_data.get("character_level", 1)
                stats = s_data.get("stats_at_level") or s_data.get("stats", {})
                fact_lines.append(f"Base Stats at Level {lvl}: {stats}")

            # Team composition building and drafting
            if s_data.get("is_composition_building"):
                fact_lines.append(f"Team Composition to Build: {s_data.get('name')}")
                if s_data.get("description"):
                    fact_lines.append(f"Strategic Profile: {s_data.get('description')}")
                if s_data.get("power_curve"):
                    fact_lines.append(f"Power Curve Focus: {s_data.get('power_curve')}")

                # Dynamic archetype roles
                if s_data.get("role_1_title") and s_data.get("role_1_champions"):
                    fact_lines.append(f"{s_data['role_1_title']}: {', '.join(s_data['role_1_champions'])}")
                elif s_data.get("hypercarries"):
                    fact_lines.append(f"Core Recommended Hypercarries: {', '.join(s_data['hypercarries'])}")

                if s_data.get("role_2_title") and s_data.get("role_2_champions"):
                    fact_lines.append(f"{s_data['role_2_title']}: {', '.join(s_data['role_2_champions'])}")
                elif s_data.get("peel_supports"):
                    fact_lines.append(f"Core Recommended Peel and Enchanter Supports: {', '.join(s_data['peel_supports'])}")

                if s_data.get("frontline_tanks"):
                    fact_lines.append(f"Core Recommended Frontline Wardens and Tanks: {', '.join(s_data['frontline_tanks'])}")

                if s_data.get("sample_draft"):
                    sd = s_data["sample_draft"]
                    sd_str = f"Top: {sd.get('top')}, Jungle: {sd.get('jungle')}, Mid: {sd.get('mid')}, Bot: {sd.get('bot')}, Support: {sd.get('support')}"
                    fact_lines.append(f"Recommended 5-Position Sample Draft: {sd_str}")

                if s_data.get("win_condition"):
                    fact_lines.append(f"Primary Win Condition: {s_data['win_condition']}")

                if s_data.get("champion_abilities"):
                    fact_lines.append("Verified Core Champion Abilities:")
                    for c_name, ab_str in s_data["champion_abilities"].items():
                        fact_lines.append(f"  * {c_name}: {ab_str}")

            # Team composition counter analysis
            if s_data.get("is_composition_query") or s_data.get("is_team_counter_analysis"):
                title = s_data.get("role_title") or s_data.get("comp_title") or s_data.get("comp_archetype") or "Enemy Team"
                fact_lines.append(f"Target Enemy Composition to Counter: {title}")
                if s_data.get("description"):
                    fact_lines.append(f"Enemy Composition Identity: {s_data.get('description')}")
                if s_data.get("weaknesses") or s_data.get("shared_weaknesses"):
                    w_list = s_data.get("weaknesses") or s_data.get("shared_weaknesses")
                    fact_lines.append(f"Core Enemy Weaknesses to Exploit: {', '.join(w_list[:4])}")
                if s_data.get("tactical_tips") or s_data.get("macro_strategy"):
                    tips = s_data.get("tactical_tips") or s_data.get("macro_strategy")
                    if isinstance(tips, list):
                        fact_lines.append("Tactical Gameplay Tips Against this Comp:\n" + "\n".join(f"  - {t}" for t in tips[:4]))
                    else:
                        fact_lines.append(f"Strategic Counter Gameplan: {tips}")
                if s_data.get("counter_picks") or s_data.get("cross_counter_picks"):
                    cp_list = s_data.get("counter_picks") or s_data.get("cross_counter_picks")
                    c_lines = []
                    for cp in cp_list[:6]:
                        c_name = cp.get("champion")
                        rsn = cp.get("reason", cp.get("tactical_reason", ""))
                        c_lines.append(f"  - {c_name}: {rsn}")
                    fact_lines.append("Top Verified Counter Picks Against this Comp:\n" + "\n".join(c_lines))
                if s_data.get("counter_items") or s_data.get("recommended_items"):
                    ci_list = s_data.get("counter_items") or s_data.get("recommended_items")
                    if ci_list and isinstance(ci_list[0], dict):
                        i_lines = [f"  - {ci.get('item')}: {ci.get('purpose', '')}" for ci in ci_list[:6]]
                        fact_lines.append("Top Verified Counter Items Against this Comp:\n" + "\n".join(i_lines))
                    else:
                        fact_lines.append(f"Top Verified Counter Items: {', '.join(str(x) for x in ci_list[:6])}")
                if s_data.get("champion_abilities"):
                    fact_lines.append("Verified Core Champion Abilities for Counter Picks:")
                    for c_name, ab_str in s_data["champion_abilities"].items():
                        fact_lines.append(f"  * {c_name}: {ab_str}")

            # Champion 1v1 / Lane Counter Query
            if s_data.get("is_counter_query") or (s_data.get("weak_against") and not s_data.get("is_team_counter_analysis")):
                target_c = s_data.get("champion") or champ
                lane_str = f" in {s_data.get('lane').upper()} lane" if s_data.get("lane") else ""
                direction = s_data.get("counter_direction") or "countered_by"
                if direction == "counters":
                    fact_lines.append(f"Target Champion: {target_c} (Analyzing matchups where {target_c} is STRONG){lane_str}")
                    strong_list = s_data.get("strong_against", [])
                    if strong_list:
                        s_lines = [f"  - {sa.get('champion')}: {sa.get('reason', '')}" for sa in strong_list[:6]]
                        fact_lines.append(f"Champions {target_c} Counters / Favorable Matchups:\n" + "\n".join(s_lines))
                else:
                    fact_lines.append(f"Target Champion to Counter: {target_c}{lane_str}")
                    if s_data.get("weaknesses"):
                        fact_lines.append(f"Core Weaknesses of {target_c}:\n" + "\n".join(f"  - {w}" for w in s_data["weaknesses"][:4]))
                    if s_data.get("enemytips"):
                        fact_lines.append(f"Official Counterplay Tips Against {target_c}:\n" + "\n".join(f"  - {et}" for et in s_data["enemytips"][:3]))
                    if s_data.get("tactical_tips"):
                        fact_lines.append(f"Lane and Tactical Tips Against {target_c}:\n" + "\n".join(f"  - {tt}" for tt in s_data["tactical_tips"][:4]))
                    weak_list = s_data.get("weak_against", [])
                    if weak_list:
                        w_lines = [f"  - {wa.get('champion')}: {wa.get('reason', '')}" for wa in weak_list[:6]]
                        fact_lines.append(f"Top Verified Counter Picks Against {target_c}:\n" + "\n".join(w_lines))
                    if s_data.get("counter_items"):
                        c_items = s_data.get("counter_items")
                        if c_items and isinstance(c_items[0], dict):
                            ci_str = ", ".join(ci.get("item", "") for ci in c_items[:5])
                        else:
                            ci_str = ", ".join(str(it) for it in c_items[:5])
                        fact_lines.append(f"Essential Counter Items Against {target_c}: {ci_str}")
                if s_data.get("champion_abilities"):
                    fact_lines.append("Verified Core Abilities for Counter Champions:")
                    for c_name, ab_str in s_data["champion_abilities"].items():
                        fact_lines.append(f"  * {c_name}: {ab_str}")

            # Champion-Centric 5-Man Team Compositions
            if s_data.get("is_champion_composition") or (s_data.get("best_team_compositions") and (intent == "CHAMPION_TEAM_COMPOSITION" or any(w in str(question).lower() for w in ["đội hình", "team comp", "lineup", "composition"]))):
                focus_c = s_data.get("focus_champion") or s_data.get("champion") or champ or "Champion"
                comps = s_data.get("best_team_compositions", [])
                fact_lines.append(f"Focus Champion: {focus_c}")
                if comps:
                    fact_lines.append(f"Top Verified 5-Man Team Compositions Centered on {focus_c}:")
                    for i, cp in enumerate(comps[:2], 1):
                        c_name = cp.get("comp_name", f"Composition {i}")
                        arch = cp.get("archetype_name") or cp.get("archetype", "Teamfight")
                        wr = cp.get("win_rate")
                        games = cp.get("games_played", 0)
                        lu = cp.get("lineup", {})
                        fact_lines.append(f"  [Composition {i}] {c_name}")
                        fact_lines.append(f"    Archetype: {arch} | Win Rate: {wr}% ({games} games)")
                        fact_lines.append(f"    Lineup: Top={lu.get('top')}, Jungle={lu.get('jungle')}, Mid={lu.get('mid')}, Bot={lu.get('bot')}, Support={lu.get('support')}")
                        teammate_syn = cp.get("teammate_synergies", {})
                        if teammate_syn:
                            fact_lines.append("    Role Synergies with Focus Champion:")
                            for r_k, syn_text in teammate_syn.items():
                                fact_lines.append(f"      - {r_k.upper()}: {syn_text}")
                        win_cond = cp.get("win_condition")
                        if win_cond:
                            fact_lines.append(f"    Win Condition: {win_cond}")

            # Champion Duo Synergy / Best Partners Query
            if s_data.get("is_synergy_query") or (s_data.get("best_duos") and not s_data.get("is_champion_composition")):
                target_c = s_data.get("champion") or champ or "Champion"
                primary_role = s_data.get("role", "")
                role_str = f" (Primary Role: {primary_role})" if primary_role else ""
                fact_lines.append(f"Target Champion: {target_c}{role_str}")

                t_insights = s_data.get("tactical_insights", [])
                if t_insights:
                    fact_lines.append("Tactical Profile and Insights:\n" + "\n".join(f"  - {ti}" for ti in t_insights[:4]))

                duo_list = s_data.get("best_duos") or s_data.get("top_duos") or []
                if duo_list:
                    fact_lines.append("Top Verified Duo Partners (Empirical Match Data):")
                    for d in duo_list[:5]:
                        p_name = d.get("partner") or d.get("champion", "Unknown")
                        p_role = d.get("role", "")
                        wr = d.get("win_rate") or d.get("soloq_winrate") or d.get("winrate") or d.get("winRate")
                        games = d.get("sample_games") or d.get("soloq_games") or d.get("games")
                        rsn = d.get("synergy_reason") or d.get("reason", "")
                        tag = d.get("synergy_tag", "")

                        stats_str = f"Win Rate: {wr}% ({games} games)" if wr is not None else "Stats: N/A"
                        tag_str = f" [{tag}]" if tag else ""
                        fact_lines.append(f"  * Partner: {p_name} ({p_role}) - {stats_str}{tag_str}")
                        if rsn:
                            fact_lines.append(f"    Synergy Mechanic: {rsn}")

            # Recommended Build Query
            if s_data.get("core_items") or s_data.get("full_build") or intent == "BUILD_QUERY":
                b_champ = s_data.get("champion") or s_data.get("name") or champ or "Champion"
                fact_lines.append(f"Recommended Build and Itemization for {b_champ}:")
                if s_data.get("starting_items"):
                    fact_lines.append(f"  Starting Items: {', '.join(str(it) for it in s_data['starting_items'])}")
                if s_data.get("core_items"):
                    fact_lines.append(f"  Core Legendary Items: {', '.join(str(it) for it in s_data['core_items'])}")
                if s_data.get("full_build"):
                    fact_lines.append(f"  Full 6-Item Build: {', '.join(str(it) for it in s_data['full_build'])}")
                if s_data.get("summoner_spells"):
                    fact_lines.append(f"  Summoner Spells: {', '.join(str(sp) for sp in s_data['summoner_spells'])}")
                runes_data = s_data.get("runes", {})
                if isinstance(runes_data, dict):
                    if runes_data.get("keystone"):
                        fact_lines.append(f"  Keystone Rune: {runes_data.get('keystone')}")
                    if runes_data.get("primary"):
                        fact_lines.append(f"  Primary Runes: {', '.join(str(r) for r in runes_data['primary'])}")
                    if runes_data.get("secondary"):
                        fact_lines.append(f"  Secondary Runes: {', '.join(str(r) for r in runes_data['secondary'])}")

            # Item Information Query
            if (s_data.get("cost") is not None and (s_data.get("buildFrom") is not None or s_data.get("buildInto") is not None or s_data.get("stats"))) or intent == "ITEM_INFO":
                i_name = s_data.get("name") or "Item"
                cost_val = s_data.get("cost", {}).get("total", 0) if isinstance(s_data.get("cost"), dict) else (s_data.get("cost") or 0)
                fact_lines.append(f"Item Name: {i_name} (Total Cost: {cost_val} gold)")
                stats_val = s_data.get("stats", {})
                if stats_val:
                    fact_lines.append(f"Item Stats: {stats_val}")
                if s_data.get("description"):
                    fact_lines.append(f"Item Description and Passives: {s_data['description']}")
                if s_data.get("buildFrom"):
                    fact_lines.append(f"Builds From (Components): {', '.join(str(b) for b in s_data['buildFrom'])}")
                if s_data.get("buildInto"):
                    fact_lines.append(f"Builds Into (Upgrades): {', '.join(str(b) for b in s_data['buildInto'])}")

            # Rune Information Query
            if s_data.get("tree") or s_data.get("longDescription") or intent == "RUNE_INFO":
                r_name = s_data.get("name") or "Rune"
                fact_lines.append(f"Rune: {r_name} (Tree: {s_data.get('tree', 'Precision')})")
                fact_lines.append(f"Rune Function and Passives: {s_data.get('longDescription') or s_data.get('description', '')}")

            # Champion Comparison Query
            if s_data.get("comparison") or s_data.get("matchup_info") or intent == "CHAMPION_COMPARISON":
                champs_comp = s_data.get("champions", [])
                fact_lines.append(f"Champion Comparison: {' vs '.join(champs_comp)}")
                matchup_info = s_data.get("matchup_info") or {}
                if isinstance(matchup_info, dict) and matchup_info:
                    winner = matchup_info.get("winner") or matchup_info.get("advantaged")
                    loser = matchup_info.get("loser") or matchup_info.get("disadvantaged")
                    wr = matchup_info.get("win_rate")
                    rsn = matchup_info.get("reason", "")
                    fact_lines.append(f"Direct Matchup Relationship: {winner} counters {loser} with {wr}% win rate. Reason: {rsn}")
                comp_stats = s_data.get("comparison", {})
                if comp_stats:
                    fact_lines.append(f"Comparative Base Stats: {comp_stats}")

            # Role Counter Pick Query
            if s_data.get("is_role_counter_pick") or intent == "ROLE_COUNTER_PICK":
                fact_lines.append(f"Role Counter Pick Strategy: Best {s_data.get('role_title', 'Champions')} Against {s_data.get('target', 'Opponents')}")
                top_c = s_data.get("top_champions", [])
                for ch in top_c[:5]:
                    c_name = ch.get("champion") or ch.get("name")
                    mech = ch.get("key_mechanics") or ch.get("reason", "")
                    fact_lines.append(f"  * Recommended Pick: {c_name} (Mechanics: {mech})")
                if s_data.get("recommended_items"):
                    fact_lines.append(f"Essential Counter Items: {', '.join(str(it) for it in s_data['recommended_items'][:4])}")
                if s_data.get("tactical_guidelines"):
                    t_guidelines = s_data["tactical_guidelines"]
                    g_str = " ".join(str(g).strip(".; ") for g in t_guidelines) if isinstance(t_guidelines, list) else str(t_guidelines)
                    fact_lines.append(f"Tactical Draft Directives: {g_str}")

            # Skills and Abilities
            if s_data.get("skill_key") or intent in ("SKILL_INFO", "SKILL_COOLDOWN", "SKILL_DAMAGE_AT_LEVEL", "LIST_SKILLS"):
                s_champ = s_data.get("champion") or s_data.get("name") or champ or "Champion"
                if s_data.get("skill_key"):
                    fact_lines.append(f"{s_champ} Ability [{s_data.get('skill_key')}]: {s_data.get('skill_name', '')}")
                    if s_data.get("description"):
                        fact_lines.append(f"  Description: {s_data['description']}")
                    if s_data.get("cooldown"):
                        fact_lines.append(f"  Cooldown: {s_data['cooldown']}")
                    if s_data.get("cost"):
                        fact_lines.append(f"  Cost: {s_data['cost']} ({s_data.get('costType', 'Mana')})")
                    if s_data.get("range"):
                        fact_lines.append(f"  Range: {s_data['range']}")
                    if s_data.get("damageType"):
                        fact_lines.append(f"  Damage Type: {s_data['damageType']}")
                elif s_data.get("abilities"):
                    fact_lines.append(f"{s_champ} Full Ability Kit:")
                    for ab_k, ab_v in s_data["abilities"].items():
                        if isinstance(ab_v, dict) and ab_v.get("name"):
                            fact_lines.append(f"  [{ab_k.upper()}] {ab_v.get('name')}: {ab_v.get('description', '')[:120]}")

            # Lore Query (Single Champion)
            if (s_data.get("is_lore_query") or intent == "LORE_QUERY") and not s_data.get("is_conflict_lore_query"):
                l_champ = s_data.get("champion") or s_data.get("name") or champ or "Champion"
                fact_lines.append(f"Lore and Universe Profile for {l_champ} ({s_data.get('title', '')}):")
                fact_lines.append(f"  Region: {s_data.get('region', 'Runeterra')}")
                if s_data.get("shortLore"):
                    fact_lines.append(f"  Summary Lore: {s_data['shortLore']}")
                stories = s_data.get("stories", [])
                if stories:
                    story_titles = [st.get("title") for st in stories if isinstance(st, dict) and st.get("title")]
                    if story_titles:
                        fact_lines.append(f"  Canon Universe Stories: {', '.join(story_titles[:6])}")
                rel = s_data.get("related_champions", [])
                if rel:
                    fact_lines.append(f"  Related Champions: {', '.join(str(r) for r in rel[:5])}")

            # Semantic Filter Queries (CC, Effect, Playstyle)
            if s_data.get("criteria") or intent in ("CHAMPION_BY_CC", "CHAMPION_BY_EFFECT", "MULTI_PROPERTY_FILTER"):
                fact_lines.append(f"Champions Matching Filter Criteria ({s_data.get('criteria')}): Total {s_data.get('total_matches', 0)} Champions")
                sample_m = s_data.get("sample_matches", [])
                if sample_m:
                    sample_names = [m.get("name") if isinstance(m, dict) else str(m) for m in sample_m]
                    fact_lines.append(f"Sample Champions: {', '.join(sample_names[:12])}")

            # Lane or Role Queries
            if s_data.get("is_role_query") or s_data.get("is_lane_query") or intent in ("ROLE_QUERY", "LANE_QUERY"):
                r_title = s_data.get("role_title") or (s_data.get("lane", "").capitalize() if s_data.get("lane") else "Role")
                fact_lines.append(f"Champion Roster for {r_title}: Total {s_data.get('count', 0)} Champions")
                if s_data.get("dominant_damage"):
                    fact_lines.append(f"Dominant Damage Profile: {s_data['dominant_damage']}")
                sample_r = s_data.get("champions") or [c.get("name") if isinstance(c, dict) else str(c) for c in (s_data.get("sample_champions") or [])]
                if sample_r:
                    fact_lines.append(f"Key Representative Champions: {', '.join(sample_r[:15])}")

            if fact_lines:
                sections.append("=== VERIFIED SPECIFIC GAME ATTRIBUTES ===\n" + "\n".join(fact_lines))

        # 2. Auxiliary Knowledge Source: Graph and Vector RAG Context (passages from FAISS and Neo4j)
        rag_ctx = data.get("rag_retrieved_context", "")
        # For composition drafting, suppress raw database cluster chunks that pollute the draft with 120+ champs and counter tips
        if s_data.get("is_composition_building") or intent == "TEAM_COMPOSITION_BUILDING":
            rag_ctx = ""

        if rag_ctx:
            if fact_lines:
                truncated_rag = rag_ctx.strip()
                if len(truncated_rag) > 1200:
                    truncated_rag = truncated_rag[:1200] + "\n[... additional context omitted for conciseness ...]"
                sections.append(truncated_rag)
            else:
                truncated_rag = rag_ctx.strip()
                if len(truncated_rag) > 2500:
                    truncated_rag = truncated_rag[:2500] + "\n[... additional context omitted for conciseness ...]"
                sections.append(truncated_rag)

        # 3. Anti-hallucination notice if no context found
        if data.get("insufficient_context") or not sections:
            sections.append(
                "=== KNOWLEDGE BASE NOTICE ===\n"
                "[NO VERIFIED INFORMATION FOUND IN KNOWLEDGE BASE FOR THIS QUERY. INFORM USER TRUTHFULLY THAT THIS DATA IS NOT AVAILABLE IN THE SYSTEM.]"
            )

        return "\n\n".join(sections)

    def generate(self, question, retrieved_data):
        """
        Generate natural language response in English by autonomously synthesizing retrieved data.

        Args:
            question: User's question in English.
            retrieved_data: Structured dictionary of game data + RAG context passages.

        Returns:
            Response string synthesized by LLM or direct fallback.
        """
        data_text = self.serialize_for_llm(retrieved_data, question = question)
        s_data = retrieved_data.get("structured_data", {})
        intent = retrieved_data.get("intent", "")
        q_lower = question.lower()

        # Select specialized, hyper-focused prompt template
        if s_data.get("is_champion_composition") or intent == "CHAMPION_TEAM_COMPOSITION" or (s_data.get("best_team_compositions") and any(w in q_lower for w in ["đội hình", "team comp", "lineup", "composition"])):
            template = champion_team_composition_prompt
        elif s_data.get("is_synergy_query") or intent == "SYNERGY_QUERY" or s_data.get("best_duos"):
            template = champion_synergy_prompt
        elif s_data.get("is_counter_query") or (intent == "COUNTER_QUERY" and s_data.get("weak_against")):
            template = counter_champion_prompt
        elif s_data.get("is_team_counter_analysis") or (intent == "TEAM_COUNTER_ANALYSIS") or (s_data.get("is_composition_query") and any(w in q_lower for w in ["counter", "against", "beat", "deal with", "facing", "versus", "vs"])):
            template = team_counter_prompt
        elif s_data.get("is_composition_building") or (intent == "TEAM_COMPOSITION_BUILDING"):
            template = team_building_prompt
        else:
            template = general_response_prompt

        prompt = template.format(
            question = question,
            data = data_text,
        )

        if is_ollama_available(self.base_url):
            try:
                response = self.client.chat.completions.create(
                    model = self.model,
                    messages=[
                        {"role": "system", "content": conversation_system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    max_tokens = llm_num_predict,
                    extra_body={
                        "num_ctx": llm_num_ctx,
                        "num_predict": llm_num_predict,
                        "options": {
                            "think": False,
                            "temperature": 0.3,
                            "num_predict": llm_num_predict,
                        },
                    },
                )
                choice = response.choices[0]
                msg = choice.message
                content = (msg.content or "").strip()
                content = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()
                content = re.sub(r"<think>[\s\S]*$", "", content).strip()

                if not content or len(content) < 80:
                    # Content is empty or model timed out / truncated during thinking -> use verified data fallback
                    return self.format_fallback(retrieved_data, question = question)
                    
                # If model emitted planning steps like "Step 1:" or "We write..." before the actual response
                for start_marker in ["### 1.", "### Core Tactical", "### Composition", "### Strategy", "### 🛡️", "### Matchup"]:
                    if start_marker in content and content.index(start_marker) > 0:
                        content = content[content.index(start_marker):].strip()
                        break

                # Check for residual Chain-of-Thought (CoT) leakage
                cot_leakage_indicators = [
                    "We write a concise",
                    "Let's break down",
                    "We must be strict",
                    "We must be concise",
                    "For Section 1:",
                    "For Section 2:",
                    "For Section 3:",
                    "From Reference Data:",
                ]
                if any(phrase in content for phrase in cot_leakage_indicators) and "### 1." not in content[:30]:
                    # Severe CoT leakage detected without proper headers -> trigger clean data fallback
                    return self.format_fallback(retrieved_data, question = question)

                for marker in [
                    "**CRITICAL ANTI-HALLUCINATION",
                    "CRITICAL ANTI-HALLUCINATION",
                    "**TACTICAL DIRECTIVES",
                    "TACTICAL DIRECTIVES",
                    "**MANDATORY",
                    "MANDATORY",
                    "**MANDATORY PRINCIPLES",
                    "MANDATORY PRINCIPLES",
                    "**FOCUS DIRECTIVE",
                    "FOCUS DIRECTIVE",
                    "**SYNTHESIS GUIDELINES",
                    "SYNTHESIS GUIDELINES",
                ]:
                    if marker in content:
                        content = content.split(marker)[0].strip()

                if content:
                    content_clean = content.rstrip()
                    # Check for premature truncation (missing end punctuation or too brief for drafting/strategy)
                    ends_properly = any(content_clean.endswith(p) for p in [".", "!", "?", '."', ".'", "*)", "**", ".\n"])
                    is_comp = s_data.get("is_composition_building") or intent == "TEAM_COMPOSITION_BUILDING"
                    
                    if is_comp and len(content_clean) < 300:
                        # Composition drafting requires a comprehensive multi-paragraph breakdown
                        return self.format_fallback(retrieved_data, question = question)

                    if len(content_clean) > 80 and ends_properly:
                        return content_clean
                    else:
                        # Incomplete sentence or token truncation -> use verified data fallback
                        return self.format_fallback(retrieved_data, question = question)
            except Exception as e:
                print(f"[ResponseGenerator] LLM notice ({e}). Using direct data fallback...")

        # Fallback direct data formatter
        return self.format_fallback(retrieved_data, question = question)

    def format_fallback(self, data, question = ""):
        """
        Direct, clean fallback synthesizer when local LLM is offline or times out.
        Presents verified structured game facts clearly in formatted Markdown.
        """
        if data.get("insufficient_context"):
            return "ℹ️ **Notice:** The knowledge base currently does not contain information to answer this question."

        lines = []
        s_data = data.get("structured_data", {})
        intent = data.get("intent", "")

        # 1. Format team composition drafting / building data
        if isinstance(s_data, dict) and s_data:
            if s_data.get("is_composition_building") or intent == "TEAM_COMPOSITION_BUILDING":
                cname = s_data.get("name", "Strategic Team Composition")
                desc = s_data.get("description", "A tactical draft designed for synchronized teamplay and objective control.")
                p_curve = s_data.get("power_curve", "Mid-to-Late Game")
                comp_id = (s_data.get("comp_id") or "").lower()

                r1_title = s_data.get("role_1_title") or "Primary Carries"
                r1_champs = s_data.get("role_1_champions") or ["Jinx", "Kog'Maw", "Vayne"]
                r1_str = ", ".join(f"**{c}**" for c in r1_champs[:6])

                r2_title = s_data.get("role_2_title") or "Support and Frontline Enablers"
                r2_champs = s_data.get("role_2_champions") or ["Lulu", "Braum", "Shen"]
                r2_str = ", ".join(f"**{c}**" for c in r2_champs[:6])

                draft = s_data.get("sample_draft", {})
                draft_str = f"**{draft.get('top', 'N/A')}** (Top), **{draft.get('jungle', 'N/A')}** (Jungle), **{draft.get('mid', 'N/A')}** (Mid), **{draft.get('bot', 'N/A')}** (Bot), and **{draft.get('support', 'N/A')}** (Support)" if draft else ""

                win_con = s_data.get("win_condition", "Coordinate vision control and execute front-to-back teamfights around neutral objectives.")

                # Dynamic archetype synthesis
                if "hypercarry" in comp_id or "protect" in comp_id:
                    p1 = f"For a **{cname}**, the strategic gameplan revolves around {desc.strip('.')}. This draft's power curve scales towards the **{p_curve}**, where an elite, fully itemized marksman backed by dedicated defensive shields and buffs delivers unmatched sustained DPS."
                    p2 = f"To draft this composition effectively, your primary damage anchor must prioritize {r1_title} such as {r1_str}. To enable these fragile carries to free-fire without fear of enemy assassins or divers, your squad must be anchored by {r2_title} like {r2_str}, providing continuous shields, disengage peel, and crowd control absorption."
                    p3 = f"A classic, highly synergistic 5-position draft features {draft_str}." if draft_str else ""
                    p4 = f"Your primary win condition is: {win_con.strip('.')}. By maintaining disciplined spacing and peeling incoming divers in front-to-back teamfights, your carry can safely shred the opposing squad and secure decisive neutral objectives."

                elif "poke" in comp_id or "siege" in comp_id:
                    p1 = f"For a **{cname}**, the strategic gameplan revolves around {desc.strip('.')}. This draft's power curve peaks during the **{p_curve}**, allowing your squad to chip away enemy health pools from safe range before major neutral objectives spawn."
                    p2 = f"To draft this composition effectively, your damage core must prioritize {r1_title} such as {r1_str}. To protect these immobile artillery champions from hard engage collapses, your lineup must feature {r2_title} like {r2_str} to disengage diving threats and maintain perimeter control."
                    p3 = f"A classic, highly synergistic 5-position draft features {draft_str}." if draft_str else ""
                    p4 = f"Your primary win condition is: {win_con.strip('.')}. By softening opponents from outside their threat range and denying counter-engages, your squad can force enemies to surrender neutral objectives or concede towers."

                elif "split" in comp_id or "duelist" in comp_id:
                    p1 = f"For a **{cname}**, the strategic gameplan revolves around {desc.strip('.')}. This draft reaches its maximum effectiveness in the **{p_curve}**, pulling the enemy team apart across multiple side lanes."
                    p2 = f"To draft this composition effectively, your side-lane pressure relies on {r1_title} such as {r1_str} creating relentless 1v1 threat. Meanwhile, your 4-man main group must feature {r2_title} like {r2_str} to safely stall, waveclear, and disengage without being collapsed upon."
                    p3 = f"A classic, highly synergistic 5-position draft features {draft_str}." if draft_str else ""
                    p4 = f"Your primary win condition is: {win_con.strip('.')}. By applying continuous side-lane pressure, you force disadvantageous enemy rotations and trade objectives cross-map to secure victory."

                elif "mage" in comp_id or "ap" in comp_id or "magic" in comp_id:
                    p1 = f"For a **{cname}**, the strategic gameplan revolves around {desc.strip('.')}. This draft's power curve peaks during the **{p_curve}**, where overlapping ability power rotations and item spikes melt clustered enemy teamfight formations."
                    p2 = f"To draft this composition effectively, your core damage output anchors around {r1_title} such as {r1_str}. To enable these skillshot-reliant and immobile casters to cast freely, your lineup requires {r2_title} like {r2_str}, providing essential frontline lockdown, crowd control zoning, and magic resistance shred."
                    p3 = f"A classic, highly synergistic 5-position draft features {draft_str}." if draft_str else ""
                    p4 = f"Your primary win condition is: {win_con.strip('.')}. Be mindful of enemy magic resistance itemization (Kaenic Rookern, Force of Nature) by prioritizing early Void Staff or drafting mixed physical utility to prevent your burst from being negated."

                elif "tank" in comp_id or "brawl" in comp_id or "juggernaut" in comp_id:
                    p1 = f"For a **{cname}**, the strategic gameplan revolves around {desc.strip('.')}. This draft's power curve peaks during the **{p_curve}**, where your massive effective health pools allow you to outlast enemy burst rotations."
                    p2 = f"To draft this composition effectively, your frontline foundation must anchor around {r1_title} such as {r1_str}. Behind this impenetrable wall, draft {r2_title} like {r2_str} to supply sustained DPS and defensive buffs throughout prolonged teamfights."
                    p3 = f"A classic, highly synergistic 5-position draft features {draft_str}." if draft_str else ""
                    p4 = f"Your primary win condition is: {win_con.strip('.')}. Force front-to-back 5v5 teamfights at neutral objectives where your frontline can absorb enemy cooldowns and grind down opposing carries."

                elif "assassin" in comp_id or "flank" in comp_id:
                    p1 = f"For a **{cname}**, the strategic gameplan revolves around {desc.strip('.')}. This draft's power curve peaks during the **{p_curve}**, relying on rapid Lethality item spikes and early roam tempo before enemy defensive items come online."
                    p2 = f"To draft this composition effectively, your threat profile relies on {r1_title} such as {r1_str} finding unexpected flank angles. To set up these sudden assassinations, pair them with {r2_title} like {r2_str} to sweep enemy vision and lock down targets with instant single-target CC."
                    p3 = f"A classic, highly synergistic 5-position draft features {draft_str}." if draft_str else ""
                    p4 = f"Your primary win condition is: {win_con.strip('.')}. Clear vision around enemy jungle exits, convert pickoffs into 5v4 collapses, and close out the match before enemies group with Zhonya's and Guardian Angel."

                elif "wombo" in comp_id or "combo" in comp_id or "heavy_cc" in comp_id:
                    p1 = f"For a **{cname}**, the strategic gameplan revolves around {desc.strip('.')}. This draft's power curve scales around the **{p_curve}**, relying on synchronized ultimate abilities that chain multi-target crowd control and wipe clustered enemy squads in one decisive rotation."
                    p2 = f"To draft this composition effectively, your initiation frontline must anchor around {r1_title} such as {r1_str}. Once primary crowd control connects, your follow-up threats must feature {r2_title} like {r2_str}, layering massive AoE burst across the lockdown area."
                    p3 = f"A classic, highly synergistic 5-position draft features {draft_str}." if draft_str else ""
                    p4 = f"Your primary win condition is: {win_con.strip('.')}. Force contested neutral objective fights in tight jungle corridors and river chokepoints where enemies cannot spread out to avoid your overlapping ultimate abilities."

                elif "sustain" in comp_id or "heal" in comp_id:
                    p1 = f"For a **{cname}**, the strategic gameplan revolves around {desc.strip('.')}. This draft's power curve peaks during the **{p_curve}**, utilizing relentless health regeneration, omnivamp, and defensive healing to outlast enemy burst in extended skirmishes."
                    p2 = f"To draft this composition effectively, your sustained frontline anchors around {r1_title} such as {r1_str}. Backing these drain tanks, draft {r2_title} like {r2_str} to supply continuous shielding, healing augmentation, and sustained teamfight DPS."
                    p3 = f"A classic, highly synergistic 5-position draft features {draft_str}." if draft_str else ""
                    p4 = f"Your primary win condition is: {win_con.strip('.')}. Drag out teamfights beyond the initial burst rotation, bait enemy ignite and anti-heal cooldowns, and grind down opponents in protracted front-to-back brawls."

                elif "stealth" in comp_id or "ambush" in comp_id:
                    p1 = f"For a **{cname}**, the strategic gameplan revolves around {desc.strip('.')}. This draft's power curve peaks during the **{p_curve}**, leveraging camouflage, invisibility, and vision denial to execute lethal ambushes before enemies can react."
                    p2 = f"To draft this composition effectively, your primary flank threats require {r1_title} such as {r1_str}. To enable these stealth initiators to collapse cleanly, anchor your lineup with {r2_title} like {r2_str} to bait enemy focus and control vision around objective entrances."
                    p3 = f"A classic, highly synergistic 5-position draft features {draft_str}." if draft_str else ""
                    p4 = f"Your primary win condition is: {win_con.strip('.')}. Aggressively clear enemy vision, stage deadly traps in the fog of war near neutral objectives, and eliminate isolated priority targets before 5v5 teamfights begin."

                elif "full_ad" in comp_id or "physical" in comp_id:
                    p1 = f"For a **{cname}**, the strategic gameplan revolves around {desc.strip('.')}. This draft's power curve peaks during the **{p_curve}**, leveraging rapid Lethality item spikes and heavy physical burst to snowball early lane leads."
                    p2 = f"To draft this composition effectively, your primary physical threats prioritize {r1_title} such as {r1_str}. To ensure your physical damage is not neutralized by enemy armor stacking, your team must incorporate {r2_title} like {r2_str}, providing essential armor shred (Black Cleaver), lethality amplification, and crowd control lockdown."
                    p3 = f"A classic, highly synergistic 5-position draft features {draft_str}." if draft_str else ""
                    p4 = f"Your primary win condition is: {win_con.strip('.')}. Snowball an overwhelming early gold lead through dragon takes and tower plates, prioritizing armor penetration items (Lord Dominik's Regards, Serylda's Grudge) before enemy tanks complete Plated Steelcaps and Thornmail."

                elif "mobility" in comp_id:
                    p1 = f"For a **{cname}**, the strategic gameplan revolves around {desc.strip('.')}. This draft's power curve peaks during the **{p_curve}**, out-maneuvering the enemy team with superior movement speed, dashes, and rapid map rotations."
                    p2 = f"To draft this composition effectively, your mobile core anchors around {r1_title} such as {r1_str}. Pair these high-tempo carries with {r2_title} like {r2_str} to provide speed boosts, disengage tools, and flank assistance."
                    p3 = f"A classic, highly synergistic 5-position draft features {draft_str}." if draft_str else ""
                    p4 = f"Your primary win condition is: {win_con.strip('.')}. Force enemies to react to cross-map plays, kite back against immobile deathballs, and collapse with overwhelming speed on isolated targets."

                else:  # Dive / Engage / Teamfight
                    p1 = f"For a **{cname}**, the strategic gameplan revolves around {desc.strip('.')}. This draft's power curve peaks during the **{p_curve}**, where decisive ultimate combinations cleanly wipe clustered enemy formations before defensive items come online."
                    p2 = f"To draft this composition effectively, your initiation frontline must anchor around {r1_title} such as {r1_str}. Once heavy crowd control lands, your team must immediately follow up with {r2_title} like {r2_str}, turning CC locks into instant eliminations."
                    p3 = f"A classic, highly synergistic 5-position draft features {draft_str}." if draft_str else ""
                    p4 = f"Your primary win condition is: {win_con.strip('.')}. By executing decisive collapses around river chokepoints, your team can cleanly secure neutral objectives like Dragon and Baron to close out the match."

                parts = [p for p in [p1, p2, p3, p4] if p]
                return "\n\n".join(parts)

            if s_data.get("is_composition_query") or s_data.get("is_team_counter_analysis") or s_data.get("is_role_query"):
                role_title = s_data.get("role_title") or s_data.get("comp_title") or "Target Composition"
                weaknesses = s_data.get("weaknesses") or s_data.get("shared_weaknesses") or []
                tips = s_data.get("tactical_tips") or []
                picks = s_data.get("counter_picks") or s_data.get("cross_counter_picks") or []
                items = s_data.get("counter_items") or s_data.get("recommended_items") or []

                weakness_clean = [w.strip(".; ") for w in weaknesses[:3] if w]
                weakness_str = "; ".join(weakness_clean) if weakness_clean else "structural cooldown windows and range limitations"

                title_lower = (role_title or "").lower()

                # Dynamic archetype-specific tactical counterplay guideline
                if any(w in title_lower for w in ["fighter", "bruiser"]):
                    tactical_rule = "To counter their gameplan effectively, maintain disciplined perimeter spacing to kite their short melee range, layer continuous ground slows and disengage tools, and build early Grievous Wounds to shut down their sustained combat healing."
                elif any(w in title_lower for w in ["tank"]):
                    tactical_rule = "To counter their gameplan effectively, draft dual-damage % max HP shredding carries, bypass their durable frontline to access squishy backline carries, and avoid blowing primary cooldowns on their tanks."
                elif any(w in title_lower for w in ["poke", "artillery"]):
                    tactical_rule = "To counter their gameplan effectively, bypass neutral standoff sieges by drafting decisive hard-engage tools, collapse through unwarded jungle flanks, and sustain through poke damage before starting neutral objectives."
                elif any(w in title_lower for w in ["assassin"]):
                    tactical_rule = "To counter their gameplan effectively, group tightly as five, maintain vision on flanking corridors, and hold point-and-click crowd control to instantly lock down assassins when they attempt to dive onto your backline."
                elif any(w in title_lower for w in ["dive", "engage"]):
                    tactical_rule = "To counter their gameplan effectively, maintain defensive perimeter spacing, avoid committing primary skillshots until their initial mobility spells are baited, and hold reliable crowd control specifically for when they attempt to dive."
                elif any(w in title_lower for w in ["sustain", "heal"]):
                    tactical_rule = "To counter their gameplan effectively, rush early Grievous Wounds across multiple teammates, focus fire the primary healer first, and chain high-burst crowd control to eliminate targets before their healing spells can cycle."
                elif any(w in title_lower for w in ["stealth"]):
                    tactical_rule = "To counter their gameplan effectively, blanket river chokepoints with Control Wards, sweep key flanking bushes with Oracle Lens, and avoid wandering alone into unwarded fog of war."
                elif any(w in title_lower for w in ["hypercarry", "protect", "funnel"]):
                    tactical_rule = "To counter their gameplan effectively, draft point-and-click crowd control to bypass enchanter peel, flank the isolated hypercarry from fog of war, and pressure side lanes to avoid 5v5 teamfights against a stacked funnel."
                elif any(w in title_lower for w in ["marksman"]):
                    tactical_rule = "To counter their gameplan effectively, stack heavy armor and attack speed slows, draft gap-closing divers with hard crowd control, and collapse onto immobile marksmen before they reach their multi-item spikes."
                elif any(w in title_lower for w in ["mage", "magic", "ap"]):
                    tactical_rule = "To counter their gameplan effectively, stack heavy magic resistance early, exploit lengthy spell cooldown windows, and coordinate hard-engage initiations before they establish objective zoning."
                else:
                    tactical_rule = "To counter their gameplan effectively, maintain defensive perimeter spacing, coordinate layered crowd control, and target their structural cooldown windows."

                p1 = f"When facing a **{role_title}**, their primary tactical vulnerabilities stem from: {weakness_str}. {tactical_rule}"

                pick_descriptions = []
                for cp in picks[:4]:
                    cname = cp.get("champion") if isinstance(cp, dict) else str(cp)
                    raw_cname = cname.split(" (")[0]
                    reason = cp.get("reason") or cp.get("tactical_reason") or "provides heavy lockdown and counter-engage"
                    pick_descriptions.append(f"**{raw_cname}** ({reason.strip('.; ')})")

                p2 = ""
                if pick_descriptions:
                    p2 = f"Your highest-leverage champion draft picks against this lineup include {', '.join(pick_descriptions)}. "

                item_names = []
                for it in items[:4]:
                    iname = it.get("item", "") if isinstance(it, dict) else str(it)
                    if iname:
                        item_names.append(f"**{iname}**")

                if item_names:
                    items_joined = ", ".join(item_names)
                    if any(w in title_lower for w in ["fighter", "bruiser"]):
                        p2 += f"In terms of tactical itemization, prioritize building {items_joined} early to reduce their healing sustain, shred their high health pools, and blunt their sustained auto-attack trading."
                    elif any(w in title_lower for w in ["tank"]):
                        p2 += f"In terms of tactical itemization, prioritize building {items_joined} early to shred through their massive armor and health pools with percent-health damage and maximum penetration."
                    elif any(w in title_lower for w in ["poke", "artillery"]):
                        p2 += f"In terms of defensive itemization, prioritize building {items_joined} early to absorb poke damage with recurring magic shields and out-of-combat health regeneration."
                    elif any(w in title_lower for w in ["assassin"]):
                        p2 += f"In terms of defensive itemization, prioritize building {items_joined} early to absorb their initial burst rotation, trigger stasis invulnerability, and neutralize their dive threat."
                    elif any(w in title_lower for w in ["dive", "engage"]):
                        p2 += f"In terms of defensive itemization, prioritize building {items_joined} early to blunt their initial dive initiation, survive burst rotations, and reset the fight."
                    elif any(w in title_lower for w in ["sustain", "heal"]):
                        p2 += f"In terms of counter itemization, prioritize building {items_joined} early to apply continuous Grievous Wounds and completely neutralize their combat healing."
                    elif any(w in title_lower for w in ["stealth"]):
                        p2 += f"In terms of defensive itemization, prioritize placing Control Wards and sweeping Oracle Lens while building {items_joined} early to survive surprise ambushes from stealth."
                    elif any(w in title_lower for w in ["hypercarry", "protect", "funnel"]):
                        p2 += f"In terms of tactical itemization, prioritize building {items_joined} early to cripple the hypercarry's attack speed, reduce critical strike damage, and bypass enchanter shields."
                    elif any(w in title_lower for w in ["marksman", "physical", "ad"]):
                        p2 += f"In terms of defensive itemization, prioritize building {items_joined} early to stack high armor, reduce incoming basic attack damage, and cripple enemy attack speed."
                    elif any(w in title_lower for w in ["mage", "magic", "ap"]):
                        p2 += f"In terms of defensive itemization, prioritize building {items_joined} early to stack high magic resistance and absorb heavy spell burst rotations."
                    else:
                        p2 += f"In terms of tactical itemization, prioritize building {items_joined} early to mitigate their primary damage profile and neutralize their strategic win condition."

                return f"{p1}\n\n{p2}".strip()

            # 2. Format 1v1 champion counter data
            if s_data.get("is_counter_query"):
                cname = s_data.get("name", "Champion")
                weaknesses = s_data.get("weaknesses") or []
                tips = s_data.get("tactical_tips") or s_data.get("enemytips") or []
                direction = s_data.get("counter_direction")
                champs_list = s_data.get("strong_against") if direction == "counters" else s_data.get("weak_against")
                c_items = s_data.get("counter_items") or []

                weakness_clean = [w.strip(".; ") for w in weaknesses[:3] if w]
                weakness_str = "; ".join(weakness_clean) if weakness_clean else "cooldown dependencies and range vulnerabilities"
                tip_clean = tips[0].strip(".; ") if tips else ""
                tip_str = f" A key counterplay rule is: {tip_clean}." if tip_clean else ""
                p1 = f"When playing against **{cname}**, their primary tactical weaknesses include: {weakness_str}.{tip_str}"

                ch_descriptions = []
                for ch in (champs_list or [])[:4]:
                    opp = ch.get("champion", "")
                    reason = ch.get("reason", "")
                    if opp:
                        ch_descriptions.append(f"**{opp}** ({reason})" if reason else f"**{opp}**")

                p2 = ""
                if ch_descriptions:
                    label = f"Champions that perform exceptionally well against **{cname}** include"
                    p2 = f"{label} {', '.join(ch_descriptions)}. "

                item_names = [f"**{it}**" for it in c_items[:4] if it]
                if item_names:
                    p2 += f"For counter itemization, prioritize building {', '.join(item_names)} to mitigate their core combat threat and shut down their trades."

                return f"{p1}\n\n{p2}".strip()

            # 3a. Format champion-centric team composition query
            if s_data.get("is_champion_composition") or (intent == "CHAMPION_TEAM_COMPOSITION" and s_data.get("best_team_compositions")) or (s_data.get("best_team_compositions") and any(w in question.lower() for w in ["team comp", "lineup", "composition"])):
                focus_c = s_data.get("focus_champion") or s_data.get("name") or s_data.get("champion") or "Champion"
                comps = s_data.get("best_team_compositions", [])

                if comps:
                    top_comp = comps[0]
                    c_name = top_comp.get("comp_name", "Standard Lineup")
                    arch = top_comp.get("archetype_name") or top_comp.get("archetype", "Teamfight")
                    wr = top_comp.get("win_rate", 0)
                    games = top_comp.get("games_played", 0)
                    lu = top_comp.get("lineup", {})
                    team_syn = top_comp.get("teammate_synergies", {})
                    win_cond = top_comp.get("win_condition", "")

                    p1 = f"The premier 5-man team composition centered on **{focus_c}** is the **{c_name}** ({arch} archetype), boasting an empirical **{wr}% Win Rate** across {games:,} recorded professional matches. The optimal 5-position draft features **{lu.get('top', 'N/A')}** (Top), **{lu.get('jungle', 'N/A')}** (Jungle), **{lu.get('mid', 'N/A')}** (Mid), **{lu.get('bot', 'N/A')}** (Bot), and **{lu.get('support', 'N/A')}** (Support)."

                    syn_sentences = []
                    for pos, text in team_syn.items():
                        syn_sentences.append(f"In the {pos}, {text}")
                    syn_text = " ".join(syn_sentences[:3])

                    p2 = f"This lineup creates decisive synergy around **{focus_c}**: {syn_text}" if syn_text else f"This lineup creates decisive crowd control and damage layering around **{focus_c}**."

                    p3 = f"Your primary win condition is: {win_cond}" if win_cond else "Your core win condition is to control neutral objective vision and execute decisive teamfight collapses around Dragon and Baron."

                    return f"{p1}\n\n{p2}\n\n{p3}".strip()
                else:
                    return f"Currently, there is no complete verified 5-man professional composition recorded for **{focus_c}**."

            # 3b. Format duo synergy query
            if s_data.get("is_synergy_query") or s_data.get("best_duos") or intent == "SYNERGY_QUERY":
                cname = s_data.get("name") or s_data.get("champion") or "Champion"
                primary_role = s_data.get("role", "Carry")
                roles_list = s_data.get("roles", [])
                roles_str = " / ".join(roles_list) if roles_list else primary_role
                playstyles = s_data.get("playstyles", [])
                ps_str = f" emphasizing {', '.join(playstyles[:2])} mechanics" if playstyles else ""
                duo_list = s_data.get("best_duos") or s_data.get("top_duos") or []

                p1 = f"As a **{roles_str}**{ps_str}, **{cname}** excels alongside partners who provide complementary crowd control, reliable peel, or synchronized burst initiation to safely unleash continuous damage."

                partner_texts = []
                for d in duo_list[:4]:
                    p_name = d.get("partner") or d.get("champion", "Champion")
                    p_role = d.get("role", "")
                    role_str = f" ({p_role})" if p_role else ""
                    wr = d.get("win_rate") or d.get("soloq_winrate") or d.get("winrate")
                    games = d.get("sample_games") or d.get("soloq_games") or d.get("games")
                    stat_str = f" (**{wr}% WR** over {games:,} matches)" if wr is not None and games else ""
                    rsn = d.get("synergy_reason") or d.get("reason", "")
                    if rsn:
                        partner_texts.append(f"**{p_name}**{role_str}{stat_str}, where {rsn}")
                    else:
                        partner_texts.append(f"**{p_name}**{role_str}{stat_str}")

                p2 = ""
                if partner_texts:
                    p2 = f"Top-performing duo partners include {'; '.join(partner_texts)}."

                p3 = "In lane, focus on synchronizing trades whenever your support lands crowd control or expends defensive buffs, maintaining discipline to disengage once key cooldowns are expended. In 5v5 teamfights, anchor near your peel enchanters and frontline to eliminate incoming divers before transitioning into decisive objective takes."

                return f"{p1}\n\n{p2}\n\n{p3}".strip()

            # 4. Micro-mechanic queries
            if s_data.get("wind_wall_verdict") or s_data.get("spellshield_verdict"):
                c_name = s_data.get("champion", "Target")
                s_name = s_data.get("skill_name", "Ability")
                s_key = s_data.get("skill_key", "")
                skill_ref = f"**{c_name}'s {s_key} ({s_name})**" if s_key else f"**{c_name}'s {s_name}**"
                interact_c = s_data.get("interaction_champion", "Yasuo")

                p_lines = []
                if s_data.get("wind_wall_verdict"):
                    p_lines.append(f"Regarding the interaction between **{interact_c}**'s Wind Wall and {skill_ref}: {s_data['wind_wall_verdict']}")
                if s_data.get("spellshield_verdict"):
                    p_lines.append(f"Regarding spell shield interactions against {skill_ref}: {s_data['spellshield_verdict']}")
                if p_lines:
                    return "\n\n".join(p_lines).strip()

            # 5. Format Champion Build and Itemization Query
            if intent == "BUILD_QUERY" or s_data.get("core_items") or s_data.get("full_build"):
                b_name = s_data.get("champion") or s_data.get("name", "Champion")
                start_items = s_data.get("starting_items", ["Doran's Blade", "Health Potion"])
                core_items = s_data.get("core_items", [])
                full_build = s_data.get("full_build", [])
                spells = s_data.get("summoner_spells", ["Flash", "Teleport"])
                runes_data = s_data.get("runes", {})
                keystone = runes_data.get("keystone", "Conqueror") if isinstance(runes_data, dict) else "Conqueror"
                p_runes = runes_data.get("primary", []) if isinstance(runes_data, dict) else []
                s_runes = runes_data.get("secondary", []) if isinstance(runes_data, dict) else []

                core_str = ", ".join(f"**{it}**" for it in core_items[:3]) if core_items else "core legendary items"
                full_str = ", ".join(f"**{it}**" for it in full_build[:6]) if full_build else "situational defensive items"
                start_str = ", ".join(f"**{it}**" for it in start_items) if start_items else "standard starting items"
                spells_str = ", ".join(f"**{sp}**" for sp in spells) if spells else "Flash and Teleport"

                p1 = f"For optimal combat performance on **{b_name}**, the recommended setup begins with {start_str} to establish early trading dominance during laning, complemented by summoner spells {spells_str} for map mobility and combat pressure."
                p2 = f"Your primary three-item power spike centers around {core_str}. Rushing these core legendaries maximizes {b_name}'s damage scaling and cooldown efficiency, enabling decisive skirmish presence once mid-game teamfights erupt."
                p3 = f"To transition into the late game, expand into a complete 6-item build featuring {full_str}, allowing you to withstand enemy burst rotations while eliminating opposing carries."
                p4 = f"For runes, anchor your page with **{keystone}** to maximize trading and sustained combat output"
                if p_runes:
                    p4 += f", followed by primary path runes {', '.join(str(r) for r in p_runes[:3])}"
                if s_runes:
                    p4 += f" and secondary runes {', '.join(str(r) for r in s_runes[:2])} for extra lane sustain and scaling."
                else:
                    p4 += "."

                return f"{p1}\n\n{p2}\n\n{p3}\n\n{p4}".strip()

            # 6. Format Item Details Query
            if intent == "ITEM_INFO" or (s_data.get("cost") is not None and (s_data.get("buildFrom") is not None or s_data.get("buildInto") is not None or s_data.get("stats"))):
                i_name = s_data.get("name", "Item")
                cost = s_data.get("cost", {})
                cost_total = cost.get("total", 0) if isinstance(cost, dict) else (cost or 0)
                cost_sell = cost.get("sell", 0) if isinstance(cost, dict) else 0
                stats = s_data.get("stats", {})
                desc = s_data.get("description", "")
                b_from = s_data.get("buildFrom", [])
                b_into = s_data.get("buildInto", [])

                stat_parts = [f"**{k.replace('Flat', '').replace('Mod', '')}: +{v}**" for k, v in stats.items() if v]
                stat_str = ", ".join(stat_parts) if stat_parts else "utility and combat passives"

                p1 = f"**{i_name}** is a premier legendary item costing **{cost_total:,} gold** (sells for {cost_sell:,} gold) that provides {stat_str}."
                
                recipe_parts = []
                if b_from:
                    from_str = ", ".join(f"**{str(bf)}**" for bf in b_from)
                    recipe_parts.append(f"It builds from {from_str}")
                if b_into:
                    into_str = ", ".join(f"**{str(bi)}**" for bi in b_into)
                    recipe_parts.append(f"can be upgraded into {into_str}")
                p2 = f"{'. '.join(recipe_parts)}." if recipe_parts else ""

                p3 = f"Passive and Active Mechanics: {desc.strip('.')}. This item represents a massive power spike for champions prioritizing critical strike scaling, burst execution, or defensive survivability."

                parts = [p for p in [p1, p2, p3] if p]
                return "\n\n".join(parts)

            # 7. Format Rune Details Query
            if intent == "RUNE_INFO" or s_data.get("tree") or s_data.get("longDescription"):
                r_name = s_data.get("name", "Rune")
                tree = s_data.get("tree", "Precision")
                desc = s_data.get("longDescription") or s_data.get("description", "")

                p1 = f"**{r_name}** is an essential keystone rune belonging to the **{tree} Tree** in League of Legends."
                p2 = f"Rune Mechanics and Combat Function: {desc.strip('.')}"
                p3 = f"This rune excels on champions who engage in extended trades or rely on rapid ability weaving, granting continuous combat stats and adaptive force throughout skirmishes and teamfights."

                return f"{p1}\n\n{p2}\n\n{p3}".strip()

            # 8. Format Ability and Skill Details Query (Check before general stats to ensure kit queries format properly)
            if intent in ("SKILL_INFO", "SKILL_DAMAGE_AT_LEVEL", "SKILL_COOLDOWN", "SKILL_MANA_COST", "LIST_SKILLS") or (s_data.get("skill_key") and not s_data.get("is_stat_calculation")):
                c_name = s_data.get("champion") or s_data.get("name", "Champion")
                sk_key = s_data.get("skill_key")
                sk_name = s_data.get("skill_name", "Ability")
                desc = s_data.get("description", "")
                cd = s_data.get("cooldown", [])
                cost = s_data.get("cost", [])
                cost_type = s_data.get("costType", "Mana")
                rng = s_data.get("range", [])
                dmg_type = s_data.get("damageType", "Magic")
                proj = s_data.get("projectile")

                if sk_key:
                    p1 = f"**{c_name}'s [{sk_key.upper()}] Ability ({sk_name})** is a core combat tool dealing {dmg_type} damage."
                    p2 = f"Ability Mechanics: {desc.strip('.')}"
                    cd_str = f"Cooldown: {cd}s" if cd else ""
                    cost_str = f"Cost: {cost} {cost_type}" if cost else ""
                    rng_str = f"Range: {rng}" if rng else ""
                    proj_str = "Blocks: Blocked by Yasuo Wind Wall (Projectile)" if proj else "Non-projectile (Cannot be blocked by Wind Wall)" if proj is False else ""
                    specs = [s for s in [cd_str, cost_str, rng_str, proj_str] if s]
                    p3 = f"Specifications: {'; '.join(specs)}." if specs else ""
                    parts = [p for p in [p1, p2, p3] if p]
                    return "\n\n".join(parts)
                elif s_data.get("abilities"):
                    p1 = f"**{c_name}** commands a versatile ability kit composed of the following signature spells:"
                    ab_lines = []
                    for k in ["passive", "Q", "W", "E", "R"]:
                        ab = s_data["abilities"].get(k)
                        if isinstance(ab, dict) and ab.get("name"):
                            ab_desc = ab.get("description", "")
                            ab_lines.append(f"**[{k.upper()}] {ab.get('name')}**: {ab_desc.strip('.')}")
                    p2 = "\n\n".join(ab_lines)
                    return f"{p1}\n\n{p2}".strip()

            # 9. Format Champion Base Stats and Scaling Query
            if intent in ("CHAMPION_BASE_STATS", "CHAMPION_STATS_AT_LEVEL") or s_data.get("is_stat_calculation"):
                c_name = s_data.get("champion") or s_data.get("name", "Champion")
                lvl = s_data.get("level") or s_data.get("character_level") or 1
                stats = s_data.get("stats_at_level") or s_data.get("base_stats") or s_data.get("stats") or {}

                def safe_float(v, default = 0.0):
                    if isinstance(v, dict):
                        return float(v.get("base", default) or default)
                    try:
                        return float(v or default)
                    except (ValueError, TypeError):
                        return default

                hp = safe_float(stats.get("hp"))
                mp = safe_float(stats.get("mp"))
                armor = safe_float(stats.get("armor"))
                mr = safe_float(stats.get("spellblock", stats.get("magic_resist", 0)))
                ad = safe_float(stats.get("attackdamage", stats.get("ad", 0)))
                as_val = safe_float(stats.get("attackspeed", 0))
                ms = safe_float(stats.get("movespeed", 0))
                rng = safe_float(stats.get("attackrange", 0))

                p1 = f"At **Level {lvl}**, **{c_name}** features base defensive attributes of **{hp:.0f} Health**, **{mp:.0f} Resource/Mana**, **{armor:.1f} Armor**, and **{mr:.1f} Magic Resist**."
                p2 = f"Offensively, {c_name} commands **{ad:.1f} Attack Damage**, **{as_val:.3f} Attack Speed**, **{ms:.0f} Movement Speed**, and a basic attack range of **{rng:.0f} units**."
                p3 = f"These base statistics define {c_name}'s trading profile and early durability, establishing a balanced stat foundation that scales steadily into late-game teamfights."

                return f"{p1}\n\n{p2}\n\n{p3}".strip()

            # 10. Format Champion Head-to-Head Comparison Query
            if intent == "CHAMPION_COMPARISON" or s_data.get("comparison") or s_data.get("matchup_info"):
                champs_list = s_data.get("champions", ["Champion 1", "Champion 2"])
                c1, c2 = champs_list[0], (champs_list[1] if len(champs_list) > 1 else "Opponent")
                matchup = s_data.get("matchup_info") or {}
                winner = matchup.get("winner") or matchup.get("advantaged")
                loser = matchup.get("loser") or matchup.get("disadvantaged")
                wr = matchup.get("win_rate")
                reason = matchup.get("reason", "")

                if winner and loser:
                    p1 = f"In a direct head-to-head matchup between **{c1}** and **{c2}**, empirical game data demonstrates that **{winner} holds the tactical counter advantage over {loser}** with a recorded **{wr}% win rate**."
                    p2 = f"The primary tactical reason for this advantage is: {reason.strip('.')}. In lane, {winner} can exploit spacing and cooldown windows to punish {loser}'s trading pattern before they reach their item spikes."
                else:
                    p1 = f"When comparing **{c1}** against **{c2}**, the matchup is heavily skill-dependent and hinges on ability baiting, wave management, and jungle assistance."
                    p2 = f"Both champions possess distinct power curves and win conditions, where early item spikes and spacing dictate who secures lane priority."

                p3 = f"To win this matchup, maintain disciplined positioning around minion waves, track enemy mobility cooldowns, and coordinate decisive all-ins once primary defensive spells are baited."

                return f"{p1}\n\n{p2}\n\n{p3}".strip()

            # 11. Format Role Counter Pick Query
            if intent == "ROLE_COUNTER_PICK" or s_data.get("is_role_counter_pick"):
                u_role = s_data.get("user_role") or "Support"
                target = s_data.get("target") or "diving assassins"
                top_champs = s_data.get("top_champions", [])
                rec_items = s_data.get("recommended_items", [])
                guidelines = s_data.get("tactical_guidelines", "")

                p1 = f"When selecting a **{u_role.capitalize()}** to counter **{target}**, your drafting priority must emphasize reliable crowd control, disengage peel, and burst mitigation to neutralize incoming aggressive collapses."

                champ_lines = []
                for ch in top_champs[:4]:
                    c_name = ch.get("champion") or ch.get("name")
                    mech = ch.get("key_mechanics") or ch.get("reason", "provides heavy crowd control and carry protection")
                    champ_lines.append(f"**{c_name}** ({mech.strip('.')})")

                p2 = f"Premier champion choices include {', '.join(champ_lines)}." if champ_lines else ""
                
                item_str = ", ".join(f"**{it}**" for it in rec_items[:4]) if rec_items else "**Locket of the Iron Solari** and **Knight's Vow**"
                p3 = f"For itemization, prioritize defensive utility such as {item_str} to shield vulnerable carries and absorb burst rotations."
                
                if isinstance(guidelines, list):
                    guidelines_str = " ".join(str(g).strip(".; ") for g in guidelines)
                else:
                    guidelines_str = str(guidelines).strip(".; ") if guidelines else ""
                p4 = f"Tactical Guideline: {guidelines_str}." if guidelines_str else "Position tightly between enemy flank angles and your backline carries, saving instant crowd control to interrupt dashes mid-animation."

                parts = [p for p in [p1, p2, p3, p4] if p]
                return "\n\n".join(parts)

            # 12. Format Champion Lore Query
            if intent == "LORE_QUERY" or s_data.get("is_lore_query") or s_data.get("shortLore") or s_data.get("lore"):
                c1_name = s_data.get("champion") or s_data.get("name", "Champion")
                c2_name = s_data.get("interaction_champion")

                # A. Multi-champion Lore Conflict / Rivalry
                if c2_name and s_data.get("is_conflict_lore_query"):
                    c1_title = s_data.get("title", "")
                    c2_title = s_data.get("interaction_title", "")
                    region = s_data.get("region") or s_data.get("interaction_region", "Ionia")

                    parts = [
                        f"In the canon lore of League of Legends, the bitter conflict between **{c1_name} ({c1_title})** and **{c2_name} ({c2_title})** is one of the most defining philosophical and martial rivalries of **{region}**."
                    ]

                    # Specific Zed & Shen canon conflict details
                    names_lower = {c1_name.lower(), c2_name.lower()}
                    if "zed" in names_lower and "shen" in names_lower:
                        parts.append(
                            "**1. Brothers in the Kinkou Order**:\n"
                            "Shen and Zed were raised together under Shen's father, **Great Master Kusho**. They trained side-by-side as foster brothers and were regarded as the most gifted pupils of the Kinkou, matching each other in discipline and martial prowess."
                        )
                        parts.append(
                            "**2. The Hunt for Jhin (The Golden Demon)**:\n"
                            "Their bond began fracturing during the pursuit of the sadistic serial killer **Khada Jhin**. When they finally captured him, Zed demanded Jhin's execution, but Master Kusho decreed that Jhin must only be imprisoned to preserve spiritual harmony. This decision bred deep resentment in Zed, who felt the Kinkou's doctrine was naive and powerless."
                        )
                        parts.append(
                            "**3. The Noxian Invasion and Shadow Magic**:\n"
                            "When the brutal Noxian empire invaded Ionia, the Kinkou insisted on remaining neutral to maintain the sacred equilibrium between spirits and mortals. Disillusioned, Zed broke into the temple's hidden catacombs, unlocked forbidden shadow spirit magic, and founded the militaristic **Order of Shadow** to violently exterminate the Noxian invaders."
                        )
                        parts.append(
                            "**4. The Slaying of Master Kusho & The Eternal Rift**:\n"
                            "Zed returned to the temple, leading to a fateful confrontation that ended in Master Kusho's apparent death. Shen took up his father's mantle as the **Eye of Twilight**, committed to dispassionate balance. Today, Shen views Zed as an extremist traitor who defiled their sacred traditions, while Zed views Shen as paralyzed by passive dogma—though in rare moments of crisis, they will secretly unite against existential threats to Ionia."
                        )
                    else:
                        c1_lore = s_data.get("shortLore", "")
                        c2_lore = s_data.get("interaction_shortLore", "")
                        parts.append(f"**{c1_name}'s Perspective**: {c1_lore}")
                        parts.append(f"**{c2_name}'s Perspective**: {c2_lore}")

                    return "\n\n".join(parts).strip()

                # B. Single Champion Lore
                c_name = c1_name
                title = s_data.get("title", "")
                region = s_data.get("region", "Runeterra")
                lore_text = s_data.get("shortLore") or s_data.get("lore", "")
                stories = s_data.get("stories", [])
                related = s_data.get("related_champions", [])

                p1 = f"In the canon lore of League of Legends, **{c_name} ({title})** hails from the historic region of **{region}**."
                p2 = f"**Biography and Background**: {lore_text.strip('.')}"

                extra_parts = []
                if stories:
                    s_titles = [st.get("title") if isinstance(st, dict) else str(st) for st in stories if st]
                    s_titles = [t for t in s_titles if t]
                    if s_titles:
                        extra_parts.append(f"Featured Universe Stories include {', '.join(f'*{t}*' for t in s_titles[:4])}")
                if related:
                    rel_names = [r.get("name") if isinstance(r, dict) else str(r) for r in related if r]
                    if rel_names:
                        rel_str = ", ".join(f"**{rn}**" for rn in rel_names[:6])
                        extra_parts.append(f"Prominent relationships in lore include connections to {rel_str}")
                p3 = f"{'. '.join(extra_parts)}." if extra_parts else ""

                parts = [p for p in [p1, p2, p3] if p]
                return "\n\n".join(parts).strip()

            # 13. Format Skin and Cosmetics Query
            if intent == "SKIN_QUERY" or s_data.get("is_skin_query") or s_data.get("unique_skin_count"):
                c_name = s_data.get("champion") or s_data.get("name", "Champion")
                actual_skins = s_data.get("actual_skins", [])
                if not actual_skins and s_data.get("skins"):
                    actual_skins = [
                        (s.get("name") if isinstance(s, dict) else str(s))
                        for s in s_data.get("skins", [])
                        if (s.get("name") if isinstance(s, dict) else str(s)).lower() != "default"
                        and "(" not in (s.get("name") if isinstance(s, dict) else str(s))
                    ]

                u_cnt = s_data.get("unique_skin_count") or len(actual_skins)
                c_cnt = s_data.get("chroma_count", 0)
                leg_prest = s_data.get("legendary_prestige", [])
                themes = s_data.get("thematic_groups", {})

                p1 = f"**{c_name}** currently has **{u_cnt} unique standalone skins** in League of Legends (along with {c_cnt} chromas and cosmetic variants)."

                parts = [p1]
                if leg_prest:
                    lp_str = ", ".join(f"**{s}**" for s in leg_prest)
                    parts.append(f"**Legendary and Prestige Editions**:\n- {lp_str}")

                if themes:
                    theme_lines = ["**Major Thematic Universes & Skin Lines**:"]
                    for t_name, t_skins in themes.items():
                        theme_lines.append(f"- **{t_name}**: {', '.join(t_skins)}")
                    parts.append("\n".join(theme_lines))
                elif actual_skins:
                    parts.append(f"**Notable Skins**: {', '.join(f'**{s}**' for s in actual_skins)}.")

                return "\n\n".join(parts).strip()

            # 14. Format ARAM Balance Modifiers Query
            if intent == "ARAM_QUERY" or s_data.get("is_aram_query") or s_data.get("aram_modifiers"):
                c_name = s_data.get("champion") or s_data.get("name", "Champion")
                aram_mods = s_data.get("aram_modifiers", {})

                parts = []
                for k, v in aram_mods.items():
                    label = k.replace("aram", "").replace("Mod", "")
                    if "Dealt" in label or "Taken" in label or "Healing" in label or "Shielding" in label:
                        parts.append(f"**{label}: {v*100:.0f}%**" if isinstance(v, float) and v < 2.0 else f"**{label}: {v}%**")
                    else:
                        parts.append(f"**{label}: {v}**")

                mod_str = ", ".join(parts) if parts else "standard baseline balance tuning"
                p1 = f"On the Howling Abyss (ARAM), **{c_name}** receives dedicated balance adjustments: {mod_str}."
                p2 = f"These targeted balance modifiers account for the single-lane teamfight dynamics of ARAM, regulating {c_name}'s durability and damage output to ensure fair combat pacing."
                return f"{p1}\n\n{p2}".strip()

            # 15. Format Role or Lane Query
            if intent in ("LANE_QUERY", "ROLE_QUERY") or s_data.get("is_role_query") or s_data.get("is_lane_query"):
                r_title = s_data.get("role_title") or (s_data.get("lane", "").capitalize() + " Lane" if s_data.get("lane") else "Role")
                cnt = s_data.get("count", 0)
                dominant = s_data.get("dominant_damage", "Mixed")
                champs_raw = s_data.get("champions") or s_data.get("sample_champions") or []
                champs_sample = [c.get("name") if isinstance(c, dict) else str(c) for c in champs_raw]
                c_str = ", ".join(f"**{c}**" for c in champs_sample[:15]) if champs_sample else "diverse champion archetypes"

                p1 = f"The **{r_title}** features a roster of **{cnt} champions**, characterized primarily by a **{dominant} damage profile**."
                p2 = f"Core representative champions frequently drafted in this position include {c_str}."
                p3 = f"Success in this role requires mastering wave manipulation, tracking roaming opportunities, and coordinating neutral objective teamfights."
                return f"{p1}\n\n{p2}\n\n{p3}".strip()

            # 16. Format Semantic Filter Query (CC, Effects, Playstyles)
            if intent in ("CHAMPION_BY_CC", "CHAMPION_BY_EFFECT", "MULTI_PROPERTY_FILTER") or s_data.get("criteria"):
                crit = s_data.get("criteria", {})
                crit_desc = []
                if isinstance(crit, dict):
                    for k, v in crit.items():
                        if v:
                            crit_desc.append(f"{k.replace('_', ' ')}: {', '.join(v) if isinstance(v, list) else v}")
                crit_str = "; ".join(crit_desc) if crit_desc else "specified mechanics"
                total = s_data.get("total_matches", 0)
                sample_raw = s_data.get("sample_matches", [])
                sample = [c.get("name") if isinstance(c, dict) else str(c) for c in sample_raw]
                c_str = ", ".join(f"**{c}**" for c in sample[:18]) if sample else "no exact champions"

                p1 = f"A total of **{total} champions** in League of Legends satisfy the criteria for **{crit_str}**."
                p2 = f"Prominent champions featuring these mechanics include {c_str}."
                p3 = f"These champions offer specialized tactical utility, enabling draft flexibility when your team requires dedicated lock-down, stealth initiation, or sustained crowd control chaining."
                return f"{p1}\n\n{p2}\n\n{p3}".strip()

        # 4. Auxiliary clean RAG passages (synthesize into natural prose paragraphs)
        rag_ctx = data.get("rag_retrieved_context", "")
        if rag_ctx:
            clean_text = re.sub(r"\[(?:vector|graph):[^\]]+\]", "", rag_ctx)
            clean_text = re.sub(r"===[^=]+===", "", clean_text).strip()
            
            # If the passage contains raw internal database guide dumps, synthesize it cleanly
            if "Team Composition Guide:" in clean_text or "Category: tactical_profile" in clean_text:
                guide_match = re.search(r"Team Composition Guide:\s*([^(]+?)\s*\(.*?\)\.\s*Strategic Overview:\s*(.*?)(?:Composition Vulnerabilities|Tactical Tips|Top Counter Picks|$)", clean_text, re.DOTALL)
                weak_match = re.search(r"Composition Vulnerabilities and Core Weaknesses:\s*(.*?)(?:Tactical Tips|Top Counter Picks|$)", clean_text, re.DOTALL)
                picks_match = re.search(r"Top Counter Picks Against this Composition:\s*(.*?)(?:Top Counter Items|$)", clean_text, re.DOTALL)
                items_match = re.search(r"Top Counter Items Against this Composition:\s*(.*?)(?:Team Composition Guide:|$)", clean_text, re.DOTALL)

                comp_name = guide_match.group(1).strip() if guide_match else "this team composition"
                
                parts = []
                p1 = f"When facing a **{comp_name}**, the enemy draft relies heavily on explosive burst, coordinated gap-closers, and momentum-driven skirmishes. To neutralize their initiation, avoid overextending in unwarded territory, maintain defensive perimeter spacing, and force them to engage into defensive choke points."
                parts.append(p1)

                if picks_match:
                    raw_picks = [re.sub(r"\s*\(.*?\)", "", line).strip() for line in picks_match.group(1).split("\n") if line.strip()]
                    clean_picks = [p.split(":")[0].strip() for p in raw_picks if p]
                    if clean_picks:
                        p2 = f"Primary counter picks against this archetype include **{', '.join(clean_picks[:4])}**, which offer defensive crowd control, point-and-click lockdown, and damage mitigation to absorb sudden initiation."
                        parts.append(p2)

                if items_match:
                    raw_items = [line.split(":")[0].strip() for line in items_match.group(1).split("\n") if ":" in line]
                    clean_items = [re.sub(r"\s*\(.*?\)", "", it).strip() for it in raw_items if it]
                    if clean_items:
                        p3 = f"Core defensive itemization such as **{', '.join(clean_items[:3])}** is crucial to survive their primary rotation, blunt incoming physical burst, and reset the fight."
                        parts.append(p3)

                if parts:
                    return "\n\n".join(parts)

            # If passage is already natural prose without internal DB tags, return it
            if clean_text and not any(marker in clean_text for marker in ["Team Composition Guide:", "Category:", "coverage against this comp"]):
                return clean_text

        return "ℹ️ No matching data found in the knowledge base."