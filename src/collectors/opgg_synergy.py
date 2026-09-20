"""
OP.GG Model Context Protocol (MCP) Synergy Collector.

Queries the official OP.GG MCP service (https://mcp-api.op.gg/mcp) to collect
empirical Solo Queue duo synergy data:
- ADC + Support pairings (e.g. Ashe + Braum, Lucian + Nami, Jinx + Thresh)
- Mid + Jungle pairings (e.g. Yasuo + Gragas/Lee Sin, Yone + Sejuani)
- Top + Jungle pairings (e.g. Renekton + Elise, Shen + Nocturne)

Saves raw MCP responses and parsed synergy rankings (win rate, games, score, rank).
"""

import argparse
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
    OPGG_SYNERGY_raw_dir,
    get_source_config,
    log,
    save_json,
)

tag = "OPGG_Synergy"

# Core champions by position for targeted synergy harvesting
default_adc_champions = [
    "Ashe", "Caitlyn", "Jinx", "KaiSa", "Ezreal", "Lucian", "Jhin",
    "Vayne", "Varus", "Samira", "Draven", "MissFortune", "Xayah",
    "KogMaw", "Tristana", "Sivir", "Twitch", "Aphelios", "Kalista",
    "Zeri", "Nilah", "Smolder"
]

default_mid_champions = [
    "Yasuo", "Yone", "Ahri", "Zed", "Orianna", "Syndra", "Sylas",
    "LeBlanc", "Akali", "Viktor", "Katarina", "Hwei", "Veigar", "Vex",
    "AurelionSol", "Galio", "Malzahar", "Azir", "Talon", "Kassadin"
]

default_top_champions = [
    "Aatrox", "Renekton", "Darius", "Garen", "Fiora", "Camille",
    "Jax", "Sett", "Mordekaiser", "Ornn", "Malphite", "Shen", "KSante"
]


def fetch_champion_synergy(champion_name, my_position, synergy_position, mcp_url = None):
    """
    Fetch synergy data for a single champion from OP.GG MCP server.
    """
    if not mcp_url:
        conf = get_source_config("opgg_synergy")
        mcp_url = conf.get("mcp_url")
        if not mcp_url:
            raise ValueError("Missing 'mcp_url' in collector.yaml under sources.opgg_synergy")

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "lol_get_champion_synergies",
            "arguments": {
                "champion": champion_name.upper(),
                "my_position": my_position.lower(),
                "synergy_position": synergy_position.lower(),
                "desired_output_fields": [
                    "champion",
                    "my_position",
                    "synergy_position",
                    "data.synergies[].{champion_name,synergy_champion_name,win,play,win_rate,score,score_rank}"
                ]
            }
        }
    }

    try:
        response = requests.post(mcp_url, json = payload, timeout = 12)
        response.raise_for_status()
        data = response.json()

        if "result" in data and "content" in data["result"]:
            raw_text = data["result"]["content"][0].get("text", "")
            pattern = r'Synergie\("([^"]+)","([^"]+)",(\d+),([\d\.]+),(\d+),(\d+),([\d\.]+)\)'
            matches = re.findall(pattern, raw_text)
            synergies = []
            for m in matches:
                synergies.append({
                    "champion": m[0],
                    "partner": m[1],
                    "rank": int(m[2]),
                    "score": float(m[3]),
                    "games": int(m[4]),
                    "wins": int(m[5]),
                    "win_rate": float(m[6])
                })

            return {
                "champion": champion_name,
                "my_position": my_position,
                "synergy_position": synergy_position,
                "raw_text": raw_text,
                "synergies": synergies
            }

    except Exception as e:
        log(tag, f"Failed fetching {champion_name} ({my_position}+{synergy_position}): {e}")

    return None


