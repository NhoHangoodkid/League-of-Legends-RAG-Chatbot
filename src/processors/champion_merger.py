"""
Champion Data Merger.

Extracts, normalizes, and merges pure raw champion data from 3 sources:
- DDragon: Base metadata, cooldowns, costs, ranges, tooltips, lore
- CDragon: Tactical playstyle ratings, detailed spell descriptions
- Meraki: Highly accurate base stats, growth formulas, precise ability scaling

Output: src/processors/processed/champions.json
"""

import json
import re
from pathlib import Path

try:
    from .utils import (
        CDRAGON_RAW_DIR,
        DDRAGON_RAW_DIR,
        LORE_RAW_DIR,
        MERAKI_RAW_DIR,
        PROCESSED_DIR,
        load_json,
        save_json,
        log,
        normalize_champion_id,
        get_champion_aliases,
        build_lore_key_map,
        clean_html,
    )
except ImportError:
    try:
        from processors.utils import (
            CDRAGON_RAW_DIR,
            DDRAGON_RAW_DIR,
            LORE_RAW_DIR,
            MERAKI_RAW_DIR,
            PROCESSED_DIR,
            load_json,
            save_json,
            log,
            normalize_champion_id,
            get_champion_aliases,
            build_lore_key_map,
            clean_html,
        )
    except ImportError:
        from utils import (
            CDRAGON_RAW_DIR,
            DDRAGON_RAW_DIR,
            LORE_RAW_DIR,
            MERAKI_RAW_DIR,
            PROCESSED_DIR,
            load_json,
            save_json,
            log,
            normalize_champion_id,
            get_champion_aliases,
            build_lore_key_map,
            clean_html,
        )


