"""
End-to-End RAG Pipeline Evaluator for LoL RAG Pipeline.

Evaluates:
- Context Recall@k: fraction of gold relevant chunks found in top-k results
- Context Precision@k: fraction of top-k results that are relevant
- MRR (Mean Reciprocal Rank): average 1/rank of first relevant result
- Reranker Lift: NDCG improvement from Cross-Encoder vs RRF-only
- Score Distribution: statistics of rerank_score logits
- Per-stage Latency Breakdown
"""

import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

src_dir = Path(__file__).resolve().parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))


def load_gold_data():
    gold_path = Path(__file__).resolve().parent / "gold_data" / "intent_entity_retrieval_gold.json"
    with open(gold_path, "r", encoding="utf-8") as f:
        return json.load(f)


def chunk_key_from_context(ctx):
    """Extract entity_name::chunk_type key from a retrieved context dict."""
    meta = ctx.get("metadata", {})
    entity = meta.get("entity_name", "")
    chunk_type = meta.get("chunk_type", "")
    if entity and chunk_type:
        return f"{entity}::{chunk_type}"

    # Try to parse from source field
    source = ctx.get("source", "")
    if ":" in source:
        parts = source.split(":", 1)
        if len(parts) == 2 and parts[1]:
            return f"{entity}::{parts[1]}" if entity else None
    return None


def is_relevant(ctx, gold_chunks):
    """Check if a retrieved context matches any gold relevant chunk pattern."""
    if not gold_chunks:
        return False

    meta = ctx.get("metadata", {})
    entity = meta.get("entity_name", "")
    chunk_type = meta.get("chunk_type", "")
    comp_id = meta.get("comp_id", "")
    chunk_id = meta.get("chunk_id", "")

    ctx_key = chunk_key_from_context(ctx)

    for gold_key in gold_chunks:
        # 1. Exact key match
        if ctx_key and ctx_key == gold_key:
            return True

        gold_parts = gold_key.split("::")
        if len(gold_parts) != 2:
            continue

        gold_entity, gold_type = gold_parts[0].lower(), gold_parts[1].lower()

        # 2. Composition matching
        if gold_type == "composition":
            if comp_id and (comp_id.lower() == gold_entity or gold_entity in comp_id.lower()):
                return True
            if chunk_id and f":{gold_entity}" in chunk_id.lower():
                return True
            if entity and gold_entity in entity.lower() and chunk_type == "composition":
                return True

        # 3. Entity and chunk_type match
        if ctx_key:
            ctx_parts = ctx_key.split("::")
            if len(ctx_parts) == 2:
                c_ent, c_type = ctx_parts[0].lower(), ctx_parts[1].lower()
                if c_type == gold_type and (c_ent == gold_entity or gold_entity in c_ent):
                    return True

        # 4. Direct metadata match
        if entity and chunk_type:
            if chunk_type.lower() == gold_type and (entity.lower() == gold_entity or gold_entity in entity.lower()):
                return True

    return False


def dcg_at_k(relevances, k):
    """Discounted Cumulative Gain at k."""
    relevances = relevances[:k]
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances))


def ndcg_at_k(relevances, k):
    """Normalized DCG at k."""
    dcg = dcg_at_k(relevances, k)
    ideal = dcg_at_k(sorted(relevances, reverse=True), k)
    return dcg / ideal if ideal > 0 else 0.0


