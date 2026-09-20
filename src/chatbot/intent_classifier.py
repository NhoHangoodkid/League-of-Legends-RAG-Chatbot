"""
Intent Classifier for LoL Knowledge Bot.

Uses local LLM (Qwen 3 4B via Ollama) with OpenAI-compatible API to classify user questions,
extract entities, and resolve conversational context. Includes a fallback rule-based classifier
in case the local LLM server is temporarily offline.
"""

import json
import re
import time
import httpx
from openai import OpenAI

from chatbot.config import llm_model, llm_temperature, ollama_base_url
from chatbot.prompts import intent_classification_prompt

ollama_status_cache = {"last_check": 0.0, "is_ready": False}


def is_ollama_available(base_url):
    now = time.time()
    if now - ollama_status_cache["last_check"] < 10.0:
        return ollama_status_cache["is_ready"]

    ollama_status_cache["last_check"] = now
    try:
        health_url = base_url.replace("/v1", "")
        r = httpx.get(health_url, timeout = httpx.Timeout(2.0, connect = 1.0))
        ollama_status_cache["is_ready"] = (r.status_code == 200)
    except Exception:
        ollama_status_cache["is_ready"] = False

    return ollama_status_cache["is_ready"]


from chatbot.knowledge_store import KnowledgeStore, get_knowledge_store


