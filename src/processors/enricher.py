"""
Champion Enricher & Automated Tactical Counter Engine.

Adds strategic and relational metadata to champions with 100% automated coverage:
- Playstyles (Burst, Poke, Sustained, Utility, Engage, etc.) - 100% Automated
- Power curves (EarlyGame, MidGame, LateGame) - 100% Automated
- Win conditions (Teamfight, Splitpush, Pick, Siege, Objective, Skirmish) - 100% Automated
- Subroles (17 Riot official classifications: Juggernaut, Vanguard, Artillery, Skirmisher, etc.)
- Positions (Top, Jungle, Mid, Bot, Support)
- Tactical Counter Intelligence (Weaknesses, Tactical Tips, Counter Items, Matchup Dynamics) - 100% Automated & in English.
Zero hardcoded champion name dictionaries. Designed to scale seamlessly to 1,000+ champions.
"""

import os


try:
    from .utils import PROCESSED_DIR, load_json, save_json, log
except ImportError:
    try:
        from processors.utils import PROCESSED_DIR, load_json, save_json, log
    except ImportError:
        from utils import PROCESSED_DIR, load_json, save_json, log


# Tunable Heuristic Thresholds (Centralized Configuration)
# Adjust these values to fine-tune automated classification accuracy.

THRESHOLDS = {
    # Range Classification
    "melee_range_max": 225,         # Attack range <= this → melee
    "ranged_min": 500,              # Attack range >= this → ranged carry
    "artillery_range_min": 600,     # Attack range >= this → artillery/poke

    # Power Curve: Late Game Scaling Indicators
    "late_ad_growth": 3.6,          # AD per-level growth >= this → late scaler
    "late_hp_growth": 108,          # HP per-level growth >= this → late scaler
    "late_as_growth": 2.5,          # AS per-level growth >= this (marksman) → late scaler

    # Power Curve: Early Game Bully Indicators
    "early_base_ad_marksman": 63,   # Base AD >= this (marksman) → early bully
    "early_base_hp_fighter": 640,   # Base HP >= this (fighter) → early bully
    "early_ad_growth_cap": 3.2,     # AD growth <= this → not scaling, early focused
    "early_hp_growth_cap_diver": 100,       # HP growth < this (diver/catcher) → early focused
    "early_base_ad_juggernaut": 62,         # Base AD >= this (juggernaut) → early bully
    "early_hp_growth_cap_juggernaut": 105,  # HP growth < this (juggernaut) → early focused

    # Attribute Rating Thresholds
    "high_rating": 3,   # Rating >= this → strong in that attribute
    "medium_rating": 2,  # Rating >= this → moderate in that attribute
    "low_rating": 1,     # Rating <= this → weak in that attribute
}

# Ability Keyword Detection (for automated kit analysis)

ABILITY_KEYWORDS = {
    "channel": ["channel", "duration of up to", "interrupted by crowd control"],
    "heal_drain": ["heal", "vamp", "lifesteal", "drain", "restores health"],
    "shield": ["shield", "absorbs damage"],
    "stealth": ["stealth", "invisible", "camouflaged"],
    "dash": ["dash", "leap", "blink", "teleport", "charges forward"],
}

# Counter Item Profiles (grouped by defensive purpose)

COUNTER_ITEM_PROFILES = {
    "anti_physical_ranged": ["Plated Steelcaps", "Frozen Heart", "Randuin's Omen", "Thornmail"],
    "anti_physical_melee": ["Plated Steelcaps", "Zhonya's Hourglass", "Death's Dance", "Sterak's Gage"],
    "anti_magic": ["Mercury's Treads", "Kaenic Rookern", "Maw of Malmortius", "Banshee's Veil"],
    "anti_tank": ["Blade of the Ruined King", "Liandry's Torment", "Lord Dominik's Regards"],
    "anti_heal": ["Thornmail", "Chempunk Chainsword"],
    "fallback": ["Zhonya's Hourglass", "Thornmail", "Mercury's Treads"],
}

# 100% Automated Tactical Counter Engine (Scalable to 1,000+ Champions)
# All generated data is strictly maintained in standard English.

