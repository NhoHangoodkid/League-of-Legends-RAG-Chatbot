"""
MongoDB Knowledge Synchronizer.

Synchronizes processed knowledge base data into MongoDB collections:
- champions: Embedded document model (base stats, abilities, tactical tags, lore, counters, synergies, builds)
- counters: Matchup profiles (weakAgainst, strongAgainst with win rates and tactical notes)
- synergies: Duo partner profiles (duo win rates and ability synergy combinations)
- builds: Recommended loadouts (starting items, core items, full build, runes, summoner spells)
- items: Item catalog (gold cost, stats, passives, build paths)
- runes: Rune perks and trees (perk descriptions, tree categories)

Outputs:
- MongoDB collections: champions, counters, synergies, builds, items, runes, relationships, team_compositions in database 'lol_rag_db'
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .utils import (
    processed_dir,
    project_root,
    src_dir,
    load_json,
    log,
    save_json,
)

# Load environment configuration
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    pass

# MongoDB Driver import
try:
    from pymongo import MongoClient, ReplaceOne
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    pymongo_available = True
except ImportError:
    pymongo_available = False


# Constants and Default Configurations
kb_dir = src_dir / "data" / "knowledge_base"
default_mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
default_db_name = os.getenv("MONGO_DB_NAME", "lol_rag_db")
default_sync_enabled = os.getenv("MONGO_SYNC_ENABLED", "true").lower() in ("true", "1", "yes")
tag = "MongoSync"


class MongoSyncManager:
    """Synchronize processed game data and knowledge base relationships to MongoDB."""

    def __init__(self, uri = None, db_name = None, enabled = None, timeout_ms = 3000):
        self.uri = uri or default_mongo_uri
        self.db_name = db_name or default_db_name
        self.enabled = default_sync_enabled if enabled is None else enabled
        self.timeout_ms = timeout_ms

        self.client = None
        self.db = None
        self._connected = False

        if self.enabled:
            self.connect()

    def connect(self):
        """Establish MongoDB connection with timeout and verify ping response."""
        if not pymongo_available:
            log(tag, "pymongo library is not installed. Install via: pip install pymongo")
            self._connected = False
            return False

        try:
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS = self.timeout_ms)
            self.client.admin.command("ping")
            self.db = self.client[self.db_name]
            self._connected = True
            log(tag, f"Successfully connected to MongoDB at {self.uri} (Database: {self.db_name})")
            return True
        except (ConnectionFailure, ServerSelectionTimeoutError, Exception) as e:
            log(tag, f"WARNING: Could not connect to MongoDB ({e}). Skipping MongoDB sync.")
            self._connected = False
            self.client = None
            self.db = None
            return False

    def is_connected(self):
        """Check if active connection to MongoDB exists."""
        return self._connected and self.db is not None

    def sync_champions(self, champions_data = None, counters_data = None, synergies_data = None, builds_data = None, kb_dir = None, processed_dir = None):
        """
        Synchronize champions to MongoDB.
        Embeds counters, synergies, and builds for O(1) query access,
        while also syncing to dedicated 'counters', 'synergies', and 'builds' collections.
        Operates directly from in-memory objects with zero required disk reads.
        """
        if not self.is_connected():
            return {"champions": 0, "counters": 0, "synergies": 0, "builds": 0}

        kb_path = kb_dir or kb_dir
        proc_path = processed_dir or processed_dir

        # Load merged champions if not passed in memory
        if not champions_data:
            champions_data = load_json(proc_path / "champions.json")
            if not champions_data and kb_path.exists():
                champions_data = load_json(kb_path / "champions.json")

        if not champions_data:
            log(tag, "No champion data found to synchronize.")
            return {"champions": 0, "counters": 0, "synergies": 0, "builds": 0}

        if not synergies_data:
            synergies_data = load_json(proc_path / "synergies.json") or load_json(kb_path / "synergies.json")

        counters_dir = kb_path / "counters"
        synergies_dir = kb_path / "synergies"
        builds_dir = kb_path / "builds"

        operations = []
        counter_ops = []
        synergy_ops = []
        build_ops = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for cid, cdata in champions_data.items():
            doc = dict(cdata)
            doc["_id"] = str(cid)
            doc["updated_at"] = now_iso

            # 1. Embed and store counter profile
            c_info = None
            if counters_data and cid in counters_data:
                c_info = counters_data[cid]
            elif doc.get("counters"):
                c_info = doc["counters"]
            else:
                for candidate in [counters_dir / f"{cid}_counters.json", counters_dir / f"{cid.lower()}_counters.json"]:
                    if candidate.exists():
                        c_info = load_json(candidate)
                        break

            if c_info:
                doc["counters"] = c_info
                c_doc = dict(c_info)
                c_doc["_id"] = str(cid)
                c_doc["champion_id"] = str(cid)
                c_doc["champion"] = cdata.get("name", str(cid))
                c_doc["updated_at"] = now_iso

                # Enrich counter profile with complete tactical intelligence from champion tacticalInfo
                tactical = cdata.get("tacticalInfo", {})
                if tactical:
                    c_doc["weaknesses"] = tactical.get("weaknesses", [])
                    c_doc["tactical_tips"] = tactical.get("tactical_tips", [])
                    c_doc["counter_items"] = tactical.get("counter_items", [])
                    c_doc["official_enemytips"] = tactical.get("official_enemytips", cdata.get("enemytips", []))
                    c_doc["official_allytips"] = tactical.get("official_allytips", cdata.get("allytips", []))
                    c_doc["projectile_abilities"] = tactical.get("projectile_abilities", [])
                    c_doc["spellshieldable_abilities"] = tactical.get("spellshieldable_abilities", [])
                    c_doc["onhit_abilities"] = tactical.get("onhit_abilities", [])
                    c_doc["aram_summary"] = tactical.get("aram_summary", "")

                counter_ops.append(ReplaceOne({"_id": c_doc["_id"]}, c_doc, upsert = True))

            # 2. Embed and store synergy profile
            s_info = None
            if synergies_data:
                s_info = (
                    synergies_data.get(cid) or
                    synergies_data.get(cdata.get("name")) or
                    synergies_data.get(str(cid).capitalize())
                )
            elif doc.get("synergies"):
                s_info = {"synergies": doc["synergies"]} if isinstance(doc["synergies"], list) else doc["synergies"]
            else:
                for candidate in [
                    synergies_dir / f"{cid}_synergy.json",
                    synergies_dir / f"{cid.lower()}_synergy.json",
                    synergies_dir / "synergies.json"
                ]:
                    if candidate.exists():
                        loaded = load_json(candidate)
                        if isinstance(loaded, dict) and (cid in loaded or cdata.get("name") in loaded):
                            s_info = loaded.get(cid) or loaded.get(cdata.get("name"))
                            break
                        elif candidate.name != "synergies.json":
                            s_info = loaded
                            break

            if s_info:
                best_duos = s_info.get("best_duos") or s_info.get("synergies", [])
                doc["synergies"] = best_duos
                s_doc = dict(s_info) if isinstance(s_info, dict) else {"synergies": s_info}
                s_doc["_id"] = str(cid)
                s_doc["champion_id"] = str(cid)
                c_name = cdata.get("name", str(cid))
                s_doc["champion"] = c_name
                s_doc["best_duos"] = best_duos
                s_doc["synergies"] = best_duos
                s_doc["tactical_insights"] = s_info.get("tactical_insights", [])
                s_doc["role"] = s_info.get("role", "")
                s_doc["updated_at"] = now_iso
                synergy_ops.append(ReplaceOne({"_id": s_doc["_id"]}, s_doc, upsert = True))
                # Also upsert by canonical champion name if different from cid
                if c_name != str(cid):
                    name_doc = dict(s_doc)
                    name_doc["_id"] = c_name
                    synergy_ops.append(ReplaceOne({"_id": name_doc["_id"]}, name_doc, upsert = True))


            # 3. Embed and store build guide
            b_info = None
            if builds_data and cid in builds_data:
                b_info = builds_data[cid]
            elif doc.get("builds"):
                b_info = doc["builds"]
            else:
                for candidate in [builds_dir / f"{cid}_build.json", builds_dir / f"{cid.lower()}_build.json"]:
                    if candidate.exists():
                        b_info = load_json(candidate)
                        break

            if b_info:
                doc["builds"] = {
                    "startingItems": b_info.get("startingItems", []),
                    "coreItems": b_info.get("coreItems", []),
                    "fullBuild": b_info.get("fullBuild", []),
                    "summonerSpells": b_info.get("summonerSpells", []),
                    "keystone": b_info.get("keystone", ""),
                    "primaryRunes": b_info.get("primaryRunes", []),
                    "secondaryRunes": b_info.get("secondaryRunes", []),
                }
                b_doc = dict(b_info)
                b_doc["_id"] = str(cid)
                b_doc["champion_id"] = str(cid)
                b_doc["champion"] = cdata.get("name", str(cid))
                b_doc["updated_at"] = now_iso
                build_ops.append(ReplaceOne({"_id": b_doc["_id"]}, b_doc, upsert = True))

            operations.append(ReplaceOne({"_id": doc["_id"]}, doc, upsert = True))

        if operations:
            self.db.champions.bulk_write(operations, ordered = False)
            self.db.champions.create_index("name")
            self.db.champions.create_index("roles")
            self.db.champions.create_index("subroles")
            self.db.champions.create_index("positions")
            self.db.champions.create_index("region")
            self.db.champions.create_index("powerCurve")
            self.db.champions.create_index("winConditions")
            log(tag, f"Synced {len(operations)} champions (embedded counters, synergies, builds) -> 'champions'")

        if counter_ops:
            self.db.counters.delete_many({"_id": {"$nin": [str(k) for k in champions_data.keys()]}})
            self.db.counters.bulk_write(counter_ops, ordered = False)
            self.db.counters.create_index("champion")
            self.db.counters.create_index("champion_id")
            log(tag, f"Synced {len(counter_ops)} counter profiles -> 'counters'")

        if synergy_ops:
            self.db.synergies.bulk_write(synergy_ops, ordered = False)
            log(tag, f"Synced {len(synergy_ops)} synergy profiles -> 'synergies'")

        if build_ops:
            self.db.builds.bulk_write(build_ops, ordered = False)
            log(tag, f"Synced {len(build_ops)} build guides -> 'builds'")

        return {
            "champions": len(operations),
            "counters": len(counter_ops),
            "synergies": len(synergy_ops),
            "builds": len(build_ops),
        }

    def sync_items(self, items_data = None, processed_dir = None):
        """Synchronize merged items into MongoDB 'items' collection."""
        if not self.is_connected():
            return 0

        proc_path = processed_dir or processed_dir
        if not items_data:
            items_data = load_json(proc_path / "items.json")
            if not items_data:
                items_data = load_json(kb_dir / "items.json")

        if not items_data:
            log(tag, "No item data found to synchronize.")
            return 0

        operations = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for item_id, idata in items_data.items():
            doc = dict(idata)
            doc["_id"] = str(item_id)
            doc["updated_at"] = now_iso
            operations.append(ReplaceOne({"_id": doc["_id"]}, doc, upsert = True))

        if operations:
            self.db.items.bulk_write(operations, ordered = False)
            self.db.items.create_index("name")
            self.db.items.create_index("tags")
            log(tag, f"Synced {len(operations)} items -> 'items'")

        return len(operations)

    def sync_runes(self, runes_data = None, processed_dir = None):
        """Synchronize rune perks and trees into MongoDB 'runes' collection."""
        if not self.is_connected():
            return 0

        proc_path = processed_dir or processed_dir
        if not runes_data:
            runes_data = load_json(proc_path / "runes.json")
            if not runes_data:
                runes_data = load_json(kb_dir / "runes.json")

        if not runes_data:
            log(tag, "No rune data found to synchronize.")
            return 0

        operations = []
        now_iso = datetime.now(timezone.utc).isoformat()

        # Sync individual rune perks by perk ID
        by_id = runes_data.get("byId", {})
        for rune_id, rdata in by_id.items():
            doc = dict(rdata)
            doc["_id"] = str(rune_id)
            doc["type"] = "rune"
            doc["updated_at"] = now_iso
            operations.append(ReplaceOne({"_id": doc["_id"]}, doc, upsert = True))

        # Sync rune tree structures
        by_tree = runes_data.get("byTree", {})
        for tree_key, tdata in by_tree.items():
            tree_doc = {
                "_id": f"tree_{tree_key}",
                "tree": tree_key,
                "runes": tdata if isinstance(tdata, list) else [tdata],
                "type": "tree",
                "updated_at": now_iso,
            }
            operations.append(ReplaceOne({"_id": tree_doc["_id"]}, tree_doc, upsert = True))

        if operations:
            self.db.runes.bulk_write(operations, ordered = False)
            self.db.runes.create_index("name")
            self.db.runes.create_index("tree")
            log(tag, f"Synced {len(operations)} runes and rune trees -> 'runes'")

        return len(operations)

    def sync_relationships(self, relationships_data = None):
        """
        Synchronize all typed relationships (edges) into MongoDB 'relationships' collection.
        Enables graph-like queries across champions, items, runes, counters, synergies, lore, and CC.
        """
        if not self.is_connected() or not relationships_data:
            return 0

        operations = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for idx, rel in enumerate(relationships_data):
            doc = dict(rel)
            # Create a deterministic unique ID for each edge
            doc_id = f"{rel['source_id']}_{rel['type']}_{rel['target_id']}"
            if "properties" in rel and "stage" in rel["properties"]:
                doc_id += f"_{rel['properties']['stage']}"
            elif "properties" in rel and "role" in rel["properties"]:
                doc_id += f"_{rel['properties']['role']}"

            doc["_id"] = doc_id
            doc["updated_at"] = now_iso
            operations.append(ReplaceOne({"_id": doc["_id"]}, doc, upsert = True))

        if operations:
            self.db.relationships.delete_many({})
            self.db.relationships.bulk_write(operations, ordered = False)
            self.db.relationships.create_index([("source_id", 1), ("type", 1)])
            self.db.relationships.create_index([("target_id", 1), ("type", 1)])
            self.db.relationships.create_index("type")
            self.db.relationships.create_index("source_name")
            self.db.relationships.create_index("target_name")
            log(tag, f"Synced {len(operations)} typed relationships -> 'relationships'")

        return len(operations)

    def sync_team_compositions(self, compositions_data = None, kb_dir = None, processed_dir = None):
        """
        Synchronize analyzed champion archetype team compositions and champion-centric pro team comps into MongoDB.
        Enables O(1) retrieval for team archetype counter matchups, items, and weaknesses.
        """
        if not self.is_connected():
            return 0

        kb_path = kb_dir or kb_dir
        proc_path = processed_dir or processed_dir

        if not compositions_data:
            compositions_data = load_json(proc_path / "team_compositions.json") or load_json(kb_path / "team_compositions.json")

        if not compositions_data:
            return 0

        # Purge existing collection
        self.db.team_compositions.delete_many({})

        operations = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for comp_id, cdata in compositions_data.items():
            doc = dict(cdata)
            doc["_id"] = str(comp_id)
            doc["updated_at"] = now_iso
            operations.append(ReplaceOne({"_id": doc["_id"]}, doc, upsert = True))

        if operations:
            self.db.team_compositions.bulk_write(operations, ordered = False)
            self.db.team_compositions.create_index("comp_id")
            self.db.team_compositions.create_index("focus_champion")
            self.db.team_compositions.create_index("category")
            self.db.team_compositions.create_index("aliases")
            log(tag, f"Synced {len(operations)} team compositions -> 'team_compositions'")

        return len(operations)

    def sync_all(self, results = None, kb_dir = None, processed_dir = None):
        """Synchronize all knowledge base datasets (champions, items, runes, relationships, compositions) to MongoDB."""
        if not self.is_connected():
            return {"champions": 0, "items": 0, "runes": 0, "counters": 0, "synergies": 0, "builds": 0, "relationships": 0, "team_compositions": 0}

        results = results or {}
        champions = results.get("champions") or results.get("enriched_champions")
        counters = results.get("counters")
        synergies = results.get("synergies")
        builds = results.get("builds")
        relationships = results.get("relationships")
        items = results.get("items")
        runes = results.get("runes")
        team_compositions = results.get("team_compositions")

        log(tag, "STARTING MONGODB SYNCHRONIZATION")

        c_stats = self.sync_champions(
            champions_data = champions,
            counters_data = counters,
            synergies_data = synergies,
            builds_data = builds,
            kb_dir = kb_dir,
            processed_dir = processed_dir,
        )
        if isinstance(c_stats, dict):
            c_count = c_stats.get("champions", 0)
            counter_count = c_stats.get("counters", 0)
            synergy_count = c_stats.get("synergies", 0)
            build_count = c_stats.get("builds", 0)
        else:
            c_count = c_stats
            counter_count = synergy_count = build_count = 0

        i_count = self.sync_items(items, processed_dir = processed_dir)
        r_count = self.sync_runes(runes, processed_dir = processed_dir)
        rel_count = self.sync_relationships(relationships)
        comp_count = self.sync_team_compositions(team_compositions)

        log(
            tag,
            f"COMPLETED: {c_count} champions, {i_count} items, {r_count} runes, "
            f"{counter_count} counters, {synergy_count} synergies, {build_count} builds, "
            f"{rel_count} relationships, {comp_count} team compositions synced to '{self.db_name}'."
        )

        return {
            "champions": c_count,
            "items": i_count,
            "runes": r_count,
            "counters": counter_count,
            "synergies": synergy_count,
            "builds": build_count,
            "relationships": rel_count,
            "team_compositions": comp_count,
        }

    def close(self):
        """Close active MongoDB connection."""
        if self.client:
            self.client.close()
            self._connected = False


def sync_knowledge_base_to_mongo(results = None, kb_dir = None, processed_dir = None):
    """Convenience function to execute full MongoDB synchronization."""
    manager = MongoSyncManager()
    try:
        return manager.sync_all(results = results, kb_dir = kb_dir, processed_dir = processed_dir)
    finally:
        manager.close()
