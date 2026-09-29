"""
Intent Classification Evaluator for LoL RAG Pipeline.

Evaluates:
- Intent Accuracy (exact match)
- Macro F1-Score across all intent classes
- Per-intent Precision / Recall / F1
- Entity Extraction Accuracy (champion_name, item_name, rune_name, skill_key, ...)
- Confusion matrix (top misclassifications)
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

src_dir = Path(__file__).resolve().parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))


def load_gold_data():
    gold_path = Path(__file__).resolve().parent / "gold_data" / "intent_entity_retrieval_gold.json"
    with open(gold_path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_intent(classifier, gold_data):
    """Run intent classification evaluation."""
    correct_intent = 0
    total = len(gold_data)

    # Per-intent tracking
    tp = Counter()   # true positives
    fp = Counter()   # false positives
    fn = Counter()   # false negatives
    confusion = Counter()  # (gold, predicted) pairs

    # Entity extraction tracking
    entity_fields = ["champion_name", "skill_key", "item_name", "rune_name",
                     "counter_direction", "lane", "role", "cc_types", "ability_effects",
                     "comp_archetype", "damage_composition", "power_curve"]
    entity_correct = 0
    entity_total = 0
    entity_field_stats = {f: {"correct": 0, "total": 0} for f in entity_fields}

    results = []

    for i, entry in enumerate(gold_data):
        query = entry["query"]
        gold_intent = entry["intent"]
        gold_entities = entry.get("entities", {})

        # Classify
        pred = classifier.classify(query)
        pred_intent = pred.get("intent", "UNKNOWN")

        # Intent accuracy
        intent_match = (pred_intent == gold_intent)
        if intent_match:
            correct_intent += 1
            tp[gold_intent] += 1
        else:
            fp[pred_intent] += 1
            fn[gold_intent] += 1
            confusion[(gold_intent, pred_intent)] += 1

        # Entity extraction accuracy
        for field in entity_fields:
            gold_val = gold_entities.get(field)
            if gold_val is None:
                continue

            entity_total += 1
            entity_field_stats[field]["total"] += 1

            pred_val = pred.get(field)

            # Normalize comparison
            if isinstance(gold_val, list) and isinstance(pred_val, list):
                match = set(str(v).lower() for v in gold_val) == set(str(v).lower() for v in pred_val)
            elif isinstance(gold_val, str) and isinstance(pred_val, str):
                match = gold_val.lower().strip() == pred_val.lower().strip()
            elif isinstance(gold_val, (int, float)) and isinstance(pred_val, (int, float)):
                match = gold_val == pred_val
            else:
                match = gold_val == pred_val

            if match:
                entity_correct += 1
                entity_field_stats[field]["correct"] += 1

        results.append({
            "query": query,
            "gold_intent": gold_intent,
            "pred_intent": pred_intent,
            "match": intent_match,
        })

    # Calculate per-intent P/R/F1
    all_intents = set(tp.keys()) | set(fp.keys()) | set(fn.keys())
    intent_metrics = {}
    f1_scores = []

    for intent in sorted(all_intents):
        p = tp[intent] / (tp[intent] + fp[intent]) if (tp[intent] + fp[intent]) > 0 else 0
        r = tp[intent] / (tp[intent] + fn[intent]) if (tp[intent] + fn[intent]) > 0 else 0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0
        intent_metrics[intent] = {"precision": p, "recall": r, "f1": f1, "support": tp[intent] + fn[intent]}
        if tp[intent] + fn[intent] > 0:  # Only include intents that appear in gold
            f1_scores.append(f1)

    macro_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0

    # Build report
    report = {
        "summary": {
            "total_samples": total,
            "intent_accuracy": correct_intent / total if total > 0 else 0,
            "intent_correct": correct_intent,
            "macro_f1": macro_f1,
            "entity_accuracy": entity_correct / entity_total if entity_total > 0 else 0,
            "entity_correct": entity_correct,
            "entity_total": entity_total,
        },
        "per_intent": intent_metrics,
        "entity_field_accuracy": {
            f: (s["correct"] / s["total"] if s["total"] > 0 else None)
            for f, s in entity_field_stats.items()
            if s["total"] > 0
        },
        "top_confusions": [
            {"gold": g, "predicted": p, "count": c}
            for (g, p), c in confusion.most_common(15)
        ],
        "misclassified_samples": [
            r for r in results if not r["match"]
        ],
    }

    return report


def print_report(report):
    """Print evaluation report to console."""
    s = report["summary"]
    print("\n  INTENT CLASSIFICATION EVALUATION REPORT")
    print(f"  Total samples:      {s['total_samples']}")
    print(f"  Intent Accuracy:    {s['intent_accuracy']:.4f} ({s['intent_correct']}/{s['total_samples']})")
    print(f"  Macro F1-Score:     {s['macro_f1']:.4f}")
    print(f"  Entity Accuracy:    {s['entity_accuracy']:.4f} ({s['entity_correct']}/{s['entity_total']})")

    print("\n  Per-Intent Metrics:")
    print(f"  {'Intent':<35} {'Prec':>6} {'Recall':>6} {'F1':>6} {'Support':>7}")
    print("  " + "-" * 65)
    for intent, m in sorted(report["per_intent"].items(), key=lambda x: -x[1]["support"]):
        print(f"  {intent:<35} {m['precision']:>6.3f} {m['recall']:>6.3f} {m['f1']:>6.3f} {m['support']:>7}")

    if report.get("entity_field_accuracy"):
        print("\n  Entity Field Accuracy:")
        for field, acc in sorted(report["entity_field_accuracy"].items(), key=lambda x: -x[1]):
            print(f"    {field:<25} {acc:.3f}")

    if report.get("top_confusions"):
        print("\n  Top Misclassifications:")
        for c in report["top_confusions"][:10]:
            print(f"    {c['gold']:<30} -> {c['predicted']:<30} ({c['count']}x)")

    if report.get("misclassified_samples"):
        print(f"\n  Misclassified Samples ({len(report['misclassified_samples'])}):")
        for m in report["misclassified_samples"][:15]:
            print(f"    Q: \"{m['query'][:60]}\"")
            print(f"       Gold: {m['gold_intent']:<30} Pred: {m['pred_intent']}")


def main():
    print("[EvalIntent] Loading gold data...")
    gold_data = load_gold_data()
    print(f"[EvalIntent] Loaded {len(gold_data)} test cases")

    print("[EvalIntent] Initializing Intent Classifier (heuristic mode)...")
    from chatbot.intent_classifier import IntentClassifier
    classifier = IntentClassifier()

    print("[EvalIntent] Running evaluation...")
    report = evaluate_intent(classifier, gold_data)

    print_report(report)

    # Save report
    output_path = Path(__file__).resolve().parent / "results" / "intent_eval_report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n[EvalIntent] Report saved to {output_path}")

    return report


if __name__ == "__main__":
    main()
