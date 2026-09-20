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
from chatbot.data_retriever import DataRetriever
from chatbot.intent_classifier import IntentClassifier
from chatbot.knowledge_store import KnowledgeStore, get_knowledge_store
from chatbot.response_generator import ResponseGenerator
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
        except Exception as e:
            print(f"[LoLBot] Notice: RAG pipeline init ({e}). Using structured retriever fallback.")
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

        # 2. Ability Mechanics Query (e.g. Does Yasuo's Wind Wall block Lux's R?)
        if intent == "ABILITY_MECHANIC_QUERY":
            sk_str = f" ability {skill_key}" if skill_key else ""
            inter = classification.get("interaction_champion", "")
            inter_str = f" {inter} wind wall spell shield" if inter else ""
            mech = classification.get("mechanic", "")
            return f"{champ or ''}{sk_str} ability description {mech}{inter_str} League of Legends".strip()

        # 3. Role-Specific Counter Pick Query (e.g. Which Support to pick against Dive and Assassins)
        if intent == "ROLE_COUNTER_PICK":
            u_role = classification.get("user_role") or role or "champion"
            t_val = classification.get("target") or "enemy"
            extra_terms = "peel disengage anti-dive crowd control protection" if ("support" in str(u_role).lower() or "dive" in str(t_val).lower() or "assassin" in str(t_val).lower()) else "items kit mechanics"
            return f"Best {u_role} counter picks against {t_val} {extra_terms} in League of Legends"

        # 4. Team Composition / Archetype Queries (Drafting vs Countering)
        if intent == "TEAM_COMPOSITION_BUILDING" or comp_archetype or damage_composition:
            target_comp = damage_composition or comp_archetype or "hypercarry_protect"
            is_counter_comp = (
                intent == "TEAM_COUNTER_ANALYSIS"
                and any(w in question.lower() for w in ["counter", "against", "beat", "facing", "versus", "vs", "punish", "enemy"])
            ) or (
                intent != "TEAM_COMPOSITION_BUILDING"
                and any(w in question.lower() for w in ["counter", "against", "beat", "facing", "versus", "vs", "punish", "enemy"])
            )
            if is_counter_comp:
                return f"Counter picks and itemization strategy against {target_comp} team composition in League of Legends"
            else:
                p_curve = classification.get("power_curve") or ""
                return f"Drafting core champions synergies {p_curve} and playstyle for {target_comp} team composition League of Legends"

        # 5. Multi-Enemy Team Counter Analysis
        if intent == "TEAM_COUNTER_ANALYSIS" or (enemy_champs and len(enemy_champs) >= 2 and intent in ("COUNTER_QUERY", "UNKNOWN")):
            team_str = ", ".join(enemy_champs) if enemy_champs else "enemy team"
            return f"Counter picks team composition strategy against {team_str} League of Legends"

        # 6. Item Queries
        if intent == "ITEM_INFO" or (item and intent not in ("BUILD_QUERY", "COUNTER_QUERY")):
            item_target = item or question
            return f"{item_target} item stats recipe build cost passive active League of Legends"

        # 7. Rune Queries
        if intent == "RUNE_INFO" or (rune and intent not in ("BUILD_QUERY", "COUNTER_QUERY")):
            rune_target = rune or question
            return f"{rune_target} rune keystone precision domination sorcery resolve inspiration League of Legends"

        # 8. Skin / Cosmetic Query
        if intent == "SKIN_QUERY":
            return f"{champ or ''} skins cosmetics chromas splash art catalog League of Legends".strip()

        # 9. ARAM Balance Query
        if intent == "ARAM_QUERY":
            return f"{champ or ''} ARAM balance damage dealt taken modifiers Howling Abyss League of Legends".strip()

        # 10. Targeted Single Champion Queries
        if champ:
            if skill_key or intent in ("SKILL_INFO", "SKILL_COOLDOWN", "SKILL_DAMAGE_AT_LEVEL", "SKILL_MANA_COST", "LIST_SKILLS"):
                sk_str = f" {skill_key}" if skill_key else ""
                return f"{champ}{sk_str} ability mechanics damage cooldown scaling cost League of Legends"
            elif intent == "LORE_QUERY":
                return f"{champ} lore story biography origin background Runeterra League of Legends"
            elif intent == "COUNTER_QUERY":
                direction = classification.get("counter_direction")
                if direction == "counters":
                    return f"Who does {champ} counter favorable matchups strong against League of Legends"
                return f"How to counter {champ} {lane_str}in League of Legends weaknesses tips counter items counter picks"
            elif intent == "BUILD_QUERY":
                return f"Best build items runes keystone guide for {champ} {lane_str}League of Legends"
            elif intent == "SYNERGY_QUERY":
                return f"Best duo synergy champions teamfight combos with {champ} League of Legends"
            elif intent in ("CHAMPION_BASE_STATS", "CHAMPION_STATS_AT_LEVEL"):
                return f"{champ} base stats growth health attack damage armor magic resist League of Legends"
            elif intent in ("CHAMPION_SEMANTIC_PROFILE", "CHAMPION_BY_PLAYSTYLE", "CHAMPION_BY_WIN_CONDITION"):
                return f"{champ} playstyle win condition power curve teamfight splitpush strategy League of Legends"
            else:
                return f"{champ} {lane_str}champion abilities playstyle tactics overview League of Legends"

        # 11. Crowd Control / Ability Effect Filters
        if cc_types or effects or intent in ("CHAMPION_BY_CC", "CHAMPION_BY_EFFECT", "MULTI_PROPERTY_FILTER"):
            criteria = []
            if cc_types:
                criteria.extend(cc_types)
            if effects:
                criteria.extend(effects)
            return f"Champions with {' '.join(criteria)} crowd control mechanics League of Legends"

        # 12. Counter Queries by Role or Lane
        if intent == "COUNTER_QUERY" and (role or lane):
            return f"How to counter {lane_str}{role or ''} champions in League of Legends strategy laning counter picks items"

        # 13. Role and Lane Queries
        if role or intent == "ROLE_QUERY":
            return f"{lane_str}{role or ''} champions archetype class tactics guide League of Legends"
        if lane or intent == "LANE_QUERY":
            return f"{lane} lane champions best picks matchups guide League of Legends"

        return question

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
                    target_comp = classification.get("comp_archetype") or classification.get("damage_composition")
                    filtered = []
                    for c in rag_contexts:
                        meta = c.get("metadata", {})
                        comp_id = meta.get("comp_id", "")
                        chunk_type = meta.get("chunk_type", "")
                        source = c.get("source", "")
                        text_lower = (c.get("text") or "").lower()
                        first_line = text_lower.split("\n")[0]

                        # Graph composition drafting results
                        if "graph" in source:
                            filtered.append(c)
                            continue

                        # Role tactical guides
                        if chunk_type == "role_guide" or "role_guide" in source:
                            filtered.append(c)
                            continue

                        # Targeted composition chunk
                        if target_comp:
                            target_tokens = [t for t in target_comp.lower().split("_") if len(t) > 2]
                            is_target = (comp_id == target_comp) or any(t in first_line for t in target_tokens)
                            if is_target:
                                filtered.append(c)
                        else:
                            filtered.append(c)

                    if filtered:
                        rag_contexts = filtered

                # Champion-specific filtering: prevent unrelated champions from polluting targeted queries (e.g. ARAM, skins, lore, skills)
                req_champ = (classification.get("champion_name") or "").lower()
                if req_champ and intent in ("ARAM_QUERY", "SKIN_QUERY", "LORE_QUERY", "BUILD_QUERY", "CHAMPION_STATS_AT_LEVEL", "CHAMPION_BASE_STATS", "SKILL_INFO", "LIST_SKILLS"):
                    champ_filtered = [
                        c for c in rag_contexts
                        if req_champ in (c.get("text") or "").lower()
                        or req_champ == (c.get("metadata", {}).get("champion") or "").lower()
                        or req_champ == (c.get("metadata", {}).get("entity_name") or "").lower()
                    ]
                    if champ_filtered:
                        rag_contexts = champ_filtered

                if rag_contexts:
                    rag_context_text = self.rag_pipeline.format_context_for_llm(rag_contexts)
            except Exception as e:
                print(f"[LoLBot] RAG retrieval exception ({e}).")

        # 3. Context Sufficiency and Anti-Hallucination Check
        has_champion = bool(classification.get("champion_name"))
        has_item = bool(classification.get("item_name"))
        has_rune = bool(classification.get("rune_name"))
        has_role = bool(classification.get("role") or classification.get("user_role"))
        has_lane = bool(classification.get("lane"))
        has_comp = bool(classification.get("comp_archetype") or classification.get("damage_composition"))
        has_entity = has_champion or has_item or has_rune or has_role or has_lane or has_comp

        top_rag_score = max([c.get("score", 0.0) for c in rag_contexts]) if rag_contexts else 0.0
        insufficient_context = False

        if not rag_contexts:
            insufficient_context = True
        elif not has_entity and top_rag_score < 0.38:
            # No domain entities recognized and retrieval confidence is low -> out of scope
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
            except Exception as e:
                print(f"[LoLBot] Notice in dispatch_query ({e})")

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
_bot_instance = None


def get_bot():
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = LoLBot()
    return _bot_instance


if __name__ == "__main__":
    bot = get_bot()
    print("\nTest Bot Query: Who counters Yasuo?")
    res = bot.answer("Who counters Yasuo?")
    print(f"Intent: {res['intent']}")
    print(f"Response:\n{res['response']}")
