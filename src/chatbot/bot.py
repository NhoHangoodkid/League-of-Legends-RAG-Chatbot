"""
LoL Knowledge Bot Orchestrator.

Combines Intent Classifier, Hybrid GraphRAG + Vector RAG Pipeline,
Deterministic Data Augmentation (for non-synthesizable math/stats/filters),
and Response Generator to provide an end-to-end question answering pipeline.
"""

import sys
from pathlib import Path

# Ensure src/ is on sys.path
src_dir = Path(__file__).resolve().parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from chatbot.config import (
    enable_graph_rag,
    enable_reranker,
    enable_vector_rag,
    graph_top_k,
    rerank_top_k,
    vector_index_dir,
    vector_top_k,
)
from chatbot.retriever import DataRetriever
from chatbot.intent_classifier import IntentClassifier
from chatbot.knowledge_store import KnowledgeStore, get_knowledge_store
from chatbot.response_generator import ResponseGenerator
from chatbot.data.query_templates import (
    CC_EFFECT_INTENTS,
    CHAMPION_PLAYSTYLE_INTENTS,
    CHAMPION_QUERY_TEMPLATES,
    CHAMPION_STAT_INTENTS,
    COUNTER_KEYWORDS,
    NON_CHAMPION_TARGETED_INTENTS,
    SKILL_INTENTS,
    STANDALONE_QUERY_TEMPLATES,
)
from rag.pipeline import RAGPipeline, get_rag_pipeline


