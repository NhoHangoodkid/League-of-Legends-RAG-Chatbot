"""
Graph-based Retriever for LoL Knowledge Bot.

Performs entity linking from the query to graph nodes, then uses
intent-driven graph traversal to collect structured context.
"""

import sys
from pathlib import Path

# Ensure src/ is on path
SRC_DIR = Path(__file__).resolve().parent.parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rag.graph.store import Neo4jStore, get_graph_store
from rag.graph.traversal import GraphTraversal


class GraphRetriever:
    """
    Retrieves context from the Knowledge Graph.

    Pipeline:
    1. Entity linking - resolve champion/item/rune names to graph node IDs
    2. Intent-based traversal - use GraphTraversal strategies
    3. Context formatting - return standardized context dicts
    """

    def __init__(self, store=None):
        self.store = store or get_graph_store()
        self.traversal = GraphTraversal(self.store)

    def retrieve(self, query, entities=None, intent=None, max_results=10):
        """Retrieve context from the Knowledge Graph."""
        entities = entities or {}
        resolved = self.resolve_entities(entities)
        merged = {**entities, **resolved}

        contexts = self.traversal.retrieve_context(
            entities=merged,
            intent=intent,
            max_results=max_results,
        )
        return contexts

    def resolve_entities(self, entities):
        """Resolve entity names to canonical graph node IDs via fuzzy matching."""
        resolved = {}

        champ_name = entities.get("champion_name")
        if champ_name:
            canonical = self.find_champion_id(champ_name)
            if canonical:
                resolved["champion_name"] = canonical

        comp_champs = entities.get("comparison_champions", [])
        if comp_champs:
            resolved["comparison_champions"] = [
                self.find_champion_id(c) or c for c in comp_champs if c
            ]

        enemy_champs = entities.get("enemy_champions", [])
        if enemy_champs:
            resolved["enemy_champions"] = [
                self.find_champion_id(c) or c for c in enemy_champs if c
            ]

        return resolved

    def find_champion_id(self, name):
        """Find canonical champion ID from name via graph lookup."""
        if not name:
            return None

        try:
            cypher = """
            MATCH (c:Champion)
            WHERE c.champion_id = $name
               OR toLower(c.name) = toLower($name)
               OR toLower(c.champion_id) = toLower($name)
            RETURN c.champion_id AS id
            LIMIT 1
            """
            results = self.store.run_cypher(cypher, name=name)
            if results:
                return results[0]["id"]

            cypher_fuzzy = """
            MATCH (c:Champion)
            WHERE toLower(c.name) CONTAINS toLower($name)
               OR toLower(c.champion_id) CONTAINS toLower($name)
            RETURN c.champion_id AS id
            LIMIT 1
            """
            results = self.store.run_cypher(cypher_fuzzy, name=name)
            if results:
                return results[0]["id"]

        except Exception:
            pass

        return None
