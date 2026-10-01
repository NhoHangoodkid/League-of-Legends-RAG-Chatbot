"""
Synergy retrieval mixin: duo synergies, champion composition recommendations, and multi-champion team synergy analysis.
"""

import json
from chatbot.config import knowledge_base_dir, processed_dir


class SynergyRetrieverMixin:
    """Provides methods for duo synergies, competitive composition pairings, and team synergy analysis."""

    def get_synergies(self, name):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)
        data = self.store.get_synergy_info(name)
        
        # Fallback to direct file loading if KnowledgeStore didn't have it loaded yet
        if not data:
            for syn_path in [knowledge_base_dir / "synergies.json", processed_dir / "synergies.json"]:
                if syn_path.exists():
                    try:
                        with open(syn_path, "r", encoding="utf-8") as f:
                            all_syn = json.load(f)
                            norm_name = self.store.normalize_key(name)
                            data = all_syn.get(name) or all_syn.get(champ.get("name")) or all_syn.get(norm_name)
                            if not data and isinstance(all_syn, dict):
                                for k, v in all_syn.items():
                                    if self.store.normalize_key(k) == norm_name:
                                        data = v
                                        break
                            if data:
                                break
                    except Exception:
                        pass

        duos = []
        team_comps = []
        tactical_insights = []
        if data:
            if isinstance(data, dict):
                duos = data.get("best_duos") or data.get("synergies", [])
                team_comps = data.get("best_team_compositions", [])
                tactical_insights = data.get("tactical_insights", [])
            elif isinstance(data, list):
                duos = data

        profile.update({
            "is_synergy_query": True,
            "best_duos": duos[:6],
            "top_duos": duos[:6],
            "best_team_compositions": team_comps,
            "tactical_insights": tactical_insights,
            "data_source_note": "Season 2025 Match Data (Pro Play + OP.GG SoloQ)",
            "notice": "No specific duo synergy data available for this champion." if not duos else None,
        })
        return profile

    def get_champion_composition(self, name):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)
        data = self.store.get_synergy_info(name)
        if not data:
            for syn_path in [knowledge_base_dir / "synergies.json", processed_dir / "synergies.json"]:
                if syn_path.exists():
                    try:
                        with open(syn_path, "r", encoding="utf-8") as f:
                            all_syn = json.load(f)
                            norm_name = self.store.normalize_key(name)
                            data = all_syn.get(name) or all_syn.get(champ.get("name")) or all_syn.get(norm_name)
                            if data:
                                break
                    except Exception:
                        pass

        comps = data.get("best_team_compositions", []) if isinstance(data, dict) else []
        duos = data.get("best_duos", []) if isinstance(data, dict) else []

        profile.update({
            "is_champion_composition": True,
            "focus_champion": champ.get("name", name),
            "best_team_compositions": comps,
            "best_duos": duos[:3],
            "tactical_insights": data.get("tactical_insights", []) if isinstance(data, dict) else [],
            "notice": f"Không có dữ liệu đội hình Pro Play cụ thể cho {champ.get('name', name)}." if not comps else None,
        })
        return profile

    def analyze_team_synergies(self, champions):
        """
        Dynamically analyze team synergies, combo chains, CC layers, and damage distribution
        across a composition using processor data from KnowledgeStore.
        """
        if not champions:
            return {"error": "A list of allied champions is required for team synergy analysis."}

        synergy_combos = []
        team_cc = set()
        team_roles = []
        team_damage = []

        champ_objs = {}
        for name in champions:
            c = self.store.get_champion(name)
            if c:
                c_name = c.get("name", name)
                champ_objs[c_name] = c
                team_cc.update(c.get("cc_types", []))
                team_roles.extend(c.get("roles", []))
                if c.get("adaptiveType"):
                    team_damage.append(c["adaptiveType"])

        names = list(champ_objs.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                c1_name = names[i]
                c2_name = names[j]
                syn_data = self.store.get_synergy_info(c1_name) or {}
                duos = (syn_data.get("best_duos") or syn_data.get("synergies", [])) if isinstance(syn_data, dict) else []
                match = next((d for d in duos if (d.get("partner") or d.get("champion", "")).lower() == c2_name.lower()), None)
                if match:
                    synergy_combos.append({
                        "pair": f"{c1_name} + {c2_name}",
                        "reason": match.get("synergy_reason") or match.get("reason", ""),
                        "winRate": match.get("soloq_winrate") or match.get("winRate"),
                        "pro_play": match.get("pro_play", False),
                        "pro_games": match.get("pro_games", 0),
                        "pro_winrate": match.get("pro_winrate"),
                    })
                else:
                    c1 = champ_objs[c1_name]
                    c2 = champ_objs[c2_name]
                    c1_hard_cc = set(c1.get("hard_cc", []))
                    c2_hard_cc = set(c2.get("hard_cc", []))
                    if c1_hard_cc and c2_hard_cc:
                        synergy_combos.append({
                            "pair": f"{c1_name} + {c2_name}",
                            "reason": f"Lockdown CC Chain: {', '.join(c1_hard_cc)} combined with {', '.join(c2_hard_cc)} enables layered crowd control.",
                            "winRate": None,
                        })

        return {
            "is_team_synergy": True,
            "team_champions": names,
            "synergy_combos": synergy_combos,
            "team_cc_types": sorted(list(team_cc)),
            "damage_distribution": list(set(team_damage)),
        }
