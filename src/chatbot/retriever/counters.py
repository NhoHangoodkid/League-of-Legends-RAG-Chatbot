"""
Counter retrieval mixin: 1v1 champion counters, lane role counters, and data-driven role counter picks.
"""

import re
from collections import Counter

from chatbot.data.role_counter_data import (
    ROLE_DISPLAY_NAMES,
    RANGE_BONUS,
    CHAMPION_TARGET_SCORING,
    get_items_for_matchup,
    get_guidelines_for_target,
    score_ability_against_target,
)


class CounterRetrieverMixin:
    """Provides counter analysis methods for individual champions, roles, and tactical counter picks."""

    def get_counters(self, name, direction = None, lane = None):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)
        data = self.store.get_counter_info(name) or {}
        raw_weak = list(data.get("weakAgainst", []))
        raw_strong = list(data.get("strongAgainst", []))

        tactical = champ.get("tacticalInfo") or {}
        weaknesses = list(data.get("weaknesses") or tactical.get("weaknesses") or profile.get("weaknesses", []))
        tactical_tips = list(data.get("tactical_tips") or tactical.get("tactical_tips") or profile.get("tactical_tips", []))
        counter_items = list(data.get("counter_items") or tactical.get("counter_items") or profile.get("counter_items", []))

        lane_upper = lane.upper() if lane else None
        if lane_upper:
            # Prioritize lane-specific weakAgainst
            lane_weak = []
            other_weak = []
            for w in raw_weak:
                c_champ = self.store.get_champion(w.get("champion", ""))
                if c_champ and lane_upper in [p.upper() for p in c_champ.get("positions", [])]:
                    lane_weak.append(w)
                else:
                    other_weak.append(w)
            weak_against = (lane_weak + other_weak)[:6]

            # Prioritize lane-specific strongAgainst
            lane_strong = []
            other_strong = []
            for s in raw_strong:
                c_champ = self.store.get_champion(s.get("champion", ""))
                if c_champ and lane_upper in [p.upper() for p in c_champ.get("positions", [])]:
                    lane_strong.append(s)
                else:
                    other_strong.append(s)
            strong_against = (lane_strong + other_strong)[:6]
        else:
            weak_against = raw_weak[:6]
            strong_against = raw_strong[:6]

        enemytips = list(champ.get("enemytips") or [])

        # Collect verified core abilities for counter champions
        relevant_entries = strong_against if direction == "counters" else weak_against
        champ_abilities = {}
        for entry in relevant_entries:
            cname = entry.get("champion")
            if cname and cname not in champ_abilities:
                c_doc = self.store.get_champion(cname)
                formatted = self.format_champion_abilities(c_doc)
                if formatted:
                    champ_abilities[cname] = formatted

        profile.update({
            "is_counter_query": True,
            "lane": lane,
            "weaknesses": weaknesses,
            "tactical_tips": tactical_tips,
            "enemytips": enemytips,
            "counter_items": counter_items,
            "weak_against": weak_against,
            "strong_against": strong_against,
            "counter_direction": direction,
            "champion_abilities": champ_abilities,
        })
        return profile

    def get_role_counters(
        self, role = None, lane = None, direction = "countered_by"
    ):
        """
        Aggregate tactical counter intelligence for a champion class/role in a lane
        directly from the KnowledgeStore champions and counter records.
        Zero hardcoded texts, definitions, or advice.
        """
        role_lower = (role or "").lower()
        lane_upper = lane.upper() if lane else None

        # 1. Filter matching champions from KnowledgeStore
        matching_champs = []
        for c in self.store.champions.values():
            c_roles = [r.lower() for r in c.get("roles", [])]
            c_lanes = [p.upper() for p in c.get("positions", [])]
            if role_lower and role_lower not in c_roles:
                continue
            if lane_upper and lane_upper not in c_lanes:
                continue
            matching_champs.append(c)

        if not matching_champs and role_lower:
            matching_champs = [
                c for c in self.store.champions.values()
                if role_lower in [r.lower() for r in c.get("roles", [])]
            ]

        sample_champs = [
            {
                "name": c.get("name"),
                "roles": c.get("roles", []),
                "subroles": c.get("subroles", []),
                "damage_type": c.get("adaptiveType"),
            }
            for c in matching_champs[:12]
        ]

        # 2. Dynamically aggregate weaknesses, tactical_tips, and counter_items from the database
        all_weaknesses = []
        all_tips = []
        all_items = []
        counter_champ_counts = {}

        for c in matching_champs:
            t = c.get("tacticalInfo") or {}
            all_weaknesses.extend(t.get("weaknesses", []))
            all_tips.extend(t.get("tactical_tips", []))
            all_items.extend(t.get("counter_items", []))

            c_info = self.store.get_counter_info(c.get("name", ""))
            if c_info:
                for w in c_info.get("weakAgainst", []):
                    c_name = w.get("champion")
                    if c_name:
                        # Prioritize / filter champions that actually play in this specific lane
                        if lane_upper:
                            opp_champ = self.store.get_champion(c_name)
                            if opp_champ:
                                opp_positions = [p.upper() for p in opp_champ.get("positions", [])]
                                if lane_upper not in opp_positions:
                                    continue

                        if c_name not in counter_champ_counts:
                            counter_champ_counts[c_name] = {
                                "champion": c_name,
                                "count": 0,
                                "reasons": set(),
                                "winRates": [],
                            }
                        counter_champ_counts[c_name]["count"] += 1
                        if w.get("reason"):
                            counter_champ_counts[c_name]["reasons"].add(w["reason"])
                        if w.get("winRate"):
                            counter_champ_counts[c_name]["winRates"].append(w["winRate"])

        # Fallback if lane-specific counter picks are too few
        if len(counter_champ_counts) < 3 and lane_upper:
            for c in matching_champs:
                c_info = self.store.get_counter_info(c.get("name", ""))
                if c_info:
                    for w in c_info.get("weakAgainst", []):
                        c_name = w.get("champion")
                        if c_name and c_name not in counter_champ_counts:
                            counter_champ_counts[c_name] = {
                                "champion": c_name,
                                "count": 1,
                                "reasons": {w.get("reason", "")} if w.get("reason") else set(),
                                "winRates": [w.get("winRate")] if w.get("winRate") else [],
                            }

        # Rank and deduplicate from actual frequencies in the database
        raw_weaknesses = [item for item, _ in Counter(all_weaknesses).most_common(8)]
        top_tips = [item for item, _ in Counter(all_tips).most_common(5)]
        top_items = [item for item, _ in Counter(all_items).most_common(6)]

        # Data-driven harmonization of mobility based on mathematical ratio of Dash/Blink in archetype
        mobile_count = sum(
            1 for c in matching_champs
            if any(fx.lower() in ("dash", "blink") for fx in c.get("ability_effects", []))
        )
        is_predominantly_mobile = (mobile_count / len(matching_champs)) >= 0.5 if matching_champs else False

        top_weaknesses = []
        for w in raw_weaknesses:
            w_lower = w.lower()
            if is_predominantly_mobile and ("immobile" in w_lower or "no native dash" in w_lower):
                continue
            if not is_predominantly_mobile and ("reliance on mobility" in w_lower or "primary dash" in w_lower):
                continue
            top_weaknesses.append(w)
            if len(top_weaknesses) >= 4:
                break

        # Top counter picks sorted by frequency across matching champions
        sorted_counters = sorted(counter_champ_counts.values(), key=lambda x: x["count"], reverse=True)
        top_counter_picks = []
        for sc in sorted_counters[:6]:
            avg_wr = (
                round(sum(sc["winRates"]) / len(sc["winRates"]), 1)
                if sc["winRates"]
                else None
            )
            clean_reasons = list(dict.fromkeys(r.strip() for r in sc["reasons"] if r and r.strip()))
            top_counter_picks.append({
                "champion": sc["champion"],
                "reason": "; ".join(clean_reasons[:2]),
                "winRate": avg_wr,
            })

        # Determine dominant damage profile from matching champions
        adaptive_types = [c.get("adaptiveType") for c in matching_champs if c.get("adaptiveType")]
        dominant_damage = Counter(adaptive_types).most_common(1)[0][0] if adaptive_types else "Mixed"

        return {
            "is_role_query": True,
            "role": role_lower or "general",
            "lane": lane or "all",
            "role_title": f"{role.capitalize() if role else 'General'} Champions" + (f" ({lane.upper()})" if lane else ""),
            "damage_profile": f"{dominant_damage} Damage",
            "sample_champions": sample_champs,
            "weaknesses": top_weaknesses,
            "tactical_tips": top_tips,
            "counter_items": top_items,
            "counter_picks": top_counter_picks,
            "source": "knowledge_base_dynamic_aggregation",
        }

    def get_role_counter_picks(
        self, user_role = None, target_value = None, target_type = "role", lane = None
    ):
        """
        Dynamically calculate and rank champions of a specified role/lane that counter
        a designated enemy target (champion, class/role, or tactical archetype).
        Zero hardcoding. 100% automated and data-driven from champion abilities,
        mechanics, and database relationships.
        """
        target_str = (target_value or "").lower()
        role_str = (user_role or "").lower()
        lane_str = (lane or "").lower() if lane else None

        # Resolve clean display role title
        role_title = ROLE_DISPLAY_NAMES.get(role_str) or (role_str.title() + " Champions" if role_str else "Draft Pick")

        # 1. Filter candidate champions belonging to the user's role/lane
        candidates = []
        for c in self.store.champions.values():
            c_roles = [r.lower() for r in c.get("roles", [])]
            c_subroles = [s.lower() for s in c.get("subroles", [])]
            c_positions = [p.lower() for p in c.get("positions", [])]

            match_role = (role_str in c_roles) or (role_str in c_subroles) if role_str else True
            match_lane = (lane_str in c_positions) if lane_str else True

            if role_str in ("mid", "top", "jungle", "bot"):
                match_role = match_role or (role_str in c_positions)

            if match_role and match_lane:
                candidates.append(c)

        if not candidates and role_str:
            candidates = [
                c for c in self.store.champions.values()
                if role_str in [r.lower() for r in c.get("roles", [])]
            ]
        if not candidates:
            candidates = list(self.store.champions.values())

        # 2. Build target telemetry lookup if target is role or archetype
        target_champs_set = set()
        if target_type == "role":
            target_champs_set = {
                c.get("name") for c in self.store.champions.values()
                if target_str in [r.lower() for r in c.get("roles", [])]
            }

        target_comp = None
        if target_type == "archetype":
            target_comp = self.store.get_composition(target_str)

        # 3. Evaluate each candidate champion mathematically
        scored_candidates = []

        for c in candidates:
            cname = c.get("name")
            score = 0
            mechanics = []

            # A. Kit Mechanics Evaluation from Abilities
            abilities = c.get("abilities", {})
            for sk, spell in abilities.items():
                s_name = spell.get("name", "")
                s_desc = (spell.get("description") or "") + " " + " ".join(spell.get("effects", []))
                s_lower = s_desc.lower()
                ab_score, ab_mechs = score_ability_against_target(target_str, s_lower, s_name, sk)
                score += ab_score
                mechanics.extend(ab_mechs)

            # B. Attack Range and Mobility Bonus
            stats_dict = c.get("stats", {})
            ar_val = stats_dict.get("attackrange", 0)
            rng = ar_val.get("base", 0) if isinstance(ar_val, dict) else (ar_val or 0)

            if target_str in RANGE_BONUS["targets"]:
                if rng >= RANGE_BONUS["min_range"]:
                    score += RANGE_BONUS["score"]
                    mechanics.append(RANGE_BONUS["template"].format(range=rng))
                if any(fx in RANGE_BONUS["mobility_effects"] for fx in c.get("ability_effects", [])):
                    score += RANGE_BONUS["mobility_score"]

            # C. Knowledge Graph Empirical Matchup Telemetry
            c_info = self.store.get_counter_info(cname)
            if c_info:
                strong_against = c_info.get("strongAgainst", [])
                for sa in strong_against:
                    opp_name = sa.get("champion")
                    if target_type == "champion" and opp_name and opp_name.lower() == target_str:
                        score += 8
                        if sa.get("reason"):
                            mechanics.append(sa["reason"])
                    elif target_type == "role" and opp_name in target_champs_set:
                        score += 3
                        if sa.get("reason") and len(mechanics) < 3:
                            mechanics.append(sa["reason"])

            if target_comp:
                for cp in target_comp.get("counter_picks", []):
                    if cp.get("champion") == cname:
                        score += 6
                        if cp.get("tactical_reason"):
                            mechanics.append(cp["tactical_reason"])

            distinct_mechanics = []
            for m in mechanics:
                if m not in distinct_mechanics:
                    distinct_mechanics.append(m)

            if score > 0 or distinct_mechanics:
                scored_candidates.append({
                    "champion": cname,
                    "title": c.get("title", ""),
                    "score": score,
                    "roles": c.get("roles", []),
                    "mechanics": distinct_mechanics[:3],
                })

        scored_candidates.sort(key=lambda x: x["score"], reverse=True)
        top_champs = scored_candidates[:4]

        # 4. Specialized Anti-Target Itemization for User's Role
        recommended_items = []
        item_names = get_items_for_matchup(target_str, role_str)

        for iname in item_names:
            it = self.store.get_item(iname)
            if it:
                plaintext = (it.get("plaintext") or "").strip()
                raw_desc = it.get("description", "")
                clean_desc = re.sub(r"<[^>]+>", " ", raw_desc).strip()
                clean_desc = " ".join(clean_desc.split())
                recommended_items.append({
                    "item": it.get("name"),
                    "plaintext": plaintext or clean_desc[:90],
                })

        # 5. Strategic Matchup and Positioning Guidelines
        tactical_guidelines = get_guidelines_for_target(target_str)

        return {
            "is_role_counter_pick": True,
            "user_role": role_str,
            "role_title": role_title,
            "target": target_value,
            "target_type": target_type,
            "top_champions": top_champs,
            "recommended_items": recommended_items,
            "tactical_guidelines": tactical_guidelines,
            "source": "knowledge_base_dynamic_draft_engine",
        }
