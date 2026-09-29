"""
Cross-Encoder Re-Ranker for LoL Knowledge Bot.

Re-ranks retrieval candidates using a cross-encoder model that
jointly encodes (query, passage) pairs for more accurate relevance scoring.
"""

import math

import torch


class CrossEncoderReranker:
    """
    Re-rank retrieval results using a cross-encoder model.

    Cross-encoders are more accurate than bi-encoders (embedding similarity)
    because they see query and passage together, enabling token-level interaction.
    """

    def __init__(self, model_name = "cross-encoder/ms-marco-MiniLM-L-6-v2", device = None):
        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None

    def load_model(self):
        """Lazy-load the cross-encoder model."""
        if self.model is not None:
            return

        from sentence_transformers import CrossEncoder

        print(f"[Reranker] Loading {self.model_name} on {self.device}...")
        self.model = CrossEncoder(self.model_name, device=self.device)
        print(f"[Reranker] Model loaded.")

    def rerank(self, query, candidates, top_k = 5, score_key = "rerank_score"):
        """Re-rank candidate passages using cross-encoder."""
        if not candidates:
            return []

        if len(candidates) <= 1:
            return candidates

        self.load_model()

        pairs = [(query, c.get("text", "")) for c in candidates]
        scores = self.model.predict(pairs, show_progress_bar=False)

        for candidate, score in zip(candidates, scores):
            raw_logit = float(score)
            candidate[score_key] = raw_logit
            # Safe sigmoid: clamp logit to [-60, 60] to prevent overflow, normalize to [0, 1]
            clamped = max(-60.0, min(60.0, raw_logit))
            candidate["score"] = 1.0 / (1.0 + math.exp(-clamped))

        reranked = sorted(candidates, key=lambda x: x.get(score_key, 0), reverse=True)
        return reranked[:top_k]
