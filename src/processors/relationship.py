"""
Relationship and Knowledge Base Generator.

Generates structured relationship and matchup data for LoL Knowledge Bot:
- Counters: Matchup advantage/disadvantage with win rates and tactical reasons
- Synergies: Duo partners with synergy win rates and ability combinations
- Builds: Recommended starting items, core/full builds, summoner spells, and runes
- Sync: Synchronizes core processed files to knowledge base directory
"""

import shutil
from pathlib import Path

from .utils import (
    DDRAGON_raw_dir,
    processed_dir,
    src_dir,
    ensure_dirs,
    load_json,
    log,
    save_json,
)

# Default knowledge base storage directory
kb_dir = src_dir / "data" / "knowledge_base"


# Automated Relationship Scoring Configuration

# Starting items mapped by primary role
starting_items_by_role = {
    "marksman": ["Doran's Blade", "Health Potion"],
    "fighter": ["Doran's Blade", "Health Potion"],
    "assassin": ["Long Sword", "Refillable Potion"],
    "mage": ["Doran's Ring", "Health Potion"],
    "tank": ["Doran's Shield", "Health Potion"],
    "support": ["World Atlas", "Health Potion"],
}

# Boots preference by archetype
boots_by_profile = {
    "marksman": "Berserker's Greaves",
    "assassin_physical": "Ionian Boots of Lucidity",
    "assassin_magic": "Sorcerer's Shoes",
    "mage": "Sorcerer's Shoes",
    "tank": "Plated Steelcaps",
    "fighter_physical": "Plated Steelcaps",
    "fighter_magic": "Sorcerer's Shoes",
    "support_enchanter": "Ionian Boots of Lucidity",
    "support_tank": "Plated Steelcaps",
}

# Summoner spells by primary position
summoner_spells_by_position = {
    "BOT": ["Flash", "Heal"],
    "SUPPORT": ["Flash", "Ignite"],
    "MID": ["Flash", "Ignite"],
    "TOP": ["Flash", "Teleport"],
    "JUNGLE": ["Flash", "Smite"],
}

# Keystone selection by archetype (role + subrole combination)
keystone_by_archetype = {
    "marksman": "Lethal Tempo",
    "assassin_physical": "Electrocute",
    "assassin_magic": "Electrocute",
    "mage_burst": "Electrocute",
    "mage_sustained": "Arcane Comet",
    "mage_default": "Arcane Comet",
    "tank_vanguard": "Aftershock",
    "tank_warden": "Grasp of the Undying",
    "tank_default": "Grasp of the Undying",
    "fighter_juggernaut": "Conqueror",
    "fighter_skirmisher": "Conqueror",
    "fighter_diver": "Conqueror",
    "fighter_default": "Conqueror",
    "support_enchanter": "Summon Aery",
    "support_catcher": "Aftershock",
    "support_default": "Summon Aery",
}

# Preferred secondary runes per tree (slot > 0, ordered by general priority)
rune_tree_secondary_prefs = {
    "Precision": ["Triumph", "Legend: Alacrity", "Coup de Grace", "Last Stand",
                   "Presence of Mind", "Legend: Bloodline", "Cut Down"],
    "Domination": ["Taste of Blood", "Grisly Mementos", "Ultimate Hunter",
                    "Treasure Hunter", "Sudden Impact"],
    "Sorcery": ["Manaflow Band", "Transcendence", "Scorch", "Gathering Storm",
                 "Absolute Focus", "Celerity"],
    "Resolve": ["Bone Plating", "Second Wind", "Revitalize", "Overgrowth",
                 "Demolish", "Conditioning"],
    "Inspiration": ["Biscuit Delivery", "Cosmic Insight", "Magical Footwear",
                      "Triple Tonic"],
}

# Preferred secondary tree pairing (primary → secondary)
secondary_tree_pairing = {
    "Precision": "Resolve",
    "Domination": "Sorcery",
    "Sorcery": "Inspiration",
    "Resolve": "Inspiration",
    "Inspiration": "Precision",
}

# Item tag affinity weights per champion archetype
item_tag_weights = {
    "marksman": {"CriticalStrike": 5, "AttackSpeed": 3, "Damage": 3, "LifeSteal": 2},
    "assassin_physical": {"Damage": 4, "ArmorPenetration": 4, "AbilityHaste": 2},
    "assassin_magic": {"SpellDamage": 4, "MagicPenetration": 4, "AbilityHaste": 2},
    "mage": {"SpellDamage": 4, "AbilityHaste": 3, "MagicPenetration": 2, "Mana": 1},
    "tank": {"Health": 4, "Armor": 3, "SpellBlock": 3, "AbilityHaste": 1},
    "fighter_physical": {"Damage": 3, "Health": 3, "AbilityHaste": 2, "Armor": 1, "LifeSteal": 1},
    "fighter_magic": {"SpellDamage": 3, "Health": 3, "AbilityHaste": 2, "SpellBlock": 1},
    "support_enchanter": {"AbilityHaste": 3, "Mana": 2, "ManaRegen": 2, "SpellDamage": 1},
    "support_tank": {"Health": 3, "Armor": 3, "AbilityHaste": 2, "SpellBlock": 2},
}

# Position pairs eligible for synergy scoring
synergy_position_pairs = {
    "BOT": {"SUPPORT"},
    "SUPPORT": {"BOT"},
    "MID": {"JUNGLE", "SUPPORT"},
    "TOP": {"JUNGLE"},
    "JUNGLE": {"MID", "TOP", "BOT"},
}


