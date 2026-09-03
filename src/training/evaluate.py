"""
Retrieval Evaluation Module for LoL Knowledge Bot.

Evaluates embedding models and retrieval performance before and after
LoRA fine-tuning using standard IR metrics:
- Recall@k (k=1, 3, 5, 10)
- MRR (Mean Reciprocal Rank)
- NDCG@k (Normalized Discounted Cumulative Gain)
- Latency (ms per query)
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

# Ensure src/ is on path
SRC_DIR = Path(__file__).resolve().parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rag.vector.embeddings import EmbeddingModel, DEFAULT_MODEL
from rag.vector.store import VectorStore
from training.data_generator import TrainingTriplet


class RetrievalEvaluator:
    """
    Evaluates retrieval metrics on test triplets.
    """

    def __init__(self, embedding_model = None):
        self.embedding_model = embedding_model or EmbeddingModel()

    def evaluate_triplets(self, triplets, top_ks = [1, 3, 5, 10], pool_size = 100):
        """
        Evaluate retrieval accuracy on triplets.
        For each triplet, ranks the positive passage against (pool_size - 1) negatives.

        Returns:
            Dict containing Recall@k, MRR, NDCG, and avg latency.
        """
        print(f"[Evaluator] Evaluating on {len(triplets)} test samples (pool size={pool_size})...")

        recall_hits = {k: 0 for k in top_ks}
        reciprocal_ranks = []
        ndcg_scores = {k: [] for k in top_ks}
        latencies = []

        all_negatives = [t.negative for t in triplets]
        rng = np.random.RandomState(42)

        for i, t in enumerate(triplets):
            query = t.query
            positive = t.positive

            # Sample pool of negatives + 1 positive
            sample_negs = rng.choice(
                all_negatives, size = min(pool_size - 1, len(all_negatives)), replace = False
            ).tolist()
            corpus = [positive] + sample_negs
            labels = [1] + [0] * len(sample_negs)  # Ground truth (positive is index 0)

            t0 = time.time()
            q_emb = self.embedding_model.encode_query(query)
            c_emb = self.embedding_model.encode(corpus)
            latencies.append((time.time() - t0) * 1000)

            # Similarity scores (inner product of normalized vectors = cosine sim)
            scores = np.dot(c_emb, q_emb.T).flatten()
            ranked_indices = np.argsort(-scores)

            # Find rank of positive document (index 0)
            pos_rank = np.where(ranked_indices == 0)[0][0] + 1  # 1-indexed

            # Calculate MRR
            reciprocal_ranks.append(1.0 / pos_rank)

            # Calculate Recall@k and NDCG@k
            for k in top_ks:
                if pos_rank <= k:
                    recall_hits[k] += 1
                    ndcg_scores[k].append(1.0 / np.log2(pos_rank + 1))
                else:
                    ndcg_scores[k].append(0.0)

        n = len(triplets)
        results = {
            "num_samples": n,
            "mrr": float(np.mean(reciprocal_ranks)),
            "avg_latency_ms": float(np.mean(latencies)),
        }

        for k in top_ks:
            results[f"recall@{k}"] = float(recall_hits[k] / n)
            results[f"ndcg@{k}"] = float(np.mean(ndcg_scores[k]))

        return results

    def compare_models(self, base_model_name, lora_adapter_path, test_data_path):
        """
        Compare Base Model vs LoRA Fine-tuned Model.
        """
        print("\n" + "-" * 60)
        print("MODEL COMPARISON BENCHMARK")
        print("-" * 60)

        with open(test_data_path, "r", encoding = "utf-8") as f:
            triplets = [TrainingTriplet(**json.loads(line)) for line in f if line.strip()]

        # 1. Evaluate Base Model
        print("\n--- 1. Evaluating Base Model ---")
        base_model = EmbeddingModel(model_name = base_model_name, use_lora = False)
        self.embedding_model = base_model
        base_results = self.evaluate_triplets(triplets)

        # 2. Evaluate LoRA Model
        print("\n--- 2. Evaluating LoRA Fine-Tuned Model ---")
        lora_model = EmbeddingModel(model_name = base_model_name, lora_path = lora_adapter_path, use_lora = True)
        self.embedding_model = lora_model
        lora_results = self.evaluate_triplets(triplets)

        comparison = {
            "base_model": base_results,
            "lora_model": lora_results,
            "improvements": {
                "mrr_delta": lora_results["mrr"] - base_results["mrr"],
                "recall@1_delta": lora_results["recall@1"] - base_results["recall@1"],
                "recall@5_delta": lora_results["recall@5"] - base_results["recall@5"],
                "ndcg@5_delta": lora_results["ndcg@5"] - base_results["ndcg@5"],
            }
        }

        print("\n" + "-" * 60)
        print("COMPARISON RESULTS:")
        print(f"  Metric       | Base Model | LoRA Tuned | Delta")
        print(f"  -------------|------------|------------|-------")
        print(f"  MRR          | {base_results['mrr']:.4f}     | {lora_results['mrr']:.4f}     | {comparison['improvements']['mrr_delta']:+.4f}")
        print(f"  Recall@1     | {base_results['recall@1']:.4f}     | {lora_results['recall@1']:.4f}     | {comparison['improvements']['recall@1_delta']:+.4f}")
        print(f"  Recall@5     | {base_results['recall@5']:.4f}     | {lora_results['recall@5']:.4f}     | {comparison['improvements']['recall@5_delta']:+.4f}")
        print(f"  NDCG@5       | {base_results['ndcg@5']:.4f}     | {lora_results['ndcg@5']:.4f}     | {comparison['improvements']['ndcg@5_delta']:+.4f}")
        print(f"  Latency (ms) | {base_results['avg_latency_ms']:.2f}      | {lora_results['avg_latency_ms']:.2f}      | -")
        print("-" * 60)

        return comparison


def main():
    parser = argparse.ArgumentParser(description = "Evaluate retrieval models")
    parser.add_argument("--base-model", type = str, default = DEFAULT_MODEL)
    parser.add_argument("--lora-path", type = str, default = "src/training/lora_model")
    parser.add_argument("--test-data", type = str, default = "src/training/test.jsonl")
    args = parser.parse_args()

    evaluator = RetrievalEvaluator()
    if Path(args.lora_path).exists() and Path(args.test_data).exists():
        evaluator.compare_models(args.base_model, args.lora_path, args.test_data)
    else:
        print(f"[Evaluator] Test data or LoRA path not found. Run data_generator.py and lora_trainer.py first.")


if __name__ == "__main__":
    main()
