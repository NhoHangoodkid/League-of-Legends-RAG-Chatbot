"""
Profile and ability formatting helpers for champion retrieval.
"""

from processors.spell_analyzer import SpellAnalyzer


class ProfileRetrieverMixin:
    """Provides methods for extracting full champion profiles and formatting abilities."""

    def format_champion_abilities(self, c_doc):
        """Format champion abilities with verified CC and effect tags (e.g. Q: Shattered Earth [Slow])."""
        if not c_doc or not c_doc.get("abilities"):
            return ""
        ab_dict = c_doc["abilities"]
        ab_parts = []
        for key in ["passive", "Q", "W", "E", "R"]:
            ab = ab_dict.get(key)
            if isinstance(ab, dict) and ab.get("name"):
                name = ab["name"]
                desc = f"{ab.get('description', '')} {ab.get('tooltip', '')}"
                cc_set = SpellAnalyzer.extract_cc(desc)
                eff_set = SpellAnalyzer.extract_effects(desc)
                tags = []
                if cc_set:
                    tags.extend(sorted(list(cc_set)))
                key_effects = eff_set & {"Shield", "Heal", "Dash", "Blink", "Stealth", "Invulnerability"}
                if key_effects:
                    tags.extend(sorted(list(key_effects)))
                tag_str = f" [{', '.join(tags)}]" if tags else ""
                ab_parts.append(f"{key.upper()}: {name}{tag_str}")
        return ", ".join(ab_parts)

    def extract_champion_full_profile(self, champ):
        """
        Extract complete, multi-dimensional profile of a champion from Processors and KnowledgeStore.
        Preserves abilities, base stats, attribute ratings, tactical info, and mechanics.
        """
        abilities = {}
        if "abilities" in champ and isinstance(champ["abilities"], dict):
            for k, v in champ["abilities"].items():
                if isinstance(v, dict):
                    abilities[k] = {
                        "name": v.get("name", ""),
                        "description": v.get("description", ""),
                        "cooldown": v.get("cooldown", []),
                        "cost": v.get("cost", []),
                        "costType": v.get("costType"),
                        "range": v.get("range", []),
                        "maxrank": v.get("maxrank"),
                        "scalingEffects": v.get("scalingEffects", []),
                        "effects": v.get("effects", []),
                        "projectile": v.get("projectile"),
                        "projectileType": v.get("projectileType"),
                        "spellshieldable": v.get("spellshieldable"),
                        "onHitEffects": v.get("onHitEffects"),
                        "damageType": v.get("damageType"),
                        "targeting": v.get("targeting"),
                        "notes": v.get("notes"),
                    }

        tactical = champ.get("tacticalInfo") if isinstance(champ.get("tacticalInfo"), dict) else {}
        stats = champ.get("stats", {})
        base_stats = {}
        stat_growths = {}
        if isinstance(stats, dict):
            for k, v in stats.items():
                if isinstance(v, dict):
                    if "base" in v:
                        base_stats[k] = v.get("base")
                    if "perLevel" in v:
                        stat_growths[k] = v.get("perLevel")
                elif isinstance(v, (int, float)):
                    base_stats[k] = v

        raw_related = champ.get("related_champions", [])
        clean_related = []
        for r in raw_related:
            r_name = r.get("name") if isinstance(r, dict) else str(r)
            if r_name and r_name not in clean_related:
                clean_related.append(r_name)

        return {
            "name": champ.get("name"),
            "champion": champ.get("name"),
            "title": champ.get("title", ""),
            "region": champ.get("region", ""),
            "roles": champ.get("roles", []),
            "subroles": champ.get("subroles", []),
            "positions": champ.get("positions", []),
            "attackType": champ.get("attackType"),
            "adaptiveType": champ.get("adaptiveType"),
            "resource": champ.get("resource"),
            "attributeRatings": champ.get("attributeRatings", {}),
            "playstyleRatings": champ.get("playstyleRatings", {}),
            "difficulty": champ.get("difficulty"),
            "base_stats": base_stats,
            "stat_growths": stat_growths,
            "stats": stats,
            "playstyles": champ.get("playstyles", []),
            "powerCurve": champ.get("powerCurve", []),
            "winConditions": champ.get("winConditions", []),
            "cc_types": champ.get("cc_types", []),
            "hard_cc": champ.get("hard_cc", []),
            "soft_cc": champ.get("soft_cc", []),
            "ability_effects": champ.get("ability_effects", []),
            "abilities": abilities,
            "tacticalInfo": tactical,
            "weaknesses": champ.get("weaknesses") or tactical.get("weaknesses", []),
            "tactical_tips": champ.get("tactical_tips") or tactical.get("tactical_tips", []),
            "counter_items": champ.get("counter_items") or tactical.get("counter_items", []),
            "official_enemytips": champ.get("enemytips") or tactical.get("official_enemytips", []),
            "official_allytips": champ.get("allytips") or tactical.get("official_allytips", []),
            "skins": champ.get("skins", []),
            "stories": champ.get("stories", []),
            "aramStats": champ.get("aramStats", {}),
            "mechanicsSummary": champ.get("mechanicsSummary", {}),
            "shortLore": champ.get("shortLore") or champ.get("lore", "")[:600],
            "lore": champ.get("lore", "")[:2500],
            "related_champions": clean_related,
        }