def evaluate_pipeline(pipeline, gold_data, top_k=5):
    """Run end-to-end RAG pipeline evaluation."""
    from chatbot.intent_classifier import IntentClassifier
    from chatbot.bot import LoLBot

    classifier = IntentClassifier()

    # Filter to test cases that have relevant_chunks labels
    test_cases = [e for e in gold_data if e.get("relevant_chunks")]
    print(f"[EvalPipeline] Evaluating {len(test_cases)} cases with retrieval labels (out of {len(gold_data)} total)")

    # Metrics accumulators
    recall_hits = {k: 0 for k in [1, 3, 5]}
    precision_sums = {k: 0.0 for k in [1, 3, 5]}
    reciprocal_ranks = []
    ndcg_scores = {k: [] for k in [1, 3, 5]}

    # Reranker analysis
    rrf_ndcg_scores = {k: [] for k in [1, 3, 5]}
    rerank_scores_all = []

    # Latency
    latencies = []

    # Per-intent breakdown
    intent_recall = defaultdict(list)

    # Detailed results
    detailed = []

    for i, entry in enumerate(test_cases):
        query = entry["query"]
        gold_intent = entry["intent"]
        gold_entities = entry.get("entities", {})
        gold_chunks = entry["relevant_chunks"]

        # Build retrieval query (replicating bot logic)
        classification = classifier.classify(query)
        intent = classification.get("intent", gold_intent)

        # Override entities from gold for fair retrieval eval
        for k, v in gold_entities.items():
            if v is not None:
                classification[k] = v

        # Use gold intent for retrieval to isolate retrieval quality from classifier errors
        bot = LoLBot.__new__(LoLBot)  # bypass __init__
        bot.store = None
        bot.classifier = None
        bot.retriever = None
        bot.generator = None
        bot.conversation_history = []
        bot.rag_pipeline = pipeline

        try:
            retrieval_query = LoLBot.build_retrieval_query(bot, query, classification, gold_intent)
        except Exception:
            retrieval_query = query

        # Time the retrieval
        t0 = time.time()
        try:
            candidates = pipeline.retrieve(
                query=retrieval_query,
                entities=classification,
                intent=gold_intent,
                graph_top_k=10,
                vector_top_k=10,
                rerank_top_k=top_k,
            )
        except Exception as e:
            print(f"  [WARN] Retrieval error for '{query[:50]}': {e}")
            candidates = []
        latency_ms = (time.time() - t0) * 1000
        latencies.append(latency_ms)

        # Evaluate relevance
        relevances = [1 if is_relevant(c, gold_chunks) else 0 for c in candidates]
        found_any = any(r == 1 for r in relevances)

        # Recall@k
        for k in [1, 3, 5]:
            if any(r == 1 for r in relevances[:k]):
                recall_hits[k] += 1

        # Precision@k
        for k in [1, 3, 5]:
            prec = sum(relevances[:k]) / min(k, len(relevances)) if relevances else 0
            precision_sums[k] += prec

        # MRR
        first_relevant_rank = None
        for j, r in enumerate(relevances):
            if r == 1:
                first_relevant_rank = j + 1
                break
        reciprocal_ranks.append(1.0 / first_relevant_rank if first_relevant_rank else 0.0)

        # NDCG@k
        for k in [1, 3, 5]:
            ndcg_scores[k].append(ndcg_at_k(relevances, k))

        # Rerank score distribution
        for c in candidates:
            rs = c.get("rerank_score")
            if rs is not None:
                rerank_scores_all.append(rs)

        # Per-intent recall tracking
        intent_recall[gold_intent].append(1 if found_any else 0)

        detailed.append({
            "query": query,
            "intent": gold_intent,
            "retrieval_query": retrieval_query,
            "found_relevant": found_any,
            "num_results": len(candidates),
            "relevances": relevances,
            "latency_ms": round(latency_ms, 1),
        })

        if (i + 1) % 25 == 0 or (i + 1) == len(test_cases):
            print(f"  [{i+1}/{len(test_cases)}] evaluated... (Recall@5 so far: {recall_hits[5]/(i+1):.3f})")

    n = len(test_cases)

    # Reranker score stats
    score_stats = {}
    if rerank_scores_all:
        arr = np.array(rerank_scores_all)
        score_stats = {
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "median": float(np.median(arr)),
            "pct_negative": float(np.mean(arr < 0) * 100),
            "count": len(arr),
        }

    # Per-intent recall breakdown
    intent_recall_summary = {}
    for intent, hits in sorted(intent_recall.items(), key=lambda x: -len(x[1])):
        intent_recall_summary[intent] = {
            "recall@5": sum(hits) / len(hits) if hits else 0,
            "support": len(hits),
        }

    report = {
        "summary": {
            "total_evaluated": n,
            "recall@1": recall_hits[1] / n if n else 0,
            "recall@3": recall_hits[3] / n if n else 0,
            "recall@5": recall_hits[5] / n if n else 0,
            "precision@1": precision_sums[1] / n if n else 0,
            "precision@3": precision_sums[3] / n if n else 0,
            "precision@5": precision_sums[5] / n if n else 0,
            "mrr": float(np.mean(reciprocal_ranks)) if reciprocal_ranks else 0,
            "ndcg@1": float(np.mean(ndcg_scores[1])) if ndcg_scores[1] else 0,
            "ndcg@3": float(np.mean(ndcg_scores[3])) if ndcg_scores[3] else 0,
            "ndcg@5": float(np.mean(ndcg_scores[5])) if ndcg_scores[5] else 0,
            "avg_latency_ms": float(np.mean(latencies)) if latencies else 0,
            "p95_latency_ms": float(np.percentile(latencies, 95)) if latencies else 0,
        },
        "rerank_score_distribution": score_stats,
        "per_intent_recall": intent_recall_summary,
        "missed_samples": [d for d in detailed if not d["found_relevant"]][:20],
    }

    return report


