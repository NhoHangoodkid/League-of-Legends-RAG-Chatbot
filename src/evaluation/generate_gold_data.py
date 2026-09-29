"""
Gold Evaluation Dataset Generator for LoL RAG Pipeline.

Generates labeled test cases for evaluating:
1. Intent Classification Accuracy & F1
2. Entity Extraction Accuracy
3. End-to-End Retrieval (relevant chunk IDs per query)
4. Entity Resolution (fuzzy name -> canonical ID)

Output: JSON files with gold labels for each evaluation dimension.
"""

import json
from pathlib import Path

output_dir = Path(__file__).resolve().parent / "gold_data"


# Part 1: Intent + Entity + Retrieval Gold Dataset (~200 test cases)

INTENT_ENTITY_RETRIEVAL_GOLD = [
    # COUNTER_QUERY (20 cases)
    {
        "query": "Who counters Yasuo?",
        "intent": "COUNTER_QUERY",
        "entities": {"champion_name": "Yasuo", "counter_direction": "countered_by"},
        "relevant_chunks": ["Yasuo::counter"],
    },
    {
        "query": "How to beat Darius in top lane?",
        "intent": "COUNTER_QUERY",
        "entities": {"champion_name": "Darius", "lane": "top", "counter_direction": "countered_by"},
        "relevant_chunks": ["Darius::counter", "Darius::overview"],
    },
    {
        "query": "What champions are weak against Zed?",
        "intent": "COUNTER_QUERY",
        "entities": {"champion_name": "Zed", "counter_direction": "counters"},
        "relevant_chunks": ["Zed::counter"],
    },
    {
        "query": "Who does Ahri counter?",
        "intent": "COUNTER_QUERY",
        "entities": {"champion_name": "Ahri", "counter_direction": "counters"},
        "relevant_chunks": ["Ahri::counter"],
    },
    {
        "query": "Best picks against Vayne bot lane",
        "intent": "COUNTER_QUERY",
        "entities": {"champion_name": "Vayne", "lane": "bot", "counter_direction": "countered_by"},
        "relevant_chunks": ["Vayne::counter"],
    },
    {
        "query": "How to deal with fed Katarina?",
        "intent": "COUNTER_QUERY",
        "entities": {"champion_name": "Katarina", "counter_direction": "countered_by"},
        "relevant_chunks": ["Katarina::counter", "Katarina::overview"],
    },
    {
        "query": "What to pick against Akali mid?",
        "intent": "COUNTER_QUERY",
        "entities": {"champion_name": "Akali", "lane": "mid", "counter_direction": "countered_by"},
        "relevant_chunks": ["Akali::counter"],
    },
    {
        "query": "Who is Malphite strong against?",
        "intent": "COUNTER_QUERY",
        "entities": {"champion_name": "Malphite", "counter_direction": "counters"},
        "relevant_chunks": ["Malphite::counter"],
    },
    {
        "query": "Counter picks for Jinx",
        "intent": "COUNTER_QUERY",
        "entities": {"champion_name": "Jinx", "counter_direction": "countered_by"},
        "relevant_chunks": ["Jinx::counter"],
    },
    {
        "query": "How to play against Irelia?",
        "intent": "COUNTER_QUERY",
        "entities": {"champion_name": "Irelia", "counter_direction": "countered_by"},
        "relevant_chunks": ["Irelia::counter", "Irelia::overview"],
    },
    {
        "query": "What beats Thresh in lane?",
        "intent": "COUNTER_QUERY",
        "entities": {"champion_name": "Thresh", "counter_direction": "countered_by"},
        "relevant_chunks": ["Thresh::counter"],
    },
    {
        "query": "Fiora matchup tips",
        "intent": "COUNTER_QUERY",
        "entities": {"champion_name": "Fiora", "counter_direction": "countered_by"},
        "relevant_chunks": ["Fiora::counter"],
    },
    {
        "query": "Who wins against Lee Sin jungle?",
        "intent": "COUNTER_QUERY",
        "entities": {"champion_name": "LeeSin", "lane": "jungle", "counter_direction": "countered_by"},
        "relevant_chunks": ["Lee Sin::counter"],
    },
    {
        "query": "Renekton counters who?",
        "intent": "COUNTER_QUERY",
        "entities": {"champion_name": "Renekton", "counter_direction": "counters"},
        "relevant_chunks": ["Renekton::counter"],
    },
    {
        "query": "Who should I pick against Yone?",
        "intent": "COUNTER_QUERY",
        "entities": {"champion_name": "Yone", "counter_direction": "countered_by"},
        "relevant_chunks": ["Yone::counter"],
    },
    {
        "query": "Is Garen a counter to Mordekaiser?",
        "intent": "COUNTER_QUERY",
        "entities": {"champion_name": "Mordekaiser", "counter_direction": "countered_by"},
        "relevant_chunks": ["Mordekaiser::counter"],
    },
    {
        "query": "How to counter Teemo as melee?",
        "intent": "COUNTER_QUERY",
        "entities": {"champion_name": "Teemo", "counter_direction": "countered_by"},
        "relevant_chunks": ["Teemo::counter"],
    },
    {
        "query": "What champions does Jax beat?",
        "intent": "COUNTER_QUERY",
        "entities": {"champion_name": "Jax", "counter_direction": "counters"},
        "relevant_chunks": ["Jax::counter"],
    },
    {
        "query": "Lux weaknesses and bad matchups",
        "intent": "COUNTER_QUERY",
        "entities": {"champion_name": "Lux", "counter_direction": "countered_by"},
        "relevant_chunks": ["Lux::counter"],
    },
    {
        "query": "Who to play against Sylas?",
        "intent": "COUNTER_QUERY",
        "entities": {"champion_name": "Sylas", "counter_direction": "countered_by"},
        "relevant_chunks": ["Sylas::counter"],
    },

    # BUILD_QUERY (15 cases)
    {"query": "Best build for Yasuo", "intent": "BUILD_QUERY", "entities": {"champion_name": "Yasuo"}, "relevant_chunks": ["Yasuo::build"]},
    {"query": "What items should I build on Jinx?", "intent": "BUILD_QUERY", "entities": {"champion_name": "Jinx"}, "relevant_chunks": ["Jinx::build"]},
    {"query": "Zed core items and runes", "intent": "BUILD_QUERY", "entities": {"champion_name": "Zed"}, "relevant_chunks": ["Zed::build"]},
    {"query": "Full build Kayn jungle", "intent": "BUILD_QUERY", "entities": {"champion_name": "Kayn", "lane": "jungle"}, "relevant_chunks": ["Kayn::build"]},
    {"query": "Rune page for Lux support", "intent": "BUILD_QUERY", "entities": {"champion_name": "Lux", "lane": "support"}, "relevant_chunks": ["Lux::build"]},
    {"query": "What keystone does Darius use?", "intent": "BUILD_QUERY", "entities": {"champion_name": "Darius"}, "relevant_chunks": ["Darius::build"]},
    {"query": "Optimal itemization for Vayne late game", "intent": "BUILD_QUERY", "entities": {"champion_name": "Vayne"}, "relevant_chunks": ["Vayne::build"]},
    {"query": "Summoner spells for Ahri mid", "intent": "BUILD_QUERY", "entities": {"champion_name": "Ahri", "lane": "mid"}, "relevant_chunks": ["Ahri::build"]},
    {"query": "Best runes for Thresh support", "intent": "BUILD_QUERY", "entities": {"champion_name": "Thresh", "lane": "support"}, "relevant_chunks": ["Thresh::build"]},
    {"query": "Items for Garen top lane", "intent": "BUILD_QUERY", "entities": {"champion_name": "Garen", "lane": "top"}, "relevant_chunks": ["Garen::build"]},
    {"query": "Core build for Ezreal ADC", "intent": "BUILD_QUERY", "entities": {"champion_name": "Ezreal", "lane": "bot"}, "relevant_chunks": ["Ezreal::build"]},
    {"query": "Best Katarina build path", "intent": "BUILD_QUERY", "entities": {"champion_name": "Katarina"}, "relevant_chunks": ["Katarina::build"]},
    {"query": "What should I build first on Camille?", "intent": "BUILD_QUERY", "entities": {"champion_name": "Camille"}, "relevant_chunks": ["Camille::build"]},
    {"query": "Recommended items for Miss Fortune", "intent": "BUILD_QUERY", "entities": {"champion_name": "MissFortune"}, "relevant_chunks": ["Miss Fortune::build"]},
    {"query": "What to build on AP Kai'Sa?", "intent": "BUILD_QUERY", "entities": {"champion_name": "Kai'Sa"}, "relevant_chunks": ["Kai'Sa::build"]},

    # SKILL_INFO / SKILL_DAMAGE / SKILL_COOLDOWN / LIST_SKILLS (20 cases)
    {"query": "What does Yasuo's Q do?", "intent": "SKILL_INFO", "entities": {"champion_name": "Yasuo", "skill_key": "Q"}, "relevant_chunks": ["Yasuo::ability"]},
    {"query": "Lux R damage at level 3", "intent": "SKILL_DAMAGE_AT_LEVEL", "entities": {"champion_name": "Lux", "skill_key": "R", "skill_level": 3}, "relevant_chunks": ["Lux::ability"]},
    {"query": "What is the cooldown of Ahri's E?", "intent": "SKILL_COOLDOWN", "entities": {"champion_name": "Ahri", "skill_key": "E"}, "relevant_chunks": ["Ahri::ability"]},
    {"query": "List all abilities of Thresh", "intent": "LIST_SKILLS", "entities": {"champion_name": "Thresh"}, "relevant_chunks": ["Thresh::ability"]},
    {"query": "Zed W description and mechanics", "intent": "SKILL_INFO", "entities": {"champion_name": "Zed", "skill_key": "W"}, "relevant_chunks": ["Zed::ability"]},
    {"query": "How much damage does Jinx ultimate do?", "intent": "SKILL_DAMAGE_AT_LEVEL", "entities": {"champion_name": "Jinx", "skill_key": "R"}, "relevant_chunks": ["Jinx::ability"]},
    {"query": "What is Veigar passive?", "intent": "SKILL_INFO", "entities": {"champion_name": "Veigar", "skill_key": "P"}, "relevant_chunks": ["Veigar::ability"]},
    {"query": "Describe Ashe's W ability", "intent": "SKILL_INFO", "entities": {"champion_name": "Ashe", "skill_key": "W"}, "relevant_chunks": ["Ashe::ability"]},
    {"query": "All skills of Lee Sin", "intent": "LIST_SKILLS", "entities": {"champion_name": "LeeSin"}, "relevant_chunks": ["Lee Sin::ability"]},
    {"query": "What abilities does Ekko have?", "intent": "LIST_SKILLS", "entities": {"champion_name": "Ekko"}, "relevant_chunks": ["Ekko::ability"]},
    {"query": "Darius R scaling and damage type", "intent": "SKILL_DAMAGE_AT_LEVEL", "entities": {"champion_name": "Darius", "skill_key": "R"}, "relevant_chunks": ["Darius::ability"]},
    {"query": "Blitzcrank Q range and cooldown", "intent": "SKILL_COOLDOWN", "entities": {"champion_name": "Blitzcrank", "skill_key": "Q"}, "relevant_chunks": ["Blitzcrank::ability"]},
    {"query": "What is Katarina E?", "intent": "SKILL_INFO", "entities": {"champion_name": "Katarina", "skill_key": "E"}, "relevant_chunks": ["Katarina::ability"]},
    {"query": "Malphite ultimate description", "intent": "SKILL_INFO", "entities": {"champion_name": "Malphite", "skill_key": "R"}, "relevant_chunks": ["Malphite::ability"]},
    {"query": "How does Fiora W work?", "intent": "SKILL_INFO", "entities": {"champion_name": "Fiora", "skill_key": "W"}, "relevant_chunks": ["Fiora::ability"]},
    {"query": "Vi Q base damage", "intent": "SKILL_DAMAGE_AT_LEVEL", "entities": {"champion_name": "Vi", "skill_key": "Q"}, "relevant_chunks": ["Vi::ability"]},
    {"query": "What are all of Orianna's abilities?", "intent": "LIST_SKILLS", "entities": {"champion_name": "Orianna"}, "relevant_chunks": ["Orianna::ability"]},
    {"query": "Tell me about Syndra Q", "intent": "SKILL_INFO", "entities": {"champion_name": "Syndra", "skill_key": "Q"}, "relevant_chunks": ["Syndra::ability"]},
    {"query": "Rengar passive explained", "intent": "SKILL_INFO", "entities": {"champion_name": "Rengar", "skill_key": "P"}, "relevant_chunks": ["Rengar::ability"]},
    {"query": "Morgana Q cooldown at max rank", "intent": "SKILL_COOLDOWN", "entities": {"champion_name": "Morgana", "skill_key": "Q"}, "relevant_chunks": ["Morgana::ability"]},

    # CHAMPION_INFO / CHAMPION_BASE_STATS / CHAMPION_STATS_AT_LEVEL (15 cases)
    {"query": "Tell me about Jinx", "intent": "CHAMPION_INFO", "entities": {"champion_name": "Jinx"}, "relevant_chunks": ["Jinx::overview"]},
    {"query": "What are Garen's base stats?", "intent": "CHAMPION_BASE_STATS", "entities": {"champion_name": "Garen"}, "relevant_chunks": ["Garen::stats", "Garen::overview"]},
    {"query": "Darius stats at level 10", "intent": "CHAMPION_STATS_AT_LEVEL", "entities": {"champion_name": "Darius", "character_level": 10}, "relevant_chunks": ["Darius::stats"]},
    {"query": "Overview of Thresh as a champion", "intent": "CHAMPION_INFO", "entities": {"champion_name": "Thresh"}, "relevant_chunks": ["Thresh::overview"]},
    {"query": "Guide for Akali", "intent": "CHAMPION_INFO", "entities": {"champion_name": "Akali"}, "relevant_chunks": ["Akali::overview"]},
    {"query": "Vayne base health and armor", "intent": "CHAMPION_BASE_STATS", "entities": {"champion_name": "Vayne"}, "relevant_chunks": ["Vayne::stats"]},
    {"query": "What is Aatrox attack speed at level 18?", "intent": "CHAMPION_STATS_AT_LEVEL", "entities": {"champion_name": "Aatrox", "character_level": 18}, "relevant_chunks": ["Aatrox::stats"]},
    {"query": "Who is Aphelios?", "intent": "CHAMPION_INFO", "entities": {"champion_name": "Aphelios"}, "relevant_chunks": ["Aphelios::overview"]},
    {"query": "Caitlyn base attack damage", "intent": "CHAMPION_BASE_STATS", "entities": {"champion_name": "Caitlyn"}, "relevant_chunks": ["Caitlyn::stats"]},
    {"query": "Tell me about Riven's playstyle", "intent": "CHAMPION_INFO", "entities": {"champion_name": "Riven"}, "relevant_chunks": ["Riven::overview"]},
    {"query": "What type of champion is Senna?", "intent": "CHAMPION_INFO", "entities": {"champion_name": "Senna"}, "relevant_chunks": ["Senna::overview"]},
    {"query": "Jhin movement speed at level 6", "intent": "CHAMPION_STATS_AT_LEVEL", "entities": {"champion_name": "Jhin", "character_level": 6}, "relevant_chunks": ["Jhin::stats"]},
    {"query": "What roles does Kayn play?", "intent": "CHAMPION_INFO", "entities": {"champion_name": "Kayn"}, "relevant_chunks": ["Kayn::overview"]},
    {"query": "Viego stats and overview", "intent": "CHAMPION_INFO", "entities": {"champion_name": "Viego"}, "relevant_chunks": ["Viego::overview", "Viego::stats"]},
    {"query": "Base HP of Cho'Gath", "intent": "CHAMPION_BASE_STATS", "entities": {"champion_name": "Cho'Gath"}, "relevant_chunks": ["Cho'Gath::stats"]},

    # SYNERGY_QUERY (10 cases)
    {"query": "Who synergizes with Yasuo?", "intent": "SYNERGY_QUERY", "entities": {"champion_name": "Yasuo"}, "relevant_chunks": ["Yasuo::synergy"]},
    {"query": "Best duo partner for Jinx bot lane", "intent": "SYNERGY_QUERY", "entities": {"champion_name": "Jinx", "lane": "bot"}, "relevant_chunks": ["Jinx::synergy"]},
    {"query": "Good support for Kai'Sa", "intent": "SYNERGY_QUERY", "entities": {"champion_name": "Kai'Sa"}, "relevant_chunks": ["Kai'Sa::synergy"]},
    {"query": "Champions that pair well with Malphite", "intent": "SYNERGY_QUERY", "entities": {"champion_name": "Malphite"}, "relevant_chunks": ["Malphite::synergy"]},
    {"query": "Who combos well with Orianna?", "intent": "SYNERGY_QUERY", "entities": {"champion_name": "Orianna"}, "relevant_chunks": ["Orianna::synergy"]},
    {"query": "Best ADC to play with Thresh", "intent": "SYNERGY_QUERY", "entities": {"champion_name": "Thresh"}, "relevant_chunks": ["Thresh::synergy"]},
    {"query": "Amumu team synergies", "intent": "SYNERGY_QUERY", "entities": {"champion_name": "Amumu"}, "relevant_chunks": ["Amumu::synergy"]},
    {"query": "Who goes well with Katarina?", "intent": "SYNERGY_QUERY", "entities": {"champion_name": "Katarina"}, "relevant_chunks": ["Katarina::synergy"]},
    {"query": "Lulu pairs with which ADC?", "intent": "SYNERGY_QUERY", "entities": {"champion_name": "Lulu"}, "relevant_chunks": ["Lulu::synergy"]},
    {"query": "Rakan and Xayah synergy", "intent": "SYNERGY_QUERY", "entities": {"champion_name": "Rakan"}, "relevant_chunks": ["Rakan::synergy"]},

    # LORE_QUERY (12 cases)
    {"query": "Tell me about Jinx lore", "intent": "LORE_QUERY", "entities": {"champion_name": "Jinx"}, "relevant_chunks": ["Jinx::overview", "Jinx::lore"]},
    {"query": "What is Yasuo's story?", "intent": "LORE_QUERY", "entities": {"champion_name": "Yasuo"}, "relevant_chunks": ["Yasuo::overview", "Yasuo::lore"]},
    {"query": "Where is Azir from?", "intent": "LORE_QUERY", "entities": {"champion_name": "Azir"}, "relevant_chunks": ["Azir::overview"]},
    {"query": "Zed biography and origin", "intent": "LORE_QUERY", "entities": {"champion_name": "Zed"}, "relevant_chunks": ["Zed::overview", "Zed::lore"]},
    {"query": "Senna and Lucian relationship", "intent": "LORE_QUERY", "entities": {"champion_name": "Senna"}, "relevant_chunks": ["Senna::overview"]},
    {"query": "Vi and Jinx backstory", "intent": "LORE_QUERY", "entities": {"champion_name": "Vi"}, "relevant_chunks": ["Vi::overview"]},
    {"query": "What region is Ahri from?", "intent": "LORE_QUERY", "entities": {"champion_name": "Ahri"}, "relevant_chunks": ["Ahri::overview"]},
    {"query": "Who killed Yasuo's master?", "intent": "LORE_QUERY", "entities": {"champion_name": "Yasuo"}, "relevant_chunks": ["Yasuo::overview", "Yasuo::lore"]},
    {"query": "Thresh lore and shadow isles connection", "intent": "LORE_QUERY", "entities": {"champion_name": "Thresh"}, "relevant_chunks": ["Thresh::overview"]},
    {"query": "Viego story about isolde", "intent": "LORE_QUERY", "entities": {"champion_name": "Viego"}, "relevant_chunks": ["Viego::overview", "Viego::lore"]},
    {"query": "Kayn origin story with Rhaast", "intent": "LORE_QUERY", "entities": {"champion_name": "Kayn"}, "relevant_chunks": ["Kayn::overview", "Kayn::lore"]},
    {"query": "Mordekaiser biography", "intent": "LORE_QUERY", "entities": {"champion_name": "Mordekaiser"}, "relevant_chunks": ["Mordekaiser::overview"]},

    # ITEM_INFO (10 cases)
    {"query": "What does Infinity Edge do?", "intent": "ITEM_INFO", "entities": {"item_name": "Infinity Edge"}, "relevant_chunks": ["Infinity Edge::item_info"]},
    {"query": "Rabadon's Deathcap stats and cost", "intent": "ITEM_INFO", "entities": {"item_name": "Rabadon's Deathcap"}, "relevant_chunks": ["Rabadon's Deathcap::item_info"]},
    {"query": "How much does Zhonya's Hourglass cost?", "intent": "ITEM_INFO", "entities": {"item_name": "Zhonya's Hourglass"}, "relevant_chunks": ["Zhonya's Hourglass::item_info"]},
    {"query": "Blade of The Ruined King passive effect", "intent": "ITEM_INFO", "entities": {"item_name": "Blade of The Ruined King"}, "relevant_chunks": ["Blade of The Ruined King::item_info"]},
    {"query": "What items build into Trinity Force?", "intent": "ITEM_INFO", "entities": {"item_name": "Trinity Force"}, "relevant_chunks": ["Trinity Force::item_info"]},
    {"query": "Black Cleaver stats", "intent": "ITEM_INFO", "entities": {"item_name": "Black Cleaver"}, "relevant_chunks": ["Black Cleaver::item_info"]},
    {"query": "What is the passive of Banshee's Veil?", "intent": "ITEM_INFO", "entities": {"item_name": "Banshee's Veil"}, "relevant_chunks": ["Banshee's Veil::item_info"]},
    {"query": "Guardian Angel recipe and stats", "intent": "ITEM_INFO", "entities": {"item_name": "Guardian Angel"}, "relevant_chunks": ["Guardian Angel::item_info"]},
    {"query": "Ardent Censer effect for supports", "intent": "ITEM_INFO", "entities": {"item_name": "Ardent Censer"}, "relevant_chunks": ["Ardent Censer::item_info"]},
    {"query": "What does Axiom Arc do?", "intent": "ITEM_INFO", "entities": {"item_name": "Axiom Arc"}, "relevant_chunks": ["Axiom Arc::item_info"]},

    # RUNE_INFO (8 cases)
    {"query": "What does Conqueror do?", "intent": "RUNE_INFO", "entities": {"rune_name": "Conqueror"}, "relevant_chunks": ["Conqueror::rune_info"]},
    {"query": "Electrocute rune description", "intent": "RUNE_INFO", "entities": {"rune_name": "Electrocute"}, "relevant_chunks": ["Electrocute::rune_info"]},
    {"query": "How does Grasp of the Undying work?", "intent": "RUNE_INFO", "entities": {"rune_name": "Grasp of the Undying"}, "relevant_chunks": ["Grasp of the Undying::rune_info"]},
    {"query": "Fleet Footwork keystone explained", "intent": "RUNE_INFO", "entities": {"rune_name": "Fleet Footwork"}, "relevant_chunks": ["Fleet Footwork::rune_info"]},
    {"query": "Arcane Comet rune effect", "intent": "RUNE_INFO", "entities": {"rune_name": "Arcane Comet"}, "relevant_chunks": ["Arcane Comet::rune_info"]},
    {"query": "What is Aftershock rune?", "intent": "RUNE_INFO", "entities": {"rune_name": "Aftershock"}, "relevant_chunks": ["Aftershock::rune_info"]},
    {"query": "Lethal Tempo rune description and stats", "intent": "RUNE_INFO", "entities": {"rune_name": "Lethal Tempo"}, "relevant_chunks": ["Lethal Tempo::rune_info"]},
    {"query": "Dark Harvest rune mechanism", "intent": "RUNE_INFO", "entities": {"rune_name": "Dark Harvest"}, "relevant_chunks": ["Dark Harvest::rune_info"]},

    # CHAMPION_COMPARISON (8 cases)
    {"query": "Yasuo vs Yone who is better?", "intent": "CHAMPION_COMPARISON", "entities": {"champion_name": "Yasuo", "comparison_champions": ["Yasuo", "Yone"]}, "relevant_chunks": ["Yasuo::overview", "Yone::overview"]},
    {"query": "Compare Darius and Garen top lane", "intent": "CHAMPION_COMPARISON", "entities": {"comparison_champions": ["Darius", "Garen"]}, "relevant_chunks": ["Darius::overview", "Garen::overview"]},
    {"query": "Zed vs Talon who wins solo?", "intent": "CHAMPION_COMPARISON", "entities": {"comparison_champions": ["Zed", "Talon"]}, "relevant_chunks": ["Zed::overview", "Talon::overview"]},
    {"query": "Vayne versus Kai'Sa comparison", "intent": "CHAMPION_COMPARISON", "entities": {"comparison_champions": ["Vayne", "Kai'Sa"]}, "relevant_chunks": ["Vayne::overview", "Kai'Sa::overview"]},
    {"query": "Jinx vs Caitlyn who is stronger late game?", "intent": "CHAMPION_COMPARISON", "entities": {"comparison_champions": ["Jinx", "Caitlyn"]}, "relevant_chunks": ["Jinx::overview", "Caitlyn::overview"]},
    {"query": "Leona vs Thresh support comparison", "intent": "CHAMPION_COMPARISON", "entities": {"comparison_champions": ["Leona", "Thresh"]}, "relevant_chunks": ["Leona::overview", "Thresh::overview"]},
    {"query": "Ahri vs Syndra mid matchup", "intent": "CHAMPION_COMPARISON", "entities": {"comparison_champions": ["Ahri", "Syndra"]}, "relevant_chunks": ["Ahri::overview", "Syndra::overview"]},
    {"query": "Lee Sin versus Elise jungle comparison", "intent": "CHAMPION_COMPARISON", "entities": {"comparison_champions": ["Lee Sin", "Elise"]}, "relevant_chunks": ["Lee Sin::overview", "Elise::overview"]},

    # ABILITY_MECHANIC_QUERY (8 cases)
    {"query": "Does Yasuo's wind wall block Lux R?", "intent": "ABILITY_MECHANIC_QUERY", "entities": {"champion_name": "Lux", "skill_key": "R", "interaction_champion": "Yasuo", "mechanic": "projectile"}, "relevant_chunks": ["Lux::ability"]},
    {"query": "Is Caitlyn Q a projectile?", "intent": "ABILITY_MECHANIC_QUERY", "entities": {"champion_name": "Caitlyn", "skill_key": "Q", "mechanic": "projectile"}, "relevant_chunks": ["Caitlyn::ability"]},
    {"query": "Can spell shield block Malzahar R?", "intent": "ABILITY_MECHANIC_QUERY", "entities": {"champion_name": "Malzahar", "skill_key": "R", "mechanic": "spellshieldable"}, "relevant_chunks": ["Malzahar::ability"]},
    {"query": "Does Ezreal Q apply on-hit effects?", "intent": "ABILITY_MECHANIC_QUERY", "entities": {"champion_name": "Ezreal", "skill_key": "Q", "mechanic": "onhit"}, "relevant_chunks": ["Ezreal::ability"]},
    {"query": "Is Blitzcrank Q blocked by wind wall?", "intent": "ABILITY_MECHANIC_QUERY", "entities": {"champion_name": "Blitzcrank", "skill_key": "Q", "mechanic": "projectile"}, "relevant_chunks": ["Blitzcrank::ability"]},
    {"query": "Can Banshee's Veil block Zed R?", "intent": "ABILITY_MECHANIC_QUERY", "entities": {"champion_name": "Zed", "skill_key": "R", "mechanic": "spellshieldable"}, "relevant_chunks": ["Zed::ability"]},
    {"query": "Does Ashe R get blocked by wind wall?", "intent": "ABILITY_MECHANIC_QUERY", "entities": {"champion_name": "Ashe", "skill_key": "R", "mechanic": "projectile"}, "relevant_chunks": ["Ashe::ability"]},
    {"query": "Is Gangplank Q on-hit?", "intent": "ABILITY_MECHANIC_QUERY", "entities": {"champion_name": "Gangplank", "skill_key": "Q", "mechanic": "onhit"}, "relevant_chunks": ["Gangplank::ability"]},

    # CHAMPION_BY_CC / CHAMPION_BY_EFFECT (10 cases)
    {"query": "Which champions have stun?", "intent": "CHAMPION_BY_CC", "entities": {"cc_types": ["Stun"]}, "relevant_chunks": []},
    {"query": "Champions with knockup abilities", "intent": "CHAMPION_BY_CC", "entities": {"cc_types": ["Knockup"]}, "relevant_chunks": []},
    {"query": "Who has a root in their kit?", "intent": "CHAMPION_BY_CC", "entities": {"cc_types": ["Root"]}, "relevant_chunks": []},
    {"query": "Champions with charm CC", "intent": "CHAMPION_BY_CC", "entities": {"cc_types": ["Charm"]}, "relevant_chunks": []},
    {"query": "Which champions have suppress?", "intent": "CHAMPION_BY_CC", "entities": {"cc_types": ["Suppress"]}, "relevant_chunks": []},
    {"query": "Champions with dash abilities", "intent": "CHAMPION_BY_EFFECT", "entities": {"ability_effects": ["Dash"]}, "relevant_chunks": []},
    {"query": "Who has stealth in their kit?", "intent": "CHAMPION_BY_EFFECT", "entities": {"ability_effects": ["Stealth"]}, "relevant_chunks": []},
    {"query": "Champions with shield abilities", "intent": "CHAMPION_BY_EFFECT", "entities": {"ability_effects": ["Shield"]}, "relevant_chunks": []},
    {"query": "Which champions can hook?", "intent": "CHAMPION_BY_EFFECT", "entities": {"ability_effects": ["Pull"]}, "relevant_chunks": []},
    {"query": "Champions with healing abilities", "intent": "CHAMPION_BY_EFFECT", "entities": {"ability_effects": ["Heal"]}, "relevant_chunks": []},

    # TEAM_COMPOSITION_BUILDING / TEAM_COUNTER_ANALYSIS (15 cases)
    {"query": "How to draft a dive composition?", "intent": "TEAM_COMPOSITION_BUILDING", "entities": {"comp_archetype": "dive"}, "relevant_chunks": ["dive::composition"]},
    {"query": "Best champions for poke comp", "intent": "TEAM_COMPOSITION_BUILDING", "entities": {"comp_archetype": "poke"}, "relevant_chunks": ["poke::composition"]},
    {"query": "How to build a wombo combo team?", "intent": "TEAM_COMPOSITION_BUILDING", "entities": {"comp_archetype": "wombo_combo"}, "relevant_chunks": ["wombo_combo::composition"]},
    {"query": "Draft a hypercarry protect composition", "intent": "TEAM_COMPOSITION_BUILDING", "entities": {"comp_archetype": "hypercarry_protect"}, "relevant_chunks": ["hypercarry_protect::composition"]},
    {"query": "Splitpush team composition guide", "intent": "TEAM_COMPOSITION_BUILDING", "entities": {"comp_archetype": "splitpush"}, "relevant_chunks": ["splitpush::composition"]},
    {"query": "How to counter a dive composition?", "intent": "TEAM_COUNTER_ANALYSIS", "entities": {"comp_archetype": "dive"}, "relevant_chunks": ["dive::composition"]},
    {"query": "What beats a poke comp?", "intent": "TEAM_COUNTER_ANALYSIS", "entities": {"comp_archetype": "poke"}, "relevant_chunks": ["poke::composition"]},
    {"query": "How to counter full AD team?", "intent": "TEAM_COUNTER_ANALYSIS", "entities": {"damage_composition": "full_ad"}, "relevant_chunks": ["full_ad::composition"]},
    {"query": "Counter strategy against full AP team", "intent": "TEAM_COUNTER_ANALYSIS", "entities": {"damage_composition": "full_ap"}, "relevant_chunks": ["full_ap::composition"]},
    {"query": "How to beat a heavy CC team composition?", "intent": "TEAM_COUNTER_ANALYSIS", "entities": {"comp_archetype": "heavy_cc"}, "relevant_chunks": ["heavy_cc::composition"]},
    {"query": "Counter picks against Yasuo Malphite Amumu Lee Sin Jinx", "intent": "TEAM_COUNTER_ANALYSIS", "entities": {"enemy_champions": ["Yasuo", "Malphite", "Amumu", "Lee Sin", "Jinx"]}, "relevant_chunks": []},
    {"query": "Early snowball comp champions and playstyle", "intent": "TEAM_COMPOSITION_BUILDING", "entities": {"comp_archetype": "early_snowball", "power_curve": "EarlyGame"}, "relevant_chunks": []},
    {"query": "How to draft against a scaling team?", "intent": "TEAM_COUNTER_ANALYSIS", "entities": {"comp_archetype": "hypercarry_protect"}, "relevant_chunks": ["hypercarry_protect::composition"]},
    {"query": "Best assassin team composition", "intent": "TEAM_COMPOSITION_BUILDING", "entities": {"comp_archetype": "assassin_heavy"}, "relevant_chunks": ["assassin_heavy::composition"]},
    {"query": "Tank heavy team comp guide", "intent": "TEAM_COMPOSITION_BUILDING", "entities": {"comp_archetype": "tank_heavy"}, "relevant_chunks": ["tank_heavy::composition"]},

    # ROLE_COUNTER_PICK / ROLE_QUERY / SEMANTIC PROFILE / POWER_CURVE (15 cases)
    {"query": "Best support to pick against assassins?", "intent": "ROLE_COUNTER_PICK", "entities": {"user_role": "support", "target": "assassin", "target_type": "role"}, "relevant_chunks": []},
    {"query": "Which tank is good against dive compositions?", "intent": "ROLE_COUNTER_PICK", "entities": {"user_role": "tank", "target": "dive", "target_type": "archetype"}, "relevant_chunks": []},
    {"query": "What ADC to pick against Draven?", "intent": "ROLE_COUNTER_PICK", "entities": {"user_role": "marksman", "target": "Draven", "target_type": "champion"}, "relevant_chunks": []},
    {"query": "Best mid laner against assassins", "intent": "ROLE_COUNTER_PICK", "entities": {"user_role": "mid", "target": "assassin", "target_type": "role"}, "relevant_chunks": []},
    {"query": "Which jungler counters tank heavy teams?", "intent": "ROLE_COUNTER_PICK", "entities": {"user_role": "jungle", "target": "tank_heavy", "target_type": "archetype"}, "relevant_chunks": []},
    {"query": "What are the best marksman champions?", "intent": "ROLE_QUERY", "entities": {"role": "marksman"}, "relevant_chunks": []},
    {"query": "Which champions are played mid lane?", "intent": "ROLE_QUERY", "entities": {"lane": "mid"}, "relevant_chunks": []},
    {"query": "Best jungle picks right now", "intent": "ROLE_QUERY", "entities": {"lane": "jungle"}, "relevant_chunks": []},
    {"query": "Good tank champions for top lane", "intent": "ROLE_QUERY", "entities": {"role": "tank", "lane": "top"}, "relevant_chunks": []},
    {"query": "Support champion pool recommendations", "intent": "ROLE_QUERY", "entities": {"role": "support"}, "relevant_chunks": []},
    {"query": "What is Fiora's playstyle?", "intent": "CHAMPION_SEMANTIC_PROFILE", "entities": {"champion_name": "Fiora"}, "relevant_chunks": ["Fiora::overview"]},
    {"query": "What is Nasus win condition?", "intent": "CHAMPION_SEMANTIC_PROFILE", "entities": {"champion_name": "Nasus"}, "relevant_chunks": ["Nasus::overview"]},
    {"query": "Best late game scaling champions", "intent": "CHAMPION_BY_POWER_CURVE", "entities": {"power_curve": "LateGame"}, "relevant_chunks": []},
    {"query": "Early game dominant champions", "intent": "CHAMPION_BY_POWER_CURVE", "entities": {"power_curve": "EarlyGame"}, "relevant_chunks": []},
    {"query": "How to play Zed effectively?", "intent": "CHAMPION_SEMANTIC_PROFILE", "entities": {"champion_name": "Zed"}, "relevant_chunks": ["Zed::overview"]},

    # EDGE CASES / UNKNOWN / OUT-OF-SCOPE (10 cases)
    {"query": "What is the weather today?", "intent": "UNKNOWN", "entities": {}, "relevant_chunks": []},
    {"query": "How to get better at League?", "intent": "UNKNOWN", "entities": {}, "relevant_chunks": []},
    {"query": "Is League of Legends free to play?", "intent": "UNKNOWN", "entities": {}, "relevant_chunks": []},
    {"query": "Hello", "intent": "UNKNOWN", "entities": {}, "relevant_chunks": []},
    {"query": "Thanks for the help!", "intent": "UNKNOWN", "entities": {}, "relevant_chunks": []},
    {"query": "Aatrox", "intent": "CHAMPION_INFO", "entities": {"champion_name": "Aatrox"}, "relevant_chunks": ["Aatrox::overview"]},
    {"query": "Infinity Edge", "intent": "ITEM_INFO", "entities": {"item_name": "Infinity Edge"}, "relevant_chunks": ["Infinity Edge::item_info"]},
    {"query": "Who has the most skins?", "intent": "UNKNOWN", "entities": {}, "relevant_chunks": []},
    {"query": "How many champions are in League?", "intent": "UNKNOWN", "entities": {}, "relevant_chunks": []},
    {"query": "Explain how to last hit minions", "intent": "UNKNOWN", "entities": {}, "relevant_chunks": []},
]


