"""
Riot Data Dragon Collector (Pure Raw).

Fetches pure raw champion, item, and rune data from Riot's static API.
Saves raw API payloads directly to pipeline/collectors/raw/ddragon/ without transformation.
"""

from typing import Any, Dict, Optional
from tqdm import tqdm

from collectors.utils import (
    DDRAGON_RAW_DIR,
    build_ddragon_url,
    fetch_json,
    get_latest_ddragon_version,
    log,
    save_json,
)

TAG = "DDragon"


def collect_champions(version = None):
    """
    Fetch pure raw champion data from Data Dragon:
    1. Fetch champion list.
    2. Fetch detailed raw JSON for each champion.
    """
    version = version or get_latest_ddragon_version()
    list_url = build_ddragon_url("champions", version)
    champion_list = fetch_json(list_url, tag = TAG)

    if not champion_list:
        log(TAG, "ERROR: Could not fetch champion list!")
        return {}

    champions_basic = champion_list.get("data", {})
    log(TAG, f"Found {len(champions_basic)} champions")

    raw_champions = {}
    for champ_id in tqdm(champions_basic, desc = "Fetching raw champion details"):
        detail_url = build_ddragon_url("champion_detail", version, id = champ_id)
        detail = fetch_json(detail_url, tag = TAG)

        if detail and "data" in detail and champ_id in detail["data"]:
            raw_champions[champ_id] = detail["data"][champ_id]
        else:
            log(TAG, f"WARNING: Could not fetch details for {champ_id}")

    save_json(raw_champions, DDRAGON_RAW_DIR / "champions.json")
    log(TAG, f"Saved raw data for {len(raw_champions)} champions")
    return raw_champions


def collect_items(version = None):
    """Fetch pure raw item data from Data Dragon."""
    version = version or get_latest_ddragon_version()
    url = build_ddragon_url("items", version)
    raw = fetch_json(url, tag = TAG)

    if not raw:
        log(TAG, "ERROR: Could not fetch item data!")
        return {}

    raw_items = raw.get("data", {})
    save_json(raw_items, DDRAGON_RAW_DIR / "items.json")
    log(TAG, f"Saved raw data for {len(raw_items)} items")
    return raw_items


def collect_runes(version = None):
    """Fetch pure raw rune data from Data Dragon."""
    version = version or get_latest_ddragon_version()
    url = build_ddragon_url("runes", version)
    raw = fetch_json(url, tag = TAG)

    if not raw:
        log(TAG, "ERROR: Could not fetch rune data!")
        return {}

    save_json(raw, DDRAGON_RAW_DIR / "runes.json")
    log(TAG, f"Saved raw data for {len(raw)} rune trees")
    return raw


def collect_ddragon(version = None):
    """Collect all pure raw data from Data Dragon (champions, items, runes)."""
    version = version or get_latest_ddragon_version()
    log(TAG, f"Using version: {version}")

    result = {}

    log(TAG, "Collecting raw champion data...")
    result["champions"] = collect_champions(version)

    log(TAG, "Collecting raw item data...")
    result["items"] = collect_items(version)

    log(TAG, "Collecting raw rune data...")
    result["runes"] = collect_runes(version)

    return result