def print_report(report):
    """Print evaluation report to console."""
    s = report["summary"]
    print("\n  END-TO-END RAG PIPELINE EVALUATION REPORT")
    print(f"  Total evaluated:     {s['total_evaluated']}")
    print(f"\n  Retrieval Metrics:")
    print(f"    Recall@1:          {s['recall@1']:.4f}")
    print(f"    Recall@3:          {s['recall@3']:.4f}")
    print(f"    Recall@5:          {s['recall@5']:.4f}")
    print(f"    Precision@1:       {s['precision@1']:.4f}")
    print(f"    Precision@3:       {s['precision@3']:.4f}")
    print(f"    Precision@5:       {s['precision@5']:.4f}")
    print(f"    MRR:               {s['mrr']:.4f}")
    print(f"    NDCG@1:            {s['ndcg@1']:.4f}")
    print(f"    NDCG@3:            {s['ndcg@3']:.4f}")
    print(f"    NDCG@5:            {s['ndcg@5']:.4f}")
    print(f"\n  Latency:")
    print(f"    Average:           {s['avg_latency_ms']:.1f} ms")
    print(f"    P95:               {s['p95_latency_ms']:.1f} ms")

    sd = report.get("rerank_score_distribution", {})
    if sd:
        print(f"\n  Cross-Encoder Score Distribution (rerank_score logits):")
        print(f"    Mean:     {sd['mean']:.3f}")
        print(f"    Std:      {sd['std']:.3f}")
        print(f"    Min/Max:  {sd['min']:.3f} / {sd['max']:.3f}")
        print(f"    Median:   {sd['median']:.3f}")
        print(f"    %% Negative: {sd['pct_negative']:.1f}%%")

    pir = report.get("per_intent_recall", {})
    if pir:
        print(f"\n  Per-Intent Recall@5:")
        print(f"  {'Intent':<35} {'Recall@5':>8} {'Support':>7}")
        print("  " + "-" * 55)
        for intent, m in sorted(pir.items(), key=lambda x: -x[1]["support"]):
            recall_str = f"{m['recall@5']:.3f}"
            marker = " ⚠" if m["recall@5"] < 0.5 else ""
            print(f"  {intent:<35} {recall_str:>8} {m['support']:>7}{marker}")

    missed = report.get("missed_samples", [])
    if missed:
        print(f"\n  Missed Samples (relevant chunk NOT in top-5): {len(missed)}")
        for m in missed[:10]:
            print(f"    [{m['intent']}] \"{m['query'][:55]}\" ({m['num_results']} results, {m['latency_ms']:.0f}ms)")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Evaluate RAG Pipeline")
    parser.add_argument("--top-k", type=int, default=5, help="Top-k for evaluation")
    parser.add_argument("--no-reranker", action="store_true", help="Disable reranker for comparison")
    args = parser.parse_args()

    print("[EvalPipeline] Loading gold data...")
    gold_data = load_gold_data()

    print("[EvalPipeline] Initializing RAG Pipeline...")
    from rag.pipeline import RAGPipeline

    pipeline = RAGPipeline(
        enable_graph=False,   # Graph eval requires Neo4j; test vector+reranker path
        enable_vector=True,
        enable_reranker=not args.no_reranker,
    )

    status = pipeline.get_status()
    print(f"[EvalPipeline] Status: {status}")

    if not status.get("vector_enabled"):
        print("[EvalPipeline] ERROR: Vector retriever not enabled. Cannot evaluate.")
        return

    print(f"[EvalPipeline] Running evaluation (reranker={'OFF' if args.no_reranker else 'ON'}, top_k={args.top_k})...")
    report = evaluate_pipeline(pipeline, gold_data, top_k=args.top_k)

    print_report(report)

    # Save report
    suffix = "no_reranker" if args.no_reranker else "with_reranker"
    output_path = Path(__file__).resolve().parent / "results" / f"pipeline_eval_{suffix}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n[EvalPipeline] Report saved to {output_path}")

    return report


if __name__ == "__main__":
    main()