class RelationshipGenerator:
    """
    Generate counter, synergy, and build relationships for champions.

    Generates structured relationship files and synchronizes knowledge base
    data for Knowledge Graph and Vector store indexing.
    """

    def __init__(self, processed_dir = None, kb_dir = None):
        self.processed_dir = processed_dir or processed_dir
        self.kb_dir = kb_dir or kb_dir
        self.counters_dir = self.kb_dir / "counters"
        self.synergies_dir = self.kb_dir / "synergies"
        self.builds_dir = self.kb_dir / "builds"
        self.champions_dir = self.kb_dir / "champions"

    def generate(self, champions = None, items = None, runes = None, save_to_disk = False):
        """
        Execute full relationship generation pipeline.
        Generates in-memory relationship structures, embeds them into champions,
        extracts complete relational edges, and optionally persists to disk.
        """
        print("[RelationshipGenerator] Generating knowledge base relationships and entity graph...")

        # Load data if not passed in-memory
        if not champions:
            champions = self.load_champions()
        if not champions:
            print("[RelationshipGenerator] ERROR: No champion data found!")
            return {"champions": {}, "counters": {}, "synergies": {}, "builds": {}, "relationships": [], "stats": {}}

        if not items:
            items = load_json(self.processed_dir / "items.json")
        if not runes:
            runes = load_json(self.processed_dir / "runes.json")

        if save_to_disk:
            self.ensure_output_dirs()
            self.sync_core_files()

        # 1. Generate counters, synergies, and builds
        counters_dict = self.generate_counters(champions, save_to_disk = save_to_disk)
        synergy_dict = self.generate_synergies(champions, save_to_disk = save_to_disk)
        build_dict = self.generate_builds(champions, items, runes, save_to_disk = save_to_disk)

        # 2. Embed relationships directly into each champion object
        for cid, champ in champions.items():
            if cid in counters_dict:
                c_info = counters_dict[cid]
                champ["counters"] = {
                    "weakAgainst": c_info.get("weakAgainst", []),
                    "strongAgainst": c_info.get("strongAgainst", []),
                }
            if cid in synergy_dict:
                champ["synergies"] = synergy_dict[cid].get("synergies", [])
            if cid in build_dict:
                champ["builds"] = build_dict[cid]

        # 3. Extract all typed relationships (Graph edges)
        all_relationships = self.extract_all_relationships(
            champions = champions,
            items = items,
            runes = runes,
            counters = counters_dict,
            synergies = synergy_dict,
            builds = build_dict,
        )

        if save_to_disk:
            self.save_individual_champions(champions)
            print(f"[RelationshipGenerator] Persisted files to disk at: {self.kb_dir}")

        stats = {
            "champions": len(champions),
            "counters": len(counters_dict),
            "synergies": len(synergy_dict),
            "builds": len(build_dict),
            "relationships": len(all_relationships),
        }
        print(
            f"[RelationshipGenerator] Generated relationships: "
            f"{stats['champions']} champions (embedded), {stats['counters']} counters, "
            f"{stats['synergies']} synergies, {stats['builds']} builds, {stats['relationships']} total graph edges."
        )

        return {
            "champions": champions,
            "counters": counters_dict,
            "synergies": synergy_dict,
            "builds": build_dict,
            "relationships": all_relationships,
            "stats": stats,
        }

    def ensure_output_dirs(self):
        """Ensure all knowledge base output subdirectories exist."""
        for d in [self.counters_dir, self.synergies_dir, self.builds_dir, self.champions_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def sync_core_files(self):
        """Sync core processed datasets into knowledge base root."""
        for fname in ["champions.json", "items.json", "runes.json"]:
            src_file = self.processed_dir / fname
            if src_file.exists():
                shutil.copy2(src_file, self.kb_dir / fname)

    def save_individual_champions(self, champions):
        """Save each champion as an individual JSON file for fast lookups."""
        for cid, data in champions.items():
            out_file = self.champions_dir / f"{cid}.json"
            save_json(data, out_file)

    def generate_counters(self, champions, save_to_disk = False):
        """Generate counter matchups by scoring all champion pairs using heuristic analysis."""
        results = {}
        champ_list = list(champions.items())

        for cid, champ in champ_list:
            name = champ.get("name", cid)

            weak_against = []
            strong_against = []

            for other_cid, other_champ in champ_list:
                if other_cid == cid:
                    continue

                other_name = other_champ.get("name", other_cid)

                # Score: how well does other_champ counter champ?
                c_score, c_reasons = self.score_counter_pair(champ, other_champ)
                if c_score > 0 and c_reasons:
                    weak_against.append({
                        "champion": other_name,
                        "_score": c_score,
                        "reason": "; ".join(c_reasons[:2]),
                    })

                # Score: how well does champ counter other_champ?
                f_score, f_reasons = self.score_counter_pair(other_champ, champ)
                if f_score > 0 and f_reasons:
                    strong_against.append({
                        "champion": other_name,
                        "_score": f_score,
                        "reason": "; ".join(f_reasons[:2]),
                    })

            # Sort by score descending, take top N, remove internal score
            weak_against.sort(key=lambda x: x["_score"], reverse=True)
            strong_against.sort(key=lambda x: x["_score"], reverse=True)
            for entry in weak_against:
                entry.pop("_score", None)
            for entry in strong_against:
                entry.pop("_score", None)

            counter_data = {
                "champion": name,
                "champion_id": cid,
                "weakAgainst": weak_against[:5],
                "strongAgainst": strong_against[:4],
            }

            results[cid] = counter_data
            if save_to_disk:
                out_file = self.counters_dir / f"{cid}_counters.json"
                save_json(counter_data, out_file)

        return results

    @staticmethod
    def score_counter_pair(champ_a, champ_b):
        """
        Score how well champion B counters champion A.
        Higher score = B is a stronger counter to A.
        Returns (score, reason_list) where reasons reference actual champion data.
        """
        score = 0
        reasons = []

        a_roles = set(r.lower() for r in champ_a.get("roles", []))
        b_roles = set(r.lower() for r in champ_b.get("roles", []))
        a_subroles = set(s.upper() for s in champ_a.get("subroles", []))
        b_subroles = set(s.upper() for s in champ_b.get("subroles", []))
        b_hard_cc = set(champ_b.get("hard_cc", []))
        a_effects = set(champ_a.get("ability_effects", []))
        b_effects = set(champ_b.get("ability_effects", []))
        a_ratings = champ_a.get("attributeRatings", {})
        b_ratings = champ_b.get("attributeRatings", {})
        a_attack = (champ_a.get("attackType") or "").upper()
        b_attack = (champ_b.get("attackType") or "").upper()
        a_adaptive = (champ_a.get("adaptiveType") or "").upper()

        b_name = champ_b.get("name", "")

        # Position overlap bonus — prioritize same-lane matchups
        a_positions = set(champ_a.get("positions", []))
        b_positions = set(champ_b.get("positions", []))
        if a_positions & b_positions:
            score += 3  # Significant bonus for same-lane counter

        is_marksman_a = "marksman" in a_roles or "MARKSMAN" in a_subroles
        has_true_damage_a = any("true" in eff.lower() for eff in champ_a.get("ability_effects", [])) or champ_a.get("name") in {"Vayne", "Fiora", "Gwen", "Master Yi"}

        # Rule 1: Hard CC shuts down assassins/divers (excluding marksmen)
        if (a_roles & {"assassin"} and not is_marksman_a) or (a_subroles & {"DIVER", "SKIRMISHER"} and not is_marksman_a):
            if b_hard_cc:
                cc_str = ", ".join(sorted(b_hard_cc))
                score += min(len(b_hard_cc) * 2, 4)
                reasons.append(f"{b_name}'s {cc_str} lockdown neutralizes dive and mobility")

        # Rule 2: Ranged kites immobile melee
        if a_attack == "MELEE" and a_ratings.get("mobility", 0) <= 1:
            if b_attack == "RANGED" and b_ratings.get("damage", 0) >= 2:
                score += 3
                reasons.append(f"{b_name}'s ranged attacks kite immobile melee from safe distance")

        # Rule 3: Tank absorbs physical assassin burst (excluding marksmen and true-damage shredders)
        if "PHYSICAL" in a_adaptive and (a_roles & {"assassin"}) and not is_marksman_a and not has_true_damage_a:
            if "tank" in b_roles or bool(b_subroles & {"VANGUARD", "WARDEN"}):
                score += 3
                reasons.append(f"{b_name}'s high armor and health pool absorbs physical burst")

        # Penalty: Immobile tanks do NOT counter champions dealing true damage or dedicated tank shredders
        if has_true_damage_a or (is_marksman_a and a_ratings.get("damage", 0) >= 2):
            if "tank" in b_roles or bool(b_subroles & {"VANGUARD", "WARDEN"}):
                score -= 4

        # Rule 4: Sustained DPS shreds tanks
        if "tank" in a_roles or bool(a_subroles & {"VANGUARD", "WARDEN", "JUGGERNAUT"}):
            if a_ratings.get("toughness", 0) >= 3:
                if "marksman" in b_roles and b_ratings.get("damage", 0) >= 2:
                    score += 3
                    reasons.append(f"{b_name}'s sustained DPS shreds high HP and armor stacking")

        # Rule 5: Gap-closer catches immobile ranged
        if a_attack == "RANGED" and a_ratings.get("mobility", 0) <= 1:
            if "Dash" in b_effects or b_ratings.get("mobility", 0) >= 3:
                score += 2
                reasons.append(f"{b_name}'s gap-closing mobility catches immobile ranged targets")

        # Rule 6: Targeted CC vs dash-reliant champions
        if "Dash" in a_effects or "Blink" in a_effects:
            disruptive_cc = b_hard_cc & {"Suppress", "Charm", "Taunt", "Polymorph"}
            if disruptive_cc:
                score += 2
                cc_str = ", ".join(sorted(disruptive_cc))
                reasons.append(f"{b_name}'s {cc_str} provides reliable lockdown against mobile champions")

        # Rule 7: Shield/defensive vs burst damage
        if a_ratings.get("damage", 0) >= 3:
            if "Shield" in b_effects and b_ratings.get("toughness", 0) >= 2:
                score += 1
                reasons.append(f"{b_name}'s shields and defensive tools absorb burst rotation")

        # Rule 8: Anti-healing capability vs sustain-reliant
        if "Heal" in a_effects:
            if "tank" in b_roles or bool(b_subroles & {"VANGUARD", "JUGGERNAUT"}):
                score += 1
                reasons.append(f"{b_name} can itemize Grievous Wounds to cripple healing sustain")

        # Rule 9: Projectile blocking and dive counters vs ranged skillshot mages
        if "mage" in a_roles and a_attack == "RANGED":
            if b_name in {"Yasuo", "Braum", "Samira"}:
                score += 3
                reasons.append(f"{b_name}'s projectile-blocking defense neutralizes skillshot mages")
            elif "Shield" in b_effects and ("Dash" in b_effects or "Blink" in b_effects) and b_ratings.get("mobility", 0) >= 2:
                score += 2
                reasons.append(f"{b_name}'s gap-closing mobility and defensive shields allow them to dive and trade effectively against skillshot mages")

        # Rule 10: Attack speed slows, blind, auto-attack evasion vs basic-attack marksmen
        if is_marksman_a or (a_attack == "RANGED" and a_ratings.get("damage", 0) >= 2):
            if b_name in {"Teemo", "Jax", "Shen", "Malphite", "Nasus"}:
                score += 4
                reasons.append(f"{b_name}'s attack speed slow, blind, or evasion cripples basic-attack reliant marksmen")
            elif "Blind" in b_hard_cc:
                score += 3
                reasons.append(f"{b_name}'s blind prevents basic attack damage and on-hit proc application")

        # Rule 11: Gap-closing burst divers/assassins punish fragile solo-lane marksmen
        if is_marksman_a and bool({"TOP", "MID"} & a_positions):
            if ("assassin" in b_roles or bool(b_subroles & {"DIVER", "SKIRMISHER", "ASSASSIN"})) and (b_ratings.get("mobility", 0) >= 2 or bool({"Dash", "Blink"} & b_effects)):
                score += 3
                reasons.append(f"{b_name}'s gap-closing all-in burst punishes fragile ranged solo-laners before they can kite")

        return score, reasons


    def generate_synergies(self, champions, save_to_disk = False):
        """Generate duo synergies by scoring position-compatible champion pairs."""
        results = {}

        # Build position index: position -> list of (cid, champ)
        position_index = {}
        for cid, champ in champions.items():
            for pos in champ.get("positions", []):
                position_index.setdefault(pos, []).append((cid, champ))

        for cid, champ in champions.items():
            name = champ.get("name", cid)
            positions = champ.get("positions", [])

            # Find candidates from compatible positions
            candidate_cids = set()
            for pos in positions:
                partner_positions = synergy_position_pairs.get(pos, set())
                for partner_pos in partner_positions:
                    for other_cid, _ in position_index.get(partner_pos, []):
                        if other_cid != cid:
                            candidate_cids.add(other_cid)

            # Score each candidate — SYMMETRIC: check both directions and take the better one
            scored = []
            for other_cid in candidate_cids:
                other_champ = champions[other_cid]
                score_ab, reasons_ab = self.score_synergy_pair(champ, other_champ)
                score_ba, reasons_ba = self.score_synergy_pair(other_champ, champ)
                # Take the better direction
                if score_ba > score_ab:
                    syn_score, syn_reasons = score_ba, reasons_ba
                else:
                    syn_score, syn_reasons = score_ab, reasons_ab
                if syn_score > 0 and syn_reasons:
                    other_name = other_champ.get("name", other_cid)
                    scored.append({
                        "champion": other_name,
                        "_score": syn_score,
                        "reason": "; ".join(syn_reasons[:2]),
                    })

            # Sort by score, take top 5, remove internal score
            scored.sort(key=lambda x: x["_score"], reverse=True)
            for entry in scored:
                entry.pop("_score", None)

            syn_data = {
                "champion": name,
                "champion_id": cid,
                "synergies": scored[:5],
            }

            results[cid] = syn_data
            if save_to_disk:
                out_file = self.synergies_dir / f"{cid}_synergy.json"
                save_json(syn_data, out_file)

        return results

    @staticmethod
    def score_synergy_pair(champ_a, champ_b):
        """
        Score how well two champions synergize.
        Returns (score, reasons) where reasons reference actual ability data.
        """
        score = 0
        reasons = []

        a_roles = set(r.lower() for r in champ_a.get("roles", []))
        b_roles = set(r.lower() for r in champ_b.get("roles", []))
        a_subroles = set(s.upper() for s in champ_a.get("subroles", []))
        b_subroles = set(s.upper() for s in champ_b.get("subroles", []))
        a_hard_cc = set(champ_a.get("hard_cc", []))
        b_hard_cc = set(champ_b.get("hard_cc", []))
        a_effects = set(champ_a.get("ability_effects", []))
        b_effects = set(champ_b.get("ability_effects", []))
        a_ratings = champ_a.get("attributeRatings", {})
        b_ratings = champ_b.get("attributeRatings", {})

        b_name = champ_b.get("name", "")

        # 1. CC chain potential (both have hard CC)
        if a_hard_cc and b_hard_cc:
            combined_cc = a_hard_cc | b_hard_cc
            score += min(len(combined_cc), 3)
            reasons.append(f"CC chain: {', '.join(sorted(combined_cc))} enables extended lockdown")

        # 2. Knockup + airborne synergy (e.g. Yasuo/Yone R requires airborne)
        if "Knockup" in a_hard_cc:
            b_abilities = champ_b.get("abilities", {})
            for ab in b_abilities.values():
                if isinstance(ab, dict):
                    desc = (ab.get("description") or "").lower()
                    # Only match abilities that REQUIRE airborne targets (e.g. Yasuo R, Yone R),
                    # NOT abilities that CAUSE knockup (which mention "knocking enemies airborne")
                    if ("airborne enemy" in desc or "airborne champion" in desc
                            or "on airborne" in desc):
                        score += 4
                        reasons.append(f"Knockup enables {b_name}'s airborne-requiring abilities")
                        break

        # 3. Enchanter + Hypercarry ADC
        if "ENCHANTER" in a_subroles and "marksman" in b_roles:
            if "Shield" in a_effects:
                score += 3
                reasons.append(f"Enchanter shields and buffs protect hypercarry {b_name}")

        # 4. Engage tank + Burst follow-up
        if bool(a_subroles & {"VANGUARD"}) and a_hard_cc:
            if b_ratings.get("damage", 0) >= 3:
                score += 2
                reasons.append(f"Hard engage initiation creates burst follow-up for {b_name}")

        # 5. AOE teamfight synergy
        if "AOE" in a_effects and "AOE" in b_effects:
            score += 1
            reasons.append(f"Combined AOE abilities create devastating teamfight damage")

        # 6. Hook/catch support + carry
        if "Pull" in a_effects and "marksman" in b_roles:
            score += 2
            reasons.append(f"Hook threat creates kill pressure and zone control for {b_name}")

        # 7. Peel support + low-mobility carry
        if "support" in a_roles and "Shield" in a_effects:
            if b_ratings.get("mobility", 0) <= 1 and b_ratings.get("damage", 0) >= 2:
                score += 2
                reasons.append(f"Protective shields compensate for {b_name}'s low mobility")

        # 8. Dive buddy synergy (both can dive backline)
        if bool(a_subroles & {"DIVER", "ASSASSIN"}) and bool(b_subroles & {"DIVER", "ASSASSIN"}):
            score += 1
            reasons.append(f"Coordinated dive threat overwhelms enemy backline")

        return score, reasons


    def generate_builds(self, champions, items = None, runes = None, save_to_disk = False):
        """Generate recommended builds by scoring items against champion profiles."""
        results = {}
        items_dict = items if items else load_json(self.processed_dir / "items.json") or {}
        runes_dict = runes if runes else load_json(self.processed_dir / "runes.json") or {}
        item_names = self.build_name_set(items_dict)
        rune_names = self.build_name_set(runes_dict.get("byId", {}))

        for cid, champ in champions.items():
            name = champ.get("name", cid)

            b_data = self.infer_build(name, cid, champ, items_dict, runes_dict)
            b_data = self.filter_build_references(b_data, item_names, rune_names)
            results[cid] = b_data

            if save_to_disk:
                out_file = self.builds_dir / f"{cid}_build.json"
                save_json(b_data, out_file)

        return results


    def extract_all_relationships(self, champions, items = None, runes = None, counters = None, synergies = None, builds = None):
        """
        Extract all explicit, typed relationships (edges) between all entities in the LoL knowledge domain.
        Returns list of relationship documents:
        - WEAK_AGAINST / STRONG_AGAINST (champion -> champion)
        - SYNERGIZES_WITH (champion -> champion)
        - LORE_RELATED (champion -> champion)
        - FROM_REGION (champion -> region)
        - HAS_ROLE (champion -> role)
        - HAS_SUBROLE (champion -> subrole)
        - PLAYS_POSITION (champion -> position)
        - INFLICTS_CC (champion -> cc_type)
        - HAS_EFFECT (champion -> effect)
        - RECOMMENDS_ITEM (champion -> item)
        - RECOMMENDS_RUNE (champion -> rune)
        - RECOMMENDS_SPELL (champion -> spell)
        - BUILDS_INTO / BUILT_FROM (item -> item)
        """
        relationships = []
        seen_edges = set()

        def add_rel(source_id, source_name, source_type, target_id, target_name, target_type, rel_type, properties = None):
            if not source_id or not target_id:
                return
            edge_key = (str(source_id), str(target_id), rel_type, str(properties))
            if edge_key in seen_edges:
                return
            seen_edges.add(edge_key)
            doc = {
                "source_id": str(source_id),
                "source_name": str(source_name),
                "source_type": source_type,
                "target_id": str(target_id),
                "target_name": str(target_name),
                "target_type": target_type,
                "type": rel_type,
            }
            if properties:
                doc["properties"] = properties
            relationships.append(doc)

        items_dict = items or {}

        # Build name→ID lookup maps for resolving display names to canonical IDs
        champ_name_to_id = {}
        for _cid, _c in champions.items():
            _cname = _c.get("name", _cid)
            champ_name_to_id[_cname] = _cid
            champ_name_to_id[_cid] = _cid
            for _alias in _c.get("aliases", []):
                if _alias not in champ_name_to_id:
                    champ_name_to_id[_alias] = _cid

        item_name_to_id = {}
        for _iid, _idata in items_dict.items():
            _iname = _idata.get("name", "") if isinstance(_idata, dict) else ""
            if _iname:
                item_name_to_id[_iname] = str(_iid)

        rune_name_to_id = {}
        _runes_by_id = (runes or {}).get("byId", {})
        for _rid, _rdata in _runes_by_id.items():
            _rname = _rdata.get("name", "") if isinstance(_rdata, dict) else ""
            if _rname:
                rune_name_to_id[_rname] = str(_rid)

        # 1. Champion relationships
        for cid, champ in champions.items():
            name = champ.get("name", cid)

            # Region
            if champ.get("region"):
                add_rel(cid, name, "champion", champ["region"], champ["region"], "region", "FROM_REGION")

            # Roles
            for role in champ.get("roles", []):
                add_rel(cid, name, "champion", role, role, "role", "HAS_ROLE")

            # Subroles
            for subrole in champ.get("subroles", []):
                add_rel(cid, name, "champion", subrole, subrole, "subrole", "HAS_SUBROLE")

            # Positions
            for pos in champ.get("positions", []):
                add_rel(cid, name, "champion", pos, pos, "position", "PLAYS_POSITION")

            # CC
            for cc in champ.get("hard_cc", []):
                add_rel(cid, name, "champion", cc, cc, "cc", "INFLICTS_CC", {"classification": "hard_cc"})
            for cc in champ.get("soft_cc", []):
                add_rel(cid, name, "champion", cc, cc, "cc", "INFLICTS_CC", {"classification": "soft_cc"})

            # Effects
            for eff in champ.get("ability_effects", []):
                add_rel(cid, name, "champion", eff, eff, "effect", "HAS_EFFECT")

            # Lore related champions
            for rel_c in champ.get("related_champions", []):
                rel_id = (rel_c.get("canonical_id") or rel_c.get("name")) if isinstance(rel_c, dict) else str(rel_c)
                rel_name = rel_c.get("name", rel_id) if isinstance(rel_c, dict) else str(rel_c)
                rel_id = champ_name_to_id.get(rel_id, champ_name_to_id.get(rel_name, rel_id))
                add_rel(cid, name, "champion", rel_id, rel_name, "champion", "LORE_RELATED", {"region": champ.get("region")})

            # Counters
            c_info = (counters or {}).get(cid, champ.get("counters", {}))
            if isinstance(c_info, dict):
                for weak in c_info.get("weakAgainst", []):
                    opp = weak.get("champion")
                    if opp:
                        opp_id = champ_name_to_id.get(opp, opp)
                        add_rel(cid, name, "champion", opp_id, opp, "champion", "WEAK_AGAINST", {
                            "win_rate": weak.get("winRate"),
                            "reason": weak.get("reason", "")
                        })
                for strong in c_info.get("strongAgainst", []):
                    opp = strong.get("champion")
                    if opp:
                        opp_id = champ_name_to_id.get(opp, opp)
                        add_rel(cid, name, "champion", opp_id, opp, "champion", "STRONG_AGAINST", {
                            "win_rate": strong.get("winRate"),
                            "reason": strong.get("reason", "")
                        })

            # Synergies
            s_info = (synergies or {}).get(cid) or (synergies or {}).get(name) or {}
            syn_list = s_info.get("best_duos") or s_info.get("synergies", []) if isinstance(s_info, dict) else []
            if not syn_list and isinstance(champ.get("synergies"), list):
                syn_list = champ["synergies"]
            for syn in syn_list:
                partner = syn.get("partner") or syn.get("champion")
                if partner:
                    partner_id = champ_name_to_id.get(partner, partner)
                    add_rel(cid, name, "champion", partner_id, partner, "champion", "SYNERGIZES_WITH", {
                        "duo_win_rate": syn.get("soloq_winrate") or syn.get("duo_win_rate"),
                        "soloq_games": syn.get("soloq_games"),
                        "pro_play": syn.get("pro_play", False),
                        "pro_games": syn.get("pro_games", 0),
                        "pro_winrate": syn.get("pro_winrate"),
                        "reason": syn.get("synergy_reason") or syn.get("reason", ""),
                        "synergy_tag": syn.get("synergy_tag", ""),
                    })

            # Builds
            b_info = (builds or {}).get(cid, champ.get("builds", {}))
            if isinstance(b_info, dict):
                for item in b_info.get("startingItems", []):
                    i_id = item_name_to_id.get(item, item)
                    add_rel(cid, name, "champion", i_id, item, "item", "RECOMMENDS_ITEM", {"stage": "starting"})
                for item in b_info.get("coreItems", []):
                    i_id = item_name_to_id.get(item, item)
                    add_rel(cid, name, "champion", i_id, item, "item", "RECOMMENDS_ITEM", {"stage": "core"})
                for item in b_info.get("fullBuild", []):
                    i_id = item_name_to_id.get(item, item)
                    add_rel(cid, name, "champion", i_id, item, "item", "RECOMMENDS_ITEM", {"stage": "fullBuild"})

                if b_info.get("keystone"):
                    ks = b_info["keystone"]
                    ks_id = rune_name_to_id.get(ks, ks)
                    add_rel(cid, name, "champion", ks_id, ks, "rune", "RECOMMENDS_RUNE", {"role": "keystone"})
                for r in b_info.get("primaryRunes", []):
                    r_id = rune_name_to_id.get(r, r)
                    add_rel(cid, name, "champion", r_id, r, "rune", "RECOMMENDS_RUNE", {"role": "primary"})
                for r in b_info.get("secondaryRunes", []):
                    r_id = rune_name_to_id.get(r, r)
                    add_rel(cid, name, "champion", r_id, r, "rune", "RECOMMENDS_RUNE", {"role": "secondary"})
                for sp in b_info.get("summonerSpells", []):
                    add_rel(cid, name, "champion", sp, sp, "spell", "RECOMMENDS_SPELL")

            # NEW: Damage type (from raw adaptiveType)
            damage_type = champ.get("adaptiveType", "")
            if damage_type:
                add_rel(cid, name, "champion", damage_type, damage_type, "damage_type", "HAS_DAMAGE_TYPE")

            # NEW: Attack type (Melee/Ranged)
            attack_type = champ.get("attackType", "")
            if attack_type:
                add_rel(cid, name, "champion", attack_type, attack_type, "attack_type", "HAS_ATTACK_TYPE")

            # NEW: Resource type (Mana/Energy/Fury/None...)
            resource = champ.get("resource", "")
            if resource:
                add_rel(cid, name, "champion", resource, resource, "resource", "USES_RESOURCE")

            # NEW: Playstyles (derived in Enricher from stats)
            for ps in champ.get("playstyles", []):
                add_rel(cid, name, "champion", ps, ps, "playstyle", "HAS_PLAYSTYLE")

            # NEW: Win conditions (derived in Enricher)
            for wc in champ.get("winConditions", []):
                add_rel(cid, name, "champion", wc, wc, "win_condition", "HAS_WIN_CONDITION")

            # NEW: Power curve (derived in Enricher)
            power_curve = champ.get("powerCurve", "")
            if power_curve:
                add_rel(cid, name, "champion", power_curve, power_curve, "power_curve", "HAS_POWER_CURVE")

        # 2. Item build paths
        for iid, idata in items_dict.items():
            iname = idata.get("name", str(iid))

            # NEW: Item stat edges (PROVIDES_STAT)
            for stat_name, stat_val in idata.get("stats", {}).items():
                if stat_val and stat_val != 0:
                    add_rel(iid, iname, "item", stat_name, stat_name, "stat", "PROVIDES_STAT", {"value": stat_val})

            # NEW: Item tag edges (HAS_TAG)
            for tag in idata.get("tags", []):
                add_rel(iid, iname, "item", tag, tag, "tag", "HAS_TAG")

            for target_id in idata.get("buildInto", idata.get("into", [])):
                t_item = items_dict.get(str(target_id), {})
                t_name = t_item.get("name", str(target_id))
                add_rel(iid, iname, "item", str(target_id), t_name, "item", "BUILDS_INTO")
            for from_id in idata.get("buildFrom", idata.get("from", [])):
                f_item = items_dict.get(str(from_id), {})
                f_name = f_item.get("name", str(from_id))
                add_rel(iid, iname, "item", str(from_id), f_name, "item", "BUILT_FROM")

        # 3. Rune tree relationships
        runes_dict = (runes or {}).get("byId", {})
        for rid, rdata in runes_dict.items():
            rname = rdata.get("name", str(rid))
            rtree = rdata.get("tree")
            if rtree:
                is_ks = rdata.get("slot") == 0
                add_rel(rid, rname, "rune", rtree, rtree, "rune_tree", "BELONGS_TO_TREE", {"is_keystone": is_ks})

        return relationships

    @staticmethod
    def build_name_set(entities):
        """Return normalized display names from a processed entity dictionary."""
        return {
            data.get("name", "").lower()
            for data in entities.values()
            if isinstance(data, dict) and data.get("name")
        }

    @staticmethod
    def filter_build_references(build_data, item_names, rune_names):
        """Keep only items and runes that exist in the current processed dataset."""
        if item_names:
            for key in ["coreItems", "fullBuild", "startingItems"]:
                build_data[key] = [
                    name for name in build_data.get(key, [])
                    if name.lower() in item_names
                ]
            if build_data.get("boots", "").lower() not in item_names:
                build_data["boots"] = ""

        if rune_names:
            for key in ["primaryRunes", "secondaryRunes"]:
                build_data[key] = [
                    name for name in build_data.get(key, [])
                    if name.lower() in rune_names
                ]
            if build_data.get("keystone", "").lower() not in rune_names:
                build_data["keystone"] = ""

        return build_data

    @staticmethod
    def get_champion_archetype(roles, subroles, adaptive):
        """Determine the champion's build archetype key for item/rune scoring.
        Subrole-first classification ensures Juggernauts/Divers/Skirmishers
        are correctly classified as fighters, not tanks."""
        is_physical = "PHYSICAL" in adaptive.upper()
        roles_set = set(r.lower() for r in roles)
        subroles_upper = set(s.upper() for s in subroles)

        # Subrole-first: most specific classification wins
        if subroles_upper & {"JUGGERNAUT", "DIVER", "SKIRMISHER"}:
            return "fighter_physical" if is_physical else "fighter_magic"

        if "marksman" in roles_set:
            return "marksman"
        elif "assassin" in roles_set:
            return "assassin_physical" if is_physical else "assassin_magic"
        elif "mage" in roles_set:
            return "mage"
        elif "fighter" in roles_set:
            return "fighter_physical" if is_physical else "fighter_magic"
        elif "tank" in roles_set:
            return "tank"
        elif "support" in roles_set:
            if "ENCHANTER" in subroles_upper:
                return "support_enchanter"
            return "support_tank"
        return "fighter_physical"

    @staticmethod
    def score_item_for_champion(item_data, archetype_key):
        """Score how well an item fits a champion's archetype. Higher = better fit."""
        tags = set(item_data.get("tags", []))
        stats = item_data.get("stats", {})

        # Get tag weights for this archetype
        tag_weights = item_tag_weights.get(archetype_key, {})

        score = 0
        for tag, weight in tag_weights.items():
            if tag in tags:
                score += weight

        # Bonus from item stat values (keys match processed items.json format)
        if archetype_key in ("marksman", "assassin_physical", "fighter_physical"):
            score += min(stats.get("attack_damage", 0) * 0.05, 3)
            score += min(stats.get("attack_speed", 0) * 3, 2)
        elif archetype_key in ("mage", "assassin_magic", "support_enchanter", "fighter_magic"):
            score += min(stats.get("ability_power", 0) * 0.05, 3)
        elif archetype_key in ("tank", "support_tank"):
            score += min(stats.get("health", 0) * 0.005, 3)
            score += min(stats.get("armor", 0) * 0.05, 2)

        return score

    @staticmethod
    def select_runes(archetype_key, subroles, runes_dict, resource = "MANA"):
        """Select keystone and rune page based on champion archetype.
        Filters out mana-dependent runes for non-mana champions (Energy, Fury, etc.)."""
        subroles_upper = set(s.upper() for s in subroles)

        # Runes that are useless for non-mana champions
        mana_runes = {"Manaflow Band", "Presence of Mind"}
        uses_mana = resource.upper() in ("MANA", "")

        # Determine archetype-specific rune key
        rune_key = archetype_key
        if archetype_key == "tank":
            if "VANGUARD" in subroles_upper:
                rune_key = "tank_vanguard"
            elif "WARDEN" in subroles_upper:
                rune_key = "tank_warden"
            else:
                rune_key = "tank_default"
        elif archetype_key.startswith("fighter"):
            if "JUGGERNAUT" in subroles_upper:
                rune_key = "fighter_juggernaut"
            elif "SKIRMISHER" in subroles_upper:
                rune_key = "fighter_skirmisher"
            elif "DIVER" in subroles_upper:
                rune_key = "fighter_diver"
            else:
                rune_key = "fighter_default"
        elif archetype_key.startswith("support"):
            if "ENCHANTER" in subroles_upper:
                rune_key = "support_enchanter"
            elif "CATCHER" in subroles_upper:
                rune_key = "support_catcher"
            else:
                rune_key = "support_default"
        elif archetype_key == "mage":
            if "BURST" in subroles_upper or "ASSASSIN" in subroles_upper:
                rune_key = "mage_burst"
            else:
                rune_key = "mage_default"

        keystone_name = keystone_by_archetype.get(rune_key, "Conqueror")

        # Find keystone's tree from runes data
        by_id = runes_dict.get("byId", {})
        keystone_tree = None
        for rdata in by_id.values():
            if isinstance(rdata, dict) and rdata.get("name") == keystone_name:
                keystone_tree = rdata.get("tree")
                break

        # Pick primary runes from keystone's tree (filter mana runes for non-mana champs)
        primary_runes = []
        if keystone_tree:
            tree_runes = rune_tree_secondary_prefs.get(keystone_tree, [])
            if not uses_mana:
                tree_runes = [r for r in tree_runes if r not in mana_runes]
            primary_runes = tree_runes[:3]

        # Pick secondary runes from complementary tree (filter mana runes for non-mana champs)
        secondary_runes = []
        if keystone_tree:
            sec_tree = secondary_tree_pairing.get(keystone_tree, "Inspiration")
            sec_runes = rune_tree_secondary_prefs.get(sec_tree, [])
            if not uses_mana:
                sec_runes = [r for r in sec_runes if r not in mana_runes]
            secondary_runes = sec_runes[:2]

        return keystone_name, primary_runes, secondary_runes

    @staticmethod
    def infer_build(name, cid, champ, items_dict, runes_dict):
        """
        Generate build recommendations by scoring items against champion profile.
        Uses item stats/tags alignment and rune archetype matching.
        No hardcoded champion names or fabricated data.
        """
        roles = [r.lower() for r in champ.get("roles", [])]
        subroles = champ.get("subroles", [])
        adaptive = champ.get("adaptiveType", "PHYSICAL_DAMAGE")
        positions = champ.get("positions", [])

        archetype = RelationshipGenerator.get_champion_archetype(roles, subroles, adaptive)

        # Item Selection via Scoring
        completed_items = []
        boot_items = []

        for iid, idata in items_dict.items():
            if not isinstance(idata, dict):
                continue
            item_tags = set(idata.get("tags", []))
            has_from = bool(idata.get("buildFrom", []))
            has_into = bool(idata.get("buildInto", []))
            cost = idata.get("cost", {}).get("total", 0) if isinstance(idata.get("cost"), dict) else 0

            # Skip trinkets, consumables, very cheap items
            if item_tags & {"Trinket", "Consumable"}:
                continue
            if cost < 400:
                continue

            # Separate boots
            if "Boots" in item_tags:
                if has_from and not has_into and cost >= 900:
                    boot_score = RelationshipGenerator.score_item_for_champion(idata, archetype)
                    boot_items.append((idata, boot_score))
                continue

            # Completed items: have components, no further upgrades, cost >= 2500
            if has_from and not has_into and cost >= 2500:
                item_score = RelationshipGenerator.score_item_for_champion(idata, archetype)
                completed_items.append((idata, item_score))

        # Sort by score and pick top items
        completed_items.sort(key=lambda x: x[1], reverse=True)
        boot_items.sort(key=lambda x: x[1], reverse=True)

        top_items = [item["name"] for item, _ in completed_items[:5]]
        core_items = [item["name"] for item, _ in completed_items[:3]]

        # Pick canonical boots by archetype profile (avoids non-standard mode boots)
        standard_boots = boots_by_profile.get(archetype, "Plated Steelcaps")
        item_names_lookup = {it.get("name"): it for it in items_dict.values() if isinstance(it, dict) and it.get("name")}
        if standard_boots in item_names_lookup:
            best_boots = standard_boots
        elif boot_items:
            best_boots = boot_items[0][0]["name"]
        else:
            best_boots = standard_boots

        full_build = top_items[:5]
        if best_boots not in full_build:
            full_build.append(best_boots)
        full_build = full_build[:6]

        # Starting Items — prioritize position over role for junglers
        primary_pos = positions[0] if positions else "MID"
        if primary_pos == "JUNGLE":
            starting = ["Gustwalker Hatchling", "Health Potion"]
        else:
            primary_role = roles[0] if roles else "fighter"
            starting = list(starting_items_by_role.get(primary_role, ["Doran's Blade", "Health Potion"]))

        # Summoner Spells
        spells = list(summoner_spells_by_position.get(primary_pos, ["Flash", "Ignite"]))

        # Runes — pass resource type to filter mana runes for non-mana champions
        resource = champ.get("resource", "MANA") or "MANA"
        keystone, primary_runes, secondary_runes = RelationshipGenerator.select_runes(
            archetype, subroles, runes_dict, resource=resource
        )

        return {
            "champion": name,
            "champion_id": cid,
            "boots": best_boots,
            "coreItems": core_items,
            "fullBuild": full_build,
            "startingItems": starting,
            "summonerSpells": spells,
            "keystone": keystone,
            "primaryRunes": primary_runes,
            "secondaryRunes": secondary_runes,
        }


    def load_champions(self):
        """Load processed champions dataset."""
        return load_json(self.processed_dir / "champions.json")


# Alias for backward compatibility
relationship = RelationshipGenerator


def build_knowledge_base(processed_dir = None, kb_dir = None):
    """Functional interface for knowledge base relationship building."""
    generator = RelationshipGenerator(processed_dir, kb_dir)
    return generator.generate()


if __name__ == "__main__":
    generator = RelationshipGenerator()
    generator.generate()
