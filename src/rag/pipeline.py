"""
RAG Pipeline Orchestrator for LoL Knowledge Bot.

End-to-end pipeline: Query -> Intent -> Hybrid Retrieval -> Re-ranking -> Context.

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

# Ensure src/ is on path
src_dir = Path(__file__).resolve().parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from rag.graph.store import Neo4jStore, get_graph_store
from rag.retriever.graph_retriever import GraphRetriever
from rag.retriever.vector_retriever import VectorRetriever
from rag.retriever.hybrid import HybridRetriever
from rag.retriever.reranker import CrossEncoderReranker
from rag.vector.embeddings import EmbeddingModel, get_embedding_model
from rag.vector.store import VectorStore

default_index_dir = src_dir / "data" / "vector_index"


class RAGPipeline:
    """
    End-to-end RAG pipeline orchestrator.

    Architecture:
        Query -> [Graph Retriever] -+
                                    +-> [Hybrid RRF Fusion] -> [Cross-Encoder Reranker] -> Context
        Query -> [Vector Retriever] -+
    """

    def __init__(self, graph_store=None, embedding_model=None, vector_store=None, index_dir=str(default_index_dir), enable_graph = True, enable_vector = True, enable_reranker = True, rrf_k=60):
        self.enable_graph = enable_graph
        self.enable_vector = enable_vector
        self.enable_reranker = enable_reranker

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
                    vstore = VectorStore(dimension=emb_model.get_dimension(), use_gpu=True)
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

        self.hybrid = HybridRetriever(
            graph_retriever=graph_retriever,
            vector_retriever=vector_retriever,
            rrf_k=rrf_k,
        )

        self.reranker = None
        if enable_reranker:
            try:
                self.reranker = CrossEncoderReranker()
                print("[RAGPipeline] Re-ranker: ENABLED (lazy loaded)")
            except Exception as e:
                print(f"[RAGPipeline] Re-ranker: DISABLED ({e})")

    def retrieve(self, query, entities = None, intent = None, graph_top_k = 10, vector_top_k = 10, rerank_top_k = 5):
        """Full RAG retrieval pipeline: Hybrid retrieval + Re-ranking."""
        candidates = self.hybrid.retrieve(
            query=query,
            entities=entities,
            intent=intent,
            graph_top_k=graph_top_k,
            vector_top_k=vector_top_k,
            final_top_k=rerank_top_k * 3,
        )

        if not candidates:
            return []

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
        """Format retrieved contexts into structured sections for LLM consumption."""
        if not contexts:
            return ""

        graph_parts = []
        vector_parts = []
        other_parts = []

        for ctx in contexts:
            source = ctx.get("source", "knowledge_base")
            text = ctx.get("text", "").strip()
            if not text:
                continue

            meta = ctx.get("metadata", {})
            meta_str = ""
            if meta and isinstance(meta, dict):
                meta_items = [f"{k}: {v}" for k, v in meta.items() if k in ("chunk_type", "entity_name", "direction", "champion")]
                if meta_items:
                    meta_str = f" ({', '.join(meta_items)})"

            entry = f"[{source}{meta_str}]\n{text}"
            if source.startswith("graph:"):
                graph_parts.append(entry)
            elif source.startswith("vector:"):
                vector_parts.append(entry)
            else:
                other_parts.append(entry)

        sections = []
        if graph_parts:
            sections.append("=== KNOWLEDGE GRAPH (RELATIONSHIPS and STRUCTURED FACTS) ===\n" + "\n\n".join(graph_parts))
        if vector_parts:
            sections.append("=== GAMEPLAY and LORE DOCUMENTS (VECTOR RETRIEVAL) ===\n" + "\n\n".join(vector_parts))
        if other_parts:
            sections.append("=== ADDITIONAL KNOWLEDGE BASE PASSAGES ===\n" + "\n\n".join(other_parts))

        return "\n\n".join(sections)

    def get_status(self):
        """Return pipeline component status."""
        return {
            "graph_enabled": self.enable_graph,
            "vector_enabled": self.enable_vector,
            "reranker_enabled": self.enable_reranker and self.reranker is not None,
        }


pipeline_instance = None


def get_rag_pipeline(**kwargs):
    """Get or create singleton RAGPipeline instance."""
    global pipeline_instance
    if pipeline_instance is None:
        pipeline_instance = RAGPipeline(**kwargs)
    return pipeline_instance