def derive_tactical_counter(champ, existing_counter_doc=None):
    """
    Derive comprehensive tactical counter metadata 100% algorithmically from champion telemetry.
    
    Evaluates:
    1. Range & Spacing (Melee kiting vulnerability vs. Ranged dive vulnerability)
    2. Mobility Profile (Dash/Blink cooldown exploitation vs. Immobile gank susceptibility)
    3. Durability & Resilience (Squishy burst targets vs. High-armor/HP tank shred)
    4. Primary Damage Profile & Defensive Counter Items (Armor, MR, Grievous Wounds, % HP shred)
    5. Ability Mechanics (Channeled ultimates, skillshot reliance, ability cooldown windows)
    6. Analytical Matchup Dynamics (English reason synthesis)
    
    Zero manual champion name lookups. Works for 173 or 10,000 champions.
    """
    cname = champ.get("name") or champ.get("id") or "Unknown"
    roles = set(r.lower() for r in champ.get("roles", []))
    subroles = set(s.upper() for s in champ.get("subroles", []))
    ratings = champ.get("attributeRatings", {})
    stats = champ.get("stats", {})
    adaptive_type = (champ.get("adaptiveType") or "").lower()
    attack_type = (champ.get("attackType") or "").lower()
    
    # Extract attack range
    range_val = stats.get("attackrange", {}).get("base", 0) if isinstance(stats.get("attackrange"), dict) else (stats.get("attackrange") or 0)
    
    # Abilities inspection (keyword-driven from ABILITY_KEYWORDS config)
    abilities = champ.get("abilities", {})
    ability_flags = {key: False for key in ABILITY_KEYWORDS}

    for _k, ab in abilities.items():
        if isinstance(ab, dict):
            desc = (ab.get("description") or "").lower()
            for flag_key, keywords in ABILITY_KEYWORDS.items():
                if any(w in desc for w in keywords):
                    ability_flags[flag_key] = True

    has_channel = ability_flags["channel"]
    has_heal_drain = ability_flags["heal_drain"]
    has_shield = ability_flags["shield"]
    has_stealth = ability_flags["stealth"]
    has_dash = ability_flags["dash"]

    mobility_rating = ratings.get("mobility", THRESHOLDS["low_rating"])
    toughness_rating = ratings.get("toughness", THRESHOLDS["low_rating"])
    damage_rating = ratings.get("damage", THRESHOLDS["medium_rating"])
    control_rating = ratings.get("control", THRESHOLDS["low_rating"])

    # 1. Core Tactical Weaknesses (English)
    weaknesses = []

    # A. Range & Positioning Weakness
    if range_val <= THRESHOLDS["melee_range_max"] or attack_type == "melee":
        weaknesses.append("Short melee combat range; highly vulnerable to continuous ranged kiting, ground slows, and perimeter zoning.")
    elif range_val >= THRESHOLDS["ranged_min"]:
        weaknesses.append("Low base health and armor; extremely fragile when caught out of position by flanking assassins or sudden gap-closers.")

    # B. Mobility Profile Weakness
    if mobility_rating <= THRESHOLDS["low_rating"] and not has_dash:
        weaknesses.append("Immobile with no native dash or terrain-crossing escape; extremely vulnerable to coordinated jungle ganks and linear skillshot CC.")
    elif mobility_rating >= THRESHOLDS["medium_rating"] or has_dash:
        weaknesses.append("High reliance on mobility cooldowns; baiting or interrupting their primary dash leaves them completely over-committed with no disengage.")

    # C. Durability & Target Profile
    if toughness_rating <= THRESHOLDS["low_rating"]:
        weaknesses.append("Vulnerable to rapid burst rotations; easily eliminated in a single crowd control lockdown before they can react.")
    elif toughness_rating >= THRESHOLDS["high_rating"] or subroles & {"VANGUARD", "WARDEN", "JUGGERNAUT"}:
        weaknesses.append("Susceptible to sustained percentage maximum health damage and armor/magic penetration in extended skirmishes.")

    # D. Ability Specific Weaknesses
    if has_channel or "reset" in champ.get("playstyles", []):
        weaknesses.append("Key ability or ultimate channels can be completely neutralized by hard crowd control (stun, airborne, silence, or suppression).")
    if has_heal_drain:
        weaknesses.append("Sustained combat power relies heavily on active healing/vamp, making them crippled by early Grievous Wounds.")

    # Ensure 3-4 concise weaknesses
    weaknesses = weaknesses[:4]

    # 2. Actionable Tactical Tips (English)
    tactical_tips = []

    if range_val <= THRESHOLDS["melee_range_max"] or attack_type == "melee":
        tactical_tips.append("Maintain defensive perimeter spacing: utilize ranged poke and slowing abilities to kite them outside their effective engagement radius.")
        tactical_tips.append("Avoid extended trades; execute short trades and disengage before they can stack conqueror or sustained passives.")
    elif range_val >= THRESHOLDS["ranged_min"]:
        tactical_tips.append("Execute flanking routes through fog of war to isolate and burst down the backline before front-to-back teamfights begin.")
        tactical_tips.append("Force them to expend primary waveclear abilities under turret, significantly reducing their lane trading pressure.")

    if mobility_rating >= THRESHOLDS["medium_rating"] or has_dash:
        tactical_tips.append("Never throw primary skillshots proactively while their dash or blink is off cooldown. Bait their mobility skill first, then punish.")
        tactical_tips.append("Hold point-and-click crowd control specifically until they dive into your team's perimeter.")
    else:
        tactical_tips.append("Coordinate early jungle ganks when they push past lane midpoint; immobile champions cannot escape collapse ganks without burning Flash.")

    if has_channel:
        tactical_tips.append("Save hard crowd control (stun, airborne, silence) specifically to interrupt their channeled ultimate, negating their primary teamfight impact.")
    if has_heal_drain:
        tactical_tips.append("Prioritize purchasing an early Grievous Wounds component (Bramble Vest, Executioner's Calling, or Oblivion Orb) on your first recall.")
    if has_stealth:
        tactical_tips.append("Deploy Control Wards in river and jungle choke points, and use Oracle Lens (Sweeper) to outline and target their stealth positioning.")

    # Ensure 3-4 concise tactical tips
    tactical_tips = tactical_tips[:4]

    # 3. Recommended Counter Items (English - clean item names)
    counter_items = []

    # Physical damage profile
    if adaptive_type == "physical" or "marksman" in roles or "assassin" in roles:
        if "marksman" in roles or range_val >= THRESHOLDS["ranged_min"] or "SKIRMISHER" in subroles:
            counter_items.extend(COUNTER_ITEM_PROFILES["anti_physical_ranged"])
        else:
            counter_items.extend(COUNTER_ITEM_PROFILES["anti_physical_melee"])

    # Magic damage profile
    elif adaptive_type == "magic" or "mage" in roles:
        counter_items.extend(COUNTER_ITEM_PROFILES["anti_magic"])

    # Anti-tank & Anti-healing universal counters
    if toughness_rating >= THRESHOLDS["high_rating"] or subroles & {"VANGUARD", "WARDEN", "JUGGERNAUT"}:
        counter_items.extend(COUNTER_ITEM_PROFILES["anti_tank"])

    if has_heal_drain:
        counter_items.extend(COUNTER_ITEM_PROFILES["anti_heal"])

    # Fallback defense
    if not counter_items:
        counter_items = list(COUNTER_ITEM_PROFILES["fallback"])

    # Deduplicate and limit to top 3 items
    counter_items = list(dict.fromkeys(counter_items))[:3]

    # 4. Analytical Matchup Dynamics (English reasons)
    weak_against = []
    strong_against = []

    # If existing counter document has matchup win-rate statistics, preserve them but ensure English reasons
    if existing_counter_doc and isinstance(existing_counter_doc, dict):
        for m in existing_counter_doc.get("weakAgainst", [])[:5]:
            enemy_name = m.get("champion", "")
            win_rate = m.get("winRate")
            reason = derive_english_matchup_reason(cname, enemy_name, is_counter=True, champ_profile=champ)
            weak_against.append({"champion": enemy_name, "winRate": win_rate, "reason": reason})

        for m in existing_counter_doc.get("strongAgainst", [])[:5]:
            enemy_name = m.get("champion", "")
            win_rate = m.get("winRate")
            reason = derive_english_matchup_reason(cname, enemy_name, is_counter=False, champ_profile=champ)
            strong_against.append({"champion": enemy_name, "winRate": win_rate, "reason": reason})

    # If no existing counter data, generate archetype-based vulnerability descriptions
    # (no fake champion names or fabricated winrates — only role-based heuristics)
    if not weak_against:
        weak_against, strong_against = generate_archetype_matchups(cname, roles, subroles, attack_type, range_val)

    return {
        "weaknesses": weaknesses,
        "tactical_tips": tactical_tips,
        "counter_items": counter_items,
        "weak_against": weak_against,
        "strong_against": strong_against
    }


