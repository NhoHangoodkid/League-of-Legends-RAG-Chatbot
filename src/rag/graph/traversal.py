"""
Graph Traversal Strategies for LoL Knowledge Bot.

Provides intent-aware graph traversal that collects relevant context
from the Knowledge Graph based on the user's query intent and extracted entities.
"""

import json
from typing import Any, Dict, List, Optional

from rag.graph.schema import EdgeType, NodeType
from rag.graph.store import Neo4jStore, get_graph_store


class GraphTraversal:
    """
    Intent-driven graph traversal for context retrieval.

    Given a classified intent and entities, traverse the Knowledge Graph
    to collect structured context for the LLM response generator.
    """

    def __init__(self, store = None):
        self.store = store or get_graph_store()

    def retrieve_context(self, entities, intent, max_results = 10):
        """
        Main entry: dispatch to intent-specific traversal strategy.

        Returns:
            List of context dicts, each with 'text', 'source', 'score', 'metadata'.
        """
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
            "TEAM_COUNTER_ANALYSIS": lambda: self.traverse_team_counters(entities.get("enemy_champions", [])),
            "ROLE_QUERY": lambda: self.traverse_by_role(entities.get("role", "")),
        }

        handler = strategy_map.get(intent)
        if handler:
            try:
                return handler()[:max_results]
            except Exception as e:
                print(f"[GraphTraversal] Error in {intent}: {e}")
                return []

        # Fallback: if champion is known, get overview
        if champ_name:
            return self.traverse_champion_overview(champ_name)[:max_results]

        return []

    #--------------------------------------------------------------------------
    # Traversal Strategies
    #--------------------------------------------------------------------------

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

        # Who counters this champion (weak against)
        cypher_weak = """
        MATCH (counter:Champion)-[r:COUNTERS]->(c:Champion)
        WHERE c.champion_id = $name OR c.name =~ ('(?i).*' + $name + '.*')
        RETURN counter.name AS counter_name, counter.champion_id AS counter_id,
               r.win_rate AS win_rate, r.games AS games
        ORDER BY r.win_rate DESC
        LIMIT 10
        """

        # Who this champion counters (strong against)
        cypher_strong = """
        MATCH (c:Champion)-[r:COUNTERS]->(weak:Champion)
        WHERE c.champion_id = $name OR c.name =~ ('(?i).*' + $name + '.*')
        RETURN weak.name AS weak_name, weak.champion_id AS weak_id,
               r.win_rate AS win_rate, r.games AS games
        ORDER BY r.win_rate DESC
        LIMIT 10
        """

        results = []

        weak_results = self.store.run_cypher(cypher_weak, name=name)
        if weak_results:
            lines = [f"{name} bị khắc chế bởi:"]
            for wr in weak_results:
                lines.append(f"  - {wr['counter_name']} (Win rate: {wr.get('win_rate', '?')}%)")
            results.append({"text": "\n".join(lines), "source": "graph:counters_weak", "score": 0.95,
                           "metadata": {"direction": "countered_by"}})

        strong_results = self.store.run_cypher(cypher_strong, name=name)
        if strong_results:
            lines = [f"{name} khắc chế tốt:"]
            for sr in strong_results:
                lines.append(f"  - {sr['weak_name']} (Win rate: {sr.get('win_rate', '?')}%)")
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
               r.duo_win_rate AS duo_win_rate, r.games AS games
        ORDER BY r.duo_win_rate DESC
        LIMIT 10
        """
        results = self.store.run_cypher(cypher, name=name)
        if not results:
            return []

        lines = [f"Đồng đội phối hợp tốt nhất với {name}:"]
        for r in results:
            lines.append(f"  - {r['partner_name']} (Duo win rate: {r.get('duo_win_rate', '?')}%)")

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
            f"Build đề xuất cho {r['champ_name']}:\n"
            f"  Trang bị cốt lõi: {', '.join(core_items) or 'N/A'}\n"
            f"  Trang bị đầy đủ: {', '.join(all_items) or 'N/A'}\n"
            f"  Ngọc bổ trợ: {', '.join(runes) or 'N/A'}"
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
            f"Chiêu thức {a.get('key', '')} - {a.get('name', '')} của {results[0]['champ_name']}:\n"
            f"  Mô tả: {a.get('description', '')}\n"
            f"  Hồi chiêu: {a.get('cooldown_json', '[]')}\n"
            f"  Năng lượng: {a.get('cost_json', '[]')}\n"
            f"  Tầm đánh: {a.get('range_json', '[]')}"
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

        lines = [f"Danh sách chiêu thức của {records[0]['champ_name']}:"]
        for r in records:
            a = dict(r["a"])
            lines.append(f"  [{a.get('key', '')}] {a.get('name', '')}: {a.get('description', '')[:150]}...")

        return [{"text": "\n".join(lines), "source": "graph:all_abilities", "score": 1.0,
                 "metadata": {"champion": name}}]

    def traverse_champion_stats(self, name):
        """Get champion stats from graph node properties."""
        if not name:
            return []

        node = self.store.get_node(name, NodeType.CHAMPION)
        if not node:
            # Try fuzzy
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
        lines = [f"Chỉ số cơ bản của {node.get('name', name)}:"]
        for stat_name, stat_val in stats.items():
            if isinstance(stat_val, dict):
                lines.append(f"  {stat_name}: {stat_val.get('base', 0)} (+{stat_val.get('perLevel', 0)}/level)")
            else:
                lines.append(f"  {stat_name}: {stat_val}")

        return [{"text": "\n".join(lines), "source": "graph:stats", "score": 1.0,
                 "metadata": {"champion": name, "stats": stats}}]

    def traverse_comparison(self, champ_names):
        """Compare multiple champions' stats."""
        if not champ_names or len(champ_names) < 2:
            return []

        results = []
        for name in champ_names:
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
            f"  Giá: {item.get('cost_total', 0)} vàng (Bán: {item.get('cost_sell', 0)})\n"
            f"  Mô tả: {item.get('description', '')}\n"
            f"  Chỉ số: {item.get('stats_json', '{}')}\n"
            f"  Ghép từ: {', '.join(r['components']) if r['components'] else 'N/A'}\n"
            f"  Nâng cấp thành: {', '.join(r['upgrades']) if r['upgrades'] else 'N/A'}"
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
            f"Ngọc: {rune.get('name', name)} (Nhánh: {rune.get('tree', '')})\n"
            f"  Mô tả: {rune.get('long_description', rune.get('description', ''))}"
        )

        return [{"text": text, "source": "graph:rune", "score": 1.0,
                 "metadata": {"rune_name": rune.get("name")}}]

    def traverse_by_tag(self, tag_type, tag_values):
        """Find champions that share specific tag nodes (CC, Effect, etc.)."""
        if not tag_values:
            return []

        label = tag_type.value
        # Map tag type to edge type
        edge_map = {
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

        lines = [f"Tướng có {', '.join(tag_values)}:"]
        for r in results:
            lines.append(f"  - {r['name']}")

        return [{"text": "\n".join(lines), "source": f"graph:filter_{tag_type.value}",
                 "score": 0.90, "metadata": {"filter": tag_values}}]

    def traverse_by_role(self, role):
        """Find champions by role."""
        if not role:
            return []
        return self.traverse_by_tag(NodeType.ROLE, [role.strip().capitalize()])

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

        # Simpler fallback approach using MATCH patterns
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
        lines = [f"Tướng thỏa mãn điều kiện ({criteria_str}):"]
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

    def traverse_team_counters(self, enemies):
        """Analyze counters against an enemy team composition."""
        if not enemies:
            return []

        all_results = []
        for enemy in enemies:
            counters = self.traverse_counters(enemy, "countered_by")
            all_results.extend(counters)
        return all_results
