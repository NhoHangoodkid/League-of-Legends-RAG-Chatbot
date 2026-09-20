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
src_dir = Path(__file__).resolve().parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from rag.vector.chunker import DocumentChunk, DocumentChunker
from rag.vector.embeddings import EmbeddingModel, get_embedding_model
from rag.vector.store import VectorStore

# Default paths
project_root = src_dir.parent
default_index_dir = src_dir / "data" / "vector_index"
processed_dir = src_dir / "processors" / "processed"
kb_dir = src_dir / "data" / "knowledge_base"
fallback_kb = project_root / "lol_chatbot" / "data" / "game_data"


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

    def __init__(self, embedding_model=None, index_dir=str(default_index_dir)):
        self.embedding_model = embedding_model or get_embedding_model()
        self.index_dir = index_dir
        self.chunker = DocumentChunker()

    def load_data(self, source = "auto", mongo_uri = None, db_name = None):
        """
        Load champions, items, runes, counters, synergies, builds, and team_compositions.
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

                    # Canonicalize counters to 173 champions matching champs.keys()
                    raw_counters = {doc["_id"]: doc for doc in db.counters.find()}
                    canonical_counters = {}
                    for cid, doc in raw_counters.items():
                        c_key = None
                        if cid in champs:
                            c_key = cid
                        else:
                            for ch_id, ch_data in champs.items():
                                if ch_data.get("name") == doc.get("champion") or ch_data.get("name") == cid:
                                    c_key = ch_id
                                    break
                        if c_key:
                            if c_key not in canonical_counters or ("weaknesses" in doc and "weaknesses" not in canonical_counters[c_key]):
                                c_doc = dict(doc)
                                c_doc["_id"] = c_key
                                c_doc["champion_id"] = c_key
                                c_doc["champion"] = champs[c_key].get("name", c_key)
                                canonical_counters[c_key] = c_doc

                    # Fill any missing champions from embedded counters
                    for cid, doc in champs.items():
                        if cid not in canonical_counters and "counters" in doc and isinstance(doc["counters"], dict):
                            cnt = dict(doc["counters"])
                            cnt["_id"] = cid
                            cnt["champion_id"] = cid
                            cnt["champion"] = doc.get("name", cid)
                            canonical_counters[cid] = cnt

                    counters = canonical_counters

                    # Populate tacticalInfo into counters
                    for cid, cnt_doc in counters.items():
                        champ_doc = champs.get(cid, {})
                        tactical = champ_doc.get("tacticalInfo", {})
                        if "weaknesses" not in cnt_doc and tactical.get("weaknesses"):
                            cnt_doc["weaknesses"] = tactical["weaknesses"]
                        if "tactical_tips" not in cnt_doc and tactical.get("tactical_tips"):
                            cnt_doc["tactical_tips"] = tactical["tactical_tips"]
                        if "counter_items" not in cnt_doc and tactical.get("counter_items"):
                            cnt_doc["counter_items"] = tactical["counter_items"]
                        if "official_enemytips" not in cnt_doc and (champ_doc.get("enemytips") or tactical.get("official_enemytips")):
                            cnt_doc["official_enemytips"] = champ_doc.get("enemytips") or tactical.get("official_enemytips")
                        if "official_allytips" not in cnt_doc and (champ_doc.get("allytips") or tactical.get("official_allytips")):
                            cnt_doc["official_allytips"] = champ_doc.get("allytips") or tactical.get("official_allytips")
                        if "projectile_abilities" not in cnt_doc and champ_doc.get("mechanicsSummary", {}).get("projectileAbilities"):
                            cnt_doc["projectile_abilities"] = champ_doc.get("mechanicsSummary", {}).get("projectileAbilities")
                        if "spellshieldable_abilities" not in cnt_doc and champ_doc.get("mechanicsSummary", {}).get("spellshieldableAbilities"):
                            cnt_doc["spellshieldable_abilities"] = champ_doc.get("mechanicsSummary", {}).get("spellshieldableAbilities")

                    synergies = {doc["_id"]: doc for doc in db.synergies.find()}
                    builds = {doc["_id"]: doc for doc in db.builds.find()}
                    team_compositions = {doc["_id"]: doc for doc in db.team_compositions.find()}

                    print(f"[Indexer] Successfully loaded knowledge data from MongoDB ('{database}'):")
                    print(f"  Champions: {len(champs)}, Items: {len(items)}, Runes: {len(by_id)}")
                    print(f"  Counters:  {len(counters)}, Synergies: {len(synergies)}, Builds: {len(builds)}")
                    print(f"  Team Compositions: {len(team_compositions)}")
                    return champs, items, runes, counters, synergies, builds, team_compositions
            except Exception as e:
                if source == "mongo":
                    raise RuntimeError(f"Failed to load from MongoDB: {e}")
                print(f"[Indexer] MongoDB unavailable ({e}), falling back to local files...")

        # Fallback to files
        print("[Indexer] Loading processed data from local files...")
        champions = self.load_json(processed_dir / "champions.json")
        items = self.load_json(processed_dir / "items.json")
        runes = self.load_json(processed_dir / "runes.json")
        counters = self.load_counter_data()
        synergies = self.load_synergy_data()
        builds = self.load_build_data()
        team_compositions = self.load_team_composition_data()
        print(f"  Champions: {len(champions)}, Items: {len(items)}, Runes: {len(runes.get('byId', {}))}")
        print(f"  Counters:  {len(counters)}, Synergies: {len(synergies)}, Builds: {len(builds)}")
        print(f"  Team Compositions: {len(team_compositions)}")
        return champions, items, runes, counters, synergies, builds, team_compositions

    def build_index(self, clear = False, source = "auto"):
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
        champions, items, runes, counters, synergies, builds, team_compositions = self.load_data(source=source)

        # 2. Chunk
        print("\n[2/4] Chunking documents...")
        chunks = self.chunker.chunk_all(
            champions=champions,
            items=items,
            runes=runes,
            counters=counters,
            synergies=synergies,
            builds=builds,
            team_compositions=team_compositions,
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
        """Load counter data from processed directory, knowledge base, or fallback."""
        if (processed_dir / "counters.json").exists():
            return self.load_json(processed_dir / "counters.json")
        data = {}
        for dir_path in [kb_dir / "counters", fallback_kb / "counter_data"]:
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
        """Load synergy data from processed directory, knowledge base, or fallback."""
        if (processed_dir / "synergies.json").exists():
            return self.load_json(processed_dir / "synergies.json")
        data = {}
        for dir_path in [kb_dir / "synergies", fallback_kb / "synergy_data"]:
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
        """Load build data from processed directory, knowledge base, or fallback."""
        if (processed_dir / "builds.json").exists():
            return self.load_json(processed_dir / "builds.json")
        data = {}
        for dir_path in [kb_dir / "builds", fallback_kb / "build_data"]:
            if dir_path.exists():
                for fpath in dir_path.glob("*.json"):
                    loaded = self.load_json(fpath)
                    if loaded:
                        key = loaded.get("champion", fpath.stem.replace("_build", ""))
                        data[key] = loaded
                if data:
                    break
        return data

    def load_team_composition_data(self):
        """Load team composition data from processed directory or knowledge base."""
        for path in [processed_dir / "team_compositions.json", kb_dir / "team_compositions.json"]:
            if path.exists():
                return self.load_json(path)
        return {}

    @staticmethod
    def load_json(path):
        """Load JSON file, return empty dict on failure."""
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding = "utf-8") as f:
                return json.load(f)
        except Exception:
            return {}


def main():
    parser = argparse.ArgumentParser(description="Build FAISS vector index for LoL Knowledge Bot")
    parser.add_argument("--clear", action="store_true", help="Rebuild index from scratch")
    parser.add_argument("--source", type=str, choices=["auto", "mongo", "files"], default="auto",
                        help="Data source: auto (MongoDB first, fallback to files), mongo, or files")
    parser.add_argument("--index-dir", type=str, default=str(default_index_dir),
                        help="Directory to save the index")
    args = parser.parse_args()

    indexer = Indexer(index_dir=args.index_dir)
    indexer.build_index(clear=args.clear, source=args.source)


if __name__ == "__main__":
    main()
