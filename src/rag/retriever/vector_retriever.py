"""
Vector-based Retriever for LoL Knowledge Bot.

Performs semantic similarity search using FAISS vector store
to find relevant document chunks based on query embedding.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from rag.vector.embeddings import EmbeddingModel, get_embedding_model
from rag.vector.store import VectorStore


# Default index directory
DEFAULT_INDEX_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "vector_index"


class VectorRetriever:
    """
    Retrieves context from the FAISS vector store via semantic search.

    Pipeline:
    1. Encode query with instruction prefix (BGE)
    2. FAISS similarity search → top-k chunks
    3. Optional metadata filtering
    4. Return standardized context dicts
    """

    def __init__(self, vector_store = None, embedding_model = None, index_dir = str(DEFAULT_INDEX_DIR)):
        self.embedding_model = embedding_model or get_embedding_model()

        if vector_store:
            self.store = vector_store
        else:
            self.store = VectorStore(
                dimension=self.embedding_model.get_dimension(),
                use_gpu = True,
            )
            if Path(index_dir).exists() and (Path(index_dir) / "faiss.index").exists():
                self.store.load(index_dir)
            else:
                print(f"[VectorRetriever] WARNING: No index at {index_dir}. Run indexer first.")

    def retrieve(self, query, top_k = 10, entity_type = None, chunk_type = None):
        """
        Retrieve relevant chunks via semantic similarity.

        Args:
            query: User query text.
            top_k: Number of results.
            entity_type: Optional filter (e.g., "champion", "item").
            chunk_type: Optional filter (e.g., "overview", "ability").

        Returns:
            List of context dicts with 'text', 'source', 'score', 'metadata'.
        """
        if len(self.store) == 0:
            return []

        # Encode query with instruction prefix
        query_embedding = self.embedding_model.encode_query(query)

        # Build filter function
        filter_fn = None
        if entity_type or chunk_type:
            def filter_fn(meta):
                if entity_type and meta.get("entity_type") != entity_type:
                    return False
                if chunk_type and meta.get("chunk_type") != chunk_type:
                    return False
                return True

        # Search
        results = self.store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            filter_fn=filter_fn,
        )

        # Convert to standardized format
        contexts = []
        for r in results:
            contexts.append({
                "text": r.text,
                "source": f"vector:{r.metadata.get('chunk_type', 'unknown')}",
                "score": r.score,
                "metadata": r.metadata,
            })

        return contexts

    def retrieve_for_entity(self, query, entity_name, top_k = 5):
        """
        Retrieve chunks specifically about an entity, boosting exact matches.
        """
        if len(self.store) == 0:
            return []

        # Search with more results to filter
        query_embedding = self.embedding_model.encode_query(query)
        results = self.store.search(query_embedding=query_embedding, top_k=top_k * 3)

        # Boost results that match the entity name
        boosted = []
        for r in results:
            score = r.score
            if r.metadata.get("entity_name", "").lower() == entity_name.lower():
                score *= 1.3  # Boost factor for entity match
            elif entity_name.lower() in r.metadata.get("entity_name", "").lower():
                score *= 1.1

            boosted.append({
                "text": r.text,
                "source": f"vector:{r.metadata.get('chunk_type', 'unknown')}",
                "score": score,
                "metadata": r.metadata,
            })

        # Sort by boosted score and limit
        boosted.sort(key=lambda x: x["score"], reverse=True)
        return boosted[:top_k]
