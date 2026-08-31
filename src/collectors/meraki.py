"""
Meraki Analytics Collector (Pure Raw).

Fetches pure raw champion data from Meraki Analytics CDN.
Saves raw API payload directly to pipeline/collectors/raw/meraki/ without transformation.
"""

from typing import Any, Dict

from collectors.utils import (
    MERAKI_RAW_DIR,
    build_meraki_url,
    fetch_json,
    log,
    save_json,
)

TAG = "Meraki"


def collect_champions():
    """
    Fetch the complete pure raw champions.json from Meraki CDN (~13MB).
    Saves directly without transformation.
    """
    url = build_meraki_url("champions")
    raw = fetch_json(url, tag = TAG)

    if not raw:
        log(TAG, "ERROR: Could not fetch Meraki champion data!")
        return {}

    save_json(raw, MERAKI_RAW_DIR / "champions.json")
    log(TAG, f"Saved raw data for {len(raw)} champions")
    return raw


def collect_meraki():
    """Collect pure raw champion data from Meraki Analytics."""
    result = {}

    log(TAG, "Collecting raw champion data (this may take a moment)...")
    result["champions"] = collect_champions()

    return result
