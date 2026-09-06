"""
Neo4j Vector Store & Ingestion for LoL Knowledge Bot.

Loads chunk embeddings directly into Neo4j:
- Creates native Neo4j Vector Index (`chunk_embeddings`) on :Chunk(embedding)
- Stores chunk texts, metadata, and 384-dim BGE embeddings
- Links :Chunk nodes to corresponding :Champion and :Item graph nodes via [:HAS_CHUNK]
- Provides vector similarity search via `db.index.vector.queryNodes`
"""

import os
import sys
import time
import pickle
from pathlib import Path
import numpy as np

# Ensure src/ is on path
SRC_DIR = Path(__file__).resolve().parent.parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rag.graph.store import Neo4jStore, get_graph_store

DEFAULT_INDEX_DIR = SRC_DIR / "data" / "vector_index"


class Neo4jVectorStore:
    """Manages vector embeddings and vector index inside Neo4j."""

    INDEX_NAME = "chunk_embeddings"
    DIMENSION = 384

    def __init__(self, store: Neo4jStore = None):
        self.store = store or get_graph_store()

    def init_vector_index(self):
        """Create native Neo4j Vector Index for :Chunk nodes."""
        cypher = f"""
        CREATE VECTOR INDEX {self.INDEX_NAME} IF NOT EXISTS
        FOR (c:Chunk) ON (c.embedding)
        OPTIONS {{
          indexConfig: {{
            `vector.dimensions`: {self.DIMENSION},
            `vector.similarity_function`: 'cosine'
          }}
        }}
        """
        with self.store.session() as sess:
            # Create uniqueness constraint on chunk_id
            try:
                sess.run("CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE")
            except Exception as e:
                print(f"[Neo4jVector] Constraint notice: {e}")

            # Create vector index
            sess.run(cypher)
            print(f"[Neo4jVector] Vector index '{self.INDEX_NAME}' created or verified.")

    def load_from_faiss(self, index_dir=str(DEFAULT_INDEX_DIR), batch_size=200):
        """
        Load pre-computed embeddings and metadata from FAISS vector_index
        and insert into Neo4j in batches.
        """
        idx_path = Path(index_dir)
        faiss_file = idx_path / "faiss.index"
        meta_file = idx_path / "metadata.pkl"

        if not faiss_file.exists() or not meta_file.exists():
            raise FileNotFoundError(f"FAISS index files not found in {index_dir}")

        import faiss
        print(f"[Neo4jVector] Reading FAISS index from {faiss_file}...")
        index = faiss.read_index(str(faiss_file))
        total = index.ntotal

        print(f"[Neo4jVector] Reconstructing {total} vectors from FAISS...")
        vectors = index.reconstruct_n(0, total)

        print(f"[Neo4jVector] Reading metadata from {meta_file}...")
        with open(meta_file, "rb") as f:
            metadata_list = pickle.load(f)

        if len(metadata_list) != total:
            print(f"[Neo4jVector] WARNING: meta count ({len(metadata_list)}) != vector count ({total})")

        return self.ingest_vectors(vectors, metadata_list, batch_size=batch_size)

    def ingest_vectors(self, vectors, metadata_list, batch_size=200):
        """Ingest vectors and metadata into Neo4j :Chunk nodes."""
        self.init_vector_index()

        total = len(metadata_list)
        print(f"[Neo4jVector] Ingesting {total} chunks into Neo4j (batch size {batch_size})...")

        insert_cypher = """
        UNWIND $batch AS item
        MERGE (c:Chunk {chunk_id: item.chunk_id})
        SET c.text = item.text,
            c.embedding = item.embedding,
            c.chunk_type = item.chunk_type,
            c.entity_name = item.entity_name,
            c.entity_type = item.entity_type,
            c.champion_id = item.champion_id
        """

        link_champ_cypher = """
        UNWIND $batch AS item
        MATCH (c:Chunk {chunk_id: item.chunk_id})
        MATCH (ch:Champion) WHERE ch.champion_id = item.champion_id OR ch.name = item.entity_name
        MERGE (ch)-[:HAS_CHUNK]->(c)
        """

        link_item_cypher = """
        UNWIND $batch AS item
        MATCH (c:Chunk {chunk_id: item.chunk_id})
        MATCH (it:Item) WHERE it.name = item.entity_name OR it.item_id = item.chunk_id
        MERGE (it)-[:HAS_CHUNK]->(c)
        """

        with self.store.session() as sess:
            for i in range(0, total, batch_size):
                batch_meta = metadata_list[i : i + batch_size]
                batch_vecs = vectors[i : i + batch_size]

                batch = []
                for meta, vec in zip(batch_meta, batch_vecs):
                    batch.append({
                        "chunk_id": meta.get("chunk_id", ""),
                        "text": meta.get("text", ""),
                        "embedding": [float(x) for x in vec],
                        "chunk_type": meta.get("chunk_type", ""),
                        "entity_name": meta.get("entity_name", ""),
                        "entity_type": meta.get("entity_type", ""),
                        "champion_id": meta.get("champion_id", ""),
                    })

                sess.run(insert_cypher, batch=batch)
                try:
                    sess.run(link_champ_cypher, batch=batch)
                    sess.run(link_item_cypher, batch=batch)
                except Exception:
                    pass

                print(f"  Ingested {min(i + batch_size, total)}/{total} chunks...")

        # Count chunks in Neo4j
        with self.store.session() as sess:
            r = sess.run("MATCH (c:Chunk) RETURN count(c) AS count")
            cnt = r.single()["count"]
            r_links = sess.run("MATCH ()-[r:HAS_CHUNK]->() RETURN count(r) AS count")
            cnt_links = r_links.single()["count"]
            print(f"[Neo4jVector] SUCCESS: {cnt} :Chunk nodes in Neo4j, {cnt_links} [:HAS_CHUNK] links.")

        return cnt

    def search(self, query_vector, top_k=10):
        """
        Search nearest neighbors using Neo4j Vector Index.
        """
        if isinstance(query_vector, np.ndarray):
            query_vector = [float(x) for x in query_vector.flatten()]

        cypher = f"""
        CALL db.index.vector.queryNodes('{self.INDEX_NAME}', $top_k, $vector)
        YIELD node, score
        RETURN node.chunk_id AS chunk_id,
               node.text AS text,
               node.entity_name AS entity_name,
               node.chunk_type AS chunk_type,
               node.entity_type AS entity_type,
               score
        ORDER BY score DESC
        """
        results = []
        with self.store.session() as sess:
            res = sess.run(cypher, top_k=top_k, vector=query_vector)
            for rec in res:
                results.append({
                    "chunk_id": rec["chunk_id"],
                    "text": rec["text"],
                    "entity_name": rec["entity_name"],
                    "chunk_type": rec["chunk_type"],
                    "entity_type": rec["entity_type"],
                    "score": float(rec["score"]),
                })
        return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ingest vector embeddings into Neo4j")
    parser.add_argument("--index-dir", default=str(DEFAULT_INDEX_DIR), help="Directory of FAISS index")
    parser.add_argument("--batch-size", type=int, default=250, help="Batch size for Cypher UNWIND")
    parser.add_argument("--test-search", action="store_true", help="Run a test vector search after loading")
    args = parser.parse_args()

    print("[Neo4jVector] Starting Neo4j vector ingestion...")

    store = Neo4jStore()
    store.connect()

    neo4j_vec = Neo4jVectorStore(store=store)
    t0 = time.time()
    count = neo4j_vec.load_from_faiss(index_dir=args.index_dir, batch_size=args.batch_size)
    print(f"[Neo4jVector] Done in {time.time() - t0:.2f}s! Total chunks: {count}")

    if args.test_search:
        print("\n[Neo4jVector] Testing vector search in Neo4j with a sample vector...")
        import faiss
        idx = faiss.read_index(str(Path(args.index_dir) / "faiss.index"))
        sample_vec = idx.reconstruct(0)
        res = neo4j_vec.search(sample_vec, top_k=3)
        print(f"Test search results count: {len(res)}")
        for r in res:
            print(f"  - [{r['entity_name']} / {r['chunk_type']}] Score: {r['score']:.4f} | ID: {r['chunk_id']}")

    store.close()


if __name__ == "__main__":
    main()
