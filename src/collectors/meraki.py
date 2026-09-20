"""
Meraki Analytics Collector (Pure Raw).

Fetches pure raw champion data from Meraki Analytics CDN.
Saves raw API payload directly to pipeline/collectors/raw/meraki/ without transformation.
"""

from collectors.utils import (
    MERAKI_raw_dir,
    build_meraki_url,
    fetch_json,
    log,
    save_json,
)

tag = "Meraki"


def collect_champions():
    """
    Fetch the complete pure raw champions.json from Meraki CDN (~13MB).
    Saves directly without transformation.
    """
    url = build_meraki_url("champions")
    raw = fetch_json(url, tag = tag)

    if not raw:
        log(tag, "ERROR: Could not fetch Meraki champion data!")
        return {}

    save_json(raw, MERAKI_raw_dir / "champions.json")
    log(tag, f"Saved raw data for {len(raw)} champions")
    return raw


def collect_meraki():
    """Collect pure raw champion data from Meraki Analytics."""
    result = {}

    log(tag, "Collecting raw champion data (this may take a moment)...")
    result["champions"] = collect_champions()

    return result
