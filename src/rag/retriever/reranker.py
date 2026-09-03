"""
Cross-Encoder Re-Ranker for LoL Knowledge Bot.

Re-ranks retrieval candidates using a cross-encoder model that
jointly encodes (query, passage) pairs for more accurate relevance scoring.
"""

from typing import Any, Dict, List, Optional

import torch


class CrossEncoderReranker:
    """
    Re-rank retrieval results using a cross-encoder model.

    Cross-encoders are more accurate than bi-encoders (embedding similarity)
    because they see query and passage together, enabling token-level interaction.
    Trade-off: slower (can't pre-compute), but much more precise.

    Default model: cross-encoder/ms-marco-MiniLM-L-6-v2
    """

    def __init__(self, model_name = "cross-encoder/ms-marco-MiniLM-L-6-v2", device = None):
        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._model = None

    def load_model(self):
        """Lazy-load the cross-encoder model."""
        if self._model is not None:
            return

        from sentence_transformers import CrossEncoder

        print(f"[Reranker] Loading {self.model_name} on {self.device}...")
        self._model = CrossEncoder(self.model_name, device=self.device)
        print(f"[Reranker] Model loaded.")

    def rerank(self, query, candidates, top_k = 5, score_key = "rerank_score"):
        """
        Re-rank candidate passages using cross-encoder.

        Args:
            query: The user query.
            candidates: List of context dicts with at least 'text' key.
            top_k: Number of top results to return after re-ranking.
            score_key: Key name for the cross-encoder score in output.

        Returns:
            Re-ranked list of context dicts (top_k), sorted by cross-encoder score.
        """
        if not candidates:
            return []

        if len(candidates) <= 1:
            return candidates

        self.load_model()

        # Create (query, passage) pairs
        pairs = [(query, c.get("text", "")) for c in candidates]

        # Score with cross-encoder
        scores = self._model.predict(pairs, show_progress_bar=False)

        # Attach scores and sort
        for candidate, score in zip(candidates, scores):
            candidate[score_key] = float(score)

        # Sort by cross-encoder score (descending)
        reranked = sorted(candidates, key=lambda x: x.get(score_key, 0), reverse=True)

        return reranked[:top_k]
