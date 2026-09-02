"""
Rune Data Merger.

Processes and structures pure raw rune data from DDragon (runesReforged.json).
Cleans HTML from descriptions and organizes by ID and tree.

Output: src/processors/processed/runes.json
"""

import json
from pathlib import Path
from typing import Any, Dict, List

try:
    from .utils import DDRAGON_RAW_DIR, PROCESSED_DIR, load_json, save_json, log, clean_html
except ImportError:
    try:
        from processors.utils import DDRAGON_RAW_DIR, PROCESSED_DIR, load_json, save_json, log, clean_html
    except ImportError:
        from utils import DDRAGON_RAW_DIR, PROCESSED_DIR, load_json, save_json, log, clean_html



class RuneMerger:
    """Process and clean pure raw rune data from DDragon."""

    def merge(self):
        """Load and process raw rune data."""
        print("[RuneMerger] Loading raw rune data...")

        raw_runes = self.load_json(DDRAGON_RAW_DIR / "runes.json")
        if not raw_runes:
            print("[RuneMerger] ERROR: No rune data found!")
            return {}

        print(f"[RuneMerger] Processing raw rune data...")

        runes_by_tree = {}
        runes_flat = {}

        # Handle raw DDragon format (list of trees)
        if isinstance(raw_runes, list):
            for tree in raw_runes:
                tree_name = tree.get("name", "")
                tree_id = tree.get("id", 0)
                runes_by_tree[tree_name] = []

                for slot_index, slot in enumerate(tree.get("slots", [])):
                    for rune in slot.get("runes", []):
                        rune_id = str(rune.get("id", ""))
                        rune_obj = {
                            "id": rune.get("id", 0),
                            "name": rune.get("name", ""),
                            "tree": tree_name,
                            "treeId": tree_id,
                            "slot": slot_index,
                            # Clean HTML from descriptions
                            "description": clean_html(rune.get("shortDesc", "")),
                            "longDescription": clean_html(rune.get("longDesc", "")),
                            "icon": rune.get("icon", ""),
                            "source": "ddragon",
                        }
                        runes_flat[rune_id] = rune_obj
                        runes_by_tree[tree_name].append(rune_obj)
        elif isinstance(raw_runes, dict):
            # Already flattened dict
            runes_flat = raw_runes
            for rune_id, rune in raw_runes.items():
                # Clean HTML from any existing descriptions
                if "description" in rune:
                    rune["description"] = clean_html(rune["description"])
                if "longDescription" in rune:
                    rune["longDescription"] = clean_html(rune["longDescription"])
                tree = rune.get("tree", "Unknown")
                if tree not in runes_by_tree:
                    runes_by_tree[tree] = []
                runes_by_tree[tree].append(rune)

        result = {
            "byId": runes_flat,
            "byTree": runes_by_tree,
        }

        self.save(result)
        print(f"[RuneMerger] Saved {len(runes_flat)} runes in {len(runes_by_tree)} trees")
        return result

    def save(self, data):
        """Save processed data."""
        return save_json(data, PROCESSED_DIR / "runes.json")

    @staticmethod
    def load_json(path: Path):
        """Load JSON file."""
        return load_json(path)


