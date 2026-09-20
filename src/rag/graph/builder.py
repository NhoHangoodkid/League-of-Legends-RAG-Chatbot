"""
Knowledge Graph Builder for LoL Knowledge Bot.

Reads processed data (champions.json, items.json, runes.json, counters, synergies, builds)
and constructs a Neo4j Knowledge Graph with typed nodes and relationships.

Usage:
    python -m rag.graph.builder          # Build full graph
    python -m rag.graph.builder --clear   # Clear and rebuild
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# Ensure src/ is on path
src_dir = Path(__file__).resolve().parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

load_dotenv(src_dir.parent / ".env")

from rag.graph.schema import EdgeType, GraphEdge, GraphNode, NodeType
from rag.graph.store import Neo4jStore
from processors.utils import normalize_champion_id


class GraphBuilder:
    """
    Builds the LoL Knowledge Graph from MongoDB (or local processed data files as fallback).

    Primary Data Source:
    - MongoDB ('lol_rag_db'):
      - 'champions' (173 champions with abilities, stats, CC, effects, playstyles)
      - 'items' (items with build paths, stats, costs)
      - 'runes' (runes by tree and byId)
      - 'counters' (counter matchup data)
      - 'synergies' (duo synergy data)
      - 'builds' (recommended item and rune builds)

    Fallback Data Sources:
    - processors/processed/champions.json
    - processors/processed/items.json
    - processors/processed/runes.json
    - data/knowledge_base/counters/
    - data/knowledge_base/synergies/
    - data/knowledge_base/builds/
    """

    def __init__(self, store = None):
        self.store = store or Neo4jStore()
        self.project_root = src_dir.parent

        # Paths (Fallback)
        self.processed_dir = src_dir / "processors" / "processed"
        self.kb_dir = src_dir / "data" / "knowledge_base"

        # Fallback paths (from legacy lol_chatbot project)
        self.fallback_kb = self.project_root.parent / "lol_chatbot" / "data" / "game_data"

        # Accumulators
        self.nodes = []
        self.edges = []

    def load_from_mongo(self, uri = None, db_name = None):
        """
        Load all entities and relationships directly from MongoDB.
        Returns:
            (champions, items, runes, counters, synergies, builds) or None
        """
        try:
            from pymongo import MongoClient
        except ImportError:
            print("[Builder] ERROR: pymongo is not installed. Run: pip install pymongo")
            return None

        mongo_uri = uri or os.getenv("MONGO_URI", "mongodb://localhost:27017")
        database_name = db_name or os.getenv("MONGO_DB_NAME", "lol_rag_db")

        try:
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS = 3000)
            client.admin.command("ping")
            db = client[database_name]

            champions = {doc["_id"]: doc for doc in db.champions.find()}
            if not champions:
                print(f"[Builder] WARNING: No champion documents found in MongoDB ('{database_name}.champions').")
                return None

            items = {doc["_id"]: doc for doc in db.items.find()}
            runes_docs = list(db.runes.find())
            by_id = {doc["_id"]: doc for doc in runes_docs if doc.get("type") != "tree"}
            by_tree = {
                doc.get("tree", doc["_id"].replace("tree_", "")): doc.get("runes", [])
                for doc in runes_docs if doc.get("type") == "tree"
            }
            runes = {"byId": by_id, "byTree": by_tree}

            # Canonicalize counters to 173 champions matching champions.keys()
            raw_counters = {doc["_id"]: doc for doc in db.counters.find()}
            canonical_counters = {}
            for cid, doc in raw_counters.items():
                c_key = None
                if cid in champions:
                    c_key = cid
                else:
                    for ch_id, ch_data in champions.items():
                        if ch_data.get("name") == doc.get("champion") or ch_data.get("name") == cid:
                            c_key = ch_id
                            break
                if c_key:
                    if c_key not in canonical_counters or ("weakAgainst" in doc and "weakAgainst" not in canonical_counters[c_key]):
                        c_doc = dict(doc)
                        c_doc["_id"] = c_key
                        c_doc["champion_id"] = c_key
                        c_doc["champion"] = champions[c_key].get("name", c_key)
                        canonical_counters[c_key] = c_doc

            for cid, doc in champions.items():
                if cid not in canonical_counters and "counters" in doc and isinstance(doc["counters"], dict):
                    cnt = dict(doc["counters"])
                    cnt["_id"] = cid
                    cnt["champion_id"] = cid
                    cnt["champion"] = doc.get("name", cid)
                    canonical_counters[cid] = cnt

            counters = canonical_counters
            synergies = {doc["_id"]: doc for doc in db.synergies.find()}
            builds = {doc["_id"]: doc for doc in db.builds.find()}

            print(f"[Builder] Successfully loaded knowledge data from MongoDB ('{database_name}'):")
            print(f"  Champions: {len(champions)}, Items: {len(items)}, Runes: {len(by_id)}")
            print(f"  Counters:  {len(counters)}, Synergies: {len(synergies)}, Builds: {len(builds)}")
            return champions, items, runes, counters, synergies, builds
        except Exception as e:
            print(f"[Builder] MongoDB connection/load failed: {e}")
            return None

    def load_data(self, source = "mongo"):
        """
        Load data from specified source ('mongo', 'file', 'auto').
        """
        if source in ("mongo", "auto"):
            mongo_data = self.load_from_mongo()
            if mongo_data:
                return mongo_data
            if source == "mongo":
                raise RuntimeError("Failed to load knowledge data from MongoDB (source='mongo' requested). Make sure MongoDB is running.")
            print("[Builder] Falling back to local files...")

        # Load from files
        print(f"[Builder] Loading data from local files ({self.processed_dir})...")
        champions = self.load_json(self.processed_dir / "champions.json")
        items = self.load_json(self.processed_dir / "items.json")
        runes = self.load_json(self.processed_dir / "runes.json")
        counters = self.load_json(self.processed_dir / "counters.json")
        synergies = self.load_json(self.processed_dir / "synergies.json")
        builds = self.load_json(self.processed_dir / "builds.json")
        return champions, items, runes, counters, synergies, builds

    def build(self, clear = False, source = "mongo"):
        """
        Execute the full graph construction pipeline.

        Args:
            clear: If True, wipe the existing graph before building.
            source: 'mongo' (default), 'file', or 'auto'.
        """
        start = time.time()
        print(f"[Builder] Starting Knowledge Graph construction (Source: {source.upper()})...")

        self.store.connect()

        if clear:
            print("\n[Builder] Clearing existing graph...")
            self.store.clear_database()

        print("\n[Builder] Initializing schema...")
        self.store.init_schema()

        # Load source data
        champions, items, runes, counters, synergies, builds = self.load_data(source = source)

        if not champions:
            print("[Builder] ERROR: No champion data found! Check MongoDB or run processors.")
            return

        # Phase 1: Build champion nodes + ability nodes + tag nodes
        print(f"\n[1/6] Building Champion and Ability nodes ({len(champions)} champions)...")
        self.build_champion_nodes(champions)

        # Phase 2: Build item nodes
        print(f"\n[2/6] Building Item nodes ({len(items)} items)...")
        self.build_item_nodes(items)

        # Phase 3: Build rune nodes
        print(f"\n[3/6] Building Rune nodes...")
        self.build_rune_nodes(runes)

        # Phase 4: Build counter/synergy relationships
        print("\n[4/6] Building Counter and Synergy relationships...")
        self.build_matchup_edges(counters = counters, synergies = synergies)

        # Phase 5: Build build-path relationships
        print("\n[5/6] Building Build/Rune recommendation relationships...")
        self.build_recommendation_edges(builds = builds, items = items, runes = runes)

        # Phase 6: Build item build-path edges
        print("\n[6/6] Building Item build-path edges...")
        self.build_item_path_edges(items)

        # Insert all nodes and edges
        print(f"\n[Builder] Inserting {len(self.nodes)} nodes into Neo4j...")
        self.store.bulk_create_nodes(self.nodes)

        print(f"\n[Builder] Inserting {len(self.edges)} edges into Neo4j...")
        self.store.bulk_create_edges(self.edges)

        elapsed = time.time() - start
        stats = self.store.get_stats()
        print(f"\n[Builder] Knowledge Graph built in {elapsed:.1f}s")
        print(f"  Total nodes: {stats['total_nodes']}")
        print(f"  Total edges: {stats['total_edges']}")
        for label, count in stats["nodes"].items():
            print(f"    {label}: {count}")
        for rel, count in stats["edges"].items():
            print(f"    {rel}: {count}")

    # Node Builders


    def build_champion_nodes(self, champions):
        """Create Champion nodes, Ability nodes, and tag nodes (Role, CC, Effect, etc.)."""
        seen_tags = {"roles": set(), "cc": set(), "effects": set(),
                     "playstyles": set(), "power_curves": set(), "win_conditions": set()}

        for champ_id, champ in champions.items():
            # Champion node
            stats_json = json.dumps(champ.get("stats", {}), ensure_ascii = False)
            self.nodes.append(GraphNode(
                node_id=champ_id,
                node_type=NodeType.CHAMPION,
                properties={
                    "id": champ_id,
                    "champion_id": champ_id,
                    "name": champ.get("name", champ_id),
                    "title": champ.get("title", ""),
                    "short_lore": (champ.get("shortLore", "") or "")[:500],
                    "resource": champ.get("resource", ""),
                    "attack_type": champ.get("attackType", ""),
                    "adaptive_type": champ.get("adaptiveType", ""),
                    "difficulty": champ.get("difficulty", 0),
                    "image": champ.get("image", ""),
                    "stats_json": stats_json,
                },
            ))

            # Ability nodes
            for key in ["passive", "Q", "W", "E", "R"]:
                ability = champ.get("abilities", {}).get(key, {})
                if not ability:
                    continue

                ability_id = f"{champ_id}_{key}"
                self.nodes.append(GraphNode(
                    node_id=ability_id,
                    node_type=NodeType.ABILITY,
                    properties={
                        "id": ability_id,
                        "ability_id": ability_id,
                        "champion_id": champ_id,
                        "key": key,
                        "name": ability.get("name", ""),
                        "description": ability.get("description", ""),
                        "cooldown_json": json.dumps(ability.get("cooldown", []), ensure_ascii = False),
                        "cost_json": json.dumps(ability.get("cost", []), ensure_ascii = False),
                        "range_json": json.dumps(ability.get("range", []), ensure_ascii = False),
                        "maxrank": ability.get("maxrank", 5 if key != "R" else 3),
                    },
                ))
                self.edges.append(GraphEdge(champ_id, ability_id, EdgeType.HAS_ABILITY))

            # Role nodes + edges
            for role in champ.get("roles", []):
                role_name = role.strip().capitalize()
                if role_name and role_name not in seen_tags["roles"]:
                    self.nodes.append(GraphNode(role_name, NodeType.ROLE, {"name": role_name}))
                    seen_tags["roles"].add(role_name)
                if role_name:
                    self.edges.append(GraphEdge(champ_id, role_name, EdgeType.HAS_ROLE))

            # CC type nodes + edges
            for cc in champ.get("cc_types", []):
                if cc not in seen_tags["cc"]:
                    self.nodes.append(GraphNode(cc, NodeType.CC_TYPE, {"name": cc}))
                    seen_tags["cc"].add(cc)
                self.edges.append(GraphEdge(champ_id, cc, EdgeType.HAS_CC))

            # Effect nodes + edges
            for effect in champ.get("ability_effects", []):
                if effect not in seen_tags["effects"]:
                    self.nodes.append(GraphNode(effect, NodeType.EFFECT, {"name": effect}))
                    seen_tags["effects"].add(effect)
                self.edges.append(GraphEdge(champ_id, effect, EdgeType.HAS_EFFECT))

            # Playstyle nodes + edges
            for ps in champ.get("playstyles", []):
                if ps not in seen_tags["playstyles"]:
                    self.nodes.append(GraphNode(ps, NodeType.PLAYSTYLE, {"name": ps}))
                    seen_tags["playstyles"].add(ps)
                self.edges.append(GraphEdge(champ_id, ps, EdgeType.HAS_PLAYSTYLE))

            # Power curve nodes + edges
            for pc in champ.get("powerCurve", []):
                if pc not in seen_tags["power_curves"]:
                    self.nodes.append(GraphNode(pc, NodeType.POWER_CURVE, {"name": pc}))
                    seen_tags["power_curves"].add(pc)
                self.edges.append(GraphEdge(champ_id, pc, EdgeType.HAS_POWER_CURVE))

            # Win condition nodes + edges
            for wc in champ.get("winConditions", []):
                if wc not in seen_tags["win_conditions"]:
                    self.nodes.append(GraphNode(wc, NodeType.WIN_CONDITION, {"name": wc}))
                    seen_tags["win_conditions"].add(wc)
                self.edges.append(GraphEdge(champ_id, wc, EdgeType.HAS_WIN_CONDITION))

        print(f"  Champions: {len(champions)}")
        print(f"  Tag nodes: {sum(len(v) for v in seen_tags.values())} "
              f"(roles={len(seen_tags['roles'])}, cc={len(seen_tags['cc'])}, "
              f"effects={len(seen_tags['effects'])}, playstyles={len(seen_tags['playstyles'])})")

    def build_item_nodes(self, items):
        """Create Item nodes."""
        for item_id, item in items.items():
            cost = item.get("cost", {})
            self.nodes.append(GraphNode(
                node_id=str(item_id),
                node_type=NodeType.ITEM,
                properties={
                    "id": str(item_id),
                    "item_id": str(item_id),
                    "name": item.get("name", ""),
                    "description": item.get("description", ""),
                    "plaintext": item.get("plaintext", ""),
                    "cost_total": cost.get("total", 0) if isinstance(cost, dict) else 0,
                    "cost_base": cost.get("base", 0) if isinstance(cost, dict) else 0,
                    "cost_sell": cost.get("sell", 0) if isinstance(cost, dict) else 0,
                    "stats_json": json.dumps(item.get("stats", {}), ensure_ascii = False),
                    "image": item.get("image", ""),
                },
            ))

    def build_rune_nodes(self, runes):
        """Create Rune nodes from runes.json (organized by ID and tree)."""
        runes_by_id = runes.get("byId", {})
        count = 0
        for rune_id, rune in runes_by_id.items():
            self.nodes.append(GraphNode(
                node_id=str(rune_id),
                node_type=NodeType.RUNE,
                properties={
                    "id": str(rune_id),
                    "rune_id": str(rune_id),
                    "name": rune.get("name", ""),
                    "tree": rune.get("tree", ""),
                    "description": rune.get("description", ""),
                    "long_description": rune.get("longDescription", ""),
                },
            ))
            count += 1
        print(f"  Runes: {count}")

    # Edge Builders (Relationships)


    def build_matchup_edges(self, counters = None, synergies = None):
        """Build COUNTERS and SYNERGIZES_WITH edges from MongoDB or local files."""
        counter_count = 0

        # 1. Build COUNTERS edges
        if counters:
            counter_docs = counters.values() if isinstance(counters, dict) else counters
            for data in counter_docs:
                champ_name = data.get("champion") or data.get("champion_id") or data.get("_id", "")
                champ_id = self.normalize_name(champ_name)

                for matchup in data.get("weakAgainst", []):
                    counter_id = self.normalize_name(matchup.get("champion", ""))
                    if counter_id and champ_id:
                        self.edges.append(GraphEdge(
                            counter_id, champ_id, EdgeType.COUNTERS,
                            properties={
                                "win_rate": matchup.get("winRate", 0),
                                "games": matchup.get("games", 0),
                                "reason": matchup.get("reason", ""),
                            },
                        ))
                        counter_count += 1

                for matchup in data.get("strongAgainst", []):
                    weak_id = self.normalize_name(matchup.get("champion", ""))
                    if weak_id and champ_id:
                        self.edges.append(GraphEdge(
                            champ_id, weak_id, EdgeType.COUNTERS,
                            properties={
                                "win_rate": matchup.get("winRate", 0),
                                "games": matchup.get("games", 0),
                                "reason": matchup.get("reason", ""),
                            },
                        ))
                        counter_count += 1
        else:
            # Fallback to local files
            counter_dir = self.find_dir(
                self.kb_dir / "counters",
                self.fallback_kb / "counter_data",
            )
            if counter_dir and counter_dir.exists():
                for fpath in counter_dir.glob("*_counters.json"):
                    data = self.load_json(fpath)
                    if not data:
                        continue
                    champ_name = data.get("champion", fpath.stem.replace("_counters", ""))
                    champ_id = self.normalize_name(champ_name)

                    for matchup in data.get("weakAgainst", []):
                        counter_id = self.normalize_name(matchup.get("champion", ""))
                        if counter_id and champ_id:
                            self.edges.append(GraphEdge(
                                counter_id, champ_id, EdgeType.COUNTERS,
                                properties={
                                    "win_rate": matchup.get("winRate", 0),
                                    "games": matchup.get("games", 0),
                                    "reason": matchup.get("reason", ""),
                                },
                            ))
                            counter_count += 1

                    for matchup in data.get("strongAgainst", []):
                        weak_id = self.normalize_name(matchup.get("champion", ""))
                        if weak_id and champ_id:
                            self.edges.append(GraphEdge(
                                champ_id, weak_id, EdgeType.COUNTERS,
                                properties={
                                    "win_rate": matchup.get("winRate", 0),
                                    "games": matchup.get("games", 0),
                                    "reason": matchup.get("reason", ""),
                                },
                            ))
                            counter_count += 1

        print(f"  Counter edges: {counter_count}")

        # 2. Build SYNERGIZES_WITH edges
        synergy_count = 0
        if synergies:
            synergy_docs = synergies.values() if isinstance(synergies, dict) else synergies
            for data in synergy_docs:
                champ_name = data.get("champion") or data.get("champion_id") or data.get("_id", "")
                champ_id = self.normalize_name(champ_name)

                duos = data.get("best_duos") or data.get("synergies", data if isinstance(data, list) else [])
                if isinstance(duos, dict):
                    duos = duos.get("best_duos") or duos.get("synergies", [])

                for duo in (duos if isinstance(duos, list) else []):
                    partner_name = duo.get("partner") or duo.get("champion", "")
                    partner_id = self.normalize_name(partner_name)
                    if partner_id and champ_id:
                        self.edges.append(GraphEdge(
                            champ_id, partner_id, EdgeType.SYNERGIZES_WITH,
                            properties={
                                "duo_win_rate": duo.get("win_rate") or duo.get("soloq_winrate") or duo.get("duo_win_rate") or duo.get("winRate", 0),
                                "games": duo.get("sample_games") or duo.get("soloq_games") or duo.get("games", 0),
                                "pro_play": duo.get("pro_play", False),
                                "pro_games": duo.get("pro_games", 0),
                                "pro_winrate": duo.get("pro_winrate"),
                                "reason": duo.get("synergy_reason") or duo.get("reason", ""),
                                "synergy_tag": duo.get("synergy_tag", ""),
                            },
                        ))
                        synergy_count += 1
        else:
            # Fallback to local files
            synergy_dir = self.find_dir(
                self.kb_dir / "synergies",
                self.fallback_kb / "synergy_data",
            )
            if synergy_dir and synergy_dir.exists():
                for fpath in synergy_dir.glob("*.json"):
                    data = self.load_json(fpath)
                    if not data:
                        continue
                    champ_name = fpath.stem.replace("_synergy", "").replace("_duos", "")
                    champ_id = self.normalize_name(champ_name)

                    synergies_list = data.get("synergies", data if isinstance(data, list) else [])
                    if isinstance(synergies_list, dict):
                        synergies_list = synergies_list.get("synergies", [])

                    for duo in (synergies_list if isinstance(synergies_list, list) else []):
                        partner_id = self.normalize_name(duo.get("champion", ""))
                        if partner_id and champ_id:
                            self.edges.append(GraphEdge(
                                champ_id, partner_id, EdgeType.SYNERGIZES_WITH,
                                properties={
                                    "duo_win_rate": duo.get("duo_win_rate", duo.get("winRate", 0)),
                                    "games": duo.get("games", 0),
                                    "reason": duo.get("reason", ""),
                                },
                            ))
                            synergy_count += 1

        print(f"  Synergy edges: {synergy_count}")

    def build_recommendation_edges(self, builds = None, items = None, runes = None):
        """Build USES_ITEM and USES_RUNE edges from MongoDB or local files."""
        item_edges = 0
        rune_edges = 0

        # Build name-to-ID lookup for items
        item_name_to_id = {}
        if items:
            for item_id, item_doc in items.items():
                name = item_doc.get("name", "")
                if name:
                    item_name_to_id[name.lower().strip()] = str(item_id)

        # Build name-to-ID lookup for runes
        rune_name_to_id = {}
        if runes:
            runes_by_id = runes.get("byId", {}) if isinstance(runes, dict) else {}
            for rune_id, rune_doc in runes_by_id.items():
                name = rune_doc.get("name", "")
                if name:
                    rune_name_to_id[name.lower().strip()] = str(rune_id)

        if builds:
            build_docs = builds.values() if isinstance(builds, dict) else builds
            for data in build_docs:
                champ_name = data.get("champion") or data.get("champion_id") or data.get("_id", "")
                champ_id = self.normalize_name(champ_name)
                if not champ_id:
                    continue

                core_items = data.get("coreItems", data.get("core_items", []))
                full_build = data.get("fullBuild", data.get("full_build", []))
                all_items = list(set(core_items + full_build))

                for item_name in all_items:
                    target_id = item_name_to_id.get(str(item_name).lower().strip(), str(item_name))
                    self.edges.append(GraphEdge(
                        champ_id, target_id, EdgeType.USES_ITEM,
                        properties={"is_core": item_name in core_items, "name": str(item_name)},
                    ))
                    item_edges += 1

                # Keystone rune
                keystone = data.get("keystone", "")
                if keystone:
                    target_rune_id = rune_name_to_id.get(str(keystone).lower().strip(), str(keystone))
                    self.edges.append(GraphEdge(
                        champ_id, target_rune_id, EdgeType.USES_RUNE,
                        properties={"is_keystone": True, "name": str(keystone)},
                    ))
                    rune_edges += 1
        else:
            # Fallback to local files
            build_dir = self.find_dir(
                self.kb_dir / "builds",
                self.fallback_kb / "build_data",
            )
            if build_dir and build_dir.exists():
                for fpath in build_dir.glob("*.json"):
                    data = self.load_json(fpath)
                    if not data:
                        continue
                    champ_name = data.get("champion", fpath.stem.replace("_build", ""))
                    champ_id = self.normalize_name(champ_name)
                    if not champ_id:
                        continue

                    # Core items
                    core_items = data.get("coreItems", data.get("core_items", []))
                    full_build = data.get("fullBuild", data.get("full_build", []))
                    all_items = list(set(core_items + full_build))

                    for item_name in all_items:
                        self.edges.append(GraphEdge(
                            champ_id, str(item_name), EdgeType.USES_ITEM,
                            properties={"is_core": item_name in core_items},
                        ))
                        item_edges += 1

                    # Keystone rune
                    keystone = data.get("keystone", "")
                    if keystone:
                        self.edges.append(GraphEdge(
                            champ_id, str(keystone), EdgeType.USES_RUNE,
                            properties={"is_keystone": True},
                        ))
                        rune_edges += 1

        print(f"  Item recommendation edges: {item_edges}")
        print(f"  Rune recommendation edges: {rune_edges}")

    def build_item_path_edges(self, items):
        """Build BUILDS_FROM and BUILDS_INTO edges for item recipes."""
        edge_count = 0
        for item_id, item in items.items():
            for component_id in item.get("buildFrom", []):
                if str(component_id) in items:
                    self.edges.append(GraphEdge(
                        str(item_id), str(component_id), EdgeType.BUILDS_FROM,
                    ))
                    edge_count += 1

            for upgrade_id in item.get("buildInto", []):
                if str(upgrade_id) in items:
                    self.edges.append(GraphEdge(
                        str(item_id), str(upgrade_id), EdgeType.BUILDS_INTO,
                    ))
                    edge_count += 1

        print(f"  Item build-path edges: {edge_count}")

    # Utilities


    @staticmethod
    def normalize_name(name):
        """Normalize champion name to canonical ID form (e.g., 'Lee Sin' → 'LeeSin', 'Wukong' → 'MonkeyKing')."""
        if not name:
            return ""
        # Use the canonical alias table for known champion names
        canonical = normalize_champion_id(name.strip())
        if canonical:
            return canonical
        # Fallback: Remove special chars and spaces to match champion IDs
        cleaned = re.sub(r"['\s\-\.]", "", name.strip())
        return cleaned

    @staticmethod
    def find_dir(primary, fallback):
        """Return primary dir if it exists and has files, else fallback."""
        if primary.exists() and any(primary.iterdir()):
            return primary
        if fallback.exists() and any(fallback.iterdir()):
            return fallback
        return None

    @staticmethod
    def load_json(path):
        """Load JSON file, return empty dict/list on failure."""
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding = "utf-8") as f:
                return json.load(f)
        except Exception:
            return {}


def main():
    parser = argparse.ArgumentParser(description="Build LoL Knowledge Graph in Neo4j from MongoDB")
    parser.add_argument("--clear", action="store_true", help="Clear existing graph before building")
    parser.add_argument(
        "--source",
        choices=["mongo", "file", "auto"],
        default="mongo",
        help="Knowledge data source: 'mongo' (default), 'file', or 'auto'",
    )
    args = parser.parse_args()

    builder = GraphBuilder()
    try:
        builder.build(clear = args.clear, source = args.source)
    finally:
        builder.store.close()


if __name__ == "__main__":
    main()
