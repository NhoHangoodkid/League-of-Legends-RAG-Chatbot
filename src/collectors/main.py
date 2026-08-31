"""
Main Collector Runner.

Orchestrates and executes all data collection tasks:
1. Data Dragon (DDragon): Champions, Items, Runes
2. Community Dragon (CDragon): Detailed champion spells, tactical info, items
3. Meraki Analytics: Precise base/scaling stats & growth formulas
4. Wiki Lore: Lore consolidation from DDragon + CDragon

Usage:
    python -m pipeline.collectors.main             # Run all collectors
    python -m pipeline.collectors.main --all       # Run all collectors
    python -m pipeline.collectors.main --ddragon   # Only DDragon
    python -m pipeline.collectors.main --cdragon   # Only CDragon
    python -m pipeline.collectors.main --meraki    # Only Meraki
    python -m pipeline.collectors.main --lore      # Only Lore consolidation
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Add project root to sys.path if run directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from collectors.cdragon import collect_cdragon
from collectors.ddragon import collect_ddragon
from collectors.meraki import collect_meraki
from collectors.wiki_lore import collect_wiki_lore
from collectors.utils import (
    CDRAGON_RAW_DIR,
    DDRAGON_RAW_DIR,
    MERAKI_RAW_DIR,
    WIKI_RAW_DIR,
)


def ensure_dirs():
    """Ensure raw data directories exist."""
    for d in [DDRAGON_RAW_DIR, CDRAGON_RAW_DIR, MERAKI_RAW_DIR, WIKI_RAW_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def run_all_collectors(ddragon_version):
    """
    Run all collectors sequentially and return the summary of collected data.
    """
    ensure_dirs()
    start_time = time.time()
    results = {}

    print("STARTING DATA COLLECTION PIPELINE")

    # 1. Data Dragon
    print("\n[1/4] Collecting Riot Data Dragon")
    t0 = time.time()
    results["ddragon"] = collect_ddragon(version=ddragon_version)
    print(f" DDragon finished in {time.time() - t0:.1f}s")

    # 2. Community Dragon
    print("\n[2/4] Collecting Community Dragon")
    t0 = time.time()
    results["cdragon"] = collect_cdragon()
    print(f" CDragon finished in {time.time() - t0:.1f}s")

    # 3. Meraki Analytics
    print("\n[3/4] Collecting Meraki Analytics")
    t0 = time.time()
    results["meraki"] = collect_meraki()
    print(f" Meraki finished in {time.time() - t0:.1f}s")

    # 4. Wiki Lore (Consolidation)
    print("\n[4/4] Collecting Wiki Lore")
    t0 = time.time()
    results["lore"] = collect_wiki_lore()
    print(f" Wiki Lore finished in {time.time() - t0:.1f}s")

    total_time = time.time() - start_time
    print(f"\nDATA COLLECTION COMPLETED IN {total_time:.1f}s")

    return results


def main():
    parser = argparse.ArgumentParser(description = "LoL Knowledge Bot - Data Collectors Runner")
    parser.add_argument("--all", action = "store_true", help = "Run all collectors (default)")
    parser.add_argument("--ddragon", action = "store_true", help = "Run Data Dragon collector")
    parser.add_argument("--cdragon", action = "store_true", help = "Run Community Dragon collector")
    parser.add_argument("--meraki", action = "store_true", help = "Run Meraki Analytics collector")
    parser.add_argument("--lore", action = "store_true", help = "Run Wiki Lore collector")
    parser.add_argument("--version", type = str, default = None, help = "Specific DDragon version to fetch")

    args = parser.parse_args()
    ensure_dirs()

    # If no specific flag is given or --all is passed, run everything
    run_all = args.all or not (args.ddragon or args.cdragon or args.meraki or args.lore)

    if run_all:
        run_all_collectors(ddragon_version=args.version)
        return

    start_time = time.time()

    if args.ddragon:
        print("\nCollecting Riot Data Dragon")
        collect_ddragon(version=args.version)

    if args.cdragon:
        print("\nCollecting Community Dragon")
        collect_cdragon()

    if args.meraki:
        print("\nCollecting Meraki Analytics")
        collect_meraki()

    if args.lore:
        print("\nCollecting Wiki Lore")
        collect_wiki_lore()

    elapsed = time.time() - start_time
    print(f"\nSelected collector(s) finished in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
