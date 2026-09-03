"""
RAG Pipeline Orchestrator for LoL Knowledge Bot.

End-to-end pipeline: Query → Intent → Hybrid Retrieval → Re-ranking → Context.

This is the main entry point for the RAG system, combining:
- Graph Retriever (Neo4j Knowledge Graph)
- Vector Retriever (FAISS + BGE embeddings)
- Hybrid Fusion (Reciprocal Rank Fusion)
- Cross-Encoder Re-ranking
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure src/ is on path
SRC_DIR = Path(__file__).resolve().parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rag.graph.store import Neo4jStore, get_graph_store
from rag.retriever.graph_retriever import GraphRetriever
from rag.retriever.vector_retriever import VectorRetriever
from rag.retriever.hybrid import HybridRetriever
from rag.retriever.reranker import CrossEncoderReranker
from rag.vector.embeddings import EmbeddingModel, get_embedding_model
from rag.vector.store import VectorStore


# Default paths
SRC_DIR = Path(__file__).resolve().parent.parent
DEFAULT_INDEX_DIR = SRC_DIR / "data" / "vector_index"


class RAGPipeline:
    """
    End-to-end RAG pipeline orchestrator.

    Architecture:
        Query → [Graph Retriever] ─┐
                                    ├→ [Hybrid RRF Fusion] → [Cross-Encoder Reranker] → Context
        Query → [Vector Retriever] ─┘

    Usage:
        pipeline = RAGPipeline()
        context = pipeline.retrieve(query, entities, intent)
        # context is a list of ranked passage dicts
    """

    def __init__(self, graph_store = None, embedding_model = None, vector_store = None, index_dir = str(DEFAULT_INDEX_DIR), enable_graph = True, enable_vector = True, enable_reranker = True, rrf_k = 60):
        """
        Args:
            graph_store: Neo4j store instance.
            embedding_model: Embedding model instance.
            vector_store: FAISS store instance.
            index_dir: Directory containing FAISS index.
            enable_graph: Whether to use graph retrieval.
            enable_vector: Whether to use vector retrieval.
            enable_reranker: Whether to use cross-encoder re-ranking.
            rrf_k: RRF fusion constant.
        """
        self.enable_graph = enable_graph
        self.enable_vector = enable_vector
        self.enable_reranker = enable_reranker

        # Initialize components
        graph_retriever = None
        vector_retriever = None

        if enable_graph:
            try:
                store = graph_store or get_graph_store()
                if store.is_connected():
                    graph_retriever = GraphRetriever(store)
                    print("[RAGPipeline] Graph retriever: ENABLED")
                else:
                    print("[RAGPipeline] Graph retriever: DISABLED (Neo4j not connected)")
                    self.enable_graph = False
            except Exception as e:
                print(f"[RAGPipeline] Graph retriever: DISABLED ({e})")
                self.enable_graph = False

        if enable_vector:
            try:
                emb_model = embedding_model or get_embedding_model()
                if vector_store:
                    vstore = vector_store
                else:
                    vstore = VectorStore(dimension=emb_model.get_dimension(), use_gpu = True)
                    idx_path = Path(index_dir)
                    if (idx_path / "faiss.index").exists():
                        vstore.load(index_dir)
                    else:
                        print(f"[RAGPipeline] WARNING: No FAISS index at {index_dir}")

                vector_retriever = VectorRetriever(
                    vector_store=vstore,
                    embedding_model=emb_model,
                )
                print(f"[RAGPipeline] Vector retriever: ENABLED ({len(vstore)} vectors)")
            except Exception as e:
                print(f"[RAGPipeline] Vector retriever: DISABLED ({e})")
                self.enable_vector = False

        # Hybrid retriever
        self.hybrid = HybridRetriever(
            graph_retriever=graph_retriever,
            vector_retriever=vector_retriever,
            rrf_k=rrf_k,
        )

        # Re-ranker (lazy loaded)
        self.reranker = None
        if enable_reranker:
            try:
                self.reranker = CrossEncoderReranker()
                print("[RAGPipeline] Re-ranker: ENABLED (lazy loaded)")
            except Exception as e:
                print(f"[RAGPipeline] Re-ranker: DISABLED ({e})")

    def retrieve(self, query, entities, intent, graph_top_k = 10, vector_top_k = 10, rerank_top_k = 5):
        """
        Full RAG retrieval pipeline.

        Steps:
        1. Hybrid retrieval (Graph + Vector with RRF fusion)
        2. Cross-encoder re-ranking (if enabled)
        3. Return ranked context passages

        Args:
            query: User query text.
            entities: Extracted entities from intent classifier.
            intent: Classified intent string.
            graph_top_k: Max graph results before fusion.
            vector_top_k: Max vector results before fusion.
            rerank_top_k: Max results after re-ranking.

        Returns:
            List of context dicts sorted by relevance, each containing:
            - text: The passage text
            - source: Origin (graph/vector)
            - score: Retrieval score
            - metadata: Additional info
        """
        # Step 1: Hybrid retrieval
        candidates = self.hybrid.retrieve(
            query=query,
            entities=entities,
            intent=intent,
            graph_top_k=graph_top_k,
            vector_top_k=vector_top_k,
            final_top_k=rerank_top_k * 3,  # Get more candidates for re-ranking
        )

        if not candidates:
            return []

        # Step 2: Re-ranking
        if self.reranker and self.enable_reranker and len(candidates) > 1:
            try:
                candidates = self.reranker.rerank(
                    query=query,
                    candidates=candidates,
                    top_k=rerank_top_k,
                )
            except Exception as e:
                print(f"[RAGPipeline] Re-ranker error: {e}. Using fusion scores.")
                candidates = candidates[:rerank_top_k]
        else:
            candidates = candidates[:rerank_top_k]

        return candidates

    def format_context_for_llm(self, contexts):
        """
        Format retrieved contexts into a single string for LLM consumption.

        Produces a numbered list of relevant passages that the LLM
        can reference when generating its response.
        """
        if not contexts:
            return "Không tìm thấy thông tin liên quan."

        parts = []
        for i, ctx in enumerate(contexts, 1):
            source = ctx.get("source", "unknown")
            text = ctx.get("text", "")
            parts.append(f"[Nguồn {i} — {source}]\n{text}")

        return "\n\n".join(parts)

    def get_status(self):
        """Return pipeline component status."""
        return {
            "graph_enabled": self.enable_graph,
            "vector_enabled": self.enable_vector,
            "reranker_enabled": self.enable_reranker and self.reranker is not None,
        }


#-----------------------------------------------------------------------------
# Singleton
#-----------------------------------------------------------------------------

_pipeline_instance: Optional[RAGPipeline] = None


def get_rag_pipeline(**kwargs):
    """Get or create singleton RAGPipeline instance."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = RAGPipeline(**kwargs)
    return _pipeline_instance
