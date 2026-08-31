"""
Main Processor Runner.

Orchestrates and executes all data processing tasks in proper sequential order:
1. Champion Merger: Merges DDragon, CDragon, Meraki, and Wiki Lore into champions.json
2. Item Merger: Merges DDragon and CDragon items into items.json
3. Rune Merger: Structures DDragon runes into runes.json (byId and byTree)
4. Spell Analyzer: Analyzes champion abilities for CC types and effects (updates champions.json)
5. Enricher: Enriches champions with strategic playstyles, power curves, and win conditions (updates champions.json)

Usage:
    python src/processors/main.py             # Run all processors
    python src/processors/main.py --all       # Run all processors
    python src/processors/main.py --champions # Only merge champions
    python src/processors/main.py --items     # Only merge items
    python src/processors/main.py --runes     # Only merge runes
    python src/processors/main.py --spells    # Only analyze spells
    python src/processors/main.py --enrich    # Only enrich champions

    # Or as module:
    python -m src.processors                  # Run all processors
    python -m src.processors.main             # Run all processors
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict

# Ensure paths are in sys.path when executed directly or via module
CURRENT_DIR = Path(__file__).resolve().parent
SRC_DIR = CURRENT_DIR.parent
PROJECT_ROOT = SRC_DIR.parent

for p in [str(PROJECT_ROOT), str(SRC_DIR), str(CURRENT_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from .champion_merger import ChampionMerger
    from .item_merger import ItemMerger
    from .rune_merger import RuneMerger
    from .spell_analyzer import SpellAnalyzer
    from .enricher import Enricher
    from .utils import ensure_dirs, PROCESSED_DIR, log
except (ImportError, ValueError):
    try:
        from processors.champion_merger import ChampionMerger
        from processors.item_merger import ItemMerger
        from processors.rune_merger import RuneMerger
        from processors.spell_analyzer import SpellAnalyzer
        from processors.enricher import Enricher
        from processors.utils import ensure_dirs, PROCESSED_DIR, log
    except (ImportError, ValueError):
        try:
            from src.processors.champion_merger import ChampionMerger
            from src.processors.item_merger import ItemMerger
            from src.processors.rune_merger import RuneMerger
            from src.processors.spell_analyzer import SpellAnalyzer
            from src.processors.enricher import Enricher
            from src.processors.utils import ensure_dirs, PROCESSED_DIR, log
        except (ImportError, ValueError):
            from champion_merger import ChampionMerger
            from item_merger import ItemMerger
            from rune_merger import RuneMerger
            from spell_analyzer import SpellAnalyzer
            from enricher import Enricher
            from utils import ensure_dirs, PROCESSED_DIR, log


def run_all_processors():
    """
    Run all processors in the correct dependency sequence.
    Returns dictionary of results from each stage.
    """
    ensure_dirs()
    start_time = time.time()
    results = {}

    print("STARTING DATA PROCESSING PIPELINE")


    # 1. Merge Champions
    print("\n[1/5] Merging Champion Data (DDragon + CDragon + Meraki + Lore)")
    t0 = time.time()
    cm = ChampionMerger()
    results["champions"] = cm.merge()
    champ_count = len(results["champions"])
    print(f"-> Champions merged: {champ_count} in {time.time() - t0:.2f}s")

    # 2. Merge Items
    print("\n[2/5] Merging Item Data (DDragon + CDragon)")
    t0 = time.time()
    im = ItemMerger()
    results["items"] = im.merge()
    item_count = len(results["items"])
    print(f"-> Items merged: {item_count} in {time.time() - t0:.2f}s")

    # 3. Merge Runes
    print("\n[3/5] Merging Rune Data (DDragon)")
    t0 = time.time()
    rm = RuneMerger()
    results["runes"] = rm.merge()
    rune_count = len(results["runes"].get("byId", {}))
    print(f"-> Runes structured: {rune_count} in {time.time() - t0:.2f}s")

    # 4. Spell Analyzer (CC & Ability Effects)
    print("\n[4/5] Analyzing Champion Spells (CC Types & Ability Effects)")
    t0 = time.time()
    sa = SpellAnalyzer()
    results["analyzed_champions"] = sa.analyze()
    print(f"-> Spell analysis finished in {time.time() - t0:.2f}s")

    # 5. Enricher (Playstyles, Power Curves, Win Conditions)
    print("\n[5/5] Enriching Champions with Strategic Metadata")
    t0 = time.time()
    en = Enricher()
    results["enriched_champions"] = en.enrich()
    print(f"-> Enrichment finished in {time.time() - t0:.2f}s")

    total_time = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"PROCESSING COMPLETED IN {total_time:.2f}s")
    print(f"Output files saved to: {PROCESSED_DIR}")
    print(f"  - champions.json : {champ_count} champions (merged + analyzed + enriched)")
    print(f"  - items.json     : {item_count} items")
    print(f"  - runes.json     : {rune_count} runes")
    print("=" * 60)

    return results


def main():
    parser = argparse.ArgumentParser(description="LoL Knowledge Bot - Data Processors Runner")
    parser.add_argument("--all", action="store_true", help="Run all processors in sequence (default)")
    parser.add_argument("--champions", action="store_true", help="Run champion merger only")
    parser.add_argument("--items", action="store_true", help="Run item merger only")
    parser.add_argument("--runes", action="store_true", help="Run rune merger only")
    parser.add_argument("--spells", action="store_true", help="Run spell analyzer only")
    parser.add_argument("--enrich", action="store_true", help="Run champion enricher only")

    args = parser.parse_args()
    ensure_dirs()

    # Default to running all if no specific flag or --all is provided
    run_all = args.all or not (args.champions or args.items or args.runes or args.spells or args.enrich)

    if run_all:
        run_all_processors()
        return

    start_time = time.time()

    if args.champions:
        print("\n[Processor] Running Champion Merger...")
        cm = ChampionMerger()
        cm.merge()

    if args.items:
        print("\n[Processor] Running Item Merger...")
        im = ItemMerger()
        im.merge()

    if args.runes:
        print("\n[Processor] Running Rune Merger...")
        rm = RuneMerger()
        rm.merge()

    if args.spells:
        print("\n[Processor] Running Spell Analyzer...")
        sa = SpellAnalyzer()
        sa.analyze()

    if args.enrich:
        print("\n[Processor] Running Champion Enricher...")
        en = Enricher()
        en.enrich()

    elapsed = time.time() - start_time
    print(f"\nSelected processor(s) finished in {elapsed:.2f}s")


if __name__ == "__main__":
    main()