# Part 2: Entity Resolution Gold Dataset (~60 test cases)

ENTITY_RESOLUTION_GOLD = [
    # Exact matches
    {"input": "Yasuo", "expected_id": "Yasuo"},
    {"input": "Jinx", "expected_id": "Jinx"},
    {"input": "Ahri", "expected_id": "Ahri"},
    {"input": "Thresh", "expected_id": "Thresh"},
    {"input": "Darius", "expected_id": "Darius"},
    {"input": "Zed", "expected_id": "Zed"},

    # Case insensitive
    {"input": "yasuo", "expected_id": "Yasuo"},
    {"input": "JINX", "expected_id": "Jinx"},
    {"input": "thresh", "expected_id": "Thresh"},
    {"input": "lux", "expected_id": "Lux"},

    # Multi-word champions (CamelCase IDs)
    {"input": "Lee Sin", "expected_id": "LeeSin"},
    {"input": "lee sin", "expected_id": "LeeSin"},
    {"input": "Miss Fortune", "expected_id": "MissFortune"},
    {"input": "miss fortune", "expected_id": "MissFortune"},
    {"input": "Aurelion Sol", "expected_id": "AurelionSol"},
    {"input": "aurelion sol", "expected_id": "AurelionSol"},
    {"input": "Dr. Mundo", "expected_id": "DrMundo"},
    {"input": "dr mundo", "expected_id": "DrMundo"},
    {"input": "Cho'Gath", "expected_id": "Chogath"},
    {"input": "chogath", "expected_id": "Chogath"},
    {"input": "Kai'Sa", "expected_id": "Kaisa"},
    {"input": "kaisa", "expected_id": "Kaisa"},
    {"input": "Kog'Maw", "expected_id": "KogMaw"},
    {"input": "kogmaw", "expected_id": "KogMaw"},
    {"input": "Vel'Koz", "expected_id": "Velkoz"},
    {"input": "Rek'Sai", "expected_id": "RekSai"},
    {"input": "Kha'Zix", "expected_id": "Khazix"},
    {"input": "Xin Zhao", "expected_id": "XinZhao"},
    {"input": "Twisted Fate", "expected_id": "TwistedFate"},
    {"input": "Tahm Kench", "expected_id": "TahmKench"},
    {"input": "Jarvan IV", "expected_id": "JarvanIV"},

    # Common abbreviations / nicknames
    {"input": "MF", "expected_id": "MissFortune"},
    {"input": "TF", "expected_id": "TwistedFate"},
    {"input": "GP", "expected_id": "Gangplank"},
    {"input": "J4", "expected_id": "JarvanIV"},

    # Partial / fuzzy inputs
    {"input": "Yas", "expected_id": "Yasuo"},
    {"input": "Kata", "expected_id": "Katarina"},
    {"input": "Morde", "expected_id": "Mordekaiser"},
    {"input": "Mundo", "expected_id": "DrMundo"},
    {"input": "Blitz", "expected_id": "Blitzcrank"},
    {"input": "Cait", "expected_id": "Caitlyn"},
    {"input": "Vlad", "expected_id": "Vladimir"},
    {"input": "Sol", "expected_id": "AurelionSol"},
    {"input": "Naut", "expected_id": "Nautilus"},
    {"input": "Ori", "expected_id": "Orianna"},
    {"input": "Ren", "expected_id": "Renekton"},
    {"input": "Nida", "expected_id": "Nidalee"},
    {"input": "Eve", "expected_id": "Evelynn"},
    {"input": "Morg", "expected_id": "Morgana"},
    {"input": "Heim", "expected_id": "Heimerdinger"},
    {"input": "WW", "expected_id": "Warwick"},

    # Should NOT match (non-existent)
    {"input": "Ryu", "expected_id": None},
    {"input": "Pikachu", "expected_id": None},
    {"input": "Superman", "expected_id": None},
    {"input": "abc123", "expected_id": None},
]


