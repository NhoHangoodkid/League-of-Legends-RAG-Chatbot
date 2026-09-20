"""
Graph Traversal Strategies for LoL Knowledge Bot.

Provides intent-aware graph traversal that collects relevant context
from the Knowledge Graph based on the user's query intent and extracted entities.
"""

import json

from rag.graph.schema import EdgeType, NodeType
from rag.graph.store import Neo4jStore, get_graph_store


class GraphTraversal:
    """Intent-driven graph traversal for context retrieval."""

    def __init__(self, store = None):
        self.store = store or get_graph_store()

    def retrieve_context(self, entities, intent, max_results = 10):
        """Main entry: dispatch to intent-specific traversal strategy."""
        champ_name = entities.get("champion_name")
        item_name = entities.get("item_name")
        rune_name = entities.get("rune_name")

        strategy_map = {
            "COUNTER_QUERY": lambda: self.traverse_counters(champ_name, entities.get("counter_direction")),
            "SYNERGY_QUERY": lambda: self.traverse_synergies(champ_name),
            "BUILD_QUERY": lambda: self.traverse_build(champ_name),
            "CHAMPION_INFO": lambda: self.traverse_champion_overview(champ_name),
            "CHAMPION_BASE_STATS": lambda: self.traverse_champion_stats(champ_name),
            "CHAMPION_STATS_AT_LEVEL": lambda: self.traverse_champion_stats(champ_name),
            "SKILL_INFO": lambda: self.traverse_ability(champ_name, entities.get("skill_key", "Q")),
            "SKILL_DAMAGE_AT_LEVEL": lambda: self.traverse_ability(champ_name, entities.get("skill_key", "Q")),
            "SKILL_COOLDOWN": lambda: self.traverse_ability(champ_name, entities.get("skill_key", "Q")),
            "LIST_SKILLS": lambda: self.traverse_all_abilities(champ_name),
            "CHAMPION_COMPARISON": lambda: self.traverse_comparison(entities.get("comparison_champions", [])),
            "ITEM_INFO": lambda: self.traverse_item(item_name),
            "RUNE_INFO": lambda: self.traverse_rune(rune_name),
            "CHAMPION_BY_CC": lambda: self.traverse_by_tag(NodeType.CC_TYPE, entities.get("cc_types", [])),
            "CHAMPION_BY_EFFECT": lambda: self.traverse_by_tag(NodeType.EFFECT, entities.get("ability_effects", [])),
            "CHAMPION_BY_PLAYSTYLE": lambda: self.traverse_by_tag(NodeType.PLAYSTYLE, entities.get("playstyles", [])),
            "CHAMPION_BY_POWER_CURVE": lambda: self.traverse_by_tag(NodeType.POWER_CURVE, [entities.get("power_curve")] if entities.get("power_curve") else []),
            "CHAMPION_BY_WIN_CONDITION": lambda: self.traverse_by_tag(NodeType.WIN_CONDITION, [entities.get("win_condition")] if entities.get("win_condition") else []),
            "MULTI_PROPERTY_FILTER": lambda: self.traverse_multi_filter(entities),
            "CHAMPION_SEMANTIC_PROFILE": lambda: self.traverse_semantic_profile(champ_name),
            "TEAM_COUNTER_ANALYSIS": lambda: self.traverse_team_counters(
                entities.get("enemy_champions", []),
                entities.get("comp_archetype") or entities.get("damage_composition")
            ),
            "ROLE_QUERY": lambda: self.traverse_by_role(entities.get("role", "")),
            "ROLE_COUNTER_PICK": lambda: self.traverse_role_counter(
                entities.get("user_role") or entities.get("role"),
                entities.get("target"),
                entities.get("target_type")
            ),
            "TEAM_COMPOSITION_BUILDING": lambda: self.traverse_composition_building(
                entities.get("comp_archetype"),
                entities.get("power_curve")
            ),
            "ABILITY_MECHANIC_QUERY": lambda: self.traverse_ability_mechanic(
                champ_name,
                entities.get("skill_key", "R"),
                entities.get("interaction_champion"),
                entities.get("mechanic"),
            ),
        }

        handler = strategy_map.get(intent)
        if handler:
            try:
                res = handler()[:max_results]
                if res:
                    return res
            except Exception as e:
                print(f"[GraphTraversal] Notice in {intent}: {e}")

        # Dynamic fallback: Traverse entity neighborhood whenever an entity is present
        if champ_name:
            return self.traverse_entity_neighborhood(champ_name)[:max_results]
        if item_name:
            return self.traverse_item(item_name)[:max_results]
        if rune_name:
            return self.traverse_rune(rune_name)[:max_results]
        if entities.get("role"):
            return self.traverse_by_role(entities["role"])[:max_results]

        return []

    def traverse_entity_neighborhood(self, name):
        """Get comprehensive graph neighborhood of champion: overview, top counters, build, and abilities."""
        results = []
        ov = self.traverse_champion_overview(name)
        if ov:
            results.extend(ov)
        cnt = self.traverse_counters(name, direction="both")
        if cnt:
            results.extend(cnt[:2])
        bld = self.traverse_build(name)
        if bld:
            results.extend(bld[:1])
        return results

    def traverse_champion_overview(self, name):
        """Get champion overview + 1-hop neighbors (roles, CC, effects, playstyles)."""
        if not name:
            return []

        cypher = """
        MATCH (c:Champion)
        WHERE c.champion_id = $name OR c.name =~ ('(?i).*' + $name + '.*')
        OPTIONAL MATCH (c)-[:HAS_ROLE]->(role:Role)
        OPTIONAL MATCH (c)-[:HAS_CC]->(cc:CrowdControl)
        OPTIONAL MATCH (c)-[:HAS_EFFECT]->(eff:Effect)
        OPTIONAL MATCH (c)-[:HAS_PLAYSTYLE]->(ps:Playstyle)
        OPTIONAL MATCH (c)-[:HAS_POWER_CURVE]->(pc:PowerCurve)
        OPTIONAL MATCH (c)-[:HAS_WIN_CONDITION]->(wc:WinCondition)
        RETURN c,
               collect(DISTINCT role.name) AS roles,
               collect(DISTINCT cc.name) AS cc_types,
               collect(DISTINCT eff.name) AS effects,
               collect(DISTINCT ps.name) AS playstyles,
               collect(DISTINCT pc.name) AS power_curves,
               collect(DISTINCT wc.name) AS win_conditions
        LIMIT 1
        """
        results = self.store.run_cypher(cypher, name=name)
        if not results:
            return []

        r = results[0]
        c = dict(r["c"])
        text = (
            f"Champion: {c.get('name', name)} — {c.get('title', '')}\n"
            f"Roles: {', '.join(r['roles'])}\n"
            f"Playstyles: {', '.join(r['playstyles'])}\n"
            f"Crowd Control: {', '.join(r['cc_types'])}\n"
            f"Ability Effects: {', '.join(r['effects'])}\n"
            f"Power Curve: {', '.join(r['power_curves'])}\n"
            f"Win Conditions: {', '.join(r['win_conditions'])}\n"
            f"Lore: {c.get('short_lore', '')}"
        )

        return [{"text": text, "source": "graph:champion_overview", "score": 1.0,
                 "metadata": {"champion_id": c.get("champion_id"), "stats_json": c.get("stats_json", "{}")}}]

    def traverse_counters(self, name, direction = None):
        """Traverse COUNTERS edges to find matchup data."""
        if not name:
            return []

        cypher_weak = """
        MATCH (counter:Champion)-[r:COUNTERS]->(c:Champion)
        WHERE c.champion_id = $name OR c.name =~ ('(?i).*' + $name + '.*')
        RETURN counter.name AS counter_name, counter.champion_id AS counter_id,
               r.win_rate AS win_rate, r.games AS games, r.reason AS reason
        ORDER BY r.win_rate DESC
        LIMIT 10
        """

        cypher_strong = """
        MATCH (c:Champion)-[r:COUNTERS]->(weak:Champion)
        WHERE c.champion_id = $name OR c.name =~ ('(?i).*' + $name + '.*')
        RETURN weak.name AS weak_name, weak.champion_id AS weak_id,
               r.win_rate AS win_rate, r.games AS games, r.reason AS reason
        ORDER BY r.win_rate DESC
        LIMIT 10
        """

        results = []

        # Only query countered_by if direction is 'countered_by' or unspecified
        if direction in ("countered_by", None, "both"):
            weak_results = self.store.run_cypher(cypher_weak, name=name)
            if weak_results:
                lines = [f"{name} is countered by:"]
                for wr in weak_results:
                    reason = wr.get("reason")
                    r_str = f" — Reason: {reason}" if reason else ""
                    lines.append(f"  - {wr['counter_name']}{r_str}")
                results.append({"text": "\n".join(lines), "source": "graph:counters_weak", "score": 0.95,
                               "metadata": {"direction": "countered_by"}})

        # Only query counters if direction is 'counters' or unspecified
        if direction in ("counters", None, "both"):
            strong_results = self.store.run_cypher(cypher_strong, name=name)
            if strong_results:
                lines = [f"{name} is strong against:"]
                for sr in strong_results:
                    reason = sr.get("reason")
                    r_str = f" — Reason: {reason}" if reason else ""
                    lines.append(f"  - {sr['weak_name']}{r_str}")
                results.append({"text": "\n".join(lines), "source": "graph:counters_strong", "score": 0.90,
                               "metadata": {"direction": "counters"}})

        return results

    def traverse_synergies(self, name):
        """Traverse SYNERGIZES_WITH edges."""
        if not name:
            return []

        cypher = """
        MATCH (c:Champion)-[r:SYNERGIZES_WITH]->(partner:Champion)
        WHERE c.champion_id = $name OR c.name =~ ('(?i).*' + $name + '.*')
        RETURN partner.name AS partner_name, partner.champion_id AS partner_id,
               r.duo_win_rate AS duo_win_rate, r.games AS games, r.reason AS reason
        ORDER BY r.duo_win_rate DESC
        LIMIT 10
        """
        results = self.store.run_cypher(cypher, name=name)
        if not results:
            return []

        lines = [f"Best synergy partners for {name}:"]
        for r in results:
            reason = r.get("reason")
            r_str = f" — Reason: {reason}" if reason else ""
            lines.append(f"  - {r['partner_name']}{r_str}")

        return [{"text": "\n".join(lines), "source": "graph:synergies", "score": 0.95,
                 "metadata": {"champion": name}}]

    def traverse_build(self, name):
        """Traverse USES_ITEM and USES_RUNE edges for build recommendations."""
        if not name:
            return []

        cypher = """
        MATCH (c:Champion)
        WHERE c.champion_id = $name OR c.name =~ ('(?i).*' + $name + '.*')
        OPTIONAL MATCH (c)-[ri:USES_ITEM]->(item)
        OPTIONAL MATCH (c)-[rr:USES_RUNE]->(rune)
        RETURN c.name AS champ_name,
               collect(DISTINCT {name: item.name, id: item.item_id, is_core: ri.is_core}) AS items,
               collect(DISTINCT {name: rune.name, id: rune.rune_id, is_keystone: rr.is_keystone}) AS runes
        """
        results = self.store.run_cypher(cypher, name=name)
        if not results:
            return []

        r = results[0]
        core_items = [i["name"] for i in r["items"] if i.get("is_core") and i.get("name")]
        all_items = [i["name"] for i in r["items"] if i.get("name")]
        runes = [ru["name"] for ru in r["runes"] if ru.get("name")]

        text = (
            f"Recommended build for {r['champ_name']}:\n"
            f"  Core Items: {', '.join(core_items) or 'N/A'}\n"
            f"  Full Build: {', '.join(all_items) or 'N/A'}\n"
            f"  Runes: {', '.join(runes) or 'N/A'}"
        )

        return [{"text": text, "source": "graph:build", "score": 0.90,
                 "metadata": {"champion": name}}]

    def traverse_ability(self, name, skill_key):
        """Get specific ability details via graph."""
        if not name:
            return []

        cypher = """
        MATCH (c:Champion)-[:HAS_ABILITY]->(a:Ability)
        WHERE (c.champion_id = $name OR c.name =~ ('(?i).*' + $name + '.*'))
        AND a.key = $key
        RETURN c.name AS champ_name, a
        LIMIT 1
        """
        results = self.store.run_cypher(cypher, name=name, key=skill_key.upper() if skill_key != "passive" else "passive")
        if not results:
            return []

        a = dict(results[0]["a"])
        text = (
            f"Ability {a.get('key', '')} - {a.get('name', '')} of {results[0]['champ_name']}:\n"
            f"  Description: {a.get('description', '')}\n"
            f"  Cooldown: {a.get('cooldown_json', '[]')}\n"
            f"  Cost: {a.get('cost_json', '[]')}\n"
            f"  Range: {a.get('range_json', '[]')}"
        )

        return [{"text": text, "source": "graph:ability", "score": 1.0,
                 "metadata": {"champion": name, "skill_key": skill_key}}]

    def traverse_all_abilities(self, name):
        """Get all abilities of a champion."""
        if not name:
            return []

        cypher = """
        MATCH (c:Champion)-[:HAS_ABILITY]->(a:Ability)
        WHERE c.champion_id = $name OR c.name =~ ('(?i).*' + $name + '.*')
        RETURN c.name AS champ_name, a
        ORDER BY a.key
        """
        records = self.store.run_cypher(cypher, name=name)
        if not records:
            return []

        lines = [f"Abilities of {records[0]['champ_name']}:"]
        for r in records:
            a = dict(r["a"])
            lines.append(f"  [{a.get('key', '')}] {a.get('name', '')}: {a.get('description', '')[:150]}...")

        return [{"text": "\n".join(lines), "source": "graph:all_abilities", "score": 1.0,
                 "metadata": {"champion": name}}]

    def traverse_ability_mechanic(self, name, skill_key, interaction_champ = None, mechanic = None):
        """Retrieve target ability and interaction champion abilities for micro-mechanic reasoning."""
        results = []
        if name and skill_key:
            main_ab = self.traverse_ability(name, skill_key)
            if main_ab:
                results.extend(main_ab)
        if interaction_champ:
            inter_abs = self.traverse_all_abilities(interaction_champ)
            if inter_abs:
                results.extend(inter_abs)
        return results

    def traverse_champion_stats(self, name):
        """Get champion stats from graph node properties."""
        if not name:
            return []

        node = self.store.get_node(name, NodeType.CHAMPION)
        if not node:
            cypher = """
            MATCH (c:Champion)
            WHERE c.name =~ ('(?i).*' + $name + '.*')
            RETURN c LIMIT 1
            """
            results = self.store.run_cypher(cypher, name=name)
            if results:
                node = dict(results[0]["c"])

        if not node:
            return []

        stats = json.loads(node.get("stats_json", "{}"))
        lines = [f"Base stats of {node.get('name', name)}:"]
        for stat_name, stat_val in stats.items():
            if isinstance(stat_val, dict):
                lines.append(f"  {stat_name}: {stat_val.get('base', 0)} (+{stat_val.get('perLevel', 0)}/level)")
            else:
                lines.append(f"  {stat_name}: {stat_val}")

        return [{"text": "\n".join(lines), "source": "graph:stats", "score": 1.0,
                 "metadata": {"champion": name, "stats": stats}}]

    def traverse_comparison(self, champ_names):
        """Compare multiple champions' stats and direct head-to-head counter relationships."""
        if not champ_names or len(champ_names) < 2:
            return []

        results = []
        # 1. Query direct head-to-head COUNTERS relationship between the two champions
        c1, c2 = champ_names[0], champ_names[1]
        cypher_matchup = """
        MATCH (winner:Champion)-[r:COUNTERS]->(loser:Champion)
        WHERE (toLower(winner.name) = toLower($c1) AND toLower(loser.name) = toLower($c2))
           OR (toLower(winner.name) = toLower($c2) AND toLower(loser.name) = toLower($c1))
           OR (winner.champion_id = $c1 AND loser.champion_id = $c2)
           OR (winner.champion_id = $c2 AND loser.champion_id = $c1)
        RETURN winner.name AS winner_name, loser.name AS loser_name,
               r.win_rate AS win_rate, r.reason AS reason
        LIMIT 2
        """
        matchups = self.store.run_cypher(cypher_matchup, c1=c1, c2=c2)
        if matchups:
            matchup_lines = [f"Direct Matchup Relationship ({c1} vs {c2}):"]
            for m in matchups:
                wr_str = f" (Win Rate: {m['win_rate']}%)" if m.get("win_rate") else ""
                reason_str = f" — Tactical Reason: {m['reason']}" if m.get("reason") else ""
                matchup_lines.append(f"  - {m['winner_name']} COUNTERS {m['loser_name']}{wr_str}{reason_str}")
            results.append({
                "text": "\n".join(matchup_lines),
                "source": "graph:matchup_counter",
                "score": 1.0,
                "metadata": {"type": "direct_matchup", "champions": [c1, c2]},
            })

        # 2. Add individual stats
        for name in champ_names[:3]:
            ctx = self.traverse_champion_stats(name)
            results.extend(ctx)
        return results

    def traverse_item(self, name):
        """Get item details and build path."""
        if not name:
            return []

        cypher = """
        MATCH (i:Item)
        WHERE i.name =~ ('(?i).*' + $name + '.*') OR i.item_id = $name
        OPTIONAL MATCH (i)-[:BUILDS_FROM]->(component:Item)
        OPTIONAL MATCH (i)-[:BUILDS_INTO]->(upgrade:Item)
        RETURN i,
               collect(DISTINCT component.name) AS components,
               collect(DISTINCT upgrade.name) AS upgrades
        LIMIT 1
        """
        results = self.store.run_cypher(cypher, name=name)
        if not results:
            return []

        r = results[0]
        item = dict(r["i"])
        text = (
            f"Item: {item.get('name', name)}\n"
            f"  Cost: {item.get('cost_total', 0)} gold (Sell: {item.get('cost_sell', 0)})\n"
            f"  Description: {item.get('description', '')}\n"
            f"  Stats: {item.get('stats_json', '{}')}\n"
            f"  Builds from: {', '.join(r['components']) if r['components'] else 'N/A'}\n"
            f"  Upgrades into: {', '.join(r['upgrades']) if r['upgrades'] else 'N/A'}"
        )

        return [{"text": text, "source": "graph:item", "score": 1.0,
                 "metadata": {"item_name": item.get("name")}}]

    def traverse_rune(self, name):
        """Get rune details."""
        if not name:
            return []

        cypher = """
        MATCH (r:Rune)
        WHERE r.name =~ ('(?i).*' + $name + '.*') OR r.rune_id = $name
        RETURN r LIMIT 1
        """
        results = self.store.run_cypher(cypher, name=name)
        if not results:
            return []

        rune = dict(results[0]["r"])
        text = (
            f"Rune: {rune.get('name', name)} (Tree: {rune.get('tree', '')})\n"
            f"  Description: {rune.get('long_description', rune.get('description', ''))}"
        )

        return [{"text": text, "source": "graph:rune", "score": 1.0,
                 "metadata": {"rune_name": rune.get("name")}}]

    def traverse_by_tag(self, tag_type, tag_values):
        """Find champions that share specific tag nodes (CC, Effect, etc.)."""
        if not tag_values:
            return []

        label = tag_type.value
        edge_map = {
            NodeType.ROLE: "HAS_ROLE",
            NodeType.CC_TYPE: "HAS_CC",
            NodeType.EFFECT: "HAS_EFFECT",
            NodeType.PLAYSTYLE: "HAS_PLAYSTYLE",
            NodeType.POWER_CURVE: "HAS_POWER_CURVE",
            NodeType.WIN_CONDITION: "HAS_WIN_CONDITION",
        }
        edge = edge_map.get(tag_type, "HAS_CC")

        cypher = f"""
        MATCH (c:Champion)-[:{edge}]->(t:{label})
        WHERE t.name IN $tags
        WITH c, collect(t.name) AS matched_tags
        WHERE size(matched_tags) = size($tags)
        RETURN c.name AS name, c.champion_id AS id, matched_tags
        LIMIT 20
        """
        results = self.store.run_cypher(cypher, tags=tag_values)
        if not results:
            return []

        lines = [f"Champions with {', '.join(tag_values)}:"]
        for r in results:
            lines.append(f"  - {r['name']}")

        return [{"text": "\n".join(lines), "source": f"graph:filter_{tag_type.value}",
                 "score": 0.90, "metadata": {"filter": tag_values}}]

    def traverse_by_role(self, role):
        """Find champions by role."""
        if not role:
            return []
        return self.traverse_by_tag(NodeType.ROLE, [role.strip().capitalize()])

    def traverse_role_counter(self, user_role, target, target_type = None):
        """
        Traverse graph to find champions of user_role that counter the target.
        For dive/assassins, queries champions with Role: user_role that have:
        Peel/Disengage/Tank playstyles, hard CC, and defensive effects.
        """
        if not user_role:
            return []

        u_role_cap = user_role.strip().capitalize()
        target_str = (target or "").lower()

        # If target is dive/assassin or archetype related to dive/burst
        if any(w in target_str for w in ["dive", "assassin", "slayer", "burst"]):
            cypher = """
            MATCH (c:Champion)-[:HAS_ROLE]->(r:Role {name: $role})
            OPTIONAL MATCH (c)-[:HAS_CC]->(cc:CrowdControl)
            OPTIONAL MATCH (c)-[:HAS_EFFECT]->(eff:Effect)
            OPTIONAL MATCH (c)-[:HAS_PLAYSTYLE]->(ps:Playstyle)
            WITH c, 
                 collect(DISTINCT cc.name) AS ccs,
                 collect(DISTINCT eff.name) AS effects,
                 collect(DISTINCT ps.name) AS playstyles
            WHERE any(x IN playstyles WHERE x IN ['Peel', 'Utility', 'Tank', 'Support', 'Warden'])
               OR any(x IN effects WHERE x IN ['Disengage', 'Shield', 'Invulnerability', 'Knockback'])
               OR any(x IN ccs WHERE x IN ['Knockup', 'Stun', 'Suppress', 'Polymorph', 'Root', 'Silence'])
            RETURN c.name AS name, c.champion_id AS id, ccs, effects, playstyles
            LIMIT 8
            """
            results = self.store.run_cypher(cypher, role=u_role_cap)
            if results:
                lines = [f"Recommended {u_role_cap} Champions with Anti-Dive and Anti-Assassin Peel Mechanics:"]
                for r in results:
                    c_name = r["name"]
                    ccs = [c for c in r.get("ccs", []) if c in ["Knockup", "Stun", "Suppress", "Polymorph", "Root", "Silence"]]
                    effs = [e for e in r.get("effects", []) if e in ["Disengage", "Shield", "Invulnerability", "AOE"]]
                    mechanics = ", ".join(ccs + effs) if (ccs or effs) else "Defensive peel kit"
                    lines.append(f"  - {c_name}: Key mechanics [{mechanics}]")
                return [{
                    "text": "\n".join(lines),
                    "source": "graph:role_counter",
                    "score": 0.95,
                    "metadata": {"role": u_role_cap, "target": target}
                }]

        # Direct COUNTERS relationship if target is an exact champion
        if target_type == "champion" or target:
            target_norm = self.store.normalize_name(target)
            cypher_counter = """
            MATCH (counter:Champion)-[:COUNTERS]->(target:Champion {champion_id: $target_id})
            MATCH (counter)-[:HAS_ROLE]->(r:Role {name: $role})
            RETURN counter.name AS name, counter.champion_id AS id
            LIMIT 5
            """
            c_res = self.store.run_cypher(cypher_counter, target_id=target_norm, role=u_role_cap)
            if c_res:
                lines = [f"{u_role_cap} Champions that directly counter {target}:"]
                for r in c_res:
                    lines.append(f"  - {r['name']}")
                return [{
                    "text": "\n".join(lines),
                    "source": "graph:role_counter",
                    "score": 0.95,
                    "metadata": {"role": u_role_cap, "target": target}
                }]

        # Fallback: traverse by role
        return self.traverse_by_role(u_role_cap)

    def traverse_composition_building(self, comp_archetype = None, power_curve = None):
        """
        Traverse graph to find champions for building a team composition.
        """
        results = []
        if power_curve or (comp_archetype and any(w in comp_archetype for w in ["late", "scaling", "hypercarry"])):
            pc_val = power_curve or "LateGame"
            cypher_pc = """
            MATCH (c:Champion)-[:HAS_POWER_CURVE]->(pc:PowerCurve {name: $pc})
            MATCH (c)-[:HAS_ROLE]->(r:Role)
            RETURN c.name AS name, collect(r.name) AS roles
            ORDER BY c.name
            LIMIT 12
            """
            pc_res = self.store.run_cypher(cypher_pc, pc=pc_val)
            if pc_res:
                lines = [f"Core Champions for {pc_val} Scaling Composition:"]
                for r in pc_res:
                    lines.append(f"  - {r['name']} ({', '.join(r['roles'])})")
                results.append({
                    "text": "\n".join(lines),
                    "source": "graph:comp_building",
                    "score": 0.95,
                    "metadata": {"power_curve": pc_val}
                })

        return results

    def traverse_multi_filter(self, entities):
        """Complex multi-criteria filter using graph intersection."""
        conditions = []
        params = {}

        if entities.get("role"):
            conditions.append("(c)-[:HAS_ROLE]->(:Role {name: $role})")
            params["role"] = entities["role"].strip().capitalize()

        if entities.get("cc_types"):
            for i, cc in enumerate(entities["cc_types"]):
                conditions.append(f"(c)-[:HAS_CC]->(:CrowdControl {{name: $cc{i}}})")
                params[f"cc{i}"] = cc

        if entities.get("ability_effects"):
            for i, eff in enumerate(entities["ability_effects"]):
                conditions.append(f"(c)-[:HAS_EFFECT]->(:Effect {{name: $eff{i}}})")
                params[f"eff{i}"] = eff

        if entities.get("playstyles"):
            for i, ps in enumerate(entities["playstyles"]):
                conditions.append(f"(c)-[:HAS_PLAYSTYLE]->(:Playstyle {{name: $ps{i}}})")
                params[f"ps{i}"] = ps

        if not conditions:
            return []

        where_clause = " AND ".join([f"EXISTS {{{cond}}}" for cond in conditions])
        cypher = f"""
        MATCH (c:Champion) WHERE {where_clause}
        RETURN c.name AS name, c.champion_id AS id
        LIMIT 20
        """

        match_clauses = ", ".join(conditions)
        cypher_simple = f"""
        MATCH (c:Champion), {match_clauses}
        RETURN DISTINCT c.name AS name, c.champion_id AS id
        LIMIT 20
        """

        try:
            results = self.store.run_cypher(cypher, **params)
        except Exception:
            try:
                results = self.store.run_cypher(cypher_simple, **params)
            except Exception:
                return []

        if not results:
            return []

        criteria_str = ", ".join(str(v) for v in params.values())
        lines = [f"Champions matching criteria ({criteria_str}):"]
        for r in results:
            lines.append(f"  - {r['name']}")

        return [{"text": "\n".join(lines), "source": "graph:multi_filter",
                 "score": 0.85, "metadata": {"criteria": params}}]

    def traverse_semantic_profile(self, name):
        """Get complete tactical profile of a champion."""
        overview = self.traverse_champion_overview(name)
        stats = self.traverse_champion_stats(name)
        abilities = self.traverse_all_abilities(name)
        return overview + stats + abilities

    def traverse_team_counters(self, enemies, comp_archetype = None):
        """Analyze counters against an enemy team composition or archetype."""
        target_enemies = list(enemies) if enemies else []

        # If no explicit enemy list but an archetype is specified, find representative champions
        if not target_enemies and comp_archetype:
            try:
                cypher_ps = """
                MATCH (c:Champion)-[:HAS_PLAYSTYLE]->(ps:Playstyle)
                WHERE toLower(ps.name) CONTAINS toLower($comp)
                RETURN c.name AS name
                LIMIT 4
                """
                ps_res = self.store.run_cypher(cypher_ps, comp=comp_archetype)
                if ps_res:
                    target_enemies = [r["name"] for r in ps_res]
            except Exception:
                pass

        if not target_enemies:
            return []

        all_results = []
        for enemy in target_enemies[:5]:
            counters = self.traverse_counters(enemy, "countered_by")
            all_results.extend(counters)
        return all_results