def collect_opgg_synergy(champions = None, include_mid = True, include_top = False, delay = 0.2, force = False):
    """
    Collect duo synergies from OP.GG MCP endpoint across selected champions and roles.
    
    Args:
        champions (list): List of champion names to collect. If None, uses default ADC list.
        include_mid (bool): Whether to also collect Mid + Jungle synergies.
        include_top (bool): Whether to also collect Top + Jungle synergies.
        delay (float): Politeness sleep between requests in seconds.
        force (bool): If True, re-fetches even if cached data exists.
        
    Returns:
        dict: Summary of collected synergy records and saved filepaths.
    """
    conf = get_source_config("opgg_synergy")
    mcp_url = conf.get("mcp_url")
    if not mcp_url:
        raise ValueError("Missing 'mcp_url' in collector.yaml under sources.opgg_synergy")


    all_file = OPGG_SYNERGY_raw_dir / "champion_synergies.json"
    bot_file = OPGG_SYNERGY_raw_dir / "synergies_bot_duo.json"
    mid_file = OPGG_SYNERGY_raw_dir / "synergies_mid_jungle.json"

    if all_file.exists() and not force:
        log(tag, f"Cached synergy file exists: {all_file}. Skipping download.")
        return {
            "status": "cached",
            "file": str(all_file)
        }

    log(tag, "Starting OP.GG MCP synergy collection...")
    start_time = time.time()

    adc_list = champions or default_adc_champions
    bot_results = {}
    mid_results = {}
    master_results = {}

    # 1. ADC + Support
    log(tag, f"Collecting Bot Duo (ADC + Support) for {len(adc_list)} champions...")
    for champ in adc_list:
        res = fetch_champion_synergy(champ, "adc", "support", mcp_url = mcp_url)
        if res and res["synergies"]:
            bot_results[champ] = res
            master_results[f"{champ}_adc_support"] = res
            log(tag, f"  {champ} (ADC+SP): Top partner {res['synergies'][0]['partner']} ({res['synergies'][0]['win_rate']*100:.1f}%)")
        time.sleep(delay)

    # 2. Mid + Jungle
    if include_mid:
        log(tag, f"Collecting Mid + Jungle for {len(default_mid_champions)} champions...")
        for champ in default_mid_champions:
            res = fetch_champion_synergy(champ, "mid", "jungle", mcp_url = mcp_url)
            if res and res["synergies"]:
                mid_results[champ] = res
                master_results[f"{champ}_mid_jungle"] = res
                log(tag, f"  {champ} (Mid+Jng): Top partner {res['synergies'][0]['partner']} ({res['synergies'][0]['win_rate']*100:.1f}%)")
            time.sleep(delay)

    # 3. Top + Jungle (Optional)
    if include_top:
        log(tag, f"Collecting Top + Jungle for {len(default_top_champions)} champions...")
        for champ in default_top_champions:
            res = fetch_champion_synergy(champ, "top", "jungle", mcp_url = mcp_url)
            if res and res["synergies"]:
                master_results[f"{champ}_top_jungle"] = res
            time.sleep(delay)

    # Save outputs
    save_json(master_results, all_file)
    save_json(bot_results, bot_file)
    if mid_results:
        save_json(mid_results, mid_file)

    elapsed = time.time() - start_time
    log(tag, f"Completed synergy collection in {elapsed:.2f}s! Total pairs saved: {len(master_results)}")

    return {
        "status": "downloaded",
        "total_records": len(master_results),
        "bot_duos": len(bot_results),
        "mid_duos": len(mid_results),
        "all_file": str(all_file),
        "bot_file": str(bot_file),
        "elapsed_seconds": round(elapsed, 2)
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = "Collect OP.GG MCP Synergy Data")
    parser.add_argument("--champions", nargs = "+", help = "Specific champions to query")
    parser.add_argument("--all-roles", action = "store_true", help = "Include Mid and Top synergies")
    parser.add_argument("--force", action = "store_true", help = "Force re-download")
    args = parser.parse_args()

    res = collect_opgg_synergy(
        champions = args.champions,
        include_mid = True,
        include_top = args.all_roles,
        force = args.force
    )
    print(res)
