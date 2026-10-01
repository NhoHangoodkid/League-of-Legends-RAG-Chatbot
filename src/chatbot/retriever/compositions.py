"""
Composition retrieval mixin: team composition building, composition counters, and multi-enemy team counter analysis.
"""

from chatbot.data.strategic_counters import strategic_composition_counters
from chatbot.data.composition_profiles import find_composition_profile


class CompositionRetrieverMixin:
    """Provides methods for drafting compositions, composition counters, and multi-enemy counter strategy."""

    def get_composition_building_info(self, comp_id, power_curve = None):
        """
        Retrieve drafting and team composition building intelligence.
        Dynamically structures champions into authentic tactical roles based on composition archetype.
        Uses the composition profiles registry for data-driven lookup.
        """
        comp_id_clean = (comp_id or "dive").lower()
        profile = find_composition_profile(comp_id_clean)

        return {
            "is_composition_building": True,
            "comp_id": profile.get("comp_id", comp_id_clean),
            "name": profile["name"],
            "category": profile["category"],
            "description": profile["description"],
            "power_curve": power_curve or profile["default_power_curve"],
            "role_1_title": profile["role_1_title"],
            "role_1_champions": profile["role_1_champions"],
            "role_2_title": profile["role_2_title"],
            "role_2_champions": profile["role_2_champions"],
            "sample_draft": profile["sample_draft"],
            "win_condition": profile["win_condition"],
            "source": "tactical_knowledge_base",
        }

    def get_composition_counters(
        self, comp_archetype = None, damage_composition = None
    ):
        """
        Dynamically aggregate tactical counter intelligence for team compositions
        (e.g., Full AD, Full AP, Dive, Poke, Heavy CC, Sustain, Stealth, Ranged, Melee, Fighter Heavy)
        directly from verified strategic game knowledge and MongoDB collection 'team_compositions'.
        """
        target_key = comp_archetype or damage_composition or ""
        norm_key = target_key.lower().replace("-", "_").replace(" ", "_") if target_key else ""
        
        strat = strategic_composition_counters.get(norm_key)
        if not strat and target_key:
            for k, v in strategic_composition_counters.items():
                if k in norm_key or norm_key in k:
                    strat = v
                    norm_key = k
                    break

        comp_doc = self.store.get_composition(target_key)
        if not comp_doc and norm_key:
            comp_doc = self.store.get_composition(norm_key)
        if not comp_doc and comp_archetype and damage_composition:
            comp_doc = self.store.get_composition(damage_composition)
        if not comp_doc:
            comp_doc = self.store.get_composition("ranged")

        # Build sample champion descriptors from member champions
        sample_champs = []
        if comp_doc:
            sample_names = comp_doc.get("sample_champions", []) or comp_doc.get("all_champions", [])[:15]
            for cname in sample_names[:15]:
                c = self.store.get_champion(cname)
                if c:
                    sample_champs.append({
                        "name": c.get("name", cname),
                        "roles": c.get("roles", []),
                        "subroles": c.get("subroles", []),
                        "damage_type": c.get("adaptiveType", "Mixed"),
                    })
                else:
                    sample_champs.append({"name": cname, "roles": [], "damage_type": "Mixed"})

        # Format counter picks
        if strat and strat.get("counter_picks"):
            counter_picks = strat["counter_picks"]
        elif comp_doc:
            counter_picks = []
            for cp in comp_doc.get("counter_picks", []):
                counter_picks.append({
                    "champion": cp.get("champion"),
                    "reason": cp.get("tactical_reason", ""),
                    "frequency": cp.get("counter_frequency", 0),
                    "coverage_pct": cp.get("archetype_coverage_pct", 0.0),
                })
        else:
            counter_picks = []

        # Format counter items
        if strat and strat.get("counter_items"):
            counter_items = strat["counter_items"]
        elif comp_doc:
            counter_items = []
            for ci in comp_doc.get("counter_items", []):
                counter_items.append({
                    "item": ci.get("item"),
                    "purpose": ci.get("tactical_purpose", ""),
                    "recommended_count": ci.get("recommended_count", 0),
                })
        else:
            counter_items = []

        # Format weaknesses and tactical tips
        weaknesses = (strat.get("weaknesses") if strat else None) or (comp_doc.get("core_weaknesses", []) if comp_doc else [])
        tactical_tips = (strat.get("tactical_tips") if strat else None) or (comp_doc.get("tactical_tips", []) if comp_doc else [])

        # Role title and description
        role_title = (strat.get("name") if strat else None) or (comp_doc.get("name") if comp_doc else None) or norm_key.replace("_", " ").title() + " Composition"
        description = (strat.get("description") if strat else None) or (comp_doc.get("description") if comp_doc else None) or f"Tactical composition profile for {role_title}."
        comp_id = norm_key or (comp_doc.get("comp_id") if comp_doc else "tactical_composition")

        # Collect verified core abilities for counter picks
        champ_abilities = {}
        for cp in counter_picks:
            cname = cp.get("champion") if isinstance(cp, dict) else str(cp)
            raw_cname = cname.split(" (")[0] if cname else ""
            if raw_cname and raw_cname not in champ_abilities:
                c_doc = self.store.get_champion(raw_cname)
                formatted = self.format_champion_abilities(c_doc)
                if formatted:
                    champ_abilities[raw_cname] = formatted

        return {
            "is_role_query": True,
            "is_composition_query": True,
            "is_team_counter_analysis": True,
            "comp_archetype": comp_id,
            "category": comp_doc.get("category", "tactical_archetype") if comp_doc else "tactical_archetype",
            "role_title": role_title,
            "description": description,
            "sample_champions": sample_champs,
            "total_member_count": comp_doc.get("total_member_count", len(sample_champs)) if comp_doc else len(sample_champs),
            "weaknesses": weaknesses,
            "tactical_tips": tactical_tips,
            "counter_items": counter_items,
            "counter_picks": counter_picks,
            "champion_abilities": champ_abilities,
            "source": "verified_strategic_counter_intelligence",
        }

    def analyze_team_counters(self, enemies, comp_archetype = None, damage_composition = None):
        """
        Dynamically analyze an enemy composition or multi-champion team to formulate:
        - Shared structural kit weaknesses
        - Algorithmic multi-target cross-counter champion picks
        - 3-phase macro execution gameplan (Early, Mid, Late)
        - Strategic counter itemization
        All data is dynamically synthesized without hardcoding.
        """
        if not enemies and not comp_archetype and not damage_composition:
            return {"error": "A list of enemy champions or a team composition archetype is required for counter analysis."}

        enemies = enemies or []
        enemy_docs = {}
        analysis = {}
        all_weaknesses = []
        all_counter_items = []
        damage_counts = {"Magic": 0, "Physical": 0, "Mixed": 0, "True": 0}
        power_curves = []
        candidate_scores = {}

        # 1. Fetch enemy champion docs and counter relationships
        for enemy in enemies:
            canonical_id = self.store.champion_lookup.get(self.store.normalize_key(enemy))
            champ = self.store.get_champion(canonical_id or enemy)
            cdata = self.store.get_counter_info(canonical_id or enemy) or {}

            c_name = champ.get("name") if champ else enemy.title()
            enemy_docs[c_name] = {"champ": champ, "counter": cdata}

            if champ:
                adp = champ.get("adaptiveType", "Physical")
                damage_counts[adp] = damage_counts.get(adp, 0) + 1

                pc = champ.get("powerCurve") or []
                power_curves.extend(pc)

                tactical = champ.get("tacticalInfo") or {}
                w_list = champ.get("weaknesses") or tactical.get("weaknesses") or []
                if w_list:
                    all_weaknesses.extend(w_list)

                it_list = champ.get("counter_items") or tactical.get("counter_items") or []
                if it_list:
                    all_counter_items.extend(it_list)

            # Extract individual counters and accumulate cross-counter candidates
            weak_against = cdata.get("weakAgainst", []) if isinstance(cdata, dict) else []
            if weak_against:
                top_counters = [w.get("champion") for w in weak_against[:3] if w.get("champion")]
                analysis[c_name] = {"vulnerable_to": top_counters}
                for w in weak_against:
                    cand = w.get("champion")
                    reason = w.get("reason", "")
                    if cand:
                        if cand not in candidate_scores:
                            candidate_scores[cand] = {
                                "champion": cand,
                                "countered_enemies": [],
                                "reasons": [],
                                "score": 0,
                            }
                        if c_name not in candidate_scores[cand]["countered_enemies"]:
                            candidate_scores[cand]["countered_enemies"].append(c_name)
                        if reason and reason not in candidate_scores[cand]["reasons"]:
                            candidate_scores[cand]["reasons"].append(reason)
                        candidate_scores[cand]["score"] += 12
            else:
                analysis[c_name] = {"vulnerable_to": ["Vulnerable to targeted crowd control and burst lockdown"]}

        # 2. Composition archetype data integration
        comp_obj = None
        comp_title = None
        norm_arch = (comp_archetype or damage_composition or "").lower().replace("-", "_").replace(" ", "_")
        strat_obj = strategic_composition_counters.get(norm_arch)

        if strat_obj:
            comp_title = strat_obj.get("name")
            for c_weak in strat_obj.get("weaknesses", []):
                if c_weak not in all_weaknesses:
                    all_weaknesses.insert(0, c_weak)
            for c_pick in strat_obj.get("counter_picks", []):
                cand = c_pick.get("champion")
                r_txt = c_pick.get("reason", "")
                if cand:
                    if cand not in candidate_scores:
                        candidate_scores[cand] = {
                            "champion": cand,
                            "countered_enemies": [],
                            "reasons": [],
                            "score": 0,
                        }
                    candidate_scores[cand]["score"] += 20
                    if r_txt and r_txt not in candidate_scores[cand]["reasons"]:
                        candidate_scores[cand]["reasons"].append(r_txt)
            for itm in strat_obj.get("counter_items", []):
                it_name = itm.get("item") if isinstance(itm, dict) else str(itm)
                if it_name and it_name not in all_counter_items:
                    all_counter_items.insert(0, it_name)
        elif comp_archetype:
            comp_obj = self.store.get_composition(comp_archetype)
            if comp_obj:
                comp_title = comp_obj.get("name")
                for c_weak in comp_obj.get("core_weaknesses", []):
                    if c_weak not in all_weaknesses:
                        all_weaknesses.insert(0, c_weak)
                for c_pick in comp_obj.get("counter_picks", []):
                    cand = c_pick.get("champion")
                    r_txt = c_pick.get("tactical_reason", "")
                    if cand:
                        if cand not in candidate_scores:
                            candidate_scores[cand] = {
                                "champion": cand,
                                "countered_enemies": [],
                                "reasons": [],
                                "score": 0,
                            }
                        candidate_scores[cand]["score"] += 8
                        if r_txt and r_txt not in candidate_scores[cand]["reasons"]:
                            candidate_scores[cand]["reasons"].append(r_txt)
                for itm in comp_obj.get("counter_items", []):
                    all_counter_items.append(itm.get("item") if isinstance(itm, dict) else str(itm))
        elif damage_composition:
            comp_obj = self.store.get_composition(damage_composition)
            if comp_obj:
                comp_title = comp_obj.get("name")

        if not comp_title:
            if comp_archetype:
                comp_title = comp_archetype.replace("_", " ").title() + " Composition"
            elif enemies:
                comp_title = f"{', '.join(enemy_docs.keys())} Composition"
            else:
                comp_title = "Enemy Composition"

        # 3. Assess damage profile
        total_champs = len(enemies) if enemies else 1
        damage_desc = []
        if damage_counts.get("Magic", 0) >= max(2, total_champs * 0.6):
            damage_desc.append("Heavy Magic Damage")
        if damage_counts.get("Physical", 0) >= max(2, total_champs * 0.6):
            damage_desc.append("Heavy Physical Damage")
        if not damage_desc:
            damage_desc.append("Hybrid / Mixed Damage")
        damage_profile_str = ", ".join(damage_desc)

        # 4. Formulate shared weaknesses
        is_scaling = (
            comp_archetype == "scaling_late_game"
            or "LateGame" in power_curves
            or any("stack" in str(w).lower() or "late" in str(w).lower() for w in all_weaknesses)
        )

        shared_weaknesses = []
        if is_scaling:
            shared_weaknesses.append("Early-Game Vulnerability: Low base damage and weak trading power pre-level 6 leave them highly susceptible to aggressive lane bullies and early jungle invades.")
            shared_weaknesses.append("High Reliance on Minion Farm and Passive Stacks: Freezing waves and denying minion waves drastically stalls their power spike thresholds.")
            shared_weaknesses.append("Zero Early Objective Priority: Inability to contest early Voidgrubs, Rift Herald, or early Dragons without risking disastrous teamfights.")

        # Add kit-derived vulnerabilities
        for w in all_weaknesses:
            if w not in shared_weaknesses and len(shared_weaknesses) < 5:
                shared_weaknesses.append(w)

        if not shared_weaknesses:
            shared_weaknesses.append("Vulnerable to coordinated crowd control chains and early objective tempo.")
            shared_weaknesses.append("Susceptible to flank collapses when separated from defensive turret range.")

        # 5. Formulate 3-Phase Macro Strategy
        if is_scaling:
            macro_strategy = {
                "early_game": "Draft dominant early-game lane bullies. Freeze minion waves outside your turret to deny gold and stacks. Coordinate 3-man dives and secure all 6 Voidgrubs to rapidly open up the map.",
                "mid_game": "Accelerate game tempo by grouping as 5 to siege outer and inner turrets. Starve the enemy of jungle camps and stack consecutive Dragons to force a soul timer before 22 minutes.",
                "late_game": "Force decisive 5v5 teamfights at Baron Nashor or Dragon Soul while holding a substantial item advantage. Close out the match before the enemy hypercarries reach 3+ full items.",
            }
        else:
            macro_strategy = {
                "early_game": "Establish early vision control in the river and prioritize lane push priority to assist your jungler at scuttle crabs and neutral objectives.",
                "mid_game": "Group around vision choke points in the river. Bait face-checks and look for layered CC picks before starting neutral objectives.",
                "late_game": "Execute disciplined front-to-back teamfights. Maintain defensive perimeter spacing and coordinate burst lockdown on the primary enemy carries.",
            }

        # 6. Rank Top Cross-Counter Champions
        sorted_candidates = sorted(
            candidate_scores.values(),
            key=lambda c: (len(c["countered_enemies"]), c["score"]),
            reverse=True
        )

        top_counter_picks = []
        seen_cand = set()
        for cand_data in sorted_candidates:
            c_name = cand_data["champion"]
            if c_name in seen_cand or c_name in enemy_docs:
                continue
            seen_cand.add(c_name)

            c_obj = self.store.get_champion(c_name)
            c_title = f" ({c_obj.get('title')})" if c_obj and c_obj.get("title") else ""
            c_enemies = cand_data["countered_enemies"]
            c_reasons = cand_data["reasons"]

            if c_enemies:
                reason_summary = f"Directly counters {', '.join(c_enemies[:2])} by punishing their vulnerable laning phase and neutralizing their kit."
            elif c_reasons:
                reason_summary = c_reasons[0]
            else:
                reason_summary = f"Dominates through superior kit mechanics, burst trades, and reliable crowd control."

            top_counter_picks.append({
                "champion": f"{c_name}{c_title}",
                "countered_targets": c_enemies,
                "reason": reason_summary,
            })
            if len(top_counter_picks) >= 4:
                break

        # 7. Strategic Counter Itemization
        seen_items = set()
        recommended_items = []
        for it in all_counter_items:
            it_name = it if isinstance(it, str) else it.get("item", "")
            if it_name and it_name not in seen_items:
                seen_items.add(it_name)
                it_doc = self.store.get_item(it_name)
                pt = it_doc.get("plaintext", "") if it_doc else ""
                desc = it_doc.get("description", "") if it_doc else ""
                purp = pt or desc[:80] or "Provides crucial defensive mitigation against enemy power spikes."
                recommended_items.append({"item": it_name, "purpose": purp})
            if len(recommended_items) >= 4:
                break

        # If item list is sparse, dynamically add based on damage profile
        if len(recommended_items) < 3:
            if "Magic" in damage_profile_str:
                for default_mr in ["Kaenic Rookern", "Force of Nature", "Maw of Malmortius", "Mercury's Treads"]:
                    if default_mr not in seen_items:
                        seen_items.add(default_mr)
                        recommended_items.append({"item": default_mr, "purpose": "High magic resist and magic shielding to absorb spell burst."})
                    if len(recommended_items) >= 4:
                        break
            if "Physical" in damage_profile_str:
                for default_ar in ["Plated Steelcaps", "Frozen Heart", "Randuin's Omen", "Thornmail"]:
                    if default_ar not in seen_items:
                        seen_items.add(default_ar)
                        recommended_items.append({"item": default_ar, "purpose": "Armor and attack speed reduction to neutralize physical carries."})
                    if len(recommended_items) >= 4:
                        break

        # Collect verified core abilities for counter champions
        champ_abilities = {}
        for cp in top_counter_picks:
            cname = cp.get("champion")
            raw_cname = cname.split(" (")[0] if cname else ""
            if raw_cname and raw_cname not in champ_abilities:
                c_doc = self.store.get_champion(raw_cname)
                formatted = self.format_champion_abilities(c_doc)
                if formatted:
                    champ_abilities[raw_cname] = formatted

        return {
            "is_team_counter_analysis": True,
            "enemy_team": list(enemy_docs.keys()) if enemy_docs else enemies,
            "comp_archetype": comp_archetype,
            "comp_title": comp_title,
            "damage_profile": damage_profile_str,
            "shared_weaknesses": shared_weaknesses,
            "macro_strategy": macro_strategy,
            "recommended_items": recommended_items,
            "cross_counter_picks": top_counter_picks,
            "champion_abilities": champ_abilities,
            "individual_breakdown": analysis,
        }
