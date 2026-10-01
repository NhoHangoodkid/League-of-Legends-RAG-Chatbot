"""
Data tables for role-specific counter pick recommendations.

Contains item recommendation tables, kit scoring rules, and tactical guidelines
extracted from DataRetriever.get_role_counter_picks().
"""

# Role display name mapping
ROLE_DISPLAY_NAMES = {
    "marksman": "Marksman (ADC)",
    "support": "Support",
    "mage": "Mage",
    "fighter": "Fighter / Bruiser",
    "tank": "Tank",
    "assassin": "Assassin",
    "mid": "Mid Laner",
    "top": "Top Laner",
    "jungle": "Jungler",
}

# Kit Scoring Rules
# Each entry: (target_aliases, rules_list)
# rules_list items: {"keywords": [...], "score": int, "template": str}
# Templates use {name} for ability name and {key} for skill key (Q/W/E/R)
KIT_SCORING_RULES = [
    # Against Tanks
    {
        "targets": ("tank", "tank_heavy", "tanker"),
        "rules": [
            {"keywords": ["maximum health", "max health", "% max hp", "percent of the target's maximum health"],
             "score": 6, "template": "**{name} ({key})** inflicts % maximum health damage to shred high HP pools."},
            {"keywords": ["current health"],
             "score": 4, "template": "**{name} ({key})** inflicts % current health damage on-hit."},
            {"keywords": ["missing health", "low health"],
             "score": 2, "template": "**{name} ({key})** deals % missing health execute damage."},
            {"keywords": ["true damage"],
             "score": 5, "template": "**{name} ({key})** deals true damage, completely bypassing high armor stacking."},
            {"keywords": ["armor pen", "shred", "reduces armor", "corrodes", "corrode", "magic resist", "penetrat"],
             "score": 4, "template": "**{name} ({key})** shreds enemy defensive resistances."},
        ],
    },
    # Against Assassins
    {
        "targets": ("assassin", "assassin_heavy"),
        "rules": [
            {"keywords": ["untargetable", "invulnerable", "stasis"],
             "score": 6, "template": "**{name} ({key})** grants untargetability to dodge lethal burst rotations."},
            {"keywords": ["shield", "barrier", "absorb"],
             "score": 4, "template": "**{name} ({key})** generates defensive shields to absorb all-in burst."},
            {"keywords": ["knockup", "stun", "suppress", "silence", "taunt"],
             "score": 4, "template": "**{name} ({key})** locks down flanking assassins with hard crowd control."},
            {"keywords": ["stealth", "invisib", "camouflage"],
             "score": 3, "template": "**{name} ({key})** uses stealth to reposition safely out of assassin target acquisition."},
        ],
    },
    # Against Dive / Hard Engage
    {
        "targets": ("dive", "heavy_cc", "engage", "wombo_combo"),
        "rules": [
            {"keywords": ["knockback", "ground", "disengage", "pushes away", "knocks back"],
             "score": 6, "template": "**{name} ({key})** disengages diving champions and resets engagement spacing."},
            {"keywords": ["knockup", "stun", "suppress"],
             "score": 4, "template": "**{name} ({key})** interrupts gap-closers and dashes with instant crowd control."},
            {"keywords": ["shield", "heal"],
             "score": 3, "template": "**{name} ({key})** provides durability to withstand initial dive combo."},
        ],
    },
    # Against Mages / Poke
    {
        "targets": ("mage", "mage_heavy", "poke"),
        "rules": [
            {"keywords": ["spell shield", "magic shield", "magic resist"],
             "score": 5, "template": "**{name} ({key})** negates hostile spell casts with magic protection."},
            {"keywords": ["dash", "blink", "gap close"],
             "score": 4, "template": "**{name} ({key})** closes the distance rapidly to punish immobile ranged casters."},
        ],
    },
]

# Generic scoring for "champion" target type (no specific archetype match)
CHAMPION_TARGET_SCORING = {
    "cc_keywords": ["knockup", "stun", "suppress", "silence"],
    "cc_score": 2,
    "utility_keywords": ["true damage", "shield", "untargetable"],
    "utility_score": 2,
}

# Attack range bonus thresholds
RANGE_BONUS = {
    "targets": ("tank", "tank_heavy", "tanker"),
    "min_range": 600,
    "score": 3,
    "template": "Exceptional attack range ({range}) enables safe perimeter kiting outside tank engage threat.",
    "mobility_effects": ("Dash", "Blink"),
    "mobility_score": 2,
}


