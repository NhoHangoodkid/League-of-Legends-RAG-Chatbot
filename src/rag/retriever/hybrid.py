"""
Hybrid Retriever for LoL Knowledge Bot.

Fuses results from Graph Retriever and Vector Retriever using
Reciprocal Rank Fusion (RRF) for robust, multi-source retrieval.
"""

import sys
from pathlib import Path

# Ensure src/ is on path
src_dir = Path(__file__).resolve().parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from rag.retriever.graph_retriever import GraphRetriever
from rag.retriever.vector_retriever import VectorRetriever

intent_chunk_types = {
    "COUNTER_QUERY": "counter",
    "SYNERGY_QUERY": "synergy",
    "BUILD_QUERY": "build",
    "SKILL_INFO": "ability",
    "SKILL_DAMAGE_AT_LEVEL": "ability",
    "SKILL_COOLDOWN": "ability",
    "LIST_SKILLS": "ability",
    "ITEM_INFO": "item_info",
    "RUNE_INFO": "rune_info",
    "LORE_QUERY": "lore",
    "CHAMPION_INFO": "overview",
    "CHAMPION_BASE_STATS": "stats",
    "CHAMPION_STATS_AT_LEVEL": "stats",
    "CHAMPION_COMPARISON": "overview",
    "TEAM_COUNTER_ANALYSIS": "composition",
    "COMPOSITION_QUERY": "composition",
    "ROLE_COUNTER_PICK": "role_guide",
    "ROLE_QUERY": "role_guide",
    "TEAM_COMPOSITION_BUILDING": "composition",
}

incompatible_chunk_types = {
    "LORE_QUERY": ["stats", "build"],
    "COUNTER_QUERY": ["build"],
    "ABILITY_MECHANIC_QUERY": ["build", "stats", "synergy"],
    "ROLE_COUNTER_PICK": ["build"],
}


class HybridRetriever:
    """Combines Graph-based and Vector-based retrieval using Reciprocal Rank Fusion."""

    def __init__(self, graph_retriever = None, vector_retriever = None, rrf_k = 60):
        self.graph_retriever = graph_retriever
        self.vector_retriever = vector_retriever
        self.rrf_k = rrf_k

    def retrieve(self, query, entities = None, intent = None, graph_top_k = 10, vector_top_k = 10, final_top_k = 10):
        """Perform hybrid retrieval with RRF fusion."""
        entities = entities or {}
        graph_results = []
        vector_results = []

        if self.graph_retriever:
            try:
                graph_results = self.graph_retriever.retrieve(
                    query=query,
                    entities=entities,
                    intent=intent,
                    max_results=graph_top_k,
                )
            except Exception as e:
                print(f"[HybridRetriever] Graph retrieval error: {e}")

        if self.vector_retriever:
            try:
                vector_results = self.vector_retriever.retrieve(
                    query=query,
                    top_k=vector_top_k,
                    entity_name=entities.get("champion_name"),
                    preferred_chunk_type=intent_chunk_types.get(intent),
                    excluded_chunk_types=incompatible_chunk_types.get(intent),
                )
            except Exception as e:
                print(f"[HybridRetriever] Vector retrieval error: {e}")

        if not graph_results and not vector_results:
            return []
        if not graph_results:
            return vector_results[:final_top_k]
        if not vector_results:
            return graph_results[:final_top_k]

        fused = self.rrf_fusion(
            ranked_lists=[graph_results, vector_results],
            k=self.rrf_k,
        )

        return fused[:final_top_k]

    def rrf_fusion(self, ranked_lists, k = 60):
        """Reciprocal Rank Fusion of multiple ranked result lists."""
        score_map = {}

        for list_idx, results in enumerate(ranked_lists):
            for rank, ctx in enumerate(results, start=1):
                text = ctx.get("text", "")
                text_key = text[:200]

                if text_key not in score_map:
                    score_map[text_key] = {
                        "context": ctx,
                        "rrf_score": 0.0,
                        "sources": [],
                    }

                score_map[text_key]["rrf_score"] += 1.0 / (k + rank)
                score_map[text_key]["sources"].append(f"list_{list_idx}:rank_{rank}")

        sorted_items = sorted(
            score_map.values(),
            key=lambda x: x["rrf_score"],
            reverse=True,
        )

        fused = []
        for item in sorted_items:
            ctx = item["context"].copy()
            ctx["score"] = item["rrf_score"]
            ctx["metadata"] = {
                **ctx.get("metadata", {}),
                "rrf_sources": item["sources"],
            }
            fused.append(ctx)

        return fused
