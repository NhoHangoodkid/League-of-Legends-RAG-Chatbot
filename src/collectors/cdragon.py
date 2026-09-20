"""
Community Dragon Collector (Pure Raw).

Fetches pure raw champion and item data from CommunityDragon.
Saves raw API payloads directly to pipeline/collectors/raw/cdragon/ without transformation.
"""

from tqdm import tqdm

from collectors.utils import (
    CDRAGON_raw_dir,
    build_cdragon_url,
    fetch_json,
    log,
    save_json,
)

tag = "CDragon"


def collect_champions():
    """
    Fetch pure raw champion data from CommunityDragon:
    1. Fetch champion summary list.
    2. Fetch raw details for each champion (by ID).
    """
    summary_url = build_cdragon_url("champion_summary")
    summary_data = fetch_json(summary_url, tag = tag)

    if not summary_data:
        log(tag, "ERROR: Could not fetch champion summary!")
        return {}

    # Filter out -1 (placeholder entry)
    champion_entries = [c for c in summary_data if c.get("id", -1) > 0]
    log(tag, f"Found {len(champion_entries)} champions")

    raw_champions = {}
    for entry in tqdm(champion_entries, desc = "Fetching raw CDragon champion details"):
        champ_id = entry.get("id")
        detail_url = build_cdragon_url("champion_detail", id = champ_id)
        detail = fetch_json(detail_url, tag = tag)

        if detail:
            name = entry.get("name", f"Champion_{champ_id}")
            alias = entry.get("alias", name)
            raw_champions[alias] = {
                "summary": entry,
                "detail": detail,
            }
        else:
            log(tag, f"WARNING: Could not fetch CDragon details for ID {champ_id}")

    save_json(raw_champions, CDRAGON_raw_dir / "champions.json")
    log(tag, f"Saved raw data for {len(raw_champions)} champions")
    return raw_champions


def collect_items():
    """Fetch pure raw item data from CommunityDragon."""
    url = build_cdragon_url("items")
    raw = fetch_json(url, tag = tag)

    if not raw:
        log(tag, "ERROR: Could not fetch item data!")
        return []

    save_json(raw, CDRAGON_raw_dir / "items.json")
    log(tag, f"Saved raw data for {len(raw)} items")
    return raw


def collect_cdragon():
    """Collect all pure raw data from Community Dragon."""
    result = {}

    log(tag, "Collecting raw champion data...")
    result["champions"] = collect_champions()

    log(tag, "Collecting raw item data...")
    result["items"] = collect_items()

    return result
