"""
Blitz.gg Tactical Insights and Matchups Collector.

Extracts live expert tactical insights and matchup meta from Blitz.gg:
- Comprehensive tactical tips for all 172 champions: insights, strengths, weaknesses.
- Role matchups and tier statistics: strong_against, weak_against, win_rate, pick_rate.
- Live competitive build patterns: core items, situational items, skill orders, keystone runes.
"""

import json
import re
import sys
import time
from pathlib import Path
import requests

# Ensure src is in sys.path if run directly
src_root = Path(__file__).resolve().parent.parent
if str(src_root) not in sys.path:
    sys.path.insert(0, str(src_root))

from collectors.utils import (
    BLITZ_raw_dir,
    get_source_config,
    log,
    save_json,
)

tag = "Blitz"


def collect_blitz(seed_champion = "ashe", force = False):
    """
    Collect tactical tips, role matchups, and competitive meta from Blitz.gg.
    
    Args:
        seed_champion (str): Seed champion slug to fetch initial state bundle.
        force (bool): If True, re-fetches even if cached files exist.
        
    Returns:
        dict: Summary of collected items and saved filepaths.
    """
    conf = get_source_config("blitz")
    base_url = conf.get("base_url")
    if not base_url:
        raise ValueError("Missing 'base_url' in collector.yaml under sources.blitz")
    seed = conf.get("seed_champion", seed_champion)
    url = f"{base_url}/{seed}/build"


    tips_file = BLITZ_raw_dir / "champion_tactical_tips.json"
    matchups_file = BLITZ_raw_dir / "champion_role_matchups.json"
    builds_file = BLITZ_raw_dir / "champion_build_meta.json"

    if tips_file.exists() and matchups_file.exists() and not force:
        log(tag, f"Cached files exist in {BLITZ_raw_dir}. Skipping download.")
        return {
            "status": "cached",
            "tips_file": str(tips_file),
            "matchups_file": str(matchups_file),
            "builds_file": str(builds_file)
        }

    log(tag, f"Fetching live tactical and meta state from Blitz ({url})...")
    start_time = time.time()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        response = requests.get(url, headers = headers, timeout = 30)
        response.raise_for_status()

        html_text = response.text
        scripts = re.findall(r'<script[^>]*>(.*?)</script>', html_text, re.DOTALL)

        tactical_tips = []
        role_matchups = []
        build_meta = []

        for s in scripts:
            s_clean = s.strip()
            if not s_clean.startswith('{"status":200'):
                continue
            try:
                wrapper = json.loads(s_clean)
                body_str = wrapper.get("body", "")
                if not body_str:
                    continue
                body_json = json.loads(body_str)

                # 1. Tactical Tips list: [{"championId": 1, "tips": {...}}, ...]
                if isinstance(body_json, list) and len(body_json) > 100:
                    if "championId" in body_json[0] and "tips" in body_json[0]:
                        tactical_tips = body_json

                # 2. Matchup / Role stats: {"data": [{"strong_against": [...], "weak_against": [...]}]}
                elif isinstance(body_json, dict) and "data" in body_json:
                    data_list = body_json.get("data", [])
                    if data_list and isinstance(data_list, list) and len(data_list) > 0:
                        first_item = data_list[0]
                        if isinstance(first_item, dict):
                            if "strong_against" in first_item or "champion_role_tier" in first_item:
                                role_matchups = data_list
                            elif "coreItems" in first_item or "itemsAfterCore" in first_item:
                                build_meta = data_list

            except Exception:
                continue

        # Save results
        results = {
            "status": "downloaded",
            "elapsed_seconds": round(time.time() - start_time, 2)
        }

        if tactical_tips:
            save_json(tactical_tips, tips_file)
            log(tag, f"Saved tactical tips for {len(tactical_tips)} champions -> {tips_file.name}")
            results["tactical_champions_count"] = len(tactical_tips)
            results["tips_file"] = str(tips_file)

        if role_matchups:
            save_json(role_matchups, matchups_file)
            log(tag, f"Saved role matchups/tier stats ({len(role_matchups)} records) -> {matchups_file.name}")
            results["role_matchups_count"] = len(role_matchups)
            results["matchups_file"] = str(matchups_file)

        if build_meta:
            save_json(build_meta, builds_file)
            log(tag, f"Saved build meta ({len(build_meta)} records) -> {builds_file.name}")
            results["build_meta_count"] = len(build_meta)
            results["builds_file"] = str(builds_file)

        return results

    except Exception as e:
        log(tag, f"Error collecting Blitz data: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description = "Collect Blitz Tactical and Meta Data")
    parser.add_argument("--force", action = "store_true", help = "Force re-download")
    args = parser.parse_args()

    res = collect_blitz(force = args.force)
    print(res)