def generate_archetype_matchups(cname, roles, subroles, attack_type, range_val):
    """
    Generate archetype-based matchup vulnerability descriptions when no real counter data exists.
    Returns (weak_against, strong_against) lists with role-based reasons, no fake champion names or winrates.
    """
    weak_against = []
    strong_against = []

    if "marksman" in roles:
        weak_against = [
            {"archetype": "Hard Engage Tank", "reason": "Unstoppable initiation and attack speed debuffs cripple sustained DPS from marksman"},
            {"archetype": "Dive Assassin", "reason": "Direct gap-close isolates fragile marksman before frontline can peel"},
            {"archetype": "Hook/Lockdown Support", "reason": "Point-and-click crowd control lockdown prevents any disengage or outplay"}
        ]
        strong_against = [
            {"archetype": "Immobile Frontline", "reason": "Slow, predictable skillshots allow continuous kiting from safe perimeter"},
            {"archetype": "Low-Threat Tank", "reason": "Sustained DPS melts frontline tanks from maximum auto-attack range"}
        ]
    elif "assassin" in roles:
        weak_against = [
            {"archetype": "CC Mage", "reason": "Point-and-click crowd control and self-peel nullifies burst combo entirely"},
            {"archetype": "Suppression Champion", "reason": "Targeted suppression instantly shuts down dive and mobility"},
            {"archetype": "Armor Stacker", "reason": "Colossal armor and taunt lockdown forces assassin to self-destruct"}
        ]
        strong_against = [
            {"archetype": "Immobile Mage", "reason": "Immobile artillery mage easily flanked and eliminated in a single rotation"},
            {"archetype": "Skillshot-Reliant Mage", "reason": "High mobility dodges linear skillshots; burst eliminates squishy mage"}
        ]
    elif "mage" in roles:
        weak_against = [
            {"archetype": "Anti-Mage Diver", "reason": "Magic damage shield and repeated gap-closing neutralizes artillery poke"},
            {"archetype": "AD Assassin", "reason": "High mobility dodges skillshots and burst eliminates squishy mage"},
            {"archetype": "Untargetable Assassin", "reason": "Untargetability dodges primary spells followed by lethal burst"}
        ]
        strong_against = [
            {"archetype": "Short-Range Juggernaut", "reason": "Easily kites short-range fighters with ranged slows and root effects"},
            {"archetype": "Immobile Melee", "reason": "Punishes lack of gap-closers from safe perimeter distance"}
        ]
    elif "tank" in roles or subroles & {"VANGUARD", "WARDEN", "JUGGERNAUT"}:
        weak_against = [
            {"archetype": "% HP Damage Carry", "reason": "Percentage maximum health true damage shreds high armor and health stacking"},
            {"archetype": "Duelist", "reason": "Sustained true damage in extended duels bypasses all defensive stacking"}
        ]
        strong_against = [
            {"archetype": "Squishy Skirmisher", "reason": "Sturdy base stats and unavoidable crowd control overpower fragile skirmishers"}
        ]
    else:
        weak_against = [
            {"archetype": "Ranged Kiter", "reason": "Superior range and sustained damage kites melee champions effectively"},
            {"archetype": "True Damage Duelist", "reason": "True damage bypasses defensive stats in extended trades"}
        ]
        strong_against = [
            {"archetype": "Immobile Squishy", "reason": "Gap-closing and burst overwhelm targets without escape tools"}
        ]

    return weak_against, strong_against