class ChampionMerger:
    """Extract and merge champion data from raw DDragon, CDragon, and Meraki data."""

    def __init__(self):
        self.ddragon_data = {}
        self.cdragon_data = {}
        self.meraki_data = {}
        self.lore_data = {}

    def merge(self):
        """
        Load all raw sources and merge into unified champion data.
        Returns dict of {champion_id: merged_data}.
        """
        print("[ChampionMerger] Loading raw source data...")
        self.load_sources()

        # DDragon is canonical for playable LoL PC roster (filters out Jade_* Wild Rift entries)
        master_ids = set(self.ddragon_data.keys())
        if self.cdragon_data:
            for cid in self.cdragon_data.keys():
                if not cid.startswith("Jade_"):
                    master_ids.add(cid)

        print(f"[ChampionMerger] Merging {len(master_ids)} champions...")

        merged = {}
        for champ_id in sorted(master_ids):
            raw_dd = self.ddragon_data.get(champ_id, {})
            raw_cd = self.cdragon_data.get(champ_id, {})
            raw_mk = self.meraki_data.get(champ_id, {})
            raw_lore = self.lore_data.get(champ_id, {})

            merged[champ_id] = self.merge_champion(champ_id, raw_dd, raw_cd, raw_mk, raw_lore)

        self.save(merged)
        print(f"[ChampionMerger] Saved {len(merged)} merged champions")
        return merged

    def merge_champion(self, champ_id, raw_dd, raw_cd, raw_mk, raw_lore):
        """Normalize each raw source and merge a single champion."""
        parsed_dd = self.parse_ddragon_champion(raw_dd)
        parsed_cd = self.parse_cdragon_champion(raw_cd)
        parsed_mk = self.parse_meraki_champion(raw_mk)

        name = parsed_dd.get("name") or parsed_cd.get("name") or parsed_mk.get("name") or champ_id
        title = parsed_dd.get("title") or parsed_cd.get("title") or parsed_mk.get("title") or ""

        # Stats: Meraki > DDragon
        stats = self.merge_stats(parsed_dd.get("stats", {}), parsed_mk.get("stats", {}))

        # Abilities: DDragon cooldown/cost + CDragon cleaned descriptions + Meraki scaling
        abilities = self.merge_abilities(
            parsed_dd.get("abilities", {}),
            parsed_cd.get("abilities", {}),
            parsed_mk.get("abilities", {}),
        )

        roles = parsed_cd.get("roles", []) or parsed_dd.get("tags", []) or parsed_mk.get("roles", [])
        tactical = parsed_cd.get("tacticalInfo", {})
        playstyle_ratings = parsed_cd.get("playstyleInfo", {})

        # Lore: prioritize dedicated lore source, fallback to DDragon/Meraki
        champion_lore = raw_lore.get("lore", "") or parsed_dd.get("lore", "") or parsed_mk.get("lore", "")
        short_lore = raw_lore.get("shortLore", "") or parsed_dd.get("blurb", "") or parsed_cd.get("shortBio", "")
        region = raw_lore.get("region", "Runeterra (Unaffiliated)")
        faction_slug = raw_lore.get("faction_slug", "unaffiliated")
        quote = raw_lore.get("quote", "")
        related_champions = raw_lore.get("related_champions", [])

        # Build aliases list for search enrichment
        aliases = get_champion_aliases(champ_id)
        # Always include the display name if it differs from the ID
        if name and name != champ_id and name not in aliases:
            aliases.insert(0, name)

        return {
            "id": champ_id,
            "name": name,
            "title": title,
            "aliases": aliases,
            "lore": champion_lore,
            "shortLore": short_lore,
            "region": region,
            "faction_slug": faction_slug,
            "quote": quote,
            "related_champions": related_champions,
            "roles": roles,
            "resource": parsed_mk.get("resource", "") or parsed_dd.get("partype", ""),
            "attackType": parsed_mk.get("attackType", ""),
            "adaptiveType": parsed_mk.get("adaptiveType", ""),
            "stats": stats,
            "abilities": abilities,
            "tacticalInfo": tactical,
            "playstyleRatings": playstyle_ratings,
            "difficulty": parsed_dd.get("info", {}).get("difficulty", tactical.get("difficulty", 0)),
            "image": parsed_dd.get("image", ""),
            "sources": self.list_sources(raw_dd, raw_cd, raw_mk),
        }

    # RAW DATA PARSERS (Moved from collectors to processor)

    def parse_ddragon_champion(self, raw):
        """Extract and structure raw DDragon champion payload."""
        if not raw:
            return {}

        abilities = {}
        passive = raw.get("passive", {})
        abilities["passive"] = {
            "name": passive.get("name", ""),
            "description": clean_html(passive.get("description", "")),
            "image": passive.get("image", {}).get("full", ""),
        }

        spell_keys = ["Q", "W", "E", "R"]
        for i, spell in enumerate(raw.get("spells", [])):
            if i < len(spell_keys):
                abilities[spell_keys[i]] = {
                    "name": spell.get("name", ""),
                    "description": clean_html(spell.get("description", "")),
                    "tooltip": spell.get("tooltip", ""),
                    "cooldown": spell.get("cooldown", []),
                    "cost": spell.get("cost", []),
                    "range": spell.get("range", []),
                    "maxrank": spell.get("maxrank", 5),
                    "image": spell.get("image", {}).get("full", ""),
                }

        stats = raw.get("stats", {})
        return {
            "id": raw.get("id", ""),
            "name": raw.get("name", ""),
            "title": raw.get("title", ""),
            "lore": raw.get("lore", ""),
            "blurb": raw.get("blurb", ""),
            "tags": raw.get("tags", []),
            "partype": raw.get("partype", ""),
            "info": raw.get("info", {}),
            "stats": stats,
            "abilities": abilities,
            "image": raw.get("image", {}).get("full", ""),
        }

    def parse_cdragon_champion(self, raw):
        """Extract and structure raw CDragon champion payload."""
        if not raw:
            return {}

        summary = raw.get("summary", {}) if "summary" in raw else raw
        detail = raw.get("detail", {}) if "detail" in raw else raw

        abilities = {}
        passive = detail.get("passive", {})
        abilities["passive"] = {
            "name": passive.get("name", ""),
            "description": clean_html(passive.get("description", "")),
        }

        spell_keys = ["Q", "W", "E", "R"]
        for i, spell in enumerate(detail.get("spells", [])):
            if i < len(spell_keys):
                abilities[spell_keys[i]] = {
                    "name": spell.get("name", ""),
                    "description": clean_html(spell.get("description", "")),
                }

        tactical = detail.get("tacticalInfo", {})
        playstyle = detail.get("playstyleInfo", {})

        return {
            "id": summary.get("alias", ""),
            "championId": detail.get("id", summary.get("id", 0)),
            "name": detail.get("name", summary.get("name", "")),
            "title": detail.get("title", ""),
            "shortBio": detail.get("shortBio", ""),
            "roles": summary.get("roles", []),
            "abilities": abilities,
            "tacticalInfo": {
                "style": tactical.get("style", 0),
                "difficulty": tactical.get("difficulty", 0),
                "damageType": tactical.get("damageType", ""),
            },
            "playstyleInfo": {
                "damage": playstyle.get("damage", 0),
                "durability": playstyle.get("durability", 0),
                "crowdControl": playstyle.get("crowdControl", 0),
                "mobility": playstyle.get("mobility", 0),
                "utility": playstyle.get("utility", 0),
            },
        }

    def parse_meraki_champion(self, raw):
        """Extract and structure raw Meraki champion payload."""
        if not raw:
            return {}

        raw_stats = raw.get("stats", {})
        stats = {}
        for stat_name, stat_data in raw_stats.items():
            if isinstance(stat_data, dict):
                stats[stat_name] = {
                    "base": stat_data.get("flat", 0),
                    "perLevel": stat_data.get("perLevel", 0),
                    "percent": stat_data.get("percent", 0),
                    "percentPerLevel": stat_data.get("percentPerLevel", 0),
                }
            else:
                stats[stat_name] = {"base": stat_data, "perLevel": 0}

        abilities = {}
        passive_data = raw.get("abilities", {}).get("P", [])
        if passive_data:
            p = passive_data[0] if isinstance(passive_data, list) else passive_data
            abilities["passive"] = {
                "name": p.get("name", ""),
                "description": clean_html(p.get("description", "")),
                "icon": p.get("icon", ""),
                "effects": p.get("effects", []),
            }

        for key in ["Q", "W", "E", "R"]:
            spell_data = raw.get("abilities", {}).get(key, [])
            if spell_data:
                spell = spell_data[0] if isinstance(spell_data, list) else spell_data
                abilities[key] = {
                    "name": spell.get("name", ""),
                    "description": clean_html(spell.get("description", "")),
                    "icon": spell.get("icon", ""),
                    "cooldown": self.extract_meraki_scaling(spell.get("cooldown", {})),
                    "cost": self.extract_meraki_scaling(spell.get("cost", {})),
                    "costType": spell.get("costType", ""),
                    "effects": spell.get("effects", []),
                }

        return {
            "id": raw.get("key", ""),
            "name": raw.get("name", ""),
            "title": raw.get("title", ""),
            "resource": raw.get("resource", ""),
            "attackType": raw.get("attackType", ""),
            "adaptiveType": raw.get("adaptiveType", ""),
            "stats": stats,
            "abilities": abilities,
            "roles": raw.get("roles", []),
            "lore": raw.get("lore", ""),
        }

    @staticmethod
    def extract_meraki_scaling(scaling_data):
        """Extract scaling modifiers from Meraki structure."""
        if not scaling_data:
            return []
        if isinstance(scaling_data, list):
            return scaling_data
        if isinstance(scaling_data, dict):
            modifiers = scaling_data.get("modifiers", [])
            if modifiers and isinstance(modifiers, list):
                first = modifiers[0]
                return first.get("values", [])
            return []
        return []

    # MERGING HELPERS

    def merge_stats(self, dd_stats, mk_stats):
        """Merge stats. Priority: Meraki > DDragon."""
        if mk_stats:
            stats = {}
            stat_mapping = {
                "health": "hp",
                "healthRegen": "hpregen",
                "mana": "mp",
                "manaRegen": "mpregen",
                "armor": "armor",
                "magicResistance": "spellblock",
                "attackDamage": "attackdamage",
                "attackSpeed": "attackspeed",
                "movespeed": "movespeed",
            }
            for mk_name, dd_name in stat_mapping.items():
                mk_stat = mk_stats.get(mk_name, {})
                if isinstance(mk_stat, dict) and mk_stat.get("base", 0) != 0:
                    stats[dd_name] = {
                        "base": mk_stat.get("base", 0),
                        "perLevel": mk_stat.get("perLevel", 0),
                    }
                elif dd_name in dd_stats:
                    stats[dd_name] = {
                        "base": dd_stats.get(dd_name, 0),
                        "perLevel": dd_stats.get(f"{dd_name}perlevel", 0),
                    }

            ar = mk_stats.get("attackRange", {})
            if isinstance(ar, dict):
                stats["attackrange"] = {"base": ar.get("base", 0), "perLevel": 0}
            elif "attackrange" in dd_stats:
                stats["attackrange"] = {"base": dd_stats["attackrange"], "perLevel": 0}

            return stats

        if dd_stats:
            result = {}
            base_stats = [
                "hp", "hpregen", "mp", "mpregen", "armor",
                "spellblock", "attackdamage", "attackspeed",
                "movespeed", "attackrange",
            ]
            for stat in base_stats:
                result[stat] = {
                    "base": dd_stats.get(stat, 0),
                    "perLevel": dd_stats.get(f"{stat}perlevel", 0),
                }
            return result

        return {}

    def merge_abilities(self, dd_abilities, cd_abilities, mk_abilities):
        """Merge abilities from all sources. Now includes scaling effects & icons."""
        merged = {}
        all_keys = {"passive", "Q", "W", "E", "R"}

        for key in all_keys:
            dd_spell = dd_abilities.get(key, {})
            cd_spell = cd_abilities.get(key, {})
            mk_spell = mk_abilities.get(key, {})

            name = cd_spell.get("name") or dd_spell.get("name") or mk_spell.get("name") or ""
            description = (
                cd_spell.get("description")
                or dd_spell.get("description")
                or mk_spell.get("description")
                or ""
            )

            ability = {
                "name": name,
                "description": description,
            }

            if key != "passive":
                ability["cooldown"] = mk_spell.get("cooldown") or dd_spell.get("cooldown", [])
                # Meraki cost is more accurate (includes cost type like % health)
                ability["cost"] = mk_spell.get("cost") or dd_spell.get("cost", [])
                ability["range"] = dd_spell.get("range", [])
                ability["maxrank"] = dd_spell.get("maxrank", 5 if key != "R" else 3)

            if dd_spell.get("tooltip"):
                ability["tooltip"] = dd_spell["tooltip"]

            # Ability icon: DDragon image > Meraki icon
            icon = dd_spell.get("image", "") or mk_spell.get("icon", "")
            if icon:
                ability["image"] = icon

            # Meraki scaling effects (AD/AP ratios, % max health damage, etc.)
            mk_effects = mk_spell.get("effects", [])
            if mk_effects:
                ability["scalingEffects"] = mk_effects

            merged[key] = ability

        return merged

    def list_sources(self, dd, cd, mk):
        """List which sources contributed data for this champion."""
        sources = []
        if dd:
            sources.append("ddragon")
        if cd:
            sources.append("cdragon")
        if mk:
            sources.append("meraki")
        return sources

    def load_sources(self):
        """Load all raw data from disk and normalize keys using the alias registry."""
        self.ddragon_data = self.load_json(DDRAGON_RAW_DIR / "champions.json") or {}
        raw_cd = self.load_json(CDRAGON_RAW_DIR / "champions.json") or {}
        self.meraki_data = self.load_json(MERAKI_RAW_DIR / "champions.json") or {}
        raw_lore = self.load_json(LORE_RAW_DIR / "lore.json") or {}

        # Normalize CDragon keys using alias registry (handles FiddleSticks→Fiddlesticks, filters Jade_*)
        self.cdragon_data = {}
        for k, v in raw_cd.items():
            canonical = normalize_champion_id(k)
            if canonical:
                self.cdragon_data[canonical] = v

        # Build master IDs from DDragon + normalized CDragon
        master_ids = set(self.ddragon_data.keys()) | set(self.cdragon_data.keys())

        # Normalize lore data keys with smart mapping (handles RenataGlasc→Renata, etc.)
        lore_key_map = build_lore_key_map(set(raw_lore.keys()), master_ids)
        self.lore_data = {}
        for lk, v in raw_lore.items():
            canonical = lore_key_map.get(lk)
            if canonical:
                self.lore_data[canonical] = v
            else:
                # Direct match fallback
                normalized = normalize_champion_id(lk)
                if normalized and normalized in master_ids:
                    self.lore_data[normalized] = v

        print(f"  DDragon: {len(self.ddragon_data)} champions")
        print(f"  CDragon: {len(self.cdragon_data)} champions (normalized)")
        print(f"  Meraki:  {len(self.meraki_data)} champions")
        print(f"  Lore:    {len(self.lore_data)} entries (normalized)")

        # Report lore coverage gaps
        missing_lore = master_ids - set(self.lore_data.keys())
        if missing_lore:
            print(f"  [WARN] Champions missing lore data: {sorted(missing_lore)}")

    def save(self, data):
        """Save merged data to processed directory."""
        PROCESSED_DIR.mkdir(parents = True, exist_ok = True)
        filepath = PROCESSED_DIR / "champions.json"
        with open(filepath, "w", encoding = "utf-8") as f:
            json.dump(data, f, indent = 2, ensure_ascii = False)

    @staticmethod
    def load_json(path):
        """Load a JSON file, return empty dict if not found."""
        if path.exists():
            with open(path, "r", encoding = "utf-8") as f:
                return json.load(f)
        return {}
