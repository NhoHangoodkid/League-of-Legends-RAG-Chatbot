"""
Data Retriever for LoL Knowledge Bot.

Acts as the main coordinator / facade combining domain-specific retriever mixins
and provides table-driven query dispatching based on classified intent and entities.
"""

# Re-export strategic_composition_counters for backward compatibility
from chatbot.data.strategic_counters import strategic_composition_counters

# Domain-specific retriever mixins
from chatbot.retriever.base import BaseRetriever
from chatbot.retriever.profile import ProfileRetrieverMixin
from chatbot.retriever.champion import ChampionRetrieverMixin
from chatbot.retriever.skills import SkillRetrieverMixin
from chatbot.retriever.lanes import LaneRetrieverMixin
from chatbot.retriever.counters import CounterRetrieverMixin
from chatbot.retriever.compositions import CompositionRetrieverMixin
from chatbot.retriever.synergy import SynergyRetrieverMixin
from chatbot.retriever.items import ItemRetrieverMixin


# Intent groups for dispatch table
SEMANTIC_FILTER_INTENTS = frozenset({
    "MULTI_PROPERTY_FILTER",
    "CHAMPION_BY_CC",
    "CHAMPION_BY_EFFECT",
    "CHAMPION_BY_PLAYSTYLE",
    "CHAMPION_BY_POWER_CURVE",
    "CHAMPION_BY_WIN_CONDITION",
})

COMPOSITION_BUILD_INTENTS = frozenset({
    "TEAM_COMPOSITION_BUILDING",
    "CHAMPION_TEAM_COMPOSITION",
    "COMPOSITION_QUERY",
})