def derive_english_matchup_reason(champ_a, champ_b, is_counter, champ_profile):
    """
    Derive standard English matchup explanations 100% dynamically from champion role/subrole profile.
    No hardcoded champion-name dictionaries — scales to any number of champions.
    """
    roles = set(r.lower() for r in champ_profile.get("roles", []))
    subroles = set(s.upper() for s in champ_profile.get("subroles", []))
    attack_type = (champ_profile.get("attackType") or "").lower()
    ratings = champ_profile.get("attributeRatings", {})

    # Derive reason from the champion's own archetype interaction
    if is_counter:
        # champ_b counters champ_a: explain WHY champ_b is dangerous to our archetype
        if "marksman" in roles:
            return f"{champ_b} leverages aggressive gap-closing and hard crowd control to burst down squishy marksman"
        elif "assassin" in roles:
            return f"{champ_b} utilizes defensive invulnerability and point-and-click crowd control to shut down burst combo"
        elif "mage" in roles:
            return f"{champ_b} closes the distance rapidly and punishes low mobility and skillshot misses"
        elif "tank" in roles or subroles & {"VANGUARD", "WARDEN", "JUGGERNAUT"}:
            return f"{champ_b} shreds through high armor and health stacking with sustained percentage damage"
        elif "fighter" in roles or subroles & {"DIVER", "SKIRMISHER"}:
            return f"{champ_b} outduels in extended trades with superior sustain or true damage"
        elif "support" in roles or subroles & {"ENCHANTER", "CATCHER"}:
            return f"{champ_b} applies heavy early pressure and all-in threat that overwhelms defensive utility"
        else:
            return f"{champ_b} maintains superior range and sustained true damage to kite and shred durability"
    else:
        # champ_a is strong against champ_b: explain WHY our archetype dominates
        if "marksman" in roles:
            return f"{champ_a} safely out-ranges and kites {champ_b} with sustained DPS from behind frontliners"
        elif "assassin" in roles:
            return f"{champ_a} easily exploits {champ_b}'s lack of mobility to burst them down before they can react"
        elif "mage" in roles:
            return f"{champ_a} zones {champ_b} with ranged crowd control and burst from safe distance"
        elif "tank" in roles or subroles & {"VANGUARD", "WARDEN"}:
            return f"{champ_a} locks down {champ_b} with unavoidable crowd control and absorbs all damage"
        elif "fighter" in roles or subroles & {"JUGGERNAUT", "DIVER"}:
            return f"{champ_a} overpowers {champ_b} with dominant stat checks and early-game pressure"
        else:
            return f"{champ_a} overpowers {champ_b} with dominant stat checks and early-game pressure"


