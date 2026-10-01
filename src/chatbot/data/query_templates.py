"""
Query template registry for RAG retrieval query synthesis.

Maps intents to parameterized English search query templates used by
the embedding and cross-encoder models.
"""

# Intents that all share the same skill/ability query template
SKILL_INTENTS = frozenset({
    "SKILL_INFO",
    "SKILL_COOLDOWN",
    "SKILL_DAMAGE_AT_LEVEL",
    "SKILL_MANA_COST",
    "LIST_SKILLS",
})

# Intents where champion-specific queries should NOT be generated
# (they have their own dedicated templates below)
NON_CHAMPION_TARGETED_INTENTS = frozenset({
    "TEAM_COMPOSITION_BUILDING",
    "TEAM_COUNTER_ANALYSIS",
    "ITEM_INFO",
    "RUNE_INFO",
})

# Intents that use champion stat / playstyle templates
CHAMPION_STAT_INTENTS = frozenset({
    "CHAMPION_BASE_STATS",
    "CHAMPION_STATS_AT_LEVEL",
})

CHAMPION_PLAYSTYLE_INTENTS = frozenset({
    "CHAMPION_SEMANTIC_PROFILE",
    "CHAMPION_BY_PLAYSTYLE",
    "CHAMPION_BY_WIN_CONDITION",
})

# CC / effect filter intents
CC_EFFECT_INTENTS = frozenset({
    "CHAMPION_BY_CC",
    "CHAMPION_BY_EFFECT",
    "MULTI_PROPERTY_FILTER",
})

# Champion-specific intent → query template (uses {champ} and {lane} placeholders)
CHAMPION_QUERY_TEMPLATES = {
    "LORE_QUERY":   "{champ} lore story biography origin background Runeterra League of Legends",
    "BUILD_QUERY":  "Best build items runes keystone guide for {champ} {lane}League of Legends",
    "SYNERGY_QUERY": "Best duo synergy champions teamfight combos with {champ} League of Legends",
}

# Standalone intent → query template (no champion required)
STANDALONE_QUERY_TEMPLATES = {
    "SKIN_QUERY": "{champ} skins cosmetics chromas splash art catalog League of Legends",
    "ARAM_QUERY": "{champ} ARAM balance damage dealt taken modifiers Howling Abyss League of Legends",
    "ITEM_INFO":  "{item} item stats recipe build cost passive active League of Legends",
    "RUNE_INFO":  "{rune} rune keystone precision domination sorcery resolve inspiration League of Legends",
}

# Team composition counter analysis keywords used to detect counter intent
COUNTER_KEYWORDS = frozenset({
    "counter", "against", "beat", "facing", "versus", "vs", "punish", "enemy",
})
