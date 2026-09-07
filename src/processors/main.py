"""
Main Processor Runner.

Orchestrates and executes all data processing tasks in proper sequential order:
1. Champion Merger: Merges DDragon, CDragon, Meraki, and Wiki Lore into champions.json
2. Item Merger: Merges DDragon and CDragon items into items.json
3. Rune Merger: Structures DDragon runes into runes.json (byId and byTree)
4. Spell Analyzer: Analyzes champion abilities for CC types and effects (updates champions.json)
5. Enricher: Enriches champions with strategic playstyles, power curves, and win conditions (updates champions.json)
6. Relationship Generator: Generates counters, synergies, builds, and entity graph
7. Archetype Processor: Analyzes 173 champions into tactical compositions & computes counter matrices
8. MongoDB Synchronization: Persists all champions, items, runes, counters, synergies, builds, relationships, and team_compositions to MongoDB

Usage:
    python src/processors/main.py                 # Run all processors & sync to MongoDB

    # Or as module:
    python -m src.processors                      # Run all processors
    python -m src.processors.main                 # Run all processors
"""

import sys
import time
from pathlib import Path

# Ensure paths are in sys.path when executed directly or via module
CURRENT_DIR = Path(__file__).resolve().parent
SRC_DIR = CURRENT_DIR.parent
PROJECT_ROOT = SRC_DIR.parent

for p in [str(PROJECT_ROOT), str(SRC_DIR), str(CURRENT_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

if not __package__:
    __package__ = "processors"

from .champion_merger import ChampionMerger
from .item_merger import ItemMerger
from .rune_merger import RuneMerger
from .spell_analyzer import SpellAnalyzer
from .enricher import Enricher
from .relationship import RelationshipGenerator
from .archetype_processor import ArchetypeProcessor
from .utils import ensure_dirs, PROCESSED_DIR, log
from .mongo_sync import sync_knowledge_base_to_mongo, MongoSyncManager


def run_all_processors(sync_mongo = True):
    """
    Run all processors in the correct dependency sequence.
    Returns dictionary of results from each stage.
    """
    ensure_dirs()
    start_time = time.time()
    results = {}

    print("STARTING DATA PROCESSING PIPELINE")

    # 1. Merge Champions
    print("\n[1/8] Merging Champion Data (DDragon + CDragon + Meraki + Lore)")
    t0 = time.time()
    cm = ChampionMerger()
    results["champions"] = cm.merge()
    champ_count = len(results["champions"])
    print(f"-> Champions merged: {champ_count} in {time.time() - t0:.2f}s")

    # 2. Merge Items
    print("\n[2/8] Merging Item Data (DDragon + CDragon)")
    t0 = time.time()
    im = ItemMerger()
    results["items"] = im.merge()
    item_count = len(results["items"])
    print(f"-> Items merged: {item_count} in {time.time() - t0:.2f}s")

    # 3. Merge Runes
    print("\n[3/8] Merging Rune Data (DDragon)")
    t0 = time.time()
    rm = RuneMerger()
    results["runes"] = rm.merge()
    rune_count = len(results["runes"].get("byId", {}))
    print(f"-> Runes structured: {rune_count} in {time.time() - t0:.2f}s")

    # 4. Spell Analyzer (CC & Ability Effects)
    print("\n[4/8] Analyzing Champion Spells (CC Types & Ability Effects)")
    t0 = time.time()
    sa = SpellAnalyzer()
    results["analyzed_champions"] = sa.analyze()
    print(f"-> Spell analysis finished in {time.time() - t0:.2f}s")

    # 5. Enricher (Playstyles, Power Curves, Win Conditions)
    print("\n[5/8] Enriching Champions with Strategic Metadata")
    t0 = time.time()
    en = Enricher()
    results["enriched_champions"] = en.enrich()
    results["champions"] = results["enriched_champions"]
    print(f"-> Enrichment finished in {time.time() - t0:.2f}s")

    # 6. Relationship Generator (Counters, Synergies, Builds, All Entity Graph Edges)
    print("\n[6/8] Generating Knowledge Base Relationships & Entity Graph")
    t0 = time.time()
    rg = RelationshipGenerator()
    kb_res = rg.generate(
        champions = results["champions"],
        items = results["items"],
        runes = results["runes"],
        save_to_disk = False,
    )
    results["champions"] = kb_res["champions"]
    results["counters"] = kb_res["counters"]
    results["synergies"] = kb_res["synergies"]
    results["builds"] = kb_res["builds"]
    results["relationships"] = kb_res["relationships"]
    results["kb"] = kb_res["stats"]
    print(f"-> Relationships generated: {kb_res['stats']['relationships']} graph edges in {time.time() - t0:.2f}s")

    # 7. Archetype Processor (Classifying 173 champions & Calculating Counter Matrices)
    print("\n[7/8] Analyzing Champion Archetypes & Calculating Counter Matrices")
    t0 = time.time()
    ap = ArchetypeProcessor()
    archetype_res = ap.process(
        champions = results["champions"],
        counters = results["counters"],
        items = results["items"],
    )
    results["team_compositions"] = archetype_res
    print(f"-> Archetype analysis finished: {len(archetype_res)} compositions in {time.time() - t0:.2f}s")

    # 8. MongoDB Synchronization
    mongo_res = None
    if sync_mongo:
        print("\n[8/8] Synchronizing Knowledge Base & All Relationships to MongoDB")
        t0 = time.time()
        try:
            mongo_res = sync_knowledge_base_to_mongo(
                results = results,
            )
            results["mongo"] = mongo_res
            print(f"-> MongoDB synchronization finished in {time.time() - t0:.2f}s")
        except Exception as e:
            print(f"[ProcessorMain] Warning: MongoDB sync failed: {e}")

    total_time = time.time() - start_time
    print(f"\nPROCESSING COMPLETED IN {total_time:.2f}s")
    print("Primary Knowledge Base: MongoDB ('lol_rag_db')")
    if mongo_res and any(mongo_res.values()):
        print(f"MongoDB Collections synchronized:")
        print(f"  - champions         : {mongo_res.get('champions', 0)} documents (embedded stats, CC, playstyles, counters, synergies, builds)")
        print(f"  - items             : {mongo_res.get('items', 0)} documents (with build paths)")
        print(f"  - runes             : {mongo_res.get('runes', 0)} documents (runes & trees)")
        print(f"  - counters          : {mongo_res.get('counters', 0)} documents")
        print(f"  - synergies         : {mongo_res.get('synergies', 0)} documents")
        print(f"  - builds            : {mongo_res.get('builds', 0)} documents")
        print(f"  - relationships     : {mongo_res.get('relationships', 0)} documents (ALL typed graph edges)")
        print(f"  - team_compositions : {mongo_res.get('team_compositions', 0)} documents (archetype counter matrices)")

    return results


def main(sync_mongo = True):
    """
    Execute all processors in sequence and synchronize to MongoDB.
    Calling main() runs the complete data processing pipeline.
    """
    if len(sys.argv) > 1 and "--no-mongo" in sys.argv:
        sync_mongo = False
    return run_all_processors(sync_mongo = sync_mongo)


if __name__ == "__main__":
    main()

