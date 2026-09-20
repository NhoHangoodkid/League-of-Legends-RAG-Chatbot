"""
Neo4j Graph Store for LoL Knowledge Bot.

Manages the Neo4j connection, schema initialization, bulk loading,
and provides a high-level query API for graph operations.
"""

import json
import os
from contextlib import contextmanager

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

from rag.graph.schema import EdgeType, NodeType, GraphNode, GraphEdge

load_dotenv()

neo4j_uri = os.getenv("NEO4J_URI") or os.getenv("neo4j_uri") or "bolt://127.0.0.1:7687"
neo4j_user = os.getenv("NEO4J_USER") or os.getenv("neo4j_user") or "neo4j"
neo4j_password = os.getenv("NEO4J_PASSWORD") or os.getenv("neo4j_password") or ""
neo4j_database = os.getenv("NEO4J_DATABASE") or os.getenv("neo4j_database") or "neo4j"


class Neo4jStore:
    """Neo4j-backed Knowledge Graph Store."""

    def __init__(self, uri = neo4j_uri, user = neo4j_user, password = neo4j_password, database = neo4j_database):
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self.driver = None

    def connect(self):
        """Establish connection to Neo4j."""
        if self.driver is not None:
            return

        try:
            self.driver = GraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )
            self.driver.verify_connectivity()
            print(f"[Neo4jStore] Connected to {self.uri}")
        except ServiceUnavailable:
            raise ConnectionError(
                f"[Neo4jStore] Cannot connect to Neo4j at {self.uri}. "
                "Make sure Neo4j is running."
            )
        except AuthError:
            raise ConnectionError(
                f"[Neo4jStore] Authentication failed for user '{self.user}'. "
                "Check neo4j_user and neo4j_password environment variables."
            )

    def close(self):
        """Close the Neo4j connection."""
        if self.driver:
            self.driver.close()
            self.driver = None
            print("[Neo4jStore] Connection closed.")

    @contextmanager
    def session(self):
        """Context manager for Neo4j sessions."""
        self.connect()
        sess = self.driver.session(database=self.database)
        try:
            yield sess
        finally:
            sess.close()

    def is_connected(self):
        """Check if Neo4j is reachable."""
        try:
            if self.driver is None:
                self.connect()
            self.driver.verify_connectivity()
            return True
        except Exception:
            return False

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
            ("Chunk", "chunk_id"),
        ]

        with self.session() as sess:
            for label, prop in constraints:
                try:
                    sess.run(
                        f"CREATE CONSTRAINT IF NOT EXISTS "
                        f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
                    )
                except Exception as e:
                    try:
                        sess.run(
                            f"CREATE CONSTRAINT ON (n:{label}) "
                            f"ASSERT n.{prop} IS UNIQUE"
                        )
                    except Exception:
                        print(f"[Neo4jStore] Warning: Could not create constraint for {label}.{prop}: {e}")

            try:
                sess.run(
                    "CREATE FULLTEXT INDEX champion_search IF NOT EXISTS "
                    "FOR (n:Champion) ON EACH [n.name, n.short_lore, n.title]"
                )
            except Exception:
                pass

            try:
                sess.run(
                    "CREATE FULLTEXT INDEX item_search IF NOT EXISTS "
                    "FOR (n:Item) ON EACH [n.name, n.description]"
                )
            except Exception:
                pass

        print("[Neo4jStore] Schema initialized with constraints and indexes.")

    def clear_database(self):
        """Remove all nodes and relationships."""
        with self.session() as sess:
            sess.run("MATCH (n) DETACH DELETE n")
        print("[Neo4jStore] Database cleared.")

    def bulk_create_nodes(self, nodes, batch_size = 500):
        """Insert nodes in batches."""
        grouped = {}
        for node in nodes:
            grouped.setdefault(node.node_type, []).append(
                {"id": node.node_id, **node.properties}
            )

        with self.session() as sess:
            for node_type, items in grouped.items():
                label = node_type.value
                id_key = self.id_key(node_type)
                for i in range(0, len(items), batch_size):
                    batch = items[i : i + batch_size]
                    cypher = (
                        f"UNWIND $batch AS props "
                        f"MERGE (n:{label} {{{id_key}: props.id}}) "
                        f"SET n += props"
                    )
                    sess.run(cypher, batch=batch)
                print(f"  Created {len(items)} {label} nodes")

    def bulk_create_edges(self, edges, batch_size = 500):
        """Bulk insert edges using UNWIND."""
        grouped = {}
        for edge in edges:
            grouped.setdefault(edge.edge_type, []).append(
                {
                    "source": edge.source_id,
                    "target": edge.target_id,
                    **edge.properties,
                }
            )

        with self.session() as sess:
            for edge_type, items in grouped.items():
                rel_name = edge_type.value
                src_label, tgt_label, src_key, tgt_key = self.edge_labels(edge_type)

                for i in range(0, len(items), batch_size):
                    batch = items[i : i + batch_size]
                    if edge_type == EdgeType.USES_ITEM:
                        cypher = (
                            f"UNWIND $batch AS props "
                            f"MATCH (a:Champion {{champion_id: props.source}}) "
                            f"MATCH (b:Item) WHERE b.item_id = props.target OR b.name = props.target "
                            f"MERGE (a)-[r:{rel_name}]->(b) "
                            f"SET r += props"
                        )
                    elif edge_type == EdgeType.USES_RUNE:
                        cypher = (
                            f"UNWIND $batch AS props "
                            f"MATCH (a:Champion {{champion_id: props.source}}) "
                            f"MATCH (b:Rune) WHERE b.rune_id = props.target OR b.name = props.target "
                            f"MERGE (a)-[r:{rel_name}]->(b) "
                            f"SET r += props"
                        )
                    else:
                        cypher = (
                            f"UNWIND $batch AS props "
                            f"MATCH (a:{src_label} {{{src_key}: props.source}}) "
                            f"MATCH (b:{tgt_label} {{{tgt_key}: props.target}}) "
                            f"MERGE (a)-[r:{rel_name}]->(b) "
                            f"SET r += props"
                        )
                    sess.run(cypher, batch=batch)
                print(f"  Created {len(items)} {rel_name} edges")

    def get_node(self, node_id, node_type = None):
        """Get a single node by ID, optionally filtering by type."""
        with self.session() as sess:
            if node_type:
                label = node_type.value
                id_key = self.id_key(node_type)
                result = sess.run(
                    f"MATCH (n:{label} {{{id_key}: $nid}}) RETURN n",
                    nid=node_id,
                )
            else:
                result = sess.run(
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
        """Get neighbors of a node, optionally filtered by edge type and direction."""
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
        with self.session() as sess:
            records = sess.run(cypher, nid=node_id, limit=limit)
            for record in records:
                results.append({
                    "node": dict(record["b"]),
                    "rel_type": record["rel_type"],
                    "rel_props": dict(record["rel_props"]) if record["rel_props"] else {},
                })
        return results

    def get_subgraph(self, node_id, max_depth = 2, max_nodes = 50):
        """Extract a k-hop subgraph around a node."""
        fallback_cypher = (
            f"MATCH path = (center)-[*1..{max_depth}]-(neighbor) "
            f"WHERE center.champion_id = $nid OR center.name = $nid "
            f"OR center.item_id = $nid "
            f"WITH center, collect(DISTINCT neighbor)[..{max_nodes}] AS neighbors, "
            f"collect(DISTINCT relationships(path)) AS all_rels "
            f"RETURN center, neighbors, all_rels"
        )

        with self.session() as sess:
            result = sess.run(fallback_cypher, nid=node_id)
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

        with self.session() as sess:
            result = sess.run(cypher, src=source_id, tgt=target_id)
            record = result.single()
            if record:
                return {
                    "nodes": record["path_nodes"],
                    "relationships": record["path_rels"],
                }
        return {"nodes": [], "relationships": []}

    def run_cypher(self, query, **params):
        """Execute an arbitrary Cypher query and return results as list of dicts."""
        with self.session() as sess:
            result = sess.run(query, **params)
            return [dict(record) for record in result]

    def get_stats(self):
        """Get graph statistics."""
        stats = {}
        with self.session() as sess:
            result = sess.run(
                "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt "
                "ORDER BY cnt DESC"
            )
            stats["nodes"] = {r["label"]: r["cnt"] for r in result}

            result = sess.run(
                "MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS cnt "
                "ORDER BY cnt DESC"
            )
            stats["edges"] = {r["rel_type"]: r["cnt"] for r in result}

            stats["total_nodes"] = sum(stats["nodes"].values())
            stats["total_edges"] = sum(stats["edges"].values())

        return stats

    @staticmethod
    def id_key(node_type):
        """Return the primary key property name for a node type."""
        mapping = {
            NodeType.CHAMPION: "champion_id",
            NodeType.ABILITY: "ability_id",
            NodeType.ITEM: "item_id",
            NodeType.RUNE: "rune_id",
            NodeType.CHUNK: "chunk_id",
        }
        return mapping.get(node_type, "name")

    @staticmethod
    def edge_labels(edge_type):
        """Return (source_label, target_label, source_key, target_key) for an edge type."""
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
            EdgeType.HAS_CHUNK: ("Champion", "Chunk", "champion_id", "chunk_id"),
        }
        return mapping.get(
            edge_type,
            ("Champion", "Champion", "champion_id", "champion_id"),
        )


store_instance = None


def get_graph_store():
    """Get or create singleton Neo4jStore instance."""
    global store_instance
    if store_instance is None:
        store_instance = Neo4jStore()
    return store_instance
