"""
Vector Indexing Pipeline for LoL Knowledge Bot.

End-to-end pipeline: Processed Data → Chunks → Embeddings → FAISS Index.

Usage:
    python -m rag.vector.indexer           # Build index
    python -m rag.vector.indexer --clear    # Rebuild from scratch
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Ensure src/ is on path
SRC_DIR = Path(__file__).resolve().parent.parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rag.vector.chunker import DocumentChunk, DocumentChunker
from rag.vector.embeddings import EmbeddingModel, get_embedding_model
from rag.vector.store import VectorStore

# Default paths
PROJECT_ROOT = SRC_DIR.parent
DEFAULT_INDEX_DIR = SRC_DIR / "data" / "vector_index"
PROCESSED_DIR = SRC_DIR / "processors" / "processed"
KB_DIR = SRC_DIR / "data" / "knowledge_base"
FALLBACK_KB = PROJECT_ROOT / "lol_chatbot" / "data" / "game_data"


class Indexer:
    """
    End-to-end indexing pipeline for the vector store.

    Pipeline steps:
    1. Load processed data (champions, items, runes, counters, synergies, builds)
    2. Chunk documents via DocumentChunker
    3. Encode chunks via EmbeddingModel (BGE + optional LoRA)
    4. Store in FAISS VectorStore
    5. Persist index + metadata to disk
    """

    def __init__(self, embedding_model=None, index_dir=str(DEFAULT_INDEX_DIR)):
        self.embedding_model = embedding_model or get_embedding_model()
        self.index_dir = index_dir
        self.chunker = DocumentChunker()

    def load_data(self, source="auto", mongo_uri=None, db_name=None):
        """
        Load champions, items, runes, counters, synergies, and builds.
        Supports 'auto' (MongoDB first, fallback to files), 'mongo', or 'files'.
        """
        if source in ("auto", "mongo"):
            try:
                from pymongo import MongoClient
                import os
                uri = mongo_uri or os.getenv("MONGO_URI", "mongodb://localhost:27017")
                database = db_name or os.getenv("MONGO_DB_NAME", "lol_rag_db")
                client = MongoClient(uri, serverSelectionTimeoutMS=3000)
                client.admin.command("ping")
                db = client[database]

                champs = {doc["_id"]: doc for doc in db.champions.find()}
                if champs:
                    items = {doc["_id"]: doc for doc in db.items.find()}
                    runes_docs = list(db.runes.find())
                    by_id = {doc["_id"]: doc for doc in runes_docs if doc.get("type") != "tree"}
                    by_tree = {doc.get("tree", doc["_id"].replace("tree_", "")): doc.get("runes", []) for doc in runes_docs if doc.get("type") == "tree"}
                    runes = {"byId": by_id, "byTree": by_tree}
                    counters = {doc["_id"]: doc for doc in db.counters.find()}
                    synergies = {doc["_id"]: doc for doc in db.synergies.find()}
                    builds = {doc["_id"]: doc for doc in db.builds.find()}

                    print(f"[Indexer] Successfully loaded knowledge data from MongoDB ('{database}'):")
                    print(f"  Champions: {len(champs)}, Items: {len(items)}, Runes: {len(by_id)}")
                    print(f"  Counters:  {len(counters)}, Synergies: {len(synergies)}, Builds: {len(builds)}")
                    return champs, items, runes, counters, synergies, builds
            except Exception as e:
                if source == "mongo":
                    raise RuntimeError(f"Failed to load from MongoDB: {e}")
                print(f"[Indexer] MongoDB unavailable ({e}), falling back to local files...")

        # Fallback to files
        print("[Indexer] Loading processed data from local files...")
        champions = self.load_json(PROCESSED_DIR / "champions.json")
        items = self.load_json(PROCESSED_DIR / "items.json")
        runes = self.load_json(PROCESSED_DIR / "runes.json")
        counters = self.load_counter_data()
        synergies = self.load_synergy_data()
        builds = self.load_build_data()
        print(f"  Champions: {len(champions)}, Items: {len(items)}, Runes: {len(runes.get('byId', {}))}")
        print(f"  Counters:  {len(counters)}, Synergies: {len(synergies)}, Builds: {len(builds)}")
        return champions, items, runes, counters, synergies, builds

    def build_index(self, clear=False, source="auto"):
        """
        Execute the full indexing pipeline.

        Args:
            clear: If True, remove existing index before building.
            source: 'auto', 'mongo', or 'files'.

        Returns:
            The populated VectorStore instance.
        """
        start = time.time()
        print("[Indexer] Starting Vector Index build...")

        # 1. Load data
        print("\n[1/4] Loading game knowledge data...")
        champions, items, runes, counters, synergies, builds = self.load_data(source=source)

        # 2. Chunk
        print("\n[2/4] Chunking documents...")
        chunks = self.chunker.chunk_all(
            champions=champions,
            items=items,
            runes=runes,
            counters=counters,
            synergies=synergies,
            builds=builds,
        )
        print(f"  Total chunks: {len(chunks)}")

        # 3. Encode
        print("\n[3/4] Encoding chunks with embedding model...")
        texts = [chunk.text for chunk in chunks]
        embeddings = self.embedding_model.encode(
            texts,
            batch_size=64,
            show_progress=True,
        )
        print(f"  Embedding shape: {embeddings.shape}")

        # 4. Build FAISS index
        print("\n[4/4] Building FAISS index...")
        store = VectorStore(
            dimension=self.embedding_model.get_dimension(),
            use_gpu=True,
        )

        # Prepare metadata
        metadata_list = [
            {
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
                "entity_type": chunk.entity_type,
                "entity_name": chunk.entity_name,
                "chunk_type": chunk.chunk_type,
                **chunk.metadata,
            }
            for chunk in chunks
        ]

        store.add(embeddings, metadata_list)

        # Save to disk
        store.save(self.index_dir)

        elapsed = time.time() - start
        stats = store.get_stats()
        print(f"\n[Indexer] Vector Index built in {elapsed:.1f}s")
        print(f"  Total vectors: {stats['total_vectors']}")
        print(f"  Dimension: {stats['dimension']}")
        print(f"  GPU: {stats['gpu']}")
        print(f"  Entity types: {stats['entity_types']}")
        print(f"  Chunk types: {stats['chunk_types']}")
        print(f"  Saved to: {self.index_dir}")

        return store

    # Data Loaders

    def load_counter_data(self):
        """Load counter data from knowledge base or fallback."""
        data = {}
        for dir_path in [KB_DIR / "counters", FALLBACK_KB / "counter_data"]:
            if dir_path.exists():
                for fpath in dir_path.glob("*_counters.json"):
                    loaded = self.load_json(fpath)
                    if loaded:
                        key = loaded.get("champion", fpath.stem.replace("_counters", ""))
                        data[key] = loaded
                if data:
                    break
        return data

    def load_synergy_data(self):
        """Load synergy data from knowledge base or fallback."""
        data = {}
        for dir_path in [KB_DIR / "synergies", FALLBACK_KB / "synergy_data"]:
            if dir_path.exists():
                for fpath in dir_path.glob("*.json"):
                    loaded = self.load_json(fpath)
                    if loaded:
                        key = fpath.stem.replace("_synergy", "").replace("_duos", "")
                        data[key] = loaded
                if data:
                    break
        return data

    def load_build_data(self):
        """Load build data from knowledge base or fallback."""
        data = {}
        for dir_path in [KB_DIR / "builds", FALLBACK_KB / "build_data"]:
            if dir_path.exists():
                for fpath in dir_path.glob("*.json"):
                    loaded = self.load_json(fpath)
                    if loaded:
                        key = loaded.get("champion", fpath.stem.replace("_build", ""))
                        data[key] = loaded
                if data:
                    break
        return data

    @staticmethod
    def load_json(path):
        """Load JSON file, return empty dict on failure."""
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}


def main():
    parser = argparse.ArgumentParser(description="Build FAISS vector index for LoL Knowledge Bot")
    parser.add_argument("--clear", action="store_true", help="Rebuild index from scratch")
    parser.add_argument("--source", type=str, choices=["auto", "mongo", "files"], default="auto",
                        help="Data source: auto (MongoDB first, fallback to files), mongo, or files")
    parser.add_argument("--index-dir", type=str, default=str(DEFAULT_INDEX_DIR),
                        help="Directory to save the index")
    args = parser.parse_args()

    indexer = Indexer(index_dir=args.index_dir)
    indexer.build_index(clear=args.clear, source=args.source)


if __name__ == "__main__":
    main()
