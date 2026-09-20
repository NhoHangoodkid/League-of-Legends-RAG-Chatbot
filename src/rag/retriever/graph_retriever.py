"""
Graph-based Retriever for LoL Knowledge Bot.

Performs entity linking from the query to graph nodes, then uses
intent-driven graph traversal to collect structured context.
"""

import sys
from pathlib import Path

# Ensure src/ is on path
src_dir = Path(__file__).resolve().parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

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

    def __init__(self, store = None):
        self.store = store or get_graph_store()
        self.traversal = GraphTraversal(self.store)
        self._champ_cache = None

    def get_champ_cache(self):
        if self._champ_cache is None:
            try:
                cypher = "MATCH (c:Champion) RETURN c.champion_id AS id, c.name AS name"
                rows = self.store.run_cypher(cypher)
                # Sort by length descending to match multi-word names first
                self._champ_cache = sorted(
                    [(r["name"], r["id"]) for r in rows if r.get("name")],
                    key=lambda x: len(x[0]),
                    reverse=True,
                )
            except Exception:
                self._champ_cache = []
        return self._champ_cache

    def detect_champion_in_text(self, text):
        """Extract champion mentioned in raw query string."""
        if not text:
            return None
        import re
        cleaned = re.sub(r"[^\w\s]", " ", text)
        t_lower = f" {cleaned.lower()} "
        for name, cid in self.get_champ_cache():
            n_lower = f" {name.lower()} "
            if n_lower in t_lower or f" {cid.lower()} " in t_lower:
                return cid
        return None

    def retrieve(self, query, entities = None, intent = None, max_results = 10):
        """Retrieve context from the Knowledge Graph."""
        entities = entities or {}
        resolved = self.resolve_entities(entities)
        merged = {**entities, **resolved}

        if not merged.get("champion_name") and query:
            detected = self.detect_champion_in_text(query)
            if detected:
                merged["champion_name"] = detected

        contexts = self.traversal.retrieve_context(
            entities=merged,
            intent=intent,
            max_results = max_results,
        )
        return contexts

    def resolve_entities(self, entities):
        """Resolve entity names to canonical graph node IDs via fuzzy matching."""
        resolved = {}

        champ_name = entities.get("champion_name") or entities.get("champion")
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

        inter_champ = entities.get("interaction_champion")
        if inter_champ:
            canonical = self.find_champion_id(inter_champ)
            if canonical:
                resolved["interaction_champion"] = canonical

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