# Role-Specific Counter Item Recommendations
# Structure: { target_group: { role: [item_names] } }
# "default" is used when no specific role matches
ROLE_COUNTER_ITEMS = {
    ("tank", "tank_heavy", "tanker"): {
        "marksman":         ["Lord Dominik's Regards", "Blade of the Ruined King", "Mortal Reminder", "Terminus"],
        "mage":             ["Liandry's Torment", "Void Staff", "Cryptbloom", "Blackfire Torch"],
        "mid":              ["Liandry's Torment", "Void Staff", "Cryptbloom", "Blackfire Torch"],
        "fighter":          ["Black Cleaver", "Blade of the Ruined King", "Eclipse", "Sundered Sky"],
        "top":              ["Black Cleaver", "Blade of the Ruined King", "Eclipse", "Sundered Sky"],
        "support":          ["Imperial Mandate", "Abyssal Mask", "Shurelya's Battlesong", "Morellonomicon"],
        "default":          ["Lord Dominik's Regards", "Blade of the Ruined King", "Black Cleaver", "Liandry's Torment"],
    },
    ("assassin", "assassin_heavy"): {
        "marksman":         ["Guardian Angel", "Immortal Shieldbow", "Maw of Malmortius", "Edge of Night"],
        "mage":             ["Zhonya's Hourglass", "Banshee's Veil", "Seraph's Embrace", "RoA"],
        "mid":              ["Zhonya's Hourglass", "Banshee's Veil", "Seraph's Embrace", "RoA"],
        "fighter":          ["Death's Dance", "Sterak's Gage", "Maw of Malmortius", "Guardian Angel"],
        "top":              ["Death's Dance", "Sterak's Gage", "Maw of Malmortius", "Guardian Angel"],
        "support":          ["Locket of the Iron Solari", "Knight's Vow", "Redemption", "Zhonya's Hourglass"],
        "default":          ["Guardian Angel", "Zhonya's Hourglass", "Death's Dance", "Randuin's Omen"],
    },
    ("dive", "heavy_cc", "engage"): {
        "marksman":         ["Immortal Shieldbow", "Guardian Angel", "Edge of Night", "Mercurial Scimitar"],
        "mage":             ["Zhonya's Hourglass", "Banshee's Veil", "Crown of the Shattered Queen"],
        "mid":              ["Zhonya's Hourglass", "Banshee's Veil", "Crown of the Shattered Queen"],
        "default":          ["Zhonya's Hourglass", "Locket of the Iron Solari", "Frozen Heart", "Randuin's Omen"],
    },
}

DEFAULT_COUNTER_ITEMS = ["Plated Steelcaps", "Mercury's Treads", "Zhonya's Hourglass", "Guardian Angel"]


# Tactical Guidelines
# Structure: { target_group: [guideline_strings] }
TACTICAL_GUIDELINES = {
    ("tank", "tank_heavy", "tanker"): [
        "Front-to-Back Teamfighting: Focus down the nearest frontline tank first; never dive or walk past high-CC tanks to reach backline targets.",
        "Perimeter Spacing and Attack-Moving: Continuously kite at maximum weapon range using Attack-Move (Orbwalking) to maintain a protective spacing buffer.",
        "Bait Engage Cooldowns: Hold your primary defensive mobility (Flash, dash, blink) until the enemy tank commits their primary crowd control skillshot.",
        "Prioritize Armor Penetration: Complete an early Last Whisper or on-hit component on your 2nd or 3rd item recall before the enemy completes two armor items.",
    ],
    ("assassin", "assassin_heavy"): [
        "Never Face-Check Fog of War: Maintain defensive positioning behind allied frontline and establish perimeter control with defensive wards.",
        "Hold Defensive Spells for All-In: Never expend key escape or self-peel abilities aggressively; save them specifically to interrupt assassin gap-closers.",
        "Stay Clustered with Support: Position within peel range of enchanters and wardens who can provide instant shields, heals, or knockups.",
        "Itemize Early Survivability: An early Stopwatch, Cloth Armor, or Null-Magic Mantle prevents assassins from snowballing early leads.",
    ],
    ("dive", "heavy_cc", "engage"): [
        "Respect Primary Engage Ranges: Track flash cooldowns and dangerous gap-closing abilities (Malphite R, Leona R, Jarvan EQ).",
        "Layer Crowd Control on Secondary Dives: Once the primary tank initiates, immediately lockdown the follow-up burst carries before they can enter range.",
        "Pre-emptively Cast Defensive Disengage: Use displacement spells (knockbacks, tornadoes, flays) reactively mid-dash to cancel enemy momentum.",
    ],
}

DEFAULT_TACTICAL_GUIDELINES = [
    "Maintain vision control around objective choke points before starting neutral monsters.",
    "Track enemy cooldowns and trade immediately after high-impact enemy skillshots are expended.",
    "Prioritize wave management to deny roaming opportunities into side lanes.",
]


def get_items_for_matchup(target_str, role_str):
    """Look up recommended counter items for a target×role combination."""
    for target_group, role_map in ROLE_COUNTER_ITEMS.items():
        if target_str in target_group:
            return role_map.get(role_str) or role_map.get("default") or role_map.get("_default", DEFAULT_COUNTER_ITEMS)
    return DEFAULT_COUNTER_ITEMS


def get_guidelines_for_target(target_str):
    """Look up tactical guidelines for a target archetype."""
    for target_group, guidelines in TACTICAL_GUIDELINES.items():
        if target_str in target_group:
            return guidelines
    return DEFAULT_TACTICAL_GUIDELINES


def score_ability_against_target(target_str, desc_lower, ability_name, skill_key):
    """
    Score a champion ability against a target archetype using keyword matching.

    Returns (score_delta, mechanic_description) or (0, None) if no match.
    """
    total_score = 0
    mechanics = []

    for rule_group in KIT_SCORING_RULES:
        if target_str not in rule_group["targets"]:
            continue
        for rule in rule_group["rules"]:
            if any(kw in desc_lower for kw in rule["keywords"]):
                total_score += rule["score"]
                mechanics.append(
                    rule["template"].format(name=ability_name, key=skill_key)
                )

    # Generic champion-target scoring
    if not mechanics and target_str not in {t for rg in KIT_SCORING_RULES for t in rg["targets"]}:
        ct = CHAMPION_TARGET_SCORING
        if any(kw in desc_lower for kw in ct["cc_keywords"]):
            total_score += ct["cc_score"]
        if any(kw in desc_lower for kw in ct["utility_keywords"]):
            total_score += ct["utility_score"]

    return total_score, mechanics