# Main Enricher Class (100% Automated Metadata Generator)

class Enricher:
    """Add strategic and relational metadata to champions with 100% automated coverage."""

    def enrich(self):
        """
        Read processed champion data, compute strategic metadata, and update champions.json.
        """
        print("[Enricher] Loading champion data...")
        champions = self.load_champions()

        if not champions:
            print("[Enricher] ERROR: No champion data found!")
            return {}

        print(f"[Enricher] Enriching {len(champions)} champions with 100% automated metadata...")

        for champ_id, champ in champions.items():
            # 1. Playstyles (100% automated algorithmic derivation)
            playstyles = self.infer_playstyles(champ)

            # 2. Subroles normalization (from Meraki roles: e.g. JUGGERNAUT, VANGUARD)
            subroles = [r.strip().title() for r in champ.get("subroles", []) if r]
            if not subroles:
                subroles = self.infer_subroles(champ)
            champ["subroles"] = subroles

            # 3. Positions normalization (from Meraki positions: e.g. TOP, MID, BOT)
            norm_positions = []
            pos_map = {"MIDDLE": "MID", "BOTTOM": "BOT"}
            for p in champ.get("positions", []):
                p_u = p.strip().upper()
                norm_positions.append(pos_map.get(p_u, p_u))
            if not norm_positions:
                norm_positions = self.infer_positions(champ)
            champ["positions"] = list(dict.fromkeys(norm_positions))

            # 4. 100% Automated Win Conditions
            win_conditions = self.compute_win_conditions(champ_id, champ, playstyles, subroles)

            # 5. 100% Automated Power Curve
            power_curve = self.compute_power_curve(champ_id, champ, subroles)

            # 6. Region & Related Champions normalization
            region = champ.get("region", "Runeterra (Unaffiliated)")
            if not region or region.strip() == "":
                region = "Runeterra (Unaffiliated)"
            champ["region"] = region

            related = champ.get("related_champions", [])
            if not isinstance(related, list):
                related = []
            champ["related_champions"] = related

            # 7. Automated English Tactical Counter Derivation
            tactical_info = derive_tactical_counter(champ)

            # Save computed attributes into champion object
            champ["playstyles"] = playstyles
            champ["powerCurve"] = power_curve
            champ["winConditions"] = win_conditions
            champ["tacticalInfo"] = {
                "weaknesses": tactical_info.get("weaknesses", []),
                "tactical_tips": tactical_info.get("tactical_tips", []),
                "counter_items": tactical_info.get("counter_items", [])
            }

        # Save updated data
        self.save_champions(champions)
        print(f"[Enricher] Successfully enriched 100% ({len(champions)}/{len(champions)}) champions!")
        return champions

    @staticmethod
    def compute_win_conditions(champ_id, champ, playstyles, subroles):
        """
        Derive win conditions automatically from Meraki Sub-roles, tactical playstyles,
        and champion kit capabilities with 100% coverage.
        """
        conditions = set()
        subroles_upper = set(s.upper() for s in subroles)
        ps_lower = set(p.lower() for p in playstyles)
        ratings = champ.get("attributeRatings", {})
        roles = set(r.lower() for r in champ.get("roles", []))

        # Teamfight
        if subroles_upper & {"VANGUARD", "BATTLEMAGE", "WARDEN", "ENCHANTER"}:
            conditions.add("Teamfight")
        if ps_lower & {"engage", "aoe", "lockdown", "zone", "peel"}:
            conditions.add("Teamfight")
        if ratings.get("control", 0) >= THRESHOLDS["high_rating"] or ratings.get("toughness", 0) >= THRESHOLDS["high_rating"]:
            conditions.add("Teamfight")

        # Splitpush
        if subroles_upper & {"SKIRMISHER"}:
            conditions.add("Splitpush")
        if ps_lower & {"splitpush", "duelist"}:
            conditions.add("Splitpush")
        if "JUGGERNAUT" in subroles_upper and ("TOP" in champ.get("positions", []) or "fighter" in roles):
            if ratings.get("damage", 0) >= THRESHOLDS["medium_rating"] and ratings.get("toughness", 0) >= THRESHOLDS["medium_rating"]:
                conditions.add("Splitpush")

        # Pick
        if subroles_upper & {"ASSASSIN", "CATCHER"}:
            conditions.add("Pick")
        if ps_lower & {"pick", "stealth", "assassin"}:
            conditions.add("Pick")

        # Siege
        if subroles_upper & {"ARTILLERY"}:
            conditions.add("Siege")
        if ps_lower & {"siege", "artillery", "poke"}:
            conditions.add("Siege")

        # Objective
        if ps_lower & {"objective"} or (ratings.get("damage", 0) >= THRESHOLDS["high_rating"] and "marksman" in roles):
            conditions.add("Objective")

        # Skirmish
        if subroles_upper & {"DIVER", "SKIRMISHER"}:
            conditions.add("Skirmish")
        if ps_lower & {"dive", "mobility", "reset", "skirmish"}:
            conditions.add("Skirmish")

        # Fallback guarantee: every champion must have at least 1-2 win conditions
        if not conditions:
            if "tank" in roles or "support" in roles or "mage" in roles:
                conditions.add("Teamfight")
            elif "marksman" in roles:
                conditions.add("Teamfight")
            elif "assassin" in roles:
                conditions.add("Pick")
            elif "fighter" in roles:
                conditions.add("Skirmish")
            else:
                conditions.add("Teamfight")

        return sorted(list(conditions))

    @staticmethod
    def compute_power_curve(champ_id, champ, subroles):
        """
        Derive power curves automatically using stat growth rates, scaling archetypes,
        and ability reliance. 100% coverage guaranteed for any number of champions.
        """
        subroles_upper = set(s.upper() for s in subroles)
        stats = champ.get("stats", {})
        roles = set(r.lower() for r in champ.get("roles", []))
        ratings = champ.get("attributeRatings", {})

        ad_growth = stats.get("attackdamage", {}).get("perLevel", 0) if isinstance(stats.get("attackdamage"), dict) else 0
        hp_growth = stats.get("hp", {}).get("perLevel", 0) if isinstance(stats.get("hp"), dict) else 0
        as_growth = stats.get("attackspeed", {}).get("perLevel", 0) if isinstance(stats.get("attackspeed"), dict) else 0
        base_ad = stats.get("attackdamage", {}).get("base", 0) if isinstance(stats.get("attackdamage"), dict) else 0
        base_hp = stats.get("hp", {}).get("base", 0) if isinstance(stats.get("hp"), dict) else 0

        # Late game scaling indicators
        is_late_scaler = (
            ad_growth >= THRESHOLDS["late_ad_growth"] or
            hp_growth >= THRESHOLDS["late_hp_growth"] or
            (as_growth >= THRESHOLDS["late_as_growth"] and "marksman" in roles) or
            (bool(subroles_upper & {"SKIRMISHER", "BATTLEMAGE"}) and ratings.get("damage", 0) >= THRESHOLDS["high_rating"]) or
            ("marksman" in roles and ratings.get("damage", 0) >= THRESHOLDS["high_rating"])
        )

        # Early game bully indicators
        is_early_bully = (
            (base_ad >= THRESHOLDS["early_base_ad_marksman"] and "marksman" in roles) or
            (base_hp >= THRESHOLDS["early_base_hp_fighter"] and "fighter" in roles and ad_growth <= THRESHOLDS["early_ad_growth_cap"]) or
            (bool(subroles_upper & {"DIVER", "CATCHER"}) and ratings.get("damage", 0) >= THRESHOLDS["high_rating"] and hp_growth < THRESHOLDS["early_hp_growth_cap_diver"]) or
            (bool(subroles_upper & {"JUGGERNAUT"}) and base_ad >= THRESHOLDS["early_base_ad_juggernaut"] and hp_growth < THRESHOLDS["early_hp_growth_cap_juggernaut"])
        )

        if is_late_scaler and not is_early_bully:
            return ["LateGame"]
        elif is_early_bully and not is_late_scaler:
            return ["EarlyGame"]
        elif is_late_scaler and is_early_bully:
            return ["EarlyGame", "LateGame"]
        
        # Tanks and Control Mages spike around mid-to-late teamfights
        if "tank" in roles or subroles_upper & {"VANGUARD", "WARDEN"}:
            return ["MidGame", "LateGame"]

        return ["MidGame"]

    @staticmethod
    def infer_subroles(champ):
        """Infer subroles when Meraki subroles are absent."""
        roles = [r.lower() for r in champ.get("roles", [])]
        inferred = []
        if "tank" in roles:
            inferred.append("Vanguard")
        if "fighter" in roles:
            inferred.append("Juggernaut")
        if "assassin" in roles:
            inferred.append("Assassin")
        if "mage" in roles:
            inferred.append("Burst")
        if "marksman" in roles:
            inferred.append("Marksman")
        if "support" in roles:
            inferred.append("Enchanter")
        return inferred if inferred else ["Specialist"]

    @staticmethod
    def infer_positions(champ):
        """Infer primary positions from champion roles."""
        roles = [r.lower() for r in champ.get("roles", [])]
        pos = []
        if "tank" in roles:
            pos.extend(["TOP", "SUPPORT"])
        if "fighter" in roles:
            pos.extend(["TOP", "JUNGLE"])
        if "assassin" in roles:
            pos.extend(["MID", "JUNGLE"])
        if "mage" in roles:
            pos.extend(["MID", "SUPPORT"])
        if "marksman" in roles:
            pos.append("BOT")
        if "support" in roles:
            pos.append("SUPPORT")
        return list(dict.fromkeys(pos)) if pos else ["MID"]

    @staticmethod
    def infer_playstyles(champ):
        """
        Derive playstyles 100% algorithmically from champion telemetry.
        No hardcoded champion names. Scales to 1,000+ champions.
        """
        playstyles = set()
        roles = set(r.lower() for r in champ.get("roles", []))
        subroles = set(s.upper() for s in champ.get("subroles", []))
        ratings = champ.get("attributeRatings", {})
        attack_type = (champ.get("attackType") or "").lower()
        range_val = champ.get("stats", {}).get("attackrange", {}).get("base", 0) if isinstance(champ.get("stats", {}).get("attackrange"), dict) else (champ.get("stats", {}).get("attackrange") or 0)

        # Core Archetypes
        if "assassin" in roles or "ASSASSIN" in subroles or (ratings.get("damage", 0) >= THRESHOLDS["high_rating"] and ratings.get("mobility", 0) >= THRESHOLDS["medium_rating"]):
            playstyles.add("Burst")
            playstyles.add("Assassin")
        if "mage" in roles or "BURST" in subroles:
            playstyles.add("Mage")
            if ratings.get("damage", 0) >= THRESHOLDS["medium_rating"]:
                playstyles.add("Burst")
        if "marksman" in roles or "MARKSMAN" in subroles or (attack_type == "ranged" and range_val >= THRESHOLDS["ranged_min"] and "marksman" in roles):
            playstyles.add("Marksman")
            playstyles.add("Sustained")
        if "tank" in roles or subroles & {"VANGUARD", "WARDEN"}:
            playstyles.add("Tank")
        if "fighter" in roles or subroles & {"JUGGERNAUT", "DIVER", "SKIRMISHER"}:
            playstyles.add("Fighter")
        if "support" in roles or subroles & {"ENCHANTER", "CATCHER"}:
            playstyles.add("Support")

        # Behavioral Tags
        if ratings.get("mobility", 0) >= THRESHOLDS["medium_rating"]:
            playstyles.add("Mobility")
        if "DIVER" in subroles or (ratings.get("mobility", 0) >= THRESHOLDS["medium_rating"] and ratings.get("toughness", 0) >= THRESHOLDS["medium_rating"]):
            playstyles.add("Dive")
        if "ARTILLERY" in subroles or range_val >= THRESHOLDS["artillery_range_min"]:
            playstyles.add("Poke")
        if ratings.get("control", 0) >= THRESHOLDS["medium_rating"]:
            playstyles.add("Engage")
        if ratings.get("utility", 0) >= THRESHOLDS["medium_rating"] or "ENCHANTER" in subroles:
            playstyles.add("Utility")

        if not playstyles:
            playstyles = set(r.capitalize() for r in champ.get("roles", [])) or {"Flexible"}
        return sorted(list(playstyles))

    @staticmethod
    def load_champions():
        """Load processed champion data."""
        return load_json(PROCESSED_DIR / "champions.json")

    @staticmethod
    def save_champions(data):
        """Save updated champion data."""
        return save_json(data, PROCESSED_DIR / "champions.json")


