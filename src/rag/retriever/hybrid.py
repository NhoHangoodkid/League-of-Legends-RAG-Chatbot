"""
Hybrid Retriever for LoL Knowledge Bot.

Fuses results from Graph Retriever and Vector Retriever using
Reciprocal Rank Fusion (RRF) for robust, multi-source retrieval.
"""

from typing import Any, Dict, List, Optional

from rag.retriever.graph_retriever import GraphRetriever
from rag.retriever.vector_retriever import VectorRetriever


class HybridRetriever:
    """
    Combines Graph-based and Vector-based retrieval using Reciprocal Rank Fusion.

    RRF Formula:
        score(d) = Σ  1 / (k + rank_i(d))
                  i∈{graph, vector}

    where k is a constant (default 60) that controls the impact of
    high-ranked vs low-ranked results.

    Benefits over single-source retrieval:
    - Graph captures structured relationships (counters, builds, etc.)
    - Vector captures semantic similarity (fuzzy queries, descriptions)
    - RRF fusion is robust and parameter-free (no learned weights)
    """

    def __init__(self, graph_retriever = None, vector_retriever = None, rrf_k = 60):
        """
        Args:
            graph_retriever: Graph-based retriever instance.
            vector_retriever: Vector-based retriever instance.
            rrf_k: RRF constant (higher = more equal weighting).
        """
        self.graph_retriever = graph_retriever
        self.vector_retriever = vector_retriever
        self.rrf_k = rrf_k

    def retrieve(self, query, entities, intent, graph_top_k = 10, vector_top_k = 10, final_top_k = 10):
        """
        Perform hybrid retrieval with RRF fusion.

        Args:
            query: User query text.
            entities: Extracted entities from intent classifier.
            intent: Classified intent string.
            graph_top_k: Max results from graph retriever.
            vector_top_k: Max results from vector retriever.
            final_top_k: Max results after fusion.

        Returns:
            Fused list of context dicts sorted by RRF score.
        """
        graph_results = []
        vector_results = []

        # Graph retrieval
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

        # Vector retrieval
        if self.vector_retriever:
            try:
                vector_results = self.vector_retriever.retrieve(
                    query=query,
                    top_k=vector_top_k,
                )
            except Exception as e:
                print(f"[HybridRetriever] Vector retrieval error: {e}")

        # If only one source returned results, return those directly
        if not graph_results and not vector_results:
            return []
        if not graph_results:
            return vector_results[:final_top_k]
        if not vector_results:
            return graph_results[:final_top_k]

        # RRF Fusion
        fused = self.rrf_fusion(
            ranked_lists=[graph_results, vector_results],
            k=self.rrf_k,
        )

        return fused[:final_top_k]

    def rrf_fusion(self, ranked_lists, k = 60):
        """
        Reciprocal Rank Fusion of multiple ranked result lists.

        For each document d appearing in any list:
            rrf_score(d) = Σ  1 / (k + rank_i(d))

        where rank_i(d) is the 1-based rank of d in list i.

        Args:
            ranked_lists: List of ranked result lists.
            k: RRF constant.

        Returns:
            Fused list sorted by RRF score (descending).
        """
        # score_map: text_hash → {rrf_score, context_dict}
        score_map: Dict[str, Dict[str, Any]] = {}

        for list_idx, results in enumerate(ranked_lists):
            for rank, ctx in enumerate(results, start=1):
                # Use text hash as dedup key
                text = ctx.get("text", "")
                text_key = text[:200]  # First 200 chars as key

                if text_key not in score_map:
                    score_map[text_key] = {
                        "context": ctx,
                        "rrf_score": 0.0,
                        "sources": [],
                    }

                # Add RRF contribution
                score_map[text_key]["rrf_score"] += 1.0 / (k + rank)
                score_map[text_key]["sources"].append(
                    f"list_{list_idx}:rank_{rank}"
                )

        # Sort by RRF score
        fused = sorted(
            score_map.values(),
            key=lambda x: x["rrf_score"],
            reverse=True,
        )

        # Return context dicts with RRF score attached
        results = []
        for item in fused:
            ctx = item["context"].copy()
            ctx["rrf_score"] = item["rrf_score"]
            ctx["fusion_sources"] = item["sources"]
            results.append(ctx)

        return results