# Part 3: Save datasets to disk

def generate_datasets():
    """Generate and save all gold evaluation datasets."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Intent + Entity + Retrieval Gold
    intent_path = output_dir / "intent_entity_retrieval_gold.json"
    with open(intent_path, "w", encoding="utf-8") as f:
        json.dump(INTENT_ENTITY_RETRIEVAL_GOLD, f, indent=2, ensure_ascii=False)
    print(f"[GoldDataGen] Saved {len(INTENT_ENTITY_RETRIEVAL_GOLD)} intent/entity/retrieval test cases")

    # Count per intent
    intent_counts = {}
    for entry in INTENT_ENTITY_RETRIEVAL_GOLD:
        intent = entry["intent"]
        intent_counts[intent] = intent_counts.get(intent, 0) + 1
    print(f"  Intent distribution:")
    for intent, count in sorted(intent_counts.items(), key=lambda x: -x[1]):
        print(f"    {intent}: {count}")

    # 2. Entity Resolution Gold
    entity_path = output_dir / "entity_resolution_gold.json"
    with open(entity_path, "w", encoding="utf-8") as f:
        json.dump(ENTITY_RESOLUTION_GOLD, f, indent=2, ensure_ascii=False)
    print(f"[GoldDataGen] Saved {len(ENTITY_RESOLUTION_GOLD)} entity resolution test cases")

    print(f"\n[GoldDataGen] All datasets saved to {output_dir}")


if __name__ == "__main__":
    generate_datasets()
