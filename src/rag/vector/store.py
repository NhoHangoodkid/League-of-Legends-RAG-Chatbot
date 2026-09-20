"""
FAISS Vector Store for LoL Knowledge Bot.

GPU-accelerated vector similarity search using FAISS with:
- Inner Product index (equivalent to cosine sim when vectors are L2-normalized)
- Metadata storage for chunk tracing
- Persistence (save/load from disk)
- Supports faiss-gpu on RTX 4050
"""

import json
import os
import pickle
from pathlib import Path
import numpy as np

try:
    import faiss
except ImportError:
    faiss = None
    print("[VectorStore] WARNING: faiss not installed. Run: pip install faiss-cpu (or faiss-gpu)")


class SearchResult:
    """A single search result from vector retrieval."""

    def __init__(self, chunk_id = "", text = "", score = 0.0, metadata = None):
        self.chunk_id = chunk_id
        self.text = text
        self.score = score
        self.metadata = metadata or {}

    def __repr__(self):
        return f"SearchResult(chunk_id='{self.chunk_id}', score={self.score:.4f})"


class VectorStore:
    """
    FAISS-backed vector store with metadata and persistence.

    Features:
    - GPU acceleration via faiss-gpu (auto-detected)
    - Inner Product search (cosine sim with normalized vectors)
    - Metadata stored in parallel list (chunk_id, text, entity info)
    - Save/Load to disk (index + metadata)
    """

    def __init__(self, dimension = 384, use_gpu = True):
        """
        Args:
            dimension: Embedding vector dimension.
            use_gpu: Whether to use GPU for FAISS (if available).
        """
        if faiss is None:
            raise ImportError("faiss is required. Install with: pip install faiss-cpu")

        self.dimension = dimension
        self.use_gpu = use_gpu

        # Create flat inner product index (exact search, best accuracy)
        self.index = faiss.IndexFlatIP(dimension)

        # Try GPU
        self.gpu_available = False
        if use_gpu and hasattr(faiss, "get_num_gpus") and faiss.get_num_gpus() > 0:
            try:
                gpu_res = faiss.StandardGpuResources()
                self.index = faiss.index_cpu_to_gpu(gpu_res, 0, self.index)
                self.gpu_available = True
                print(f"[VectorStore] Using GPU FAISS (dim={dimension})")
            except Exception:
                print(f"[VectorStore] GPU FAISS not available, using CPU (dim={dimension})")
        else:
            print(f"[VectorStore] Using CPU FAISS (dim={dimension})")

        # Metadata storage (parallel to index vectors)
        self.metadata = []

    def add(self, embeddings, metadata_list):
        """
        Add vectors and their metadata to the store.

        Args:
            embeddings: numpy array of shape (n, dimension), float32.
            metadata_list: List of metadata dicts, one per embedding.
                Each must have at least 'chunk_id' and 'text'.
        """
        if len(embeddings) != len(metadata_list):
            raise ValueError(
                f"Embedding count ({len(embeddings)}) != metadata count ({len(metadata_list)})"
            )

        # Ensure float32
        if embeddings.dtype != np.float32:
            embeddings = embeddings.astype(np.float32)

        self.index.add(embeddings)
        self.metadata.extend(metadata_list)

    def search(self, query_embedding, top_k = 10, filter_fn = None):
        """
        Search for nearest neighbors.

        Args:
            query_embedding: Query vector of shape (1, dimension) or (dimension,).
            top_k: Number of results to return.
            filter_fn: Optional function(metadata) -> bool to filter results.

        Returns:
            List of SearchResult sorted by score (descending).
        """
        if self.index.ntotal == 0:
            return []

        # Reshape if needed
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)

        if query_embedding.dtype != np.float32:
            query_embedding = query_embedding.astype(np.float32)

        # Search more if we need to filter
        search_k = top_k * 3 if filter_fn else top_k

        scores, indices = self.index.search(query_embedding, min(search_k, self.index.ntotal))

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue

            meta = self.metadata[idx]

            # Apply filter
            if filter_fn and not filter_fn(meta):
                continue

            results.append(SearchResult(
                chunk_id=meta.get("chunk_id", ""),
                text=meta.get("text", ""),
                score=float(score),
                metadata=meta,
            ))

            if len(results) >= top_k:
                break

        return results

    def save(self, directory):
        """
        Save index and metadata to disk.

        Creates:
        - {directory}/faiss.index — FAISS index
        - {directory}/metadata.pkl — Metadata list
        """
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)

        # Save FAISS index (need to convert GPU index to CPU for saving)
        cpu_index = self.index
        if self.gpu_available:
            cpu_index = faiss.index_gpu_to_cpu(self.index)

        faiss.write_index(cpu_index, str(path / "faiss.index"))

        # Save metadata
        with open(path / "metadata.pkl", "wb") as f:
            pickle.dump(self.metadata, f)

        # Save human-readable stats
        stats = {
            "total_vectors": self.index.ntotal,
            "dimension": self.dimension,
            "gpu": self.gpu_available,
        }
        with open(path / "index_stats.json", "w") as f:
            json.dump(stats, f, indent=2)

        print(f"[VectorStore] Saved {self.index.ntotal} vectors to {directory}")

    def load(self, directory):
        """Load index and metadata from disk."""
        path = Path(directory)

        index_path = path / "faiss.index"
        meta_path = path / "metadata.pkl"

        if not index_path.exists():
            raise FileNotFoundError(f"FAISS index not found at {index_path}")

        # Load FAISS index
        cpu_index = faiss.read_index(str(index_path))

        # Optionally move to GPU
        if self.use_gpu and self.gpu_available:
            try:
                gpu_res = faiss.StandardGpuResources()
                self.index = faiss.index_cpu_to_gpu(gpu_res, 0, cpu_index)
            except Exception:
                self.index = cpu_index
        else:
            self.index = cpu_index

        self.dimension = self.index.d

        # Load metadata
        if meta_path.exists():
            with open(meta_path, "rb") as f:
                self.metadata = pickle.load(f)

        print(f"[VectorStore] Loaded {self.index.ntotal} vectors from {directory}")

    def get_stats(self):
        """Return store statistics."""
        entity_types = {}
        chunk_types = {}
        for m in self.metadata:
            et = m.get("entity_type", "unknown")
            ct = m.get("chunk_type", "unknown")
            entity_types[et] = entity_types.get(et, 0) + 1
            chunk_types[ct] = chunk_types.get(ct, 0) + 1

        return {
            "total_vectors": self.index.ntotal,
            "dimension": self.dimension,
            "gpu": self.gpu_available,
            "entity_types": entity_types,
            "chunk_types": chunk_types,
        }

    def clear(self):
        """Remove all vectors and metadata."""
        self.index.reset()
        self.metadata = []

    def __len__(self):
        return self.index.ntotal
