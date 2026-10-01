"""
Champion-specific retrieval mixin: info, lore, skins, ARAM stats, base stats, stats at level, and comparisons.
"""


class ChampionRetrieverMixin:
    """Provides champion queries: profile, lore, skins, ARAM, stats, and 1v1 comparison."""

    def get_champion_info(self, name):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}
        return self.extract_champion_full_profile(champ)

    def get_champion_lore(self, name, interaction_champ = None):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)

        # Clean related champions (extract string names, never raw dicts)
        raw_related = profile.get("related_champions", [])
        clean_related = []
        for r in raw_related:
            r_name = r.get("name") if isinstance(r, dict) else str(r)
            if r_name and r_name not in clean_related:
                clean_related.append(r_name)

        result = {
            "is_lore_query": True,
            "champion": profile.get("name"),
            "title": profile.get("title"),
            "region": profile.get("region"),
            "roles": profile.get("roles"),
            "shortLore": profile.get("shortLore", ""),
            "lore": profile.get("lore", ""),
            "stories": profile.get("stories", []),
            "related_champions": clean_related,
        }

        # Multi-champion lore relationship / conflict query
        if interaction_champ:
            inter_champ = self.store.get_champion(interaction_champ)
            if inter_champ:
                inter_profile = self.extract_champion_full_profile(inter_champ)
                inter_raw_related = inter_profile.get("related_champions", [])
                inter_clean_related = [
                    (r.get("name") if isinstance(r, dict) else str(r))
                    for r in inter_raw_related
                ]

                result["is_conflict_lore_query"] = True
                result["interaction_champion"] = inter_profile.get("name")
                result["interaction_title"] = inter_profile.get("title")
                result["interaction_region"] = inter_profile.get("region")
                result["interaction_shortLore"] = inter_profile.get("shortLore", "")
                result["interaction_lore"] = inter_profile.get("lore", "")
                result["interaction_related"] = [r for r in inter_clean_related if r]

        return result

    def get_champion_skins(self, name):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)
        raw_skins = champ.get("skins", [])

        # Filter out default base champion and separate actual skins from color chromas
        actual_skins = []
        chromas = []
        for s in raw_skins:
            s_name = s.get("name") if isinstance(s, dict) else str(s)
            s_num = s.get("num", -1) if isinstance(s, dict) else -1
            if not s_name or s_name.lower() == "default" or s_num == 0:
                continue
            if "(" in s_name and ")" in s_name:
                chromas.append(s_name)
            else:
                actual_skins.append(s_name)

        # Categorize skins into recognizable thematic universes and tiers
        thematic_groups = {}
        legendary_prestige = []
        for sk in actual_skins:
            sk_lower = sk.lower()
            if any(k in sk_lower for k in ["prestige", "nightbringer", "truth dragon", "dream dragon", "genesis"]):
                legendary_prestige.append(sk)

            if "project" in sk_lower:
                thematic_groups.setdefault("Cyberpunk (PROJECT)", []).append(sk)
            elif any(k in sk_lower for k in ["nightbringer", "dawnbringer"]):
                thematic_groups.setdefault("Order & Chaos (Nightbringer)", []).append(sk)
            elif any(k in sk_lower for k in ["spirit blossom", "blood moon", "inkshadow", "snow moon"]):
                thematic_groups.setdefault("Ionian Spirit & Lore", []).append(sk)
            elif "dragon" in sk_lower:
                thematic_groups.setdefault("Dragonmancer", []).append(sk)
            elif "high noon" in sk_lower:
                thematic_groups.setdefault("Wild West (High Noon)", []).append(sk)
            elif any(k in sk_lower for k in ["odyssey", "dark star", "cosmic"]):
                thematic_groups.setdefault("Sci-Fi & Cosmic (Odyssey)", []).append(sk)
            elif any(k in sk_lower for k in ["true damage", "k/da", "heartsteel", "pentakill"]):
                thematic_groups.setdefault("Music & Pop Culture", []).append(sk)
            elif any(k in sk_lower for k in ["arcade", "battle boss"]):
                thematic_groups.setdefault("Arcade Universe", []).append(sk)
            elif any(k in sk_lower for k in ["battle wolf", "battle bat", "anima squad"]):
                thematic_groups.setdefault("Anima Squad", []).append(sk)
            elif "foreseen" in sk_lower:
                thematic_groups.setdefault("Cinematic & Canon Lore", []).append(sk)

        return {
            "is_skin_query": True,
            "champion": profile.get("name"),
            "title": profile.get("title"),
            "unique_skin_count": len(actual_skins),
            "chroma_count": len(chromas),
            "total_cosmetics": len(actual_skins) + len(chromas),
            "actual_skins": actual_skins,
            "legendary_prestige": legendary_prestige,
            "thematic_groups": thematic_groups,
            "sample_skins": actual_skins[:15],
            "skins": actual_skins,
            "total_skins": len(actual_skins),
        }

    def get_aram_stats(self, name):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)
        aram = champ.get("aramStats", {})
        return {
            "is_aram_query": True,
            "champion": profile.get("name"),
            "title": profile.get("title"),
            "has_aram_stats": bool(aram),
            "aram_modifiers": aram,
            "aram_stats": aram,
            "aramStats": aram,
            "tacticalInfo": champ.get("tacticalInfo", {}),
        }

    def get_champion_base_stats(self, name):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)
        profile["level"] = 1
        return profile

    def get_champion_stats_at_level(self, name, level):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)
        stats = champ.get("stats", {})
        calculated = {}
        for k, v in stats.items():
            if isinstance(v, dict):
                base = v.get("base", 0)
                growth = v.get("perLevel", 0)
                if level > 1 and growth > 0:
                    val = base + growth * (level - 1) * (0.7025 + 0.0175 * (level - 1))
                else:
                    val = base
                calculated[k] = round(val, 2)

        profile["level"] = level
        profile["stats_at_level"] = calculated
        return profile

    def compare_champions(self, champ_names, stat_name = None):
        if not champ_names or len(champ_names) < 2:
            return {"error": "At least 2 champions are required for comparison."}

        data = {}
        for name in champ_names:
            champ = self.store.get_champion(name)
            if champ:
                profile = self.extract_champion_full_profile(champ)
                data[champ.get("name")] = {
                    "roles": profile.get("roles", []),
                    "attackType": profile.get("attackType"),
                    "adaptiveType": profile.get("adaptiveType"),
                    "attributeRatings": profile.get("attributeRatings", {}),
                    "base_stats": profile.get("base_stats", {}),
                    "playstyles": profile.get("playstyles", []),
                    "winConditions": profile.get("winConditions", []),
                    "hard_cc": profile.get("hard_cc", []),
                    "ability_effects": profile.get("ability_effects", []),
                }

        # Check direct counter relationship between the two champions
        matchup_info = None
        c1_name = champ_names[0]
        c2_name = champ_names[1]
        c1_counters = self.store.get_counter_info(c1_name)
        if c1_counters:
            for wa in c1_counters.get("weakAgainst", []):
                if wa.get("champion", "").lower() == c2_name.lower():
                    matchup_info = {
                        "advantaged": c2_name,
                        "disadvantaged": c1_name,
                        "win_rate": wa.get("winRate"),
                        "reason": wa.get("reason", ""),
                    }
                    break
            if not matchup_info:
                for sa in c1_counters.get("strongAgainst", []):
                    if sa.get("champion", "").lower() == c2_name.lower():
                        matchup_info = {
                            "advantaged": c1_name,
                            "disadvantaged": c2_name,
                            "win_rate": sa.get("winRate"),
                            "reason": sa.get("reason", ""),
                        }
                        break
        if not matchup_info:
            c2_counters = self.store.get_counter_info(c2_name)
            if c2_counters:
                for wa in c2_counters.get("weakAgainst", []):
                    if wa.get("champion", "").lower() == c1_name.lower():
                        matchup_info = {
                            "advantaged": c1_name,
                            "disadvantaged": c2_name,
                            "win_rate": wa.get("winRate"),
                            "reason": wa.get("reason", ""),
                        }
                        break
                if not matchup_info:
                    for sa in c2_counters.get("strongAgainst", []):
                        if sa.get("champion", "").lower() == c1_name.lower():
                            matchup_info = {
                                "advantaged": c2_name,
                                "disadvantaged": c1_name,
                                "win_rate": sa.get("winRate"),
                                "reason": sa.get("reason", ""),
                            }
                            break

        return {
            "comparison": data,
            "target_stat": stat_name,
            "matchup_info": matchup_info,
            "champions": [c1_name, c2_name],
        }

    def get_semantic_profile(self, name):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)
        profile["is_semantic_profile"] = True
        return profile