class IntentClassifier:
    """Classify user intent and extract query entities dynamically from KnowledgeStore."""

    def __init__(
        self,
        base_url = ollama_base_url,
        model = llm_model,
        store = None,
    ):
        self.base_url = base_url
        self.model = model
        self.store = store or get_knowledge_store()
        self.client = OpenAI(
            base_url = base_url,
            api_key = "ollama",
            timeout = httpx.Timeout(5.0, connect = 2.0),
            max_retries = 1,
        )

    def classify(self, question, conversation_history = None):
        """
        Classify intent and extract entities from question.

        Args:
            question: The user's question.
            conversation_history: List of past {"role": "user"|"assistant", "content": "..."}.

        Returns:
            Dict containing intent and extracted entity fields.
        """
        # 1. Fast Heuristic Check First (Instant ~0.001s)
        # If question has clear keywords/entities, avoid 60s+ Ollama JSON prompt overhead
        heuristic_res = self.heuristic_fallback(question)
        if heuristic_res.get("intent") != "UNKNOWN" and (
            heuristic_res.get("champion_name")
            or heuristic_res.get("item_name")
            or heuristic_res.get("rune_name")
            or heuristic_res.get("role")
            or heuristic_res.get("lane")
            or heuristic_res.get("cc_types")
            or heuristic_res.get("ability_effects")
            or heuristic_res.get("comp_archetype")
            or heuristic_res.get("damage_composition")
            or heuristic_res.get("enemy_champions")
            or heuristic_res.get("allied_champions")
            or heuristic_res.get("comparison_champions")
            or heuristic_res.get("target")
        ):
            return heuristic_res

        # Build conversational context
        context_str = ""
        if conversation_history:
            recent_history = conversation_history[-4:]
            context_lines = []
            for msg in recent_history:
                role = "User" if msg.get("role") == "user" else "Assistant"
                context_lines.append(f"{role}: {msg.get('content', '')}")
            context_str = "\n".join(context_lines)

        prompt = intent_classification_prompt.format(question = question)
        messages = []
        if context_str:
            messages.append({
                "role": "system",
                "content": f"Previous conversation context:\n{context_str}\nUse this context to resolve pronouns or follow-up questions.",
            })
        messages.append({"role": "user", "content": prompt})

        # Try LLM classification if server is running
        if is_ollama_available(self.base_url):
            try:
                response = self.client.chat.completions.create(
                    model = self.model,
                    messages = messages,
                    temperature = 0.0,
                    max_tokens = 300,
                    timeout = 25.0,
                    extra_body = {
                        "num_ctx": 8192,
                    },
                )

                raw_content = response.choices[0].message.content.strip()
                parsed = self.extract_json(raw_content)
                if parsed and isinstance(parsed, dict) and "intent" in parsed:
                    if parsed.get("intent") not in ("UNKNOWN", None) and (
                        parsed.get("champion_name")
                        or parsed.get("item_name")
                        or parsed.get("rune_name")
                        or parsed.get("cc_types")
                        or parsed.get("ability_effects")
                        or parsed.get("role")
                        or parsed.get("comparison_champions")
                    ):
                        return self.normalize_entities(parsed)
                    elif parsed.get("champion_name"):
                        return self.normalize_entities(parsed)

            except Exception as e:
                print(f"[IntentClassifier] LLM classification notice ({e}). Falling back to heuristic classifier...")

        # Rule-based fallback
        return self.heuristic_fallback(question)

    @staticmethod
    def extract_json(content):
        """Extract and parse JSON from markdown code block or raw string."""
        if not content:
            return None

        # Clean code fences
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        try:
            return json.loads(content)
        except Exception:
            # Try finding first { and last }
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    pass
        return None

    @staticmethod
    def normalize_entities(entities):
        """Normalize extracted entity casing."""
        if entities.get("champion_name"):
            entities["champion_name"] = str(entities["champion_name"]).strip()

        if entities.get("skill_key"):
            entities["skill_key"] = str(entities["skill_key"]).upper().strip()

        if entities.get("comparison_champions"):
            entities["comparison_champions"] = [
                str(c).strip() for c in entities["comparison_champions"] if c
            ]

        if entities.get("enemy_champions"):
            entities["enemy_champions"] = [
                str(c).strip() for c in entities["enemy_champions"] if c
            ]

        return entities

    def heuristic_fallback(self, question):
        """Fast fallback rule-based classifier when LLM is unavailable."""
        q = question.lower()

        # Normalize common user typos and spelling variations
        typo_map = {
            r"\ben?gag\w*\b": "engage",
            r"\benaged\b": "engage",
            r"\bassasins?\b": "assassin",
            r"\bchamps\b": "champions",
            r"\bmages?\b": "mage",
            r"\btankers?\b": "tank",
        }
        for pattern, repl in typo_map.items():
            q = re.sub(pattern, repl, q)

        result = {
            "intent": "UNKNOWN",
            "champion_name": None,
            "comp_archetype": None,
            "damage_composition": None,
            "skill_key": None,
            "skill_level": None,
            "character_level": None,
            "stat_name": None,
            "comparison_champions": None,
            "role": None,
            "lane": None,
            "counter_direction": None,
            "item_name": None,
            "rune_name": None,
            "cc_types": None,
            "ability_effects": None,
            "playstyles": None,
            "power_curve": None,
            "win_condition": None,
            "enemy_champions": None,
            "user_role": None,
            "target": None,
            "target_type": None,
            "interaction_champion": None,
            "mechanic": None,
        }

        # 1. Detect explicit skill ownership pattern first
        sorted_champs = self.store.get_all_champion_names_sorted()
        aliases = self.store.get_champion_aliases()

        # Check for interaction champion (e.g. "Yasuo's wind wall", "Yasuo wind wall", "wind wall of Yasuo")
        interaction_match = re.search(
            r"([a-z0-9 .-]+)(?:'s|\s+)?\s+(?:wind\s*wall|wall|shield|spell\s*shield)",
            q
        ) or re.search(
            r"(?:wind\s*wall|wall|shield|spell\s*shield)\s+(?:of|from)\s+([a-z0-9 .-]+)",
            q
        )
        if interaction_match:
            inter_cand = interaction_match.group(1).strip()
            for candidate in sorted_champs:
                if re.search(r"(?:\b|^)" + re.escape(candidate) + r"(?:\b|$)", inter_cand):
                    canonical_id = aliases.get(candidate) or self.store.champion_lookup.get(self.store.normalize_key(candidate))
                    champ_obj = self.store.get_champion(canonical_id or candidate)
                    result["interaction_champion"] = champ_obj.get("name") if champ_obj else candidate.title()
                    break

        # Pattern A: English possessive or direct adjacency (e.g. "Lux's R", "Lux R", "Ahri Q", "Jinx ultimate")
        possessive_match = re.search(
            r"\b([a-z0-9 .-]+)(?:'s|\s+)?\s+([qwer]|passive|ult|ultimate)\b",
            q
        )
        if possessive_match:
            cand_name = possessive_match.group(1).strip()
            k = possessive_match.group(2).upper()
            sk_val = "R" if k in ("ULT", "ULTIMATE") else ("P" if k == "PASSIVE" else k)
            for candidate in sorted_champs:
                if re.search(r"(?:\b|^)" + re.escape(candidate) + r"(?:\b|$)", cand_name):
                    # Make sure the candidate is not the defender who owns the shield/wall
                    if result.get("interaction_champion") and candidate.lower() == result["interaction_champion"].lower():
                        continue
                    canonical_id = aliases.get(candidate) or self.store.champion_lookup.get(self.store.normalize_key(candidate))
                    champ_obj = self.store.get_champion(canonical_id or candidate)
                    result["champion_name"] = champ_obj.get("name") if champ_obj else candidate.title()
                    result["skill_key"] = sk_val
                    break

        # Pattern B: Prepositional ownership (e.g. "R of Lux", "ultimate of Lux", "skill Q of Yasuo")
        if not result["champion_name"]:
            skill_owner_match = re.search(
                r"\b(?:skill|ability|ult|ultimate)?\s*\b([qwer]|passive|ult|ultimate)\b\s+(?:of|from|on)\b\s+([a-z0-9' .-]+)",
                q
            )
            if skill_owner_match:
                k = skill_owner_match.group(1).upper().replace(" ", "")
                result["skill_key"] = "R" if k in ("ULT", "ULTIMATE") else ("P" if k == "PASSIVE" else k)
                owner_text = skill_owner_match.group(2).strip()
                for candidate in sorted_champs:
                    if re.search(r"(?:\b|^)" + re.escape(candidate) + r"(?:\b|$)", owner_text):
                        canonical_id = aliases.get(candidate) or self.store.champion_lookup.get(self.store.normalize_key(candidate))
                        champ_obj = self.store.get_champion(canonical_id or candidate)
                        result["champion_name"] = champ_obj.get("name") if champ_obj else candidate.title()
                        break

        if not result["skill_key"]:
            skill_match = re.search(r"\b([qwer]|passive|ult|ultimate)\b", q)
            if skill_match:
                k = skill_match.group(1).upper().replace(" ", "")
                result["skill_key"] = "R" if k in ("ULT", "ULTIMATE") else ("P" if k == "PASSIVE" else k)

        lvl_match = re.search(r"(?:level|rank|lvl|lv)\s*(\d+)", q)
        if lvl_match:
            val = int(lvl_match.group(1))
            if result["skill_key"] and val <= 5:
                result["skill_level"] = val
            else:
                result["character_level"] = val

        # 2. Extract champion name dynamically from KnowledgeStore (if not already extracted via ownership)
        if not result["champion_name"]:
            for candidate in sorted_champs:
                pattern = r"(?:\b|^)" + re.escape(candidate) + r"(?:\b|$)"
                if re.search(pattern, q):
                    canonical_id = aliases.get(candidate) or self.store.champion_lookup.get(self.store.normalize_key(candidate))
                    champ_obj = self.store.get_champion(canonical_id or candidate)
                    result["champion_name"] = champ_obj.get("name") if champ_obj else candidate.title()
                    break

        # Check for secondary / interaction champion (e.g. Yasuo in "Does Yasuo's wind wall block Lux's R?")
        for candidate in sorted_champs:
            pattern = r"(?:\b|^)" + re.escape(candidate) + r"(?:\b|$)"
            if re.search(pattern, q):
                canonical_id = aliases.get(candidate) or self.store.champion_lookup.get(self.store.normalize_key(candidate))
                champ_obj = self.store.get_champion(canonical_id or candidate)
                c_name = champ_obj.get("name") if champ_obj else candidate.title()
                if c_name != result.get("champion_name"):
                    result["interaction_champion"] = c_name
                    break

        # Lane / Position recognition (with plurals and synonyms)
        lane_patterns = {
            "top": [r"\b(?:top|toplane|toplaner|toplaners)\b"],
            "mid": [r"\b(?:mid|midlane|midlaner|midlaners|middle)\b"],
            "bot": [r"\b(?:bot|botlane|botlaner|botlaners|bottom)\b"],
            "jungle": [r"\b(?:jungle|jungler|junglers|jg)\b"],
            "support": [r"\b(?:support|supports|supp|sp)\b"],
        }
        for l_name, patterns in lane_patterns.items():
            if any(re.search(pat, q) for pat in patterns):
                result["lane"] = l_name
                break

        # Comprehensive Role / Class recognition with plurals, subroles, and synonyms
        role_patterns = {
            "fighter": [
                r"\b(?:fighter|fighters|bruiser|bruisers|juggernaut|juggernauts|diver|divers|skirmisher|skirmishers)\b"
            ],
            "assassin": [
                r"\b(?:assassin|assassins|slayer|slayers)\b"
            ],
            "mage": [
                r"\b(?:mage|mages|caster|casters|ap carry|ap carries|burst mage|burst mages)\b"
            ],
            "tank": [
                r"\b(?:tank|tanks|tanker|tankers|vanguard|vanguards|warden|wardens)\b"
            ],
            "marksman": [
                r"\b(?:marksman|marksmen|adc|adcs|ad carry|ad carries)\b"
            ],
            "support": [
                r"\b(?:support|supports|enchanter|enchanters|catcher|catchers|supp|sp)\b"
            ],
        }
        for r_name, patterns in role_patterns.items():
            if any(re.search(pat, q) for pat in patterns):
                result["role"] = r_name
                break

        # Composition and Archetype recognition dynamically from KnowledgeStore
        is_comp_context = any(w in q for w in ["comp", "composition", "draft", "lineup", "line-up", "team", "build around", "build a", "for a", "bo khung", "đội hình"])
        sorted_comp_aliases = self.store.get_all_composition_aliases_sorted()
        for alias in sorted_comp_aliases:
            pattern = r"(?:\b|^)" + re.escape(alias) + r"(?:\b|$)"
            if re.search(pattern, q):
                matched_comp = self.store.get_composition(alias)
                if matched_comp:
                    cid = matched_comp.get("comp_id")
                    # If alias is an effect word (like stealth, sustain) but query is not about a comp, skip
                    if cid in ("stealth", "sustain", "heavy_cc", "high_mobility") and not is_comp_context:
                        continue
                    if cid in ("full_ad", "full_ap"):
                        result["damage_composition"] = cid
                    else:
                        result["comp_archetype"] = cid
                    break

        # Power curve recognition
        if re.search(r"\b(?:late game|late-game|scaling|scaled|hypercarry|infinite scaling)\b", q):
            result["power_curve"] = "LateGame"
        elif re.search(r"\b(?:early game|early-game|snowball|early pressure|early aggression|lane bully)\b", q):
            result["power_curve"] = "EarlyGame"
        elif re.search(r"\b(?:mid game|mid-game)\b", q):
            result["power_curve"] = "MidGame"

        # Fallback archetype recognition if not matched via aliases
        if not result.get("comp_archetype") and not result.get("damage_composition"):
            if re.search(r"\b(?:dive|diving|diver|divers|en?gag\w*|all-?in|backline dive)\b", q):
                result["comp_archetype"] = "dive"
            elif re.search(r"\b(?:poke|poking|pokers?|artillery|siege|sieging)\b", q):
                result["comp_archetype"] = "poke"
            elif re.search(r"\b(?:split-?push\w*|duelist\w*|side-?lane\w*)\b", q):
                result["comp_archetype"] = "splitpush"
            elif re.search(r"\b(?:sustain\w*|heal\w*|vamp\w*)\b", q) and is_comp_context:
                result["comp_archetype"] = "sustain"
            elif re.search(r"\b(?:stealth|invisibility|ambush)\b", q) and is_comp_context:
                result["comp_archetype"] = "stealth"
            elif re.search(r"\b(?:wombo|wombo-?combo|teamfight|team-?fight|5v5|aoe teamfight|aoe combo|catastrophic aoe|giao tranh tong|giao tranh tổng)\b", q):
                result["comp_archetype"] = "wombo_combo"
            elif re.search(r"\b(?:heavy cc|cc heavy|crowd control|lockdown\w*)\b", q) and is_comp_context:
                result["comp_archetype"] = "heavy_cc"
            elif re.search(r"\b(?:high mobility|mobility|mobile)\b", q) and is_comp_context:
                result["comp_archetype"] = "high_mobility"
            elif re.search(r"\b(?:scaled|scaling|late game|late-game|hypercarry|hypercarries|infinite stack\w*|stacking|very scaled|protect the hypercarry|protect hypercarry)\b", q) and is_comp_context:
                result["comp_archetype"] = "hypercarry_protect"
                result["power_curve"] = "LateGame"
            elif re.search(r"\b(?:snowball\w*|early game|early-game|early aggression|lane bully|early pressure|aggro)\b", q) and is_comp_context:
                result["comp_archetype"] = "early_snowball"
                result["power_curve"] = "EarlyGame"
            elif re.search(r"\b(?:full ad|all ad|ad heavy|physical damage)\b", q) and is_comp_context:
                result["damage_composition"] = "full_ad"
            elif re.search(r"\b(?:full ap|all ap|ap heavy|magic damage)\b", q) and is_comp_context:
                result["damage_composition"] = "full_ap"
            elif re.search(r"\b(?:fighter|bruiser|juggernaut)\b", q) and any(w in q for w in ["comp", "composition", "team"]):
                result["comp_archetype"] = "fighter_heavy"
            elif re.search(r"\b(?:mage|caster|ap)\b", q) and any(w in q for w in ["comp", "composition", "team"]):
                result["comp_archetype"] = "mage_heavy"
            elif re.search(r"\b(?:tank|tanker|frontline)\b", q) and any(w in q for w in ["comp", "composition", "team"]):
                result["comp_archetype"] = "tank_heavy"
            elif re.search(r"\b(?:assassin|slayer)\b", q) and any(w in q for w in ["comp", "composition", "team"]):
                result["comp_archetype"] = "assassin_heavy"
            elif re.search(r"\b(?:marksman|adc)\b", q) and any(w in q for w in ["comp", "composition", "team"]):
                result["comp_archetype"] = "marksman_heavy"
            elif re.search(r"\b(?:support|enchanter)\b", q) and any(w in q for w in ["comp", "composition", "team"]):
                result["comp_archetype"] = "support_heavy"
            elif re.search(r"\b(?:shield|shields|barrier)\b", q) and any(w in q for w in ["comp", "composition", "team"]):
                result["comp_archetype"] = "shield_heavy"

        # 3. Item recognition dynamically from KnowledgeStore
        sorted_items = self.store.get_all_item_names_sorted()
        english_stopwords_2letter = {"is", "in", "at", "to", "on", "as", "an", "or", "no", "so", "do", "it"}
        for item_candidate in sorted_items:
            # Avoid common English grammatical words (e.g. "what IS dc in lol") being falsely detected as Immortal Shieldbow
            if item_candidate.lower() in english_stopwords_2letter:
                if not (re.search(r"\b" + re.escape(item_candidate.upper()) + r"\b", question)
                        or re.search(r"\b(?:item|build)\s+" + re.escape(item_candidate) + r"\b", q)
                        or re.search(r"\b" + re.escape(item_candidate) + r"\s+(?:item|build|stats)\b", q)):
                    continue

            pattern = r"(?:\b|^)" + re.escape(item_candidate) + r"(?:\b|$)"
            if re.search(pattern, q):
                matched_item = self.store.get_item(item_candidate)
                if matched_item:
                    result["item_name"] = matched_item.get("name")
                    if any(w in q for w in ["cost", "price", "how much", "stats", "recipe", "build into", "passive", "active", "effect"]):
                        result["intent"] = "ITEM_INFO"
                    elif not result.get("champion_name"):
                        result["intent"] = "ITEM_INFO"
                    break

        # 4. Rune recognition dynamically from KnowledgeStore
        sorted_runes = self.store.get_all_rune_names_sorted()
        for rune_candidate in sorted_runes:
            pattern = r"(?:\b|^)" + re.escape(rune_candidate) + r"(?:\b|$)"
            if re.search(pattern, q):
                matched_rune = self.store.get_rune(rune_candidate)
                if matched_rune:
                    result["rune_name"] = matched_rune.get("name")
                    if any(w in q for w in ["rune", "keystone", "perk", "rune tree"]):
                        result["intent"] = "RUNE_INFO"
                    break

        # 5. Multi-champion detection (for team compositions / matchups)
        detected_champs = []
        for candidate in sorted_champs:
            pattern = r"(?:\b|^)" + re.escape(candidate) + r"(?:\b|$)"
            if re.search(pattern, q):
                canonical_id = aliases.get(candidate) or self.store.champion_lookup.get(self.store.normalize_key(candidate))
                champ_obj = self.store.get_champion(canonical_id or candidate)
                c_name = champ_obj.get("name") if champ_obj else candidate.title()
                if c_name not in detected_champs:
                    detected_champs.append(c_name)
        if len(detected_champs) >= 2:
            result["enemy_champions"] = detected_champs

        # 6. Intent detection
        # 6.0 Specialized Draft Counter Pick Check (e.g. Which [Role] to pick [against/into/for anti] [Target])
        role_map_draft = {
            "adc": "marksman", "adcs": "marksman", "marksman": "marksman", "marksmen": "marksman",
            "support": "support", "supports": "support", "supp": "support", "sp": "support",
            "mid": "mid", "midlane": "mid", "midlaner": "mid",
            "top": "top", "toplane": "top", "toplaner": "top",
            "jungle": "jungle", "jungler": "jungle", "jg": "jungle",
            "tank": "tank", "tanks": "tank", "tanker": "tank", "tankers": "tank",
            "mage": "mage", "mages": "mage", "caster": "mage",
            "fighter": "fighter", "fighters": "fighter", "bruiser": "fighter", "bruisers": "fighter",
            "assassin": "assassin", "assassins": "assassin",
        }
        counter_link_pat = r"(?:for\s+anti|anti|against|into|to\s+counter|to\s+beat|countering|counters|good\s+against|best\s+against|deal\s+with|shred)"
        roles_regex = "|".join(re.escape(k) for k in sorted(role_map_draft.keys(), key=len, reverse=True))
        full_role_pattern = rf"\b({roles_regex}|champion|champ|champions)\b.*?\b{counter_link_pat}\b\s+(?:heavy\s+|many\s+)?([a-z0-9 '\-]+)"
        inverted_anti_pattern = rf"\banti\s+([a-z0-9 '\-]+)\s+({roles_regex})\b"

        role_counter_match = re.search(full_role_pattern, q)
        inverted_match = re.search(inverted_anti_pattern, q) if not role_counter_match else None

        if role_counter_match or inverted_match:
            if role_counter_match:
                role_token = role_counter_match.group(1).lower()
                target_token = role_counter_match.group(2).lower().strip()
            else:
                target_token = inverted_match.group(1).lower().strip()
                role_token = inverted_match.group(2).lower()

            u_role = role_map_draft.get(role_token)

            # Resolve target
            t_type = "unknown"
            t_val = target_token
            for cname in sorted_champs:
                if re.search(r"\b" + re.escape(cname) + r"\b", target_token):
                    canonical_id = aliases.get(cname) or self.store.champion_lookup.get(self.store.normalize_key(cname))
                    champ_obj = self.store.get_champion(canonical_id or cname)
                    t_type = "champion"
                    t_val = champ_obj.get("name") if champ_obj else cname.title()
                    break

            if t_type == "unknown":
                for a in sorted_comp_aliases:
                    if re.search(r"\b" + re.escape(a) + r"\b", target_token):
                        c = self.store.get_composition(a)
                        if c:
                            t_type = "archetype"
                            t_val = c.get("comp_id")
                            break

            if t_type == "unknown":
                for r_word, r_canon in role_map_draft.items():
                    if re.search(r"\b" + re.escape(r_word) + r"\b", target_token):
                        t_type = "role"
                        t_val = r_canon
                        break

            if t_type != "unknown":
                result["intent"] = "ROLE_COUNTER_PICK"
                result["user_role"] = u_role
                result["target"] = t_val
                result["target_type"] = t_type
                if u_role in ("mid", "top", "jungle"):
                    result["lane"] = u_role
                    result["role"] = u_role
                elif u_role:
                    result["role"] = u_role
                    if u_role == "marksman":
                        result["lane"] = "bot"
                    elif u_role == "support":
                        result["lane"] = "support"
                return result

        is_comparison = (len(detected_champs) == 2) and any(w in q for w in [
            "vs", "versus", "solo", "compare", "comparison",
            "who wins", "better", "stronger"
        ]) and not any(w in q for w in ["lore", "story", "origin", "biography", "relationship", "conflict", "rivalry", "history"])
        is_counter_intent = any(w in q for w in [
            "counter", "counters", "countered", "beat", "beats", "against", "weak against",
            "matchup", "how to beat", "counter pick", "counter picks", "pick to counter",
            "what to pick against", "who to pick against", "how to deal with", "how to play against",
            "what should i play against", "who to play against", "how to deal", "how to win against"
        ]) or (
            (result.get("comp_archetype") or result.get("damage_composition"))
            and any(w in q for w in ["deal with", "face", "counter", "against", "beat", "punish", "enemy"])
        ) or (
            ("enemy" in q or "they have" in q or "facing" in q or "against" in q)
            and any(w in q for w in ["counter", "beat", "punish", "deal with", "win against"])
            and not any(w in q for w in ["build", "rune", "lore", "skill", "combo", "synerg"])
        ) or (
            result.get("role") and any(w in q for w in ["enemy", "counter", "face", "against", "beat"])
            and not any(w in q for w in ["build", "rune", "lore", "skill", "combo", "synerg"])
        )

        # Check micro-mechanics queries (Wind Wall, Projectile, Spell Shield, On-Hit)
        is_projectile_q = any(w in q for w in ["wind wall", "windwall", "projectile", "block projectile", "blocked by wind wall", "block skill"]) or ("blocked" in q and any(w in q for w in ["wall", "yasuo", "samira", "braum"]))
        is_spellshield_q = any(w in q for w in ["spell shield", "spellshield", "banshee", "edge of night"]) or ("shield" in q and "block" in q)
        is_onhit_q = any(w in q for w in ["on-hit", "on hit", "onhit", "on-hit effect", "applies on-hit"])
        is_mechanic_query = is_projectile_q or is_spellshield_q or is_onhit_q

        is_skin_query = any(w in q for w in ["skin", "skins", "chroma", "chromas"])
        is_aram_query = any(w in q for w in ["aram", "aram stats", "aram buff", "aram nerf", "aram balance"])

        has_comp = bool(result.get("comp_archetype") or result.get("damage_composition"))
        is_draft_query = any(w in q for w in [
            "draft", "drafting", "draft a", "draft for", "how should we draft", "how to draft",
            "team comp", "team composition", "composition", "compositions", "lineup", "line-up",
            "for a", "for the", "in a", "in the", "pick for", "picks for", "pick in",
            "build for", "build a", "build around", "which champions", "who should we pick",
            "what should we pick", "which champion should we pick", "which champions should we pick",
            "champions for", "best champions for"
        ])

        if is_comparison:
            result["intent"] = "CHAMPION_COMPARISON"
            result["comparison_champions"] = detected_champs[:2]
            result["champion_name"] = detected_champs[0]
            result["enemy_champions"] = None
        elif is_mechanic_query and (result.get("champion_name") or result.get("skill_key")):
            result["intent"] = "ABILITY_MECHANIC_QUERY"
            result["enemy_champions"] = None
            if is_projectile_q:
                result["mechanic"] = "projectile"
            elif is_spellshield_q:
                result["mechanic"] = "spellshieldable"
            elif is_onhit_q:
                result["mechanic"] = "onhit"
        elif is_skin_query and result.get("champion_name"):
            result["intent"] = "SKIN_QUERY"
        elif is_aram_query and result.get("champion_name"):
            result["intent"] = "ARAM_QUERY"
        elif (any(w in q for w in ["doi hinh", "đội hình", "team comp", "teamcomp", "composition", "lineup", "bo khung", "bộ khung"])) and result.get("champion_name"):
            result["intent"] = "CHAMPION_TEAM_COMPOSITION"
        elif has_comp and is_draft_query and not any(w in q for w in ["counter", "against", "beat", "punish", "enemy"]):
            result["intent"] = "TEAM_COMPOSITION_BUILDING"
        elif is_counter_intent:
            is_comp_q = has_comp or any(w in q for w in ["comp", "composition", "team comp", "lineup", "line-up", "bo khung", "đội hình"])
            if len(detected_champs) >= 2 or (is_comp_q and any(w in q for w in ["counter", "against", "beat", "punish", "enemy", "deal with", "face", "facing", "versus", "vs"])):
                result["intent"] = "TEAM_COUNTER_ANALYSIS"
                if detected_champs:
                    result["enemy_champions"] = detected_champs
                if not result.get("comp_archetype") and not result.get("damage_composition"):
                    if re.search(r"\b(?:dive|diving|diver|divers|e?ngag\w*|all-?in)\b", q):
                        result["comp_archetype"] = "dive"
                    elif re.search(r"\b(?:poke|poking|artillery|siege)\b", q):
                        result["comp_archetype"] = "poke"
                    elif re.search(r"\b(?:wombo|teamfight|team-?fight|5v5|aoe|giao tranh)\b", q):
                        result["comp_archetype"] = "wombo_combo"
            elif has_comp:
                result["intent"] = "TEAM_COMPOSITION_BUILDING"
            elif not result.get("champion_name") and is_comp_q:
                result["intent"] = "TEAM_COUNTER_ANALYSIS"
                if not result.get("comp_archetype"):
                    if re.search(r"\b(?:teamfight|team-?fight|5v5|wombo|aoe|giao tranh)\b", q):
                        result["comp_archetype"] = "wombo_combo"
                    elif re.search(r"\b(?:poke|artillery|siege)\b", q):
                        result["comp_archetype"] = "poke"
                    elif re.search(r"\b(?:dive|engage)\b", q):
                        result["comp_archetype"] = "dive"
                    else:
                        result["comp_archetype"] = "wombo_combo"
            else:
                result["intent"] = "COUNTER_QUERY"
            # Determine counter direction:
            # "counters" = who does this champion counter / favorable matchups (e.g. "Who does Yasuo counter?")
            # "countered_by" = who counters this champion / how to play against them (e.g. "Who counters Yasuo?")
            is_outgoing_counter = False
            champ_q = (result.get("champion_name") or "").lower()
            if any(re.search(pat, q) for pat in [
                r"\bwho\s+does\b.*\bcounter\b",
                r"\bwho\s+is\b.*\bweak\s+against\b",
                r"\bstrong\s+against\b",
                r"\bwho\s+does\b.*\bbeats?\b",
            ]):
                is_outgoing_counter = True
            elif champ_q and re.search(rf"\b{re.escape(champ_q)}\s+(counters\s+who|beats\s+who|wins\s+against\s+who)\b", q):
                is_outgoing_counter = True

            result["counter_direction"] = "counters" if is_outgoing_counter else "countered_by"
        elif any(w in q for w in [
            "synerg", "pair with", "pairs with", "combo with", "duo with", "best support for", "partner", "good with",
            "an y", "ăn ý", "hop voi", "hợp với", "di chung", "đi chung",
            "di cap", "đi cặp", "cap voi", "cặp với", "bo doi", "bộ đôi", "di voi", "đi với", "ket hop", "kết hợp",
            "tuong di cung", "tướng đi cùng", "tuong hop", "tướng hợp", "sp cho", "support cho", "ho tro cho", "hỗ trợ cho",
            "phoi hop", "phối hợp", "hop nhat", "hợp nhất", "choi cung", "chơi cùng", "danh cung", "đánh cùng"
        ]):
            result["intent"] = "SYNERGY_QUERY"
        elif any(w in q for w in [
            "build", "items", "itemization", "runes", "keystone", "core items", "spells",
            "core item", "core", "full build", "rune page", "summoner spell", "summoner spells"
        ]) and not any(re.search(r"\b" + re.escape(w) + r"\b", q) for w in ["cost", "price", "how much", "stats"]):
            if result.get("item_name") and not result.get("champion_name"):
                result["intent"] = "ITEM_INFO"
            else:
                result["intent"] = "BUILD_QUERY"
        elif any(w in q for w in ["damage", "scaling", "ratio", "base damage", "ad ratio", "ap ratio"]):
            result["intent"] = "SKILL_DAMAGE_AT_LEVEL" if result["skill_key"] else "CHAMPION_INFO"
        elif any(w in q for w in ["cooldown", "cd"]):
            result["intent"] = "SKILL_COOLDOWN"
        # Champion Stats Intent (Base stats or stats at level)
        elif any(re.search(r"\b" + re.escape(w) + r"\b", q) for w in [
            "base stat", "base stats", "stats", "stat",
            "base health", "health", "hp", "armor", "magic resist", "mr",
            "attack speed", "movement speed", "attack range", "base ad", "attack damage"
        ]) and (result.get("champion_name") or not result.get("item_name")):
            if result.get("character_level"):
                result["intent"] = "CHAMPION_STATS_AT_LEVEL"
            else:
                result["intent"] = "CHAMPION_BASE_STATS"

        # Ability effects: Pull / Hook, Stealth, Dash / Mobility, Shield, Heal / Sustain
        elif re.search(r"\b(?:hook|pull|grab)\b", q):
            result["intent"] = "CHAMPION_BY_EFFECT"
            result["ability_effects"] = ["Pull"]
        elif re.search(r"\b(?:stealth|camouflage|invisible|invisibility)\b", q):
            result["intent"] = "CHAMPION_BY_EFFECT"
            result["ability_effects"] = ["Stealth"]
        elif re.search(r"\b(?:dash|blink|mobility|leap)\b", q):
            result["intent"] = "CHAMPION_BY_EFFECT"
            result["ability_effects"] = ["Dash"]
        elif re.search(r"\b(?:shield|shields|barrier)\b", q) and not is_spellshield_q:
            result["intent"] = "CHAMPION_BY_EFFECT"
            result["ability_effects"] = ["Shield"]
        elif re.search(r"\b(?:heal|heals|healing|sustain|vamp|life\s*steal)\b", q):
            result["intent"] = "CHAMPION_BY_EFFECT"
            result["ability_effects"] = ["Heal"]

        # Crowd Control: Stun, Root, Knockup, Silence, Taunt, Charm, Fear, Suppress
        elif re.search(r"\b(?:stun|knockup|root|silence|taunt|charm|fear|suppress|cc|crowd\s*control)\b", q):
            result["intent"] = "CHAMPION_BY_CC"
            if re.search(r"\bstun\b", q):
                result["cc_types"] = ["Stun"]
            if re.search(r"\b(?:knockup|airborne)\b", q):
                result["cc_types"] = (result["cc_types"] or []) + ["Knockup"]
            if re.search(r"\b(?:root|snare)\b", q):
                result["cc_types"] = (result["cc_types"] or []) + ["Root"]
            if re.search(r"\bsilence\b", q):
                result["cc_types"] = (result["cc_types"] or []) + ["Silence"]
            if re.search(r"\btaunt\b", q):
                result["cc_types"] = (result["cc_types"] or []) + ["Taunt"]
            if re.search(r"\bcharm\b", q):
                result["cc_types"] = (result["cc_types"] or []) + ["Charm"]
            if re.search(r"\b(?:fear|flee)\b", q):
                result["cc_types"] = (result["cc_types"] or []) + ["Fear"]
            if re.search(r"\b(?:suppress|suppression)\b", q):
                result["cc_types"] = (result["cc_types"] or []) + ["Suppress"]
        elif any(w in q for w in ["win condition", "win conditions", "how to win"]):
            result["intent"] = "CHAMPION_SEMANTIC_PROFILE" if result.get("champion_name") else "CHAMPION_BY_WIN_CONDITION"
        elif any(w in q for w in ["playstyle", "playstyles", "how to play"]):
            result["intent"] = "CHAMPION_SEMANTIC_PROFILE" if result.get("champion_name") else "CHAMPION_BY_PLAYSTYLE"
        elif any(w in q for w in ["late game", "early game", "scaling"]):
            result["intent"] = "CHAMPION_BY_POWER_CURVE"
            result["power_curve"] = "LateGame" if ("late" in q or "scaling" in q) else "EarlyGame"
        elif any(re.search(r"\b" + re.escape(w) + r"\b", q) for w in ["cost", "price", "how much"]):
            result["intent"] = "ITEM_INFO"
        elif any(w in q for w in [
            "lore", "story", "origin", "biography", "crime", "killed", "murder", "who is",
            "backstory", "short story", "color story", "brother", "master", "past",
            "souma", "region", "ionia", "noxus", "demacia", "zaun", "piltover",
            "shurima", "freljord", "targon", "shadow isles", "bilgewater", "ixtal",
            "conflict", "rivalry", "relationship", "relation", "happened between", "feud",
            "betrayal", "order of shadow", "kinkou"
        ]):
            result["intent"] = "LORE_QUERY"
        elif result.get("champion_name") and any(w in q for w in ["abilities", "skills", "all skills", "all abilities", "what abilities", "what skills", "list skills", "list abilities", "kit"]):
            result["intent"] = "LIST_SKILLS"
        elif result.get("lane") and not result.get("champion_name") and any(w in q for w in ["champion", "champions", "champ", "champs", "played", "who is", "what are", "picks", "pool", "meta"]):
            result["intent"] = "LANE_QUERY"
        elif result.get("role") and not result.get("champion_name") and any(w in q for w in ["champion", "champions", "champ", "champs", "who is", "what are", "picks", "pool", "meta", "list"]):
            result["intent"] = "ROLE_QUERY"
        elif any(w in q for w in ["tell me about", "overview", "guide", "who is", "about"]):
            result["intent"] = "CHAMPION_INFO"

        # 5. Default Fallback: If entity detected but intent is UNKNOWN
        if result["intent"] == "UNKNOWN":
            if result.get("comp_archetype") or result.get("damage_composition"):
                result["intent"] = "TEAM_COMPOSITION_BUILDING"
            elif result["item_name"]:
                result["intent"] = "ITEM_INFO"
            elif result["rune_name"]:
                result["intent"] = "RUNE_INFO"
            elif result["champion_name"]:
                if result["skill_key"]:
                    result["intent"] = "SKILL_INFO"
                else:
                    result["intent"] = "CHAMPION_INFO"

        return result