class LoLBot:
    """Main Chatbot Orchestrator for League of Legends with Hybrid GraphRAG + Vector RAG."""

    def __init__(self, store = None, rag_pipeline = None):
        self.store = store or get_knowledge_store()
        self.classifier = IntentClassifier()
        self.retriever = DataRetriever(self.store)
        self.generator = ResponseGenerator()
        self.conversation_history = []

        # RAG Pipeline initialization
        try:
            self.rag_pipeline = rag_pipeline or get_rag_pipeline(
                index_dir = str(vector_index_dir),
                enable_graph = enable_graph_rag,
                enable_vector = enable_vector_rag,
                enable_reranker = enable_reranker,
            )
        except Exception:
            self.rag_pipeline = None

    def build_retrieval_query(self, question, classification, intent):
        """
        Synthesize an English search query for the underlying English embedding and cross-encoder models
        based on the extracted intent and entities (champion, abilities, items, runes, lanes, etc.).
        """
        champ = classification.get("champion_name") or classification.get("champion") or classification.get("target_champion")
        lane = classification.get("lane")
        role = classification.get("role")
        skill_key = classification.get("skill_key")
        item = classification.get("item_name")
        rune = classification.get("rune_name")
        comparison = classification.get("comparison_champions")
        enemy_champs = classification.get("enemy_champions")
        cc_types = classification.get("cc_types")
        effects = classification.get("ability_effects")
        comp_archetype = classification.get("comp_archetype")
        damage_composition = classification.get("damage_composition")

        lane_str = f"{lane} " if lane else ""

        # 1. Champion Head-to-Head Comparison / 1v1 Matchup
        if (comparison and len(comparison) >= 2) or intent == "CHAMPION_COMPARISON":
            comp_list = comparison if (comparison and len(comparison) >= 2) else ([champ] if champ else ["champion1", "champion2"])
            return f"Compare {' vs '.join(comp_list[:2])} matchup counter head to head lane mechanics stats League of Legends"

        # 2. Ability Mechanics Query
        if intent == "ABILITY_MECHANIC_QUERY":
            sk_str = f" ability {skill_key}" if skill_key else ""
            inter = classification.get("interaction_champion", "")
            inter_str = f" {inter} wind wall spell shield" if inter else ""
            mech = classification.get("mechanic", "")
            return f"{champ or ''}{sk_str} ability description {mech}{inter_str} League of Legends".strip()

        # 3. Role-Specific Counter Pick Query
        if intent == "ROLE_COUNTER_PICK":
            u_role = classification.get("user_role") or role or "champion"
            t_val = classification.get("target") or "enemy"
            extra_terms = "peel disengage anti-dive crowd control protection" if ("support" in str(u_role).lower() or "dive" in str(t_val).lower() or "assassin" in str(t_val).lower()) else "items kit mechanics"
            return f"Best {u_role} counter picks against {t_val} {extra_terms} in League of Legends"

        # 4. Targeted Single Champion Queries
        if champ and intent not in NON_CHAMPION_TARGETED_INTENTS:
            if skill_key or intent in SKILL_INTENTS:
                sk_str = f" {skill_key}" if skill_key else ""
                return f"{champ}{sk_str} ability mechanics damage cooldown scaling cost League of Legends"
            if intent == "COUNTER_QUERY":
                if classification.get("counter_direction") == "counters":
                    return f"Who does {champ} counter favorable matchups strong against League of Legends"
                return f"How to counter {champ} {lane_str}in League of Legends weaknesses tips counter items counter picks"
            if intent in CHAMPION_QUERY_TEMPLATES:
                return CHAMPION_QUERY_TEMPLATES[intent].format(champ=champ, lane=lane_str)
            if intent in CHAMPION_STAT_INTENTS:
                return f"{champ} base stats growth health attack damage armor magic resist League of Legends"
            if intent in CHAMPION_PLAYSTYLE_INTENTS:
                return f"{champ} playstyle win condition power curve teamfight splitpush strategy League of Legends"
            return f"{champ} {lane_str}champion abilities playstyle tactics overview League of Legends"

        # 5. Team Composition / Archetype Queries
        if intent in ("TEAM_COMPOSITION_BUILDING", "TEAM_COUNTER_ANALYSIS") or ((comp_archetype or damage_composition) and not champ):
            target_comp = damage_composition or comp_archetype or "hypercarry_protect"
            is_counter = intent == "TEAM_COUNTER_ANALYSIS" or any(w in question.lower() for w in COUNTER_KEYWORDS)
            if is_counter:
                return f"Counter picks and itemization strategy against {target_comp} team composition in League of Legends"
            p_curve = classification.get("power_curve") or ""
            return f"Drafting core champions synergies {p_curve} and playstyle for {target_comp} team composition League of Legends"

        # 6. Multi-Enemy Team Counter Analysis
        if intent == "TEAM_COUNTER_ANALYSIS" or (enemy_champs and len(enemy_champs) >= 2 and intent in ("COUNTER_QUERY", "UNKNOWN")):
            team_str = ", ".join(enemy_champs) if enemy_champs else "enemy team"
            return f"Counter picks team composition strategy against {team_str} League of Legends"

        # 7-10. Standalone Item, Rune, Skin, ARAM queries via template table
        if intent == "ITEM_INFO" or (item and not champ):
            return STANDALONE_QUERY_TEMPLATES["ITEM_INFO"].format(item=item or question)
        if intent == "RUNE_INFO" or (rune and not champ):
            return STANDALONE_QUERY_TEMPLATES["RUNE_INFO"].format(rune=rune or question)
        if intent in STANDALONE_QUERY_TEMPLATES:
            return STANDALONE_QUERY_TEMPLATES[intent].format(champ=champ or "").strip()

        # 11. Crowd Control / Ability Effect Filters
        if cc_types or effects or intent in CC_EFFECT_INTENTS:
            criteria = (cc_types or []) + (effects or [])
            return f"Champions with {' '.join(criteria)} crowd control mechanics League of Legends"

        # 12-13. Counter / Role / Lane Queries
        if intent == "COUNTER_QUERY" and (role or lane):
            return f"How to counter {lane_str}{role or ''} champions in League of Legends strategy laning counter picks items"
        if role or intent == "ROLE_QUERY":
            return f"{lane_str}{role or ''} champions archetype class tactics guide League of Legends"
        if lane or intent == "LANE_QUERY":
            return f"{lane} lane champions best picks matchups guide League of Legends"

        return question

    def filter_composition_contexts(self, rag_contexts, classification):
        """Filter RAG results for team composition queries."""
        target_comp = classification.get("comp_archetype") or classification.get("damage_composition")
        filtered = []
        for c in rag_contexts:
            meta = c.get("metadata", {})
            comp_id = meta.get("comp_id", "")
            chunk_type = meta.get("chunk_type", "")
            source = c.get("source", "")
            text_lower = (c.get("text") or "").lower()
            first_line = text_lower.split("\n")[0]

            if "graph" in source or chunk_type == "role_guide" or "role_guide" in source:
                filtered.append(c)
                continue

            if target_comp:
                target_tokens = [t for t in target_comp.lower().split("_") if len(t) > 2]
                if (comp_id == target_comp) or any(t in first_line for t in target_tokens):
                    filtered.append(c)
            else:
                filtered.append(c)

        return filtered or rag_contexts

    def filter_champion_contexts(self, rag_contexts, champion):
        """Filter RAG results to ensure the requested champion is present in metadata or text."""
        req_champ = champion.lower()
        champ_filtered = [
            c for c in rag_contexts
            if req_champ in (c.get("text") or "").lower()
            or req_champ == (c.get("metadata", {}).get("champion") or "").lower()
            or req_champ == (c.get("metadata", {}).get("entity_name") or "").lower()
        ]
        return champ_filtered or rag_contexts

    def answer(self, question):
        """
        Process a user question through the hybrid RAG-first pipeline.

        Returns:
            Dict with:
            - question: Original user query
            - intent: Extracted intent info
            - rag_contexts: Retrieved passages from Graph + Vector
            - structured_data: Specific static attributes if applicable (skins/ARAM)
            - response: Final natural language response
        """
        # 1. Intent and Entity Extraction
        classification = self.classifier.classify(question, self.conversation_history)
        intent = classification.get("intent", "UNKNOWN")

        # Entity recovery: If champion not detected by classifier, detect from raw question via Graph
        if not classification.get("champion_name") and self.rag_pipeline and hasattr(self.rag_pipeline, "hybrid"):
            gr = getattr(self.rag_pipeline.hybrid, "graph_retriever", None)
            if gr and hasattr(gr, "detect_champion_in_text"):
                detected_c = gr.detect_champion_in_text(question)
                if detected_c:
                    classification["champion_name"] = detected_c

        # 2. Hybrid RAG Retrieval (Graph + Vector + Re-ranking)
        rag_contexts = []
        rag_context_text = ""
        if self.rag_pipeline:
            try:
                retrieval_query = self.build_retrieval_query(question, classification, intent)
                rag_contexts = self.rag_pipeline.retrieve(
                    query=retrieval_query,
                    entities=classification,
                    intent=intent,
                    graph_top_k = graph_top_k,
                    vector_top_k = vector_top_k,
                    rerank_top_k = rerank_top_k,
                )
                if intent in ("TEAM_COMPOSITION_BUILDING", "TEAM_COUNTER_ANALYSIS") or (classification.get("comp_archetype") and intent == "COUNTER_QUERY"):
                    rag_contexts = self.filter_composition_contexts(rag_contexts, classification)

                # Champion-specific filtering: prevent unrelated champions from polluting targeted queries (e.g. ARAM, skins, lore, skills)
                req_champ = (classification.get("champion_name") or "").lower()
                if req_champ and intent in ("ARAM_QUERY", "SKIN_QUERY", "LORE_QUERY", "BUILD_QUERY", "CHAMPION_STATS_AT_LEVEL", "CHAMPION_BASE_STATS", "SKILL_INFO", "LIST_SKILLS"):
                    rag_contexts = self.filter_champion_contexts(rag_contexts, req_champ)

                if rag_contexts:
                    rag_context_text = self.rag_pipeline.format_context_for_llm(rag_contexts)
            except Exception:
                pass

        # 3. Context Sufficiency and Anti-Hallucination Check
        has_champion = bool(classification.get("champion_name"))
        has_item = bool(classification.get("item_name"))
        has_rune = bool(classification.get("rune_name"))
        has_role = bool(classification.get("role") or classification.get("user_role"))
        has_lane = bool(classification.get("lane"))
        has_comp = bool(classification.get("comp_archetype") or classification.get("damage_composition"))
        has_entity = has_champion or has_item or has_rune or has_role or has_lane or has_comp

        # After reranking, "score" is sigmoid-normalized [0,1].
        # Before reranking (fallback), "score" is RRF (always < 0.1).
        # Use rerank_score (raw logit) if available, otherwise use score.
        top_rag_score = max([c.get("score", 0.0) for c in rag_contexts]) if rag_contexts else 0.0
        insufficient_context = False

        if not rag_contexts:
            insufficient_context = True
        elif not has_entity and top_rag_score < 0.3:
            # No domain entities recognized and retrieval confidence is low -> out of scope
            # 0.3 sigmoid ≈ logit of -0.85, meaning "probably not relevant"
            insufficient_context = True
            rag_contexts = []
            rag_context_text = ""

        # Structured data attributes (highest-priority verified facts from MongoDB and KnowledgeStore)
        structured_data = {}
        if intent != "UNKNOWN":
            try:
                res_disp = self.retriever.dispatch_query(intent, classification)
                if isinstance(res_disp, dict) and not res_disp.get("error") and not res_disp.get("info"):
                    structured_data = res_disp
            except Exception:
                pass

        if structured_data:
            insufficient_context = False

        # Merge payload for generator
        merged_payload = {
            "intent": intent,
            "entities": classification,
            "question": question,
            "insufficient_context": insufficient_context,
        }
        if rag_context_text:
            merged_payload["rag_retrieved_context"] = rag_context_text
        if structured_data:
            merged_payload["structured_data"] = structured_data

        # 4. Response Generation via LLM (or dynamic fallback)
        response_text = self.generator.generate(
            question,
            merged_payload,
        )

        # 5. Save to conversation history
        self.conversation_history.append({"role": "user", "content": question})
        self.conversation_history.append({"role": "assistant", "content": response_text})

        return {
            "question": question,
            "intent": intent,
            "entities": classification,
            "rag_contexts": rag_contexts,
            "structured_data": structured_data,
            "response": response_text,
        }

    def reset_conversation(self):
        """Clear conversation history."""
        self.conversation_history = []


# Singleton
bot_instance = None


def get_bot():
    global bot_instance
    if bot_instance is None:
        bot_instance = LoLBot()
    return bot_instance


if __name__ == "__main__":
    bot = get_bot()
    res = bot.answer("Who counters Yasuo?")
