"""
Item, build, and rune retrieval mixin.
"""


class ItemRetrieverMixin:
    """Provides methods for champion item builds, item details, recipes, and runes."""

    def get_build(self, name):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)
        data = self.store.get_build_info(name)
        if not data:
            profile["notice"] = "No specific build data found; utilizing archetype and role recommendations."
            return profile

        core = data.get("coreItems") or data.get("core_items") or []
        full = data.get("fullBuild") or data.get("full_build") or []
        start = data.get("startingItems") or data.get("starting_items") or []
        spells = data.get("summonerSpells") or data.get("summoner_spells") or []
        p_runes = data.get("primaryRunes") or data.get("primary_runes") or []
        s_runes = data.get("secondaryRunes") or data.get("secondary_runes") or []

        profile.update({
            "starting_items": start,
            "core_items": core or full[:3],
            "full_build": full,
            "summoner_spells": spells,
            "runes": {
                "keystone": data.get("keystone"),
                "primary": p_runes,
                "secondary": s_runes,
            },
        })
        return profile

    def get_item_info(self, item_name):
        item = self.store.get_item(item_name)
        if not item:
            return {"error": f"Item '{item_name}' not found."}

        build_from_resolved = []
        for bf in item.get("buildFrom", []):
            resolved = self.store.get_item(bf)
            if resolved and resolved.get("name"):
                build_from_resolved.append(resolved["name"])
            else:
                build_from_resolved.append(str(bf))

        build_into_resolved = []
        for bi in item.get("buildInto", []):
            resolved = self.store.get_item(bi)
            if resolved and resolved.get("name"):
                build_into_resolved.append(resolved["name"])
            else:
                build_into_resolved.append(str(bi))

        return {
            "name": item.get("name"),
            "cost": item.get("cost", {}),
            "stats": item.get("stats", {}),
            "description": item.get("description", "") or item.get("plaintext", ""),
            "aliases": item.get("aliases", []),
            "colloquial": item.get("colloquial", []),
            "requiredChampion": item.get("requiredChampion", ""),
            "requiredAlly": item.get("requiredAlly", ""),
            "active": item.get("active", False),
            "buildFrom": build_from_resolved,
            "buildInto": build_into_resolved,
        }

    def get_rune_info(self, rune_name):
        rune = self.store.get_rune(rune_name)
        if not rune:
            return {"error": f"Rune '{rune_name}' not found."}

        return {
            "name": rune.get("name"),
            "tree": rune.get("tree"),
            "description": rune.get("description", ""),
            "longDescription": rune.get("longDescription", ""),
        }
