"""
Embedding Model Wrapper for LoL Knowledge Bot.

Wraps sentence-transformers with support for:
- Base model: BAAI/bge-small-en-v1.5 (384-dim)
- Optional LoRA adapter loading for domain-tuned embeddings
- Query-prefix instruction (required by BGE models)
- GPU acceleration (CUDA / RTX 4050)
"""

import os
from pathlib import Path
import numpy as np
import torch
from sentence_transformers import SentenceTransformer

# BGE models require a query instruction prefix for asymmetric retrieval
bge_query_instruction = "Represent this sentence for searching relevant passages: "

# Default model
src_dir = Path(__file__).resolve().parent.parent.parent
default_model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
default_dimension = 384


class EmbeddingModel:
    """
    Embedding model wrapper with LoRA adapter support.

    Features:
    - Automatic GPU detection (CUDA / CPU)
    - BGE query instruction prefixing
    - LoRA adapter loading from disk
    - Batch encoding for efficiency
    - L2 normalization for cosine similarity
    """

    def __init__(self, model_name = default_model, lora_path = None, device = None, normalize = True, use_lora = True):
        self.model_name = model_name
        self.normalize = normalize
        self.dimension = default_dimension

        # Auto-detect device
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        # Determine if model is BGE (needs query instruction prefix)
        self.is_bge = "bge" in model_name.lower()

        # Load model
        print(f"[EmbeddingModel] Loading {model_name} on {self.device}...")
        self.model = SentenceTransformer(model_name, device=self.device)
        self.dimension = self.model.get_embedding_dimension() if hasattr(self.model, "get_embedding_dimension") else self.model.get_sentence_embedding_dimension()
        print(f"[EmbeddingModel] Loaded. Dimension: {self.dimension}, Device: {self.device}")

        # Auto-discover and load LoRA adapter if present
        if use_lora:
            resolved_lora_path = lora_path
            if not resolved_lora_path:
                candidates = [
                    src_dir / "training" / "lora_model",
                    src_dir / "training" / "lora_embedding",
                    src_dir / "models" / "lora_embedding",
                ]
                for cand in candidates:
                    if cand.exists() and (cand / "adapter_config.json").exists():
                        resolved_lora_path = str(cand)
                        break

            if resolved_lora_path and Path(resolved_lora_path).exists():
                self.load_lora_adapter(resolved_lora_path)

    def encode(self, texts, batch_size = 64, show_progress = False):
        """
        Encode texts (passages/documents) to dense vectors.

        For BGE models, this encodes WITHOUT the query instruction prefix,
        since these are passages, not queries.
        """
        if isinstance(texts, str):
            texts = [texts]

        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            normalize_embeddings=self.normalize,
            convert_to_numpy=True,
        )

        return embeddings

    def encode_query(self, query, batch_size = 32):
        """
        Encode queries with instruction prefix (for asymmetric retrieval).

        BGE models use a query instruction prefix to distinguish
        queries from passages during retrieval.
        """
        if isinstance(query, str):
            queries = [query]
        else:
            queries = query

        # Add BGE instruction prefix
        if self.is_bge:
            queries = [bge_query_instruction + q for q in queries]

        embeddings = self.model.encode(
            queries,
            batch_size=batch_size,
            normalize_embeddings=self.normalize,
            convert_to_numpy=True,
        )

        return embeddings

    def load_lora_adapter(self, lora_path):
        """
        Load a LoRA adapter and merge it into the base model.

        The adapter should be saved by the LoRA trainer in PEFT format.
        """
        try:
            from peft import PeftModel

            print(f"[EmbeddingModel] Loading LoRA adapter from {lora_path}...")

            # Get the underlying HuggingFace model from SentenceTransformer
            base_model = self.model._first_module().auto_model

            # Load and merge LoRA adapter
            peft_model = PeftModel.from_pretrained(base_model, lora_path)
            merged_model = peft_model.merge_and_unload()

            # Replace the model in SentenceTransformer
            self.model._first_module().auto_model = merged_model
            print("[EmbeddingModel] LoRA adapter loaded and merged successfully.")

        except ImportError:
            print("[EmbeddingModel] WARNING: peft not installed. Skipping LoRA adapter.")
        except Exception as e:
            print(f"[EmbeddingModel] WARNING: Failed to load LoRA adapter: {e}")

    def get_dimension(self):
        """Return embedding dimension."""
        return self.dimension

    def get_device(self):
        """Return current device."""
        return self.device

    def __repr__(self):
        return (
            f"EmbeddingModel(model={self.model_name}, dim={self.dimension}, "
            f"device={self.device}, bge={self.is_bge})"
        )


embedding_instance = None


def get_embedding_model(model_name = default_model, lora_path = None):
    """Get or create singleton EmbeddingModel instance."""
    global embedding_instance
    if embedding_instance is None:
        embedding_instance = EmbeddingModel(model_name=model_name, lora_path=lora_path)
    return embedding_instance