class DataRetriever(
    BaseRetriever,
    ProfileRetrieverMixin,
    ChampionRetrieverMixin,
    SkillRetrieverMixin,
    LaneRetrieverMixin,
    CounterRetrieverMixin,
    CompositionRetrieverMixin,
    SynergyRetrieverMixin,
    ItemRetrieverMixin,
):
    """
    Main Data Retriever for League of Legends Knowledge Bot.
    Coordinates domain-specific retriever mixins and dispatches classified intents.
    """

    def __init__(self, store = None):
        super().__init__(store=store)
        self.dispatch_table = self.init_dispatch_table()

    # Dispatch Table
    # Maps intent strings to handler callables. Each handler receives (entities).
    # Complex intents that need branching logic are routed to small private methods.

    def init_dispatch_table(self):
        """Build the intent → handler dispatch table (called once in __init__)."""
        return {
            # Skill / ability queries
            "SKILL_DAMAGE_AT_LEVEL": lambda e: self.get_skill_damage(
                e.get("champion_name"), e.get("skill_key") or "Q", e.get("skill_level") or 1),
            "SKILL_INFO":           lambda e: self.get_skill_info(e.get("champion_name"), e.get("skill_key") or "Q"),
            "SKILL_COOLDOWN":       lambda e: self.get_skill_cooldown(e.get("champion_name"), e.get("skill_key") or "Q"),
            "SKILL_MANA_COST":      lambda e: self.get_skill_info(e.get("champion_name"), e.get("skill_key") or "Q"),
            "LIST_SKILLS":          lambda e: self.list_skills(e.get("champion_name")),

            # Champion stat queries
            "CHAMPION_BASE_STATS":     lambda e: self.get_champion_base_stats(e.get("champion_name")),
            "CHAMPION_STATS_AT_LEVEL": lambda e: self.get_champion_stats_at_level(
                e.get("champion_name"), e.get("character_level") or 1),

            # Champion info / lore
            "CHAMPION_INFO":       self.dispatch_champion_info,
            "LORE_QUERY":          self.dispatch_lore,
            "CHAMPION_COMPARISON": lambda e: self.compare_champions(
                e.get("comparison_champions") or [e.get("champion_name")], e.get("stat_name")),

            # Role / lane queries
            "ROLE_QUERY": lambda e: self.get_champions_by_role(
                e.get("role") or (self.store.all_roles[0] if self.store.all_roles else "fighter"),
                e.get("lane")),
            "LANE_QUERY": lambda e: self.get_champions_by_lane(
                e.get("lane") or (self.store.all_positions[0].lower() if self.store.all_positions else "top")),

            # Counter / matchup queries
            "ROLE_COUNTER_PICK":     self.dispatch_role_counter_pick,
            "TEAM_COUNTER_ANALYSIS": self.dispatch_team_counter,
            "COUNTER_QUERY":         self.dispatch_counter,

            # Synergy
            "SYNERGY_QUERY":        lambda e: self.get_synergies(e.get("champion_name")),
            "TEAM_SYNERGY_ANALYSIS": lambda e: self.analyze_team_synergies(
                e.get("allied_champions") or e.get("comparison_champions") or
                ([e.get("champion_name")] if e.get("champion_name") else [])),

            # Build / items / runes
            "BUILD_QUERY":  self.dispatch_build,
            "ITEM_INFO":    lambda e: self.get_item_info(e.get("item_name") or e.get("champion_name")),
            "RUNE_INFO":    lambda e: self.get_rune_info(e.get("rune_name") or e.get("champion_name")),

            # Cosmetics / game modes
            "SKIN_QUERY":   lambda e: self.get_champion_skins(e.get("champion_name")),
            "ARAM_QUERY":   lambda e: self.get_aram_stats(e.get("champion_name")),

            # Mechanics
            "ABILITY_MECHANIC_QUERY": lambda e: self.get_mechanics_info(
                name=e.get("champion_name"),
                skill_key=e.get("skill_key"),
                mechanic=e.get("mechanic"),
                interaction_champ=e.get("interaction_champion")),

            # Semantic profile
            "CHAMPION_SEMANTIC_PROFILE": lambda e: self.get_semantic_profile(e.get("champion_name")),
        }

    # Dispatch helpers for intents with branching logic

    def dispatch_champion_info(self, entities):
        inter_c = entities.get("interaction_champion")
        if inter_c:
            return self.get_champion_lore(entities.get("champion_name"), interaction_champ=inter_c)
        return self.get_champion_info(entities.get("champion_name"))

    def dispatch_lore(self, entities):
        champ_name = entities.get("champion_name")
        inter_c = entities.get("interaction_champion")
        enemy_champs = entities.get("enemy_champions") or []
        if not champ_name and enemy_champs:
            champ_name = enemy_champs[0]
            if len(enemy_champs) >= 2 and not inter_c:
                inter_c = enemy_champs[1]
        if not inter_c and len(enemy_champs) >= 2:
            candidates = [c for c in enemy_champs if c.lower() != (champ_name or "").lower()]
            if candidates:
                inter_c = candidates[0]
        return self.get_champion_lore(champ_name, interaction_champ=inter_c)

    def dispatch_role_counter_pick(self, entities):
        champ_name = entities.get("champion_name")
        return self.get_role_counter_picks(
            user_role=entities.get("user_role") or entities.get("role"),
            target_value=entities.get("target") or champ_name,
            target_type=entities.get("target_type") or ("champion" if champ_name else "role"),
            lane=entities.get("lane"),
        )

    def dispatch_team_counter(self, entities):
        enemy_champs = entities.get("enemy_champions") or []
        comp_archetype = entities.get("comp_archetype")
        damage_comp = entities.get("damage_composition")
        if enemy_champs:
            return self.analyze_team_counters(enemy_champs, comp_archetype=comp_archetype, damage_composition=damage_comp)
        elif comp_archetype or damage_comp:
            return self.get_composition_counters(comp_archetype, damage_comp)
        elif entities.get("role") or entities.get("lane"):
            return self.get_role_counters(entities.get("role"), entities.get("lane"), entities.get("counter_direction"))
        return self.get_composition_counters("dive")

    def dispatch_counter(self, entities):
        champ_name = entities.get("champion_name")
        if champ_name:
            return self.get_counters(champ_name, entities.get("counter_direction"), entities.get("lane"))
        elif entities.get("comp_archetype") or entities.get("damage_composition"):
            return self.get_composition_counters(entities.get("comp_archetype"), entities.get("damage_composition"))
        elif entities.get("role") or entities.get("lane"):
            return self.get_role_counters(entities.get("role"), entities.get("lane"), entities.get("counter_direction"))
        return None

    def dispatch_build(self, entities):
        champ_name = entities.get("champion_name")
        if not champ_name and entities.get("item_name"):
            return self.get_item_info(entities["item_name"])
        return self.get_build(champ_name)

    def dispatch_composition_build(self, entities):
        champ_name = entities.get("champion_name")
        if champ_name:
            return self.get_champion_composition(champ_name)
        comp_key = entities.get("comp_archetype") or entities.get("damage_composition") or "hypercarry_protect"
        return self.get_composition_building_info(comp_key, power_curve=entities.get("power_curve"))

    def dispatch_semantic_filter(self, entities):
        return self.filter_semantic(
            roles=[entities.get("role")] if entities.get("role") else None,
            cc_types=entities.get("cc_types"),
            effects=entities.get("ability_effects"),
            playstyles=entities.get("playstyles"),
            power_curve=entities.get("power_curve"),
            win_condition=entities.get("win_condition"),
        )

    def dispatch_fallback(self, entities):
        """Fallback when no intent matches the dispatch table."""
        champ_name = entities.get("champion_name")
        if champ_name:
            return self.get_champion_info(champ_name)
        elif entities.get("comp_archetype") or entities.get("damage_composition"):
            return self.get_composition_counters(entities.get("comp_archetype"), entities.get("damage_composition"))
        elif entities.get("role"):
            return self.get_role_counters(entities.get("role"), entities.get("lane"), entities.get("counter_direction"))
        elif entities.get("lane"):
            return self.get_champions_by_lane(entities.get("lane"))
        return {"info": "Please provide more information about the champion, item, or mechanics you want to ask about."}

    def dispatch_query(self, intent, entities):
        """Dispatch classified intent to the appropriate retriever method."""
        # 1. Direct table lookup
        handler = self.dispatch_table.get(intent)
        if handler:
            return handler(entities)

        # 2. Composition building intent group
        if intent in COMPOSITION_BUILD_INTENTS:
            return self.dispatch_composition_build(entities)

        # 3. Semantic filter intent group
        if intent in SEMANTIC_FILTER_INTENTS:
            return self.dispatch_semantic_filter(entities)

        # 4. Fallback
        return self.dispatch_fallback(entities)
