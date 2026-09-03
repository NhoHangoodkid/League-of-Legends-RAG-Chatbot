"""
Neo4j Graph Store for LoL Knowledge Bot.

Manages the Neo4j connection, schema initialization, bulk loading,
and provides a high-level query API for graph operations.

Requires Neo4j Community Edition running locally (default bolt://localhost:7687).
"""

import json
import os
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

from rag.graph.schema import EdgeType, NodeType, GraphNode, GraphEdge


#-----------------------------------------------------------------------------
# Default Neo4j connection settings
#-----------------------------------------------------------------------------

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "lolbot2024")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")


class Neo4jStore:
    """
    Neo4j-backed Knowledge Graph Store.

    Provides:
    - Connection lifecycle management
    - Schema & constraint initialization
    - Bulk node/edge insertion
    - High-level Cypher query API (get_node, get_neighbors, subgraph, paths)
    """

    def __init__(self, uri = NEO4J_URI, user = NEO4J_USER, password = NEO4J_PASSWORD, database = NEO4J_DATABASE):
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self._driver = None

    #--------------------------------------------------------------------------
    # Connection Management
    #--------------------------------------------------------------------------

    def connect(self):
        """Establish connection to Neo4j."""
        if self._driver is not None:
            return

        try:
            self._driver = GraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )
            self._driver.verify_connectivity()
            print(f"[Neo4jStore] Connected to {self.uri}")
        except ServiceUnavailable:
            raise ConnectionError(
                f"[Neo4jStore] Cannot connect to Neo4j at {self.uri}. "
                "Make sure Neo4j is running (Neo4j Desktop or Docker)."
            )
        except AuthError:
            raise ConnectionError(
                f"[Neo4jStore] Authentication failed for user '{self.user}'. "
                "Check NEO4J_USER and NEO4J_PASSWORD environment variables."
            )

    def close(self):
        """Close the Neo4j connection."""
        if self._driver:
            self._driver.close()
            self._driver = None
            print("[Neo4jStore] Connection closed.")

    @contextmanager
    def session(self):
        """Context manager for Neo4j sessions."""
        self.connect()
        session = self._driver.session(database=self.database)
        try:
            yield session
        finally:
            session.close()

    def is_connected(self):
        """Check if Neo4j is reachable."""
        try:
            if self._driver is None:
                self.connect()
            self._driver.verify_connectivity()
            return True
        except Exception:
            return False

    #--------------------------------------------------------------------------
    # Schema Initialization
    #--------------------------------------------------------------------------

    def init_schema(self):
        """Create uniqueness constraints and indexes for all node types."""
        constraints = [
            ("Champion", "champion_id"),
            ("Ability", "ability_id"),
            ("Item", "item_id"),
            ("Rune", "rune_id"),
            ("Role", "name"),
            ("CrowdControl", "name"),
            ("Effect", "name"),
            ("Playstyle", "name"),
            ("PowerCurve", "name"),
            ("WinCondition", "name"),
        ]

        with self.session() as session:
            for label, prop in constraints:
                try:
                    session.run(
                        f"CREATE CONSTRAINT IF NOT EXISTS "
                        f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
                    )
                except Exception as e:
                    # Fallback for older Neo4j versions
                    try:
                        session.run(
                            f"CREATE CONSTRAINT ON (n:{label}) "
                            f"ASSERT n.{prop} IS UNIQUE"
                        )
                    except Exception:
                        print(f"[Neo4jStore] Warning: Could not create constraint for {label}.{prop}: {e}")

            # Full-text search index on Champion name + lore for fuzzy search
            try:
                session.run(
                    "CREATE FULLTEXT INDEX champion_search IF NOT EXISTS "
                    "FOR (n:Champion) ON EACH [n.name, n.short_lore, n.title]"
                )
            except Exception:
                pass

            try:
                session.run(
                    "CREATE FULLTEXT INDEX item_search IF NOT EXISTS "
                    "FOR (n:Item) ON EACH [n.name, n.description]"
                )
            except Exception:
                pass

        print("[Neo4jStore] Schema initialized with constraints and indexes.")

    def clear_database(self):
        """Remove all nodes and relationships. Use with caution."""
        with self.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        print("[Neo4jStore] Database cleared.")

    #--------------------------------------------------------------------------
    # Bulk Write Operations
    #--------------------------------------------------------------------------

    def bulk_create_nodes(self, nodes, batch_size = 500):
        """
        Bulk insert nodes using UNWIND for performance.
        Groups nodes by type and inserts each group in batches.
        """
        # Group by node type
        grouped: Dict[NodeType, List[Dict]] = {}
        for node in nodes:
            grouped.setdefault(node.node_type, []).append(
                {"id": node.node_id, **node.properties}
            )

        with self.session() as session:
            for node_type, items in grouped.items():
                label = node_type.value
                for i in range(0, len(items), batch_size):
                    batch = items[i : i + batch_size]
                    session.run(
                        f"UNWIND $batch AS props "
                        f"MERGE (n:{label} {{{self.id_key(node_type)}: props.id}}) "
                        f"SET n += props",
                        batch=batch,
                    )
                print(f"  Created {len(items)} {label} nodes")

    def bulk_create_edges(self, edges, batch_size = 500):
        """
        Bulk insert edges using UNWIND.
        Groups edges by type for efficient batch creation.
        """
        # Group by edge type
        grouped: Dict[EdgeType, List[Dict]] = {}
        for edge in edges:
            grouped.setdefault(edge.edge_type, []).append(
                {
                    "source": edge.source_id,
                    "target": edge.target_id,
                    **edge.properties,
                }
            )

        with self.session() as session:
            for edge_type, items in grouped.items():
                rel_name = edge_type.value
                src_label, tgt_label, src_key, tgt_key = self.edge_labels(edge_type)

                for i in range(0, len(items), batch_size):
                    batch = items[i : i + batch_size]
                    cypher = (
                        f"UNWIND $batch AS props "
                        f"MATCH (a:{src_label} {{{src_key}: props.source}}) "
                        f"MATCH (b:{tgt_label} {{{tgt_key}: props.target}}) "
                        f"MERGE (a)-[r:{rel_name}]->(b) "
                        f"SET r += props"
                    )
                    session.run(cypher, batch=batch)
                print(f"  Created {len(items)} {rel_name} edges")

    #--------------------------------------------------------------------------
    # Query API
    #--------------------------------------------------------------------------

    def get_node(self, node_id, node_type = None):
        """Get a single node by ID, optionally filtering by type."""
        with self.session() as session:
            if node_type:
                label = node_type.value
                id_key = self.id_key(node_type)
                result = session.run(
                    f"MATCH (n:{label} {{{id_key}: $nid}}) RETURN n",
                    nid=node_id,
                )
            else:
                # Try all major types
                result = session.run(
                    "MATCH (n) WHERE n.champion_id = $nid OR n.item_id = $nid "
                    "OR n.ability_id = $nid OR n.rune_id = $nid OR n.name = $nid "
                    "RETURN n LIMIT 1",
                    nid=node_id,
                )
            record = result.single()
            if record:
                return dict(record["n"])
        return None

    def get_neighbors(self, node_id, edge_type = None, direction = "out", limit = 50):
        """
        Get neighbors of a node, optionally filtered by edge type and direction.

        Args:
            node_id: The source node identifier.
            edge_type: Filter by specific relationship type.
            direction: 'out' (outgoing), 'in' (incoming), or 'both'.
            limit: Maximum number of neighbors to return.

        Returns:
            List of dicts with 'node' properties and 'edge' properties.
        """
        rel_filter = f":{edge_type.value}" if edge_type else ""

        if direction == "out":
            pattern = f"(a)-[r{rel_filter}]->(b)"
        elif direction == "in":
            pattern = f"(a)<-[r{rel_filter}]-(b)"
        else:
            pattern = f"(a)-[r{rel_filter}]-(b)"

        cypher = (
            f"MATCH {pattern} "
            f"WHERE a.champion_id = $nid OR a.item_id = $nid "
            f"OR a.ability_id = $nid OR a.rune_id = $nid OR a.name = $nid "
            f"RETURN b, type(r) AS rel_type, properties(r) AS rel_props "
            f"LIMIT $limit"
        )

        results = []
        with self.session() as session:
            records = session.run(cypher, nid=node_id, limit=limit)
            for record in records:
                results.append({
                    "node": dict(record["b"]),
                    "rel_type": record["rel_type"],
                    "rel_props": dict(record["rel_props"]) if record["rel_props"] else {},
                })
        return results

    def get_subgraph(self, node_id, max_depth = 2, max_nodes = 50):
        """
        Extract a k-hop subgraph around a node.

        Returns:
            Dict with 'center', 'nodes', and 'edges' keys.
        """
        cypher = (
            f"MATCH (center) "
            f"WHERE center.champion_id = $nid OR center.name = $nid "
            f"OR center.item_id = $nid "
            f"CALL apoc.path.subgraphAll(center, {{maxLevel: $depth}}) "
            f"YIELD nodes, relationships "
            f"RETURN nodes[..{max_nodes}] AS nodes, relationships AS edges"
        )

        # Fallback without APOC (more compatible)
        fallback_cypher = (
            f"MATCH path = (center)-[*1..{max_depth}]-(neighbor) "
            f"WHERE center.champion_id = $nid OR center.name = $nid "
            f"OR center.item_id = $nid "
            f"WITH center, collect(DISTINCT neighbor)[..{max_nodes}] AS neighbors, "
            f"collect(DISTINCT relationships(path)) AS all_rels "
            f"RETURN center, neighbors, all_rels"
        )

        with self.session() as session:
            try:
                result = session.run(cypher, nid=node_id, depth=max_depth)
                record = result.single()
                if record:
                    return {
                        "nodes": [dict(n) for n in record["nodes"]],
                        "edges": [
                            {
                                "type": type(r).__name__,
                                "source": dict(r.start_node),
                                "target": dict(r.end_node),
                                "props": dict(r),
                            }
                            for r in record["edges"]
                        ],
                    }
            except Exception:
                # APOC not available, use fallback
                pass

            result = session.run(fallback_cypher, nid=node_id)
            record = result.single()
            if record:
                center = dict(record["center"])
                neighbors = [dict(n) for n in record["neighbors"]]
                return {
                    "center": center,
                    "nodes": [center] + neighbors,
                    "edges": [],
                }

        return {"nodes": [], "edges": []}

    def find_path(self, source_id, target_id, max_depth = 4):
        """Find shortest path between two nodes."""
        cypher = (
            f"MATCH (a), (b), "
            f"path = shortestPath((a)-[*..{max_depth}]-(b)) "
            f"WHERE (a.champion_id = $src OR a.name = $src OR a.item_id = $src) "
            f"AND (b.champion_id = $tgt OR b.name = $tgt OR b.item_id = $tgt) "
            f"RETURN [n IN nodes(path) | properties(n)] AS path_nodes, "
            f"[r IN relationships(path) | type(r)] AS path_rels"
        )

        with self.session() as session:
            result = session.run(cypher, src=source_id, tgt=target_id)
            record = result.single()
            if record:
                return {
                    "nodes": record["path_nodes"],
                    "relationships": record["path_rels"],
                }
        return {"nodes": [], "relationships": []}

    def run_cypher(self, query, **params):
        """Execute an arbitrary Cypher query and return results as list of dicts."""
        with self.session() as session:
            result = session.run(query, **params)
            return [dict(record) for record in result]

    def get_stats(self):
        """Get graph statistics (node counts by label, edge counts by type)."""
        stats = {}
        with self.session() as session:
            # Node counts
            result = session.run(
                "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt "
                "ORDER BY cnt DESC"
            )
            stats["nodes"] = {r["label"]: r["cnt"] for r in result}

            # Edge counts
            result = session.run(
                "MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS cnt "
                "ORDER BY cnt DESC"
            )
            stats["edges"] = {r["rel_type"]: r["cnt"] for r in result}

            # Totals
            stats["total_nodes"] = sum(stats["nodes"].values())
            stats["total_edges"] = sum(stats["edges"].values())

        return stats

    #--------------------------------------------------------------------------
    # Internal Helpers
    #--------------------------------------------------------------------------

    @staticmethod
    def id_key(node_type):
        """Return the primary key property name for a node type."""
        mapping = {
            NodeType.CHAMPION: "champion_id",
            NodeType.ABILITY: "ability_id",
            NodeType.ITEM: "item_id",
            NodeType.RUNE: "rune_id",
        }
        return mapping.get(node_type, "name")

    @staticmethod
    def edge_labels(edge_type):
        """
        Return (source_label, target_label, source_key, target_key) for an edge type.
        """
        mapping = {
            EdgeType.HAS_ABILITY: ("Champion", "Ability", "champion_id", "ability_id"),
            EdgeType.HAS_ROLE: ("Champion", "Role", "champion_id", "name"),
            EdgeType.HAS_CC: ("Champion", "CrowdControl", "champion_id", "name"),
            EdgeType.HAS_EFFECT: ("Champion", "Effect", "champion_id", "name"),
            EdgeType.HAS_PLAYSTYLE: ("Champion", "Playstyle", "champion_id", "name"),
            EdgeType.HAS_POWER_CURVE: ("Champion", "PowerCurve", "champion_id", "name"),
            EdgeType.HAS_WIN_CONDITION: ("Champion", "WinCondition", "champion_id", "name"),
            EdgeType.COUNTERS: ("Champion", "Champion", "champion_id", "champion_id"),
            EdgeType.SYNERGIZES_WITH: ("Champion", "Champion", "champion_id", "champion_id"),
            EdgeType.USES_ITEM: ("Champion", "Item", "champion_id", "item_id"),
            EdgeType.USES_RUNE: ("Champion", "Rune", "champion_id", "rune_id"),
            EdgeType.BUILDS_FROM: ("Item", "Item", "item_id", "item_id"),
            EdgeType.BUILDS_INTO: ("Item", "Item", "item_id", "item_id"),
            EdgeType.ABILITY_HAS_CC: ("Ability", "CrowdControl", "ability_id", "name"),
            EdgeType.ABILITY_HAS_EFFECT: ("Ability", "Effect", "ability_id", "name"),
        }
        return mapping.get(
            edge_type,
            ("Champion", "Champion", "champion_id", "champion_id"),
        )


#-----------------------------------------------------------------------------
# Singleton
#-----------------------------------------------------------------------------

_store_instance: Optional[Neo4jStore] = None


def get_graph_store():
    """Get or create singleton Neo4jStore instance."""
    global _store_instance
    if _store_instance is None:
        _store_instance = Neo4jStore()
    return _store_instance