# Direct MongoDB Tactical Enrichment (Zero JSON Files on Disk)

def enrich_tactical_counters_to_mongo(uri=None, db_name=None):  # noqa: C901
    """
    Directly enriches tactical counter profiles into MongoDB collections:
    - db.counters: adds English weaknesses, tactical_tips, counter_items, weakAgainst, strongAgainst.
    - db.champions: updates tacticalInfo embedded fields.
    Does NOT write any intermediate JSON files to disk.
    """
    try:
        from datetime import datetime, timezone
        from pymongo import MongoClient, UpdateOne
    except ImportError:
        print("[Enricher] pymongo is not installed. Please install pymongo to sync to MongoDB.")
        return False

    uri = uri or os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = db_name or os.getenv("MONGO_DB_NAME", "lol_rag_db")

    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        db = client[db_name]
    except Exception as e:
        print(f"[Enricher] Failed to connect to MongoDB ({e}).")
        return False

    champions = list(db.champions.find())
    if not champions:
        print(f"[Enricher] No champions found in {db_name}.champions.")
        return False

    print(f"[Enricher] Enriching automated English tactical counter profiles for {len(champions)} champions directly into MongoDB ('{db_name}')...")

    # Build lookup of existing counter docs to preserve match stats
    existing_counters = {doc["_id"]: doc for doc in db.counters.find()}

    counter_updates = []
    champion_updates = []

    for champ in champions:
        cid = champ.get("name") or champ.get("id") or champ["_id"]
        existing_doc = existing_counters.get(cid)
        tactics = derive_tactical_counter(champ, existing_counter_doc=existing_doc)

        update_fields = {
            "champion": cid,
            "champion_id": cid,
            "weaknesses": tactics.get("weaknesses", []),
            "tactical_tips": tactics.get("tactical_tips", []),
            "counter_items": tactics.get("counter_items", []),
            "weakAgainst": tactics.get("weak_against", []),
            "strongAgainst": tactics.get("strong_against", []),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        counter_updates.append(
            UpdateOne(
                {"_id": cid},
                {"$set": update_fields},
                upsert=True
            )
        )

        champion_updates.append(
            UpdateOne(
                {"_id": champ["_id"]},
                {"$set": {
                    "tacticalInfo.weaknesses": tactics.get("weaknesses", []),
                    "tacticalInfo.tactical_tips": tactics.get("tactical_tips", []),
                    "tacticalInfo.counter_items": tactics.get("counter_items", [])
                }}
            )
        )

    if counter_updates:
        res_counters = db.counters.bulk_write(counter_updates)
        print(f"[Enricher] Successfully updated {res_counters.modified_count + res_counters.upserted_count} counter docs in MongoDB.")

    if champion_updates:
        res_champs = db.champions.bulk_write(champion_updates)
        print(f"[Enricher] Successfully updated {res_champs.modified_count} champion tactical docs in MongoDB.")

    print("[Enricher] Direct MongoDB tactical enrichment completed in English. No JSON files created on disk.")
    return True

