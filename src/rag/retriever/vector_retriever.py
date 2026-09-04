"""
Vector-based Retriever for LoL Knowledge Bot.

Performs semantic similarity search using FAISS vector store
to find relevant document chunks based on query embedding.
"""

import sys
from pathlib import Path

# Ensure src/ is on path
SRC_DIR = Path(__file__).resolve().parent.parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rag.vector.embeddings import EmbeddingModel, get_embedding_model
from rag.vector.store import VectorStore

DEFAULT_INDEX_DIR = SRC_DIR / "data" / "vector_index"


class VectorRetriever:
    """
    Retrieves context from the FAISS vector store via semantic search.

    Pipeline:
    1. Encode query with instruction prefix (BGE)
    2. FAISS similarity search -> top-k chunks
    3. Optional metadata filtering
    4. Return standardized context dicts
    """

    def __init__(self, vector_store=None, embedding_model=None, index_dir=str(DEFAULT_INDEX_DIR)):
        self.embedding_model = embedding_model or get_embedding_model()

        if vector_store:
            self.store = vector_store
        else:
            self.store = VectorStore(
                dimension=self.embedding_model.get_dimension(),
                use_gpu=True,
            )
            if Path(index_dir).exists() and (Path(index_dir) / "faiss.index").exists():
                self.store.load(index_dir)
            else:
                print(f"[VectorRetriever] WARNING: No index at {index_dir}. Run indexer first.")

    def retrieve(self, query, top_k=10, entity_type=None, chunk_type=None, entity_name=None, preferred_chunk_type=None):
        """Retrieve relevant chunks via semantic similarity."""
        if len(self.store) == 0:
            return []

        query_embedding = self.embedding_model.encode_query(query)

        filter_fn = None
        if entity_type or chunk_type:
            def filter_fn(meta):
                if entity_type and meta.get("entity_type") != entity_type:
                    return False
                if chunk_type and meta.get("chunk_type") != chunk_type:
                    return False
                return True

        candidate_k = top_k * 3 if (entity_name or preferred_chunk_type) else top_k
        results = self.store.search(
            query_embedding=query_embedding,
            top_k=candidate_k,
            filter_fn=filter_fn,
        )

        contexts = []
        for r in results:
            score = r.score
            result_entity = r.metadata.get("entity_name", "")
            if entity_name and result_entity:
                if result_entity.lower() == entity_name.lower():
                    score *= 1.3
                elif entity_name.lower() in result_entity.lower():
                    score *= 1.1
            if preferred_chunk_type and r.metadata.get("chunk_type") == preferred_chunk_type:
                score *= 1.15
            contexts.append({
                "text": r.text,
                "source": f"vector:{r.metadata.get('chunk_type', 'unknown')}",
                "score": score,
                "metadata": r.metadata,
            })

        contexts.sort(key=lambda x: x["score"], reverse=True)
        return contexts[:top_k]

    def retrieve_for_entity(self, query, entity_name, top_k=5):
        """Retrieve chunks specifically about an entity, boosting exact matches."""
        if len(self.store) == 0:
            return []

        query_embedding = self.embedding_model.encode_query(query)
        results = self.store.search(query_embedding=query_embedding, top_k=top_k * 3)

        boosted = []
        for r in results:
            score = r.score
            if r.metadata.get("entity_name", "").lower() == entity_name.lower():
                score *= 1.3
            elif entity_name.lower() in r.metadata.get("entity_name", "").lower():
                score *= 1.1

            boosted.append({
                "text": r.text,
                "source": f"vector:{r.metadata.get('chunk_type', 'unknown')}",
                "score": score,
                "metadata": r.metadata,
            })

        boosted.sort(key=lambda x: x["score"], reverse=True)
        return boosted[:top_k]


if __name__ == "__main__":
    print("[VectorRetriever] Testing vector retriever...")
    retriever = VectorRetriever()

    test_queries = [
        "Who counters Yasuo?",
        "What items should I build on Aatrox?",
        "Tell me about Jinx lore",
    ]

    for q in test_queries:
        print(f"\n[Query] '{q}'")
        results = retriever.retrieve(q, top_k=2)
        for idx, res in enumerate(results, 1):
            print(f"  Result {idx}: {res['source']} (score: {res['score']:.4f})")
            print(f"  {res['text'][:120]}...")
