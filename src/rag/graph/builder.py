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
import re
import sys
import time
from pathlib import Path

# Ensure src/ is on path
SRC_DIR = Path(__file__).resolve().parent.parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rag.graph.schema import EdgeType, GraphEdge, GraphNode, NodeType
from rag.graph.store import Neo4jStore


class GraphBuilder:
    """
    Builds the LoL Knowledge Graph from processed data files.

    Data sources:
    - processors/processed/champions.json  (173 champions with abilities, stats, CC, effects, etc.)
    - processors/processed/items.json      (items with build paths)
    - processors/processed/runes.json      (runes by tree)
    - data/knowledge_base/counters/        (counter matchup data)
    - data/knowledge_base/synergies/       (duo synergy data)
    - data/knowledge_base/builds/          (recommended builds)
    """

    def __init__(self, store = None):
        self.store = store or Neo4jStore()
        self.project_root = SRC_DIR.parent

        # Paths
        self.processed_dir = SRC_DIR / "processors" / "processed"
        self.kb_dir = SRC_DIR / "data" / "knowledge_base"

        # Fallback paths (from legacy lol_chatbot project)
        self.fallback_kb = self.project_root.parent / "lol_chatbot" / "data" / "game_data"

        # Accumulators
        self.nodes = []
        self.edges = []

    def build(self, clear = False):
        """
        Execute the full graph construction pipeline.

        Args:
            clear: If True, wipe the existing graph before building.
        """
        start = time.time()
        print("-" * 60)
        print("KNOWLEDGE GRAPH BUILDER — Starting")
        print("-" * 60)

        self.store.connect()

        if clear:
            print("\n[Builder] Clearing existing graph...")
            self.store.clear_database()

        print("\n[Builder] Initializing schema...")
        self.store.init_schema()

        # Load source data
        champions = self.load_json(self.processed_dir / "champions.json")
        items = self.load_json(self.processed_dir / "items.json")
        runes = self.load_json(self.processed_dir / "runes.json")

        if not champions:
            print("[Builder] ERROR: No champion data found! Run processors first.")
            return

        # Phase 1: Build champion nodes + ability nodes + tag nodes
        print(f"\n[1/6] Building Champion & Ability nodes ({len(champions)} champions)...")
        self.build_champion_nodes(champions)

        # Phase 2: Build item nodes
        print(f"\n[2/6] Building Item nodes ({len(items)} items)...")
        self.build_item_nodes(items)

        # Phase 3: Build rune nodes
        print(f"\n[3/6] Building Rune nodes...")
        self.build_rune_nodes(runes)

        # Phase 4: Build counter/synergy relationships
        print("\n[4/6] Building Counter & Synergy relationships...")
        self.build_matchup_edges()

        # Phase 5: Build build-path relationships
        print("\n[5/6] Building Build/Rune recommendation relationships...")
        self.build_recommendation_edges()

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
        print("\n" + "=" * 60)
        print(f"KNOWLEDGE GRAPH BUILT in {elapsed:.1f}s")
        print(f"  Total nodes: {stats['total_nodes']}")
        print(f"  Total edges: {stats['total_edges']}")
        for label, count in stats["nodes"].items():
            print(f"    {label}: {count}")
        for rel, count in stats["edges"].items():
            print(f"    {rel}: {count}")
        print("-" * 60)

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


    def build_matchup_edges(self):
        """Build COUNTERS and SYNERGIZES_WITH edges from knowledge base."""
        # Counters
        counter_dir = self.find_dir(
            self.kb_dir / "counters",
            self.fallback_kb / "counter_data",
        )
        counter_count = 0
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
                            },
                        ))
                        counter_count += 1

        print(f"  Counter edges: {counter_count}")

        # Synergies
        synergy_dir = self.find_dir(
            self.kb_dir / "synergies",
            self.fallback_kb / "synergy_data",
        )
        synergy_count = 0
        if synergy_dir and synergy_dir.exists():
            for fpath in synergy_dir.glob("*.json"):
                data = self.load_json(fpath)
                if not data:
                    continue
                champ_name = fpath.stem.replace("_synergy", "").replace("_duos", "")
                champ_id = self.normalize_name(champ_name)

                synergies = data.get("synergies", data if isinstance(data, list) else [])
                if isinstance(synergies, dict):
                    synergies = synergies.get("synergies", [])

                for duo in (synergies if isinstance(synergies, list) else []):
                    partner_id = self.normalize_name(duo.get("champion", ""))
                    if partner_id and champ_id:
                        self.edges.append(GraphEdge(
                            champ_id, partner_id, EdgeType.SYNERGIZES_WITH,
                            properties={
                                "duo_win_rate": duo.get("duo_win_rate", duo.get("winRate", 0)),
                                "games": duo.get("games", 0),
                            },
                        ))
                        synergy_count += 1

        print(f"  Synergy edges: {synergy_count}")

    def build_recommendation_edges(self):
        """Build USES_ITEM and USES_RUNE edges from build data."""
        build_dir = self.find_dir(
            self.kb_dir / "builds",
            self.fallback_kb / "build_data",
        )
        item_edges = 0
        rune_edges = 0

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
                    # Item names need to be resolved to IDs — store by name for now
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
        """Normalize champion name to canonical ID form (e.g., 'Lee Sin' → 'LeeSin')."""
        if not name:
            return ""
        # Remove special chars and spaces to match champion IDs
        cleaned = re.sub(r"['\s\-\.]", "", name.strip())
        # Capitalize first letter of each word
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
    parser = argparse.ArgumentParser(description="Build LoL Knowledge Graph in Neo4j")
    parser.add_argument("--clear", action="store_true", help="Clear existing graph before building")
    args = parser.parse_args()

    builder = GraphBuilder()
    try:
        builder.build(clear = args.clear)
    finally:
        builder.store.close()


if __name__ == "__main__":
    main()
