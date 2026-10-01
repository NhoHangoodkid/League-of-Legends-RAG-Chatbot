"""
Lane, role, and semantic filter retrieval mixin.
"""

from collections import Counter


class LaneRetrieverMixin:
    """Provides queries for filtering champions by role, lane, and semantic criteria."""

    def get_champions_by_role(self, role, lane = None):
        champs = self.store.filter_champions(roles=[role], positions=[lane] if lane else None)
        if not champs and lane:
            champs = self.store.filter_champions(roles=[role])

        subroles = [s for c in champs for s in c.get("subroles", [])]
        top_subroles = [s for s, _ in Counter(subroles).most_common(5)]

        damage_types = [c.get("adaptiveType") for c in champs if c.get("adaptiveType")]
        dominant_damage = Counter(damage_types).most_common(1)[0][0] if damage_types else "Mixed"

        sample_champs = [
            {
                "name": c.get("name"),
                "subroles": c.get("subroles", []),
                "positions": c.get("positions", []),
                "damage_type": c.get("adaptiveType"),
                "playstyles": c.get("playstyles", []),
                "power_curve": c.get("powerCurve", []),
            }
            for c in champs[:25]
        ]
        return {
            "is_role_query": True,
            "role": role,
            "lane": lane or "all",
            "role_title": f"{role.capitalize()} Champions" + (f" ({lane.upper()})" if lane else ""),
            "count": len(champs),
            "dominant_damage": dominant_damage,
            "subroles": top_subroles,
            "champions": [c.get("name") for c in champs[:25]],
            "sample_champions": sample_champs,
        }

    def get_champions_by_lane(self, lane):
        champs = self.store.get_champions_by_lane(lane)

        roles = [r for c in champs for r in c.get("roles", [])]
        top_roles = [r for r, _ in Counter(roles).most_common(4)]

        subroles = [s for c in champs for s in c.get("subroles", [])]
        top_subroles = [s for s, _ in Counter(subroles).most_common(5)]

        damage_types = [c.get("adaptiveType") for c in champs if c.get("adaptiveType")]
        dominant_damage = Counter(damage_types).most_common(1)[0][0] if damage_types else "Mixed"

        sample_champs = [
            {
                "name": c.get("name"),
                "roles": c.get("roles", []),
                "subroles": c.get("subroles", []),
                "damage_type": c.get("adaptiveType"),
                "playstyles": c.get("playstyles", []),
                "power_curve": c.get("powerCurve", []),
            }
            for c in champs[:25]
        ]
        return {
            "is_lane_query": True,
            "lane": lane.upper(),
            "count": len(champs),
            "dominant_damage": dominant_damage,
            "top_roles": top_roles,
            "top_subroles": top_subroles,
            "champions": [c.get("name") for c in champs[:25]],
            "sample_champions": sample_champs,
        }

    def filter_semantic(
        self,
        roles = None,
        cc_types = None,
        effects = None,
        playstyles = None,
        power_curve = None,
        win_condition = None,
    ):
        matches = self.store.filter_champions(
            roles=roles,
            cc_types=cc_types,
            effects=effects,
            playstyles=playstyles,
            power_curve=power_curve,
            win_condition=win_condition,
        )

        return {
            "criteria": {
                "roles": roles,
                "cc_types": cc_types,
                "effects": effects,
                "playstyles": playstyles,
                "power_curve": power_curve,
                "win_condition": win_condition,
            },
            "total_matches": len(matches),
            "sample_matches": [
                {
                    "name": m.get("name"),
                    "roles": m.get("roles", []),
                    "cc": m.get("cc_types", []),
                    "effects": m.get("ability_effects", []),
                    "playstyles": m.get("playstyles", []),
                }
                for m in matches[:10]
            ],
        }
