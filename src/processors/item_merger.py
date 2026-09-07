"""
Item Data Merger.

Merges pure raw item data from DDragon and CDragon into a unified format:
- DDragon: costs, stats, build paths, maps
- CDragon: categories, cleaned descriptions

Output: src/processors/processed/items.json
"""

import json
import re
from pathlib import Path

from .utils import (
    CDRAGON_RAW_DIR,
    DDRAGON_RAW_DIR,
    PROCESSED_DIR,
    load_json,
    save_json,
    log,
    clean_html,
    normalize_item_stats,
)

# Common item shorthand aliases for search enrichment
ITEM_ALIASES = {
    # Mythic / Legendary common abbreviations
    "Infinity Edge": ["IE"],
    "Rabadon's Deathcap": ["Rabadon", "Deathcap"],
    "Zhonya's Hourglass": ["Zhonya", "Zhonyas"],
    "Guardian Angel": ["GA"],
    "Blade of the Ruined King": ["BOTRK", "BotRK"],
    "Thornmail": ["Thorn"],
    "Randuin's Omen": ["Randuin", "Randuins"],
    "Dead Man's Plate": ["DMP", "Deadmans"],
    "Spirit Visage": ["SV"],
    "Warmog's Armor": ["Warmog", "Warmogs"],
    "Banshee's Veil": ["Banshee", "Banshees"],
    "Morellonomicon": ["Morello"],
    "Hextech Rocketbelt": ["Rocketbelt", "Protobelt"],
    "Luden's Companion": ["Luden", "Ludens"],
    "Trinity Force": ["Triforce", "TF item"],
    "Black Cleaver": ["BC"],
    "Death's Dance": ["DD"],
    "Sterak's Gage": ["Sterak", "Steraks"],
    "Kraken Slayer": ["Kraken"],
    "Phantom Dancer": ["PD"],
    "Rapid Firecannon": ["RFC"],
    "Statikk Shiv": ["Shiv", "Statikk"],
    "Mercurial Scimitar": ["Mercurial", "QSS upgrade"],
    "Quicksilver Sash": ["QSS"],
    "Plated Steelcaps": ["Tabi", "Ninja Tabi"],
    "Mercury's Treads": ["Mercs", "Mercury"],
    "Berserker's Greaves": ["Berserker", "Berserkers"],
    "Sorcerer's Shoes": ["Sorcs"],
}


class ItemMerger:
    """Merge raw item data from DDragon and CDragon."""

    def __init__(self):
        self.ddragon_data = {}
        self.cdragon_data = {}

    def merge(self):
        """Load and merge item data from all sources."""
        print("[ItemMerger] Loading source data...")
        self.load_sources()

        all_ids = set(self.ddragon_data.keys())
        print(f"[ItemMerger] Merging {len(all_ids)} items...")

        merged = {}
        for item_id in sorted(all_ids, key = lambda x: int(x) if str(x).isdigit() else 0):
            dd = self.ddragon_data.get(item_id, {})
            cd = self.cdragon_data.get(item_id, {})

            gold = dd.get("gold", dd.get("cost", {}))
            if not gold.get("purchasable", True):
                continue

            maps = dd.get("maps", {})
            if maps and not maps.get("11", True):
                continue

            merged[item_id] = self.merge_item(item_id, dd, cd)

        self.save(merged)
        print(f"[ItemMerger] Saved {len(merged)} merged items")
        return merged

    def merge_item(self, item_id, dd, cd):
        """Merge a single item from DDragon + CDragon raw data."""
        name = dd.get("name", "") or cd.get("name", "")
        # Clean HTML from name (some items have <font> tags in name)
        name = clean_html(name)

        description = clean_html(dd.get("description", ""))
        plaintext = dd.get("plaintext", "") or clean_html(cd.get("description", ""))

        # Normalize stat keys from Riot internal format to human-readable
        raw_stats = dd.get("stats", {})
        stats = normalize_item_stats(raw_stats)

        gold = dd.get("gold", dd.get("cost", {}))
        total_cost = gold.get("total", cd.get("priceTotal", 0))
        base_cost = gold.get("base", cd.get("price", 0))
        sell_cost = gold.get("sell", 0)

        build_from = dd.get("from", dd.get("buildFrom", []))
        build_into = dd.get("into", dd.get("buildInto", []))

        categories = cd.get("categories", [])
        tags = dd.get("tags", [])

        image = dd.get("image", {}).get("full", "") if isinstance(dd.get("image"), dict) else dd.get("image", "")

        # Lookup aliases for this item
        aliases = ITEM_ALIASES.get(name, [])

        return {
            "id": int(item_id) if str(item_id).isdigit() else item_id,
            "name": name,
            "aliases": aliases,
            "description": description,
            "plaintext": plaintext,
            "cost": {
                "total": total_cost,
                "base": base_cost,
                "sell": sell_cost,
            },
            "stats": stats,
            "tags": list(set(tags + categories)),
            "buildFrom": build_from,
            "buildInto": build_into,
            "image": image,
            "sources": ["ddragon"] + (["cdragon"] if cd else []),
        }

    def load_sources(self):
        """Load raw data from disk."""
        self.ddragon_data = self.load_json(DDRAGON_RAW_DIR / "items.json")
        raw_cd = self.load_json(CDRAGON_RAW_DIR / "items.json")

        # Normalize CDragon items (list -> dict by ID)
        if isinstance(raw_cd, list):
            self.cdragon_data = {str(item.get("id")): item for item in raw_cd if item.get("id")}
        elif isinstance(raw_cd, dict):
            self.cdragon_data = raw_cd
        else:
            self.cdragon_data = {}

        print(f"  DDragon: {len(self.ddragon_data)} items")
        print(f"  CDragon: {len(self.cdragon_data)} items")

    def save(self, data):
        """Save merged data."""
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        filepath = PROCESSED_DIR / "items.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def load_json(path):
        """Load JSON file."""
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
