"""
Vector-based Retriever for LoL Knowledge Bot.

Performs semantic similarity search using FAISS vector store
to find relevant document chunks based on query embedding.
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure src/ is on path
src_dir = Path(__file__).resolve().parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from rag.vector.embeddings import EmbeddingModel, get_embedding_model
from rag.vector.store import VectorStore

default_index_dir = src_dir / "data" / "vector_index"


class VectorRetriever:
    """
    Retrieves context from the FAISS vector store via semantic search.

    Pipeline:
    1. Encode query with instruction prefix (BGE)
    2. FAISS similarity search -> top-k chunks
    3. Optional metadata filtering
    4. Return standardized context dicts
    """

    def __init__(self, vector_store=None, embedding_model=None, index_dir=str(default_index_dir)):
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

    def retrieve(self, query, top_k = 10, entity_type = None, chunk_type = None, entity_name = None, preferred_chunk_type = None, excluded_chunk_types = None):
        """Retrieve relevant chunks via semantic similarity."""
        if len(self.store) == 0:
            return []

        query_embedding = self.embedding_model.encode_query(query)

        filter_fn = None
        if entity_type or chunk_type or excluded_chunk_types:
            def filter_fn(meta):
                if entity_type and meta.get("entity_type") != entity_type:
                    return False
                if chunk_type and meta.get("chunk_type") != chunk_type:
                    return False
                if excluded_chunk_types and meta.get("chunk_type") in excluded_chunk_types:
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

    def retrieve_for_entity(self, query, entity_name, top_k = 5):
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

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Vector Retriever CLI for LoL Knowledge Bot")
    parser.add_argument("--query", "-q", type=str, default=None, help="Direct query to retrieve relevant context")
    parser.add_argument("--top-k", "-k", type=int, default=3, help="Number of chunks to retrieve (default: 3)")
    parser.add_argument("--interactive", "-i", action="store_true", help="Start interactive query loop")
    args = parser.parse_args()

    print("[VectorRetriever] Initializing retriever...")
    retriever = VectorRetriever()

    def print_results(query, k):
        print(f"\n[Query] {query}")
        results = retriever.retrieve(query, top_k=k)
        if not results:
            print("  (No results found)")
            return
        for idx, res in enumerate(results, 1):
            source = res.get("source", "unknown")
            score = res.get("score", 0.0)
            meta = res.get("metadata", {})
            entity = meta.get("entity_name", "N/A")
            chunk_type = meta.get("chunk_type", "N/A")
            print(f"\nResult #{idx} | Source: {source} | Score: {score:.4f} | Entity: {entity} ({chunk_type}):")
            print(res["text"].strip())

    if args.query:
        print_results(args.query, args.top_k)
    elif args.interactive:
        print("\n[VectorRetriever] Interactive mode (Type 'exit' or 'q' to quit)")
        while True:
            try:
                user_q = input("\nEnter query > ").strip()
                if not user_q:
                    continue
                if user_q.lower() in ("exit", "quit", "q"):
                    print("Exiting interactive mode.")
                    break
                print_results(user_q, args.top_k)
            except (KeyboardInterrupt, EOFError):
                print("\nExiting interactive mode.")
                break
    else:
        test_queries = [
            "Who counters Yasuo?",
            "What items should I build on Aatrox?",
            "Tell me about Jinx lore",
        ]
        for q in test_queries:
            print_results(q, 2)


if __name__ == "__main__":
    main()
