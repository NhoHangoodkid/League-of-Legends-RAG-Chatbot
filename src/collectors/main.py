"""
Main Collector Runner.

Orchestrates and executes all data collection tasks:
1. Data Dragon (DDragon): Champions, Items, Runes
2. Community Dragon (CDragon): Detailed champion spells, tactical info, items
3. Meraki Analytics: Precise base/scaling stats and growth formulas
4. Universe Lore: In-depth champion lore and universe relationships

Usage:
    python src/collectors/main.py             # Run all collectors
    python src/collectors/main.py --all       # Run all collectors
    python src/collectors/main.py --ddragon   # Only DDragon
    python src/collectors/main.py --cdragon   # Only CDragon
    python src/collectors/main.py --meraki    # Only Meraki
    python src/collectors/main.py --lore      # Only Lore
"""

import argparse
import sys
import time
from pathlib import Path

# Add project root to sys.path if run directly
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from collectors.cdragon import collect_cdragon
from collectors.ddragon import collect_ddragon
from collectors.lore import collect_lore
from collectors.meraki import collect_meraki
from collectors.oracles_elixir import collect_oracles_elixir
from collectors.opgg_synergy import collect_opgg_synergy
from collectors.blitz import collect_blitz
from collectors.utils import (
    BLITZ_raw_dir,
    CDRAGON_raw_dir,
    DDRAGON_raw_dir,
    LORE_raw_dir,
    MERAKI_raw_dir,
    OPGG_SYNERGY_raw_dir,
    ORACLES_ELIXIR_raw_dir,
)


def ensure_dirs():
    """Ensure raw data directories exist."""
    for d in [
        DDRAGON_raw_dir,
        CDRAGON_raw_dir,
        MERAKI_raw_dir,
        LORE_raw_dir,
        ORACLES_ELIXIR_raw_dir,
        OPGG_SYNERGY_raw_dir,
        BLITZ_raw_dir,
    ]:
        d.mkdir(parents = True, exist_ok = True)


def run_all_collectors(ddragon_version = None):
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
    results["ddragon"] = collect_ddragon(version = ddragon_version)
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

    # 4. Riot Universe Lore
    print("\n[4/4] Collecting Lore")
    t0 = time.time()
    results["lore"] = collect_lore()
    print(f"Lore finished in {time.time() - t0:.1f}s")

    # 5. Oracle's Elixir (Esports match data)
    print("\n[5/7] Collecting Oracle's Elixir Pro Match Data")
    t0 = time.time()
    results["oracles_elixir"] = collect_oracles_elixir()
    print(f"Oracle's Elixir finished in {time.time() - t0:.1f}s")

    # 6. Blitz.gg (Tactical tips and role matchups)
    print("\n[6/7] Collecting Blitz.gg Tactical Insights")
    t0 = time.time()
    results["blitz"] = collect_blitz()
    print(f"Blitz finished in {time.time() - t0:.1f}s")

    # 7. OP.GG MCP (SoloQ Duo Synergies)
    print("\n[7/7] Collecting OP.GG MCP Synergy Data")
    t0 = time.time()
    results["opgg_synergy"] = collect_opgg_synergy()
    print(f"OP.GG Synergy finished in {time.time() - t0:.1f}s")

    total_time = time.time() - start_time
    print(f"\nDATA COLLECTION COMPLETED IN {total_time:.1f}s")

    return results


def main():
    parser = argparse.ArgumentParser(description = "LoL Knowledge Bot - Data Collectors Runner")
    parser.add_argument("--all", action = "store_true", help = "Run all collectors (game data + matches + synergies)")
    parser.add_argument("--ddragon", action = "store_true", help = "Run Data Dragon collector")
    parser.add_argument("--cdragon", action = "store_true", help = "Run Community Dragon collector")
    parser.add_argument("--meraki", action = "store_true", help = "Run Meraki Analytics collector")
    parser.add_argument("--lore", action = "store_true", help = "Run Universe Lore collector")
    parser.add_argument("--oracles-elixir", action = "store_true", help = "Run Oracle's Elixir match data collector")
    parser.add_argument("--opgg", action = "store_true", help = "Run OP.GG MCP synergy collector")
    parser.add_argument("--blitz", action = "store_true", help = "Run Blitz.gg tactical tips collector")
    parser.add_argument("--matches-all", action = "store_true", help = "Run the 3 match/synergy/tactical collectors")
    parser.add_argument("--year", type = str, default = None, help = "Specific match dataset year (e.g. 2026, 2025, 2024)")
    parser.add_argument("--version", type = str, default = None, help = "Specific DDragon version to fetch")
    parser.add_argument("--force", action = "store_true", help = "Force re-download and overwrite existing cached files")

    args = parser.parse_args()
    ensure_dirs()

    if args.matches_all:
        print("\nRUNNING ALL MATCH and SYNERGY COLLECTORS")
        t0 = time.time()
        collect_oracles_elixir(year = args.year, force = args.force)
        collect_blitz(force = args.force)
        collect_opgg_synergy(force = args.force)
        print(f"\nMatch and synergy collection finished in {time.time() - t0:.1f}s")
        return


    # If no specific flag is given or --all is passed, run everything
    specific_flags = (
        args.ddragon or args.cdragon or args.meraki or args.lore or
        args.oracles_elixir or args.opgg or args.blitz or args.matches_all
    )
    run_all = args.all or not specific_flags

    if run_all:
        run_all_collectors(ddragon_version = args.version)
        return

    start_time = time.time()

    if args.ddragon:
        print("\nCollecting Riot Data Dragon")
        collect_ddragon(version = args.version)

    if args.cdragon:
        print("\nCollecting Community Dragon")
        collect_cdragon()

    if args.meraki:
        print("\nCollecting Meraki Analytics")
        collect_meraki()

    if args.lore:
        print("\nCollecting Lore")
        collect_lore()

    if args.oracles_elixir:
        print("\nCollecting Oracle's Elixir Match Data")
        collect_oracles_elixir(year = args.year, force = args.force)

    if args.blitz:
        print("\nCollecting Blitz.gg Tactical Data")
        collect_blitz(force = args.force)

    if args.opgg:
        print("\nCollecting OP.GG MCP Synergy Data")
        collect_opgg_synergy(force = args.force)


    elapsed = time.time() - start_time
    print(f"\nSelected collector(s) finished in {elapsed:.1f}s")


if __name__ == "__main__":
    main()

