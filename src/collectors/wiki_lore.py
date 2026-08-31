"""
Wiki/Lore Collector (Pure Raw).

Aggregates lore data from DDragon and CDragon raw champion files.
DDragon provides 'lore' (full) and 'blurb' (short) fields.
CDragon provides 'shortBio' field.
"""

from typing import Any, Dict

from collectors.utils import (
    CDRAGON_RAW_DIR,
    DDRAGON_RAW_DIR,
    WIKI_RAW_DIR,
    load_json,
    log,
    save_json,
)

TAG = "WikiLore"


def collect_wiki_lore():
    """
    Consolidate lore from raw DDragon and CDragon data.
    Must be run AFTER DDragon and CDragon collectors.
    """
    log(TAG, "Consolidating lore data from raw DDragon + CDragon...")

    ddragon_data = load_json(DDRAGON_RAW_DIR / "champions.json") or {}
    cdragon_data = load_json(CDRAGON_RAW_DIR / "champions.json") or {}

    if not ddragon_data and not cdragon_data:
        log(TAG, "ERROR: No source data found! Run DDragon and CDragon collectors first.")
        return {}

    lore = {}
    all_ids = set(ddragon_data.keys()) | set(cdragon_data.keys())

    for champ_id in sorted(all_ids):
        dd = ddragon_data.get(champ_id, {})
        cd_entry = cdragon_data.get(champ_id, {})
        cd_summary = cd_entry.get("summary", {}) if isinstance(cd_entry, dict) and "summary" in cd_entry else cd_entry
        cd_detail = cd_entry.get("detail", {}) if isinstance(cd_entry, dict) and "detail" in cd_entry else cd_entry

        full_lore = dd.get("lore", "") or cd_detail.get("shortBio", "")
        short_lore = dd.get("blurb", "") or cd_detail.get("shortBio", "")
        name = dd.get("name", "") or cd_summary.get("name", "")
        title = dd.get("title", "") or cd_detail.get("title", "")

        lore[champ_id] = {
            "id": champ_id,
            "name": name,
            "title": title,
            "lore": full_lore,
            "shortLore": short_lore,
            "source": "ddragon+cdragon",
        }

    save_json(lore, WIKI_RAW_DIR / "lore.json")
    log(TAG, f"Saved lore for {len(lore)} champions")
    return lore
