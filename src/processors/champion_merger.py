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

from .utils import (
    CDRAGON_raw_dir,
    DDRAGON_raw_dir,
    LORE_raw_dir,
    MERAKI_raw_dir,
    processed_dir,
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
        self.universe_stories = {}

    def merge(self, save_to_disk = False):
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

        if save_to_disk:
            self.save(merged)
            print(f"[ChampionMerger] Saved {len(merged)} merged champions to disk")
        else:
            print(f"[ChampionMerger] Merged {len(merged)} champions (in-memory)")
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

        # Collect enriched metadata
        allytips = parsed_dd.get("allytips", [])
        enemytips = parsed_dd.get("enemytips", [])
        skins = parsed_dd.get("skins", [])
        aram_stats = parsed_mk.get("aramStats", {})
        price = parsed_mk.get("price", {})
        release_date = parsed_mk.get("releaseDate") or raw_lore.get("release_date", "")
        patch_last_changed = parsed_mk.get("patchLastChanged", "")

        champ_slug = re.sub(r"[^a-zA-Z0-9]", "", champ_id.lower())
        stories = self.universe_stories.get(champ_slug, self.universe_stories.get(champ_id.lower(), []))

        attack_type = parsed_mk.get("attackType", "")
        if not attack_type:
            rng = stats.get("attackrange", {}).get("base", 175) if isinstance(stats.get("attackrange"), dict) else (stats.get("attackrange") or 175)
            attack_type = "MELEE" if rng <= 325 else "RANGED"

        adaptive_type = parsed_mk.get("adaptiveType", "")
        if not adaptive_type:
            adaptive_type = "MAGIC_DAMAGE" if "mage" in [r.lower() for r in roles] else "PHYSICAL_DAMAGE"

        ratings = parsed_mk.get("attributeRatings", {})
        if not ratings:
            roles_lower = [r.lower() for r in roles]
            ratings = {
                "damage": 3 if any(r in ["assassin", "marksman", "fighter", "mage"] for r in roles_lower) else 2,
                "toughness": 3 if "tank" in roles_lower else (2 if "fighter" in roles_lower else 1),
                "control": 2 if any(r in ["tank", "support", "mage"] for r in roles_lower) else 1,
                "mobility": 2 if any(r in ["assassin", "fighter"] for r in roles_lower) else 1,
                "utility": 2 if "support" in roles_lower else 1,
            }

        return {
            "id": champ_id,
            "name": name,
            "title": title,
            "aliases": aliases,
            "lore": champion_lore,
            "shortLore": short_lore,
            "stories": stories,
            "region": region,
            "faction_slug": faction_slug,
            "quote": quote,
            "related_champions": related_champions,
            "roles": roles,
            "subroles": parsed_mk.get("roles", []),
            "positions": parsed_mk.get("positions", []),
            "attributeRatings": ratings,
            "resource": parsed_mk.get("resource", "") or parsed_dd.get("partype", ""),
            "attackType": attack_type,
            "adaptiveType": adaptive_type,
            "stats": stats,
            "aramStats": aram_stats,
            "abilities": abilities,
            "tacticalInfo": tactical,
            "playstyleRatings": playstyle_ratings,
            "allytips": allytips,
            "enemytips": enemytips,
            "skins": skins,
            "price": price,
            "releaseDate": release_date,
            "patchLastChanged": patch_last_changed,
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
        allytips = [clean_html(t) for t in raw.get("allytips", []) if clean_html(t)]
        enemytips = [clean_html(t) for t in raw.get("enemytips", []) if clean_html(t)]
        skins = []
        for s in raw.get("skins", []):
            if isinstance(s, dict):
                skins.append({
                    "id": str(s.get("id", "")),
                    "num": s.get("num", 0),
                    "name": s.get("name", ""),
                    "chromas": bool(s.get("chromas", False)),
                })

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
            "allytips": allytips,
            "enemytips": enemytips,
            "skins": skins,
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

        raw_stats = raw.get("stats", {})
        aram_stats = {}
        for k, v in raw_stats.items():
            if k.startswith("aram") and isinstance(v, dict):
                flat_val = v.get("flat", 1.0)
                if flat_val not in (1.0, 0.0, 1, 0, None):
                    aram_stats[k] = flat_val
            elif k.startswith("aram") and v not in (0, 1, 0.0, 1.0, None):
                aram_stats[k] = v

        abilities = {}
        passive_data = raw.get("abilities", {}).get("P", [])
        if passive_data:
            p = passive_data[0] if isinstance(passive_data, list) else passive_data
            p_text = (json.dumps(p.get("effects", [])) + " " + (p.get("notes") or "")).lower()
            p_onhit = bool(p.get("onHitEffects")) or ("on-hit" in p_text or "on hit" in p_text)
            p_proj = str(p.get("projectile", "")).upper() in ("TRUE", "SPECIAL")
            p_shield = str(p.get("spellshieldable", "")).upper() in ("TRUE", "SPECIAL")
            abilities["passive"] = {
                "name": p.get("name", ""),
                "description": clean_html(p.get("description", "")),
                "icon": p.get("icon", ""),
                "effects": p.get("effects", []),
                "projectile": p_proj,
                "projectileType": p.get("projectile"),
                "spellshieldable": p_shield,
                "onHitEffects": p_onhit,
                "damageType": p.get("damageType"),
                "notes": p.get("notes"),
            }

        for key in ["Q", "W", "E", "R"]:
            spell_data = raw.get("abilities", {}).get(key, [])
            if spell_data:
                spell = spell_data[0] if isinstance(spell_data, list) else spell_data
                sp_text = (json.dumps(spell.get("effects", [])) + " " + (spell.get("notes") or "")).lower()
                is_proj = str(spell.get("projectile", "")).upper() in ("TRUE", "SPECIAL")
                is_shield = str(spell.get("spellshieldable", "")).upper() in ("TRUE", "SPECIAL")
                is_onhit = bool(spell.get("onHitEffects")) or ("on-hit" in sp_text or "on hit" in sp_text)
                abilities[key] = {
                    "name": spell.get("name", ""),
                    "description": clean_html(spell.get("description", "")),
                    "icon": spell.get("icon", ""),
                    "cooldown": self.extract_meraki_scaling(spell.get("cooldown", {})),
                    "cost": self.extract_meraki_scaling(spell.get("cost", {})),
                    "costType": spell.get("costType", ""),
                    "effects": spell.get("effects", []),
                    "projectile": is_proj,
                    "projectileType": spell.get("projectile"),
                    "spellshieldable": is_shield,
                    "onHitEffects": is_onhit,
                    "damageType": spell.get("damageType"),
                    "targeting": spell.get("targeting"),
                    "affects": spell.get("affects"),
                    "notes": spell.get("notes"),
                }

        return {
            "id": raw.get("key", ""),
            "name": raw.get("name", ""),
            "title": raw.get("title", ""),
            "resource": raw.get("resource", ""),
            "attackType": raw.get("attackType", ""),
            "adaptiveType": raw.get("adaptiveType", ""),
            "stats": stats,
            "aramStats": aram_stats,
            "abilities": abilities,
            "roles": raw.get("roles", []),
            "positions": raw.get("positions", []),
            "attributeRatings": raw.get("attributeRatings", {}),
            "price": raw.get("price", {}),
            "releaseDate": raw.get("releaseDate", ""),
            "releasePatch": raw.get("releasePatch", ""),
            "patchLastChanged": raw.get("patchLastChanged", ""),
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
        """Merge abilities from all sources. Now includes scaling effects and icons."""
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

            # Meraki micro mechanics and interaction properties
            for mech in ["projectile", "projectileType", "spellshieldable", "onHitEffects", "damageType", "targeting", "affects", "notes"]:
                val = mk_spell.get(mech)
                if val is not None and val != "":
                    ability[mech] = val

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
        self.ddragon_data = self.load_json(DDRAGON_raw_dir / "champions.json") or {}
        raw_cd = self.load_json(CDRAGON_raw_dir / "champions.json") or {}
        self.meraki_data = self.load_json(MERAKI_raw_dir / "champions.json") or {}
        raw_lore = self.load_json(LORE_raw_dir / "lore.json") or {}

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

        # Load Color Stories from universe directory
        self.universe_stories = {}
        universe_dir = LORE_raw_dir / "universe"
        if universe_dir.exists():
            for fpath in universe_dir.glob("*.json"):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        u_data = json.load(f)
                    modules = u_data.get("modules", [])
                    u_stories = []
                    for m in modules:
                        if m.get("type") == "story-preview":
                            u_stories.append({
                                "title": m.get("title", ""),
                                "description": clean_html(m.get("description", "")),
                                "story_slug": m.get("story-slug", ""),
                                "url": m.get("url", ""),
                                "release_date": m.get("release-date", "")
                            })
                    if u_stories:
                        stem = fpath.stem.lower()
                        self.universe_stories[stem] = u_stories
                except Exception:
                    pass

        print(f"  DDragon:  {len(self.ddragon_data)} champions")
        print(f"  CDragon:  {len(self.cdragon_data)} champions (normalized)")
        print(f"  Meraki:   {len(self.meraki_data)} champions")
        print(f"  Lore:     {len(self.lore_data)} entries (normalized)")
        print(f"  Universe: {len(self.universe_stories)} champions with Color Stories")

        # Report lore coverage gaps
        missing_lore = master_ids - set(self.lore_data.keys())
        if missing_lore:
            print(f"  [WARN] Champions missing lore data: {sorted(missing_lore)}")

    def save(self, data):
        """Save merged data to processed directory."""
        processed_dir.mkdir(parents = True, exist_ok = True)
        filepath = processed_dir / "champions.json"
        with open(filepath, "w", encoding = "utf-8") as f:
            json.dump(data, f, indent = 2, ensure_ascii = False)

    @staticmethod
    def load_json(path):
        """Load a JSON file, return empty dict if not found."""
        if path.exists():
            with open(path, "r", encoding = "utf-8") as f:
                return json.load(f)
        return {}
