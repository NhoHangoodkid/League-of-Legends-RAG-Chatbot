"""
Qualitative Question-Type Tester for LoL RAG Pipeline.

Tests representative questions across 8 domains:
1. Counter Query (Single champ matchup)
2. Build Query (Items and runes)
3. Skill Mechanics (Ability interaction / mechanics)
4. Base Stats (Specific stat numbers)
5. Synergy / Duos (Pairings and team combos)
6. Team Composition (Drafting and countering archetypes)
7. Team Counter Analysis
8. Lore (Origin, biography, region)
"""

import sys
import time
from pathlib import Path

src_dir = Path(__file__).resolve().parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from chatbot.intent_classifier import IntentClassifier
from chatbot.bot import LoLBot
from rag.pipeline import RAGPipeline


SAMPLE_QUESTIONS = [
    {
        "category": "1. Counter Query",
        "question": "How to counter Teemo as melee?",
        "expected_intent": "COUNTER_QUERY",
    },
    {
        "category": "2. Build & Itemization",
        "question": "What is the best build and runes for Jinx adc?",
        "expected_intent": "BUILD_QUERY",
    },
    {
        "category": "3. Skill & Ability Mechanics",
        "question": "Tell me about Syndra Q ability mechanics",
        "expected_intent": "SKILL_INFO",
    },
    {
        "category": "4. Champion Base Stats",
        "question": "Base HP of Cho'Gath",
        "expected_intent": "CHAMPION_BASE_STATS",
    },
    {
        "category": "5. Champion Synergy / Duos",
        "question": "Good support for Kai'Sa",
        "expected_intent": "SYNERGY_QUERY",
    },
    {
        "category": "6. Team Composition Drafting",
        "question": "How to draft a dive composition?",
        "expected_intent": "TEAM_COMPOSITION_BUILDING",
    },
    {
        "category": "7. Team Counter Analysis",
        "question": "What beats a poke comp?",
        "expected_intent": "TEAM_COUNTER_ANALYSIS",
    },
    {
        "category": "8. Lore & Background",
        "question": "Where is Azir from?",
        "expected_intent": "LORE_QUERY",
    },
]


def run_tests():
    print("  RUNNING QUALITATIVE TESTS ON REPRESENTATIVE QUESTION TYPES")

    print("\n[Init] Initializing Intent Classifier...")
    classifier = IntentClassifier()

    print("[Init] Initializing RAG Pipeline (Vector + Re-ranker)...")
    pipeline = RAGPipeline(enable_graph=False, enable_vector=True, enable_reranker=True)

    bot = LoLBot.__new__(LoLBot)
    bot.store = None
    bot.classifier = None
    bot.retriever = None
    bot.generator = None
    bot.conversation_history = []
    bot.rag_pipeline = pipeline

    for item in SAMPLE_QUESTIONS:
        cat = item["category"]
        q = item["question"]

        print(f"\n{'─' * 80}")
        print(f"▶ [{cat}] Query: \"{q}\"")

        # 1. Intent Classification
        t0 = time.time()
        cls = classifier.classify(q)
        cls_time = (time.time() - t0) * 1000
        intent = cls.get("intent", "UNKNOWN")
        entities = {k: v for k, v in cls.items() if v and k != "intent"}
        print(f"  • Intent:   {intent} (Expected: {item['expected_intent']}) [{cls_time:.1f}ms]")
        print(f"  • Entities: {entities}")

        # 2. Query Rewriting
        retrieval_query = LoLBot.build_retrieval_query(bot, q, cls, intent)
        print(f"  • Rewritten Query: \"{retrieval_query}\"")

        # 3. Retrieval
        t1 = time.time()
        results = pipeline.retrieve(
            query=retrieval_query,
            entities=cls,
            intent=intent,
            vector_top_k=8,
            rerank_top_k=3,
        )
        ret_time = (time.time() - t1) * 1000
        print(f"  • Retrieved Chunks: {len(results)} chunks [{ret_time:.1f}ms]")

        # 4. Display retrieved chunks
        for idx, r in enumerate(results[:3], start=1):
            source = r.get("source", "unknown")
            meta = r.get("metadata", {})
            entity_name = meta.get("entity_name") or meta.get("champion") or meta.get("item") or meta.get("comp_id") or "N/A"
            chunk_type = meta.get("chunk_type") or "N/A"
            score = r.get("score", 0.0)
            rerank_score = r.get("rerank_score")
            score_str = f"Score: {score:.3f}"
            if rerank_score is not None:
                score_str += f" (raw logit: {rerank_score:.2f})"

            text_preview = (r.get("text") or "").strip().replace("\n", " ")[:140]
            print(f"    [{idx}] [{source}] Entity: {entity_name} | Type: {chunk_type} | {score_str}")
            print(f"        \"{text_preview}...\"")

    print("\n  ALL QUALITATIVE TESTS COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    run_tests()
