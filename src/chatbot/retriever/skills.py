"""
Skill and mechanics retrieval mixin: damage, cooldown, ability details, mechanics, wind wall / spellshield interactions.
"""


class SkillRetrieverMixin:
    """Provides methods for champion abilities, mechanics, damage scaling, and cooldown queries."""

    def get_mechanics_info(self, name, skill_key = None, mechanic = None, interaction_champ = None):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)
        abilities = champ.get("abilities", {})
        mechanics_summary = champ.get("mechanicsSummary", {})

        if skill_key:
            sk = skill_key.upper()
            # If name is a known defender (e.g. Yasuo with Wind Wall) and interaction_champ has the skill (e.g. Lux with R)
            if interaction_champ and self.store.get_champion(interaction_champ):
                inter_champ_obj = self.store.get_champion(interaction_champ)
                inter_abilities = inter_champ_obj.get("abilities", {})
                if sk in inter_abilities and (name.lower() in ["yasuo", "braum", "samira", "sivir", "nocturne"] or not abilities.get(sk, {}).get("description")):
                    champ = inter_champ_obj
                    profile = self.extract_champion_full_profile(champ)
                    abilities = inter_abilities
                    mechanics_summary = champ.get("mechanicsSummary", {})
                    interaction_champ, name = name, profile.get("name")

            ability = abilities.get(sk, {})
            is_projectile = ability.get("projectile", False)
            is_spellshieldable = ability.get("spellshieldable", False)
            is_onhit = ability.get("onHitEffects", False)
            damage_type = ability.get("damageType")

            wind_wall_blocked = is_projectile
            wind_wall_verdict = (
                "BLOCKED by Wind Wall (Yasuo W, Samira W, Braum E) because it is a projectile."
                if is_projectile
                else "NOT BLOCKED by Wind Wall (Yasuo W, Samira W) because it is an instant beam/area ability, not a projectile."
            )

            spellshield_verdict = (
                "BLOCKED / Absorbed by Spell Shields (Banshee's Veil, Edge of Night, Sivir E, Nocturne W)."
                if is_spellshieldable
                else "NOT BLOCKED by Spell Shields."
            )

            return {
                "is_mechanics_query": True,
                "champion": profile.get("name"),
                "skill_key": sk,
                "skill_name": ability.get("name", sk),
                "description": ability.get("description", ""),
                "is_projectile": is_projectile,
                "projectile": is_projectile,
                "spellshieldable": is_spellshieldable,
                "triggers_on_hit": is_onhit,
                "onHitEffects": is_onhit,
                "damageType": damage_type,
                "wind_wall_blocked": wind_wall_blocked,
                "wind_wall_verdict": wind_wall_verdict,
                "spellshield_verdict": spellshield_verdict,
                "mechanic_tested": mechanic,
                "interaction_champion": interaction_champ,
                "mechanicsSummary": mechanics_summary,
            }

        return {
            "is_mechanics_query": True,
            "champion": profile.get("name"),
            "mechanic_tested": mechanic,
            "mechanic_requested": mechanic,
            "projectile_abilities": mechanics_summary.get("projectileAbilities", []),
            "spellshieldable_abilities": mechanics_summary.get("spellshieldableAbilities", []),
            "onhit_abilities": mechanics_summary.get("onHitAbilities", []),
            "damage_types": mechanics_summary.get("abilityDamageTypes", []),
            "mechanicsSummary": mechanics_summary,
            "abilities": profile.get("abilities", {}),
        }

    def get_skill_damage(self, name, skill_key, rank):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)
        key = skill_key.upper()
        skill = champ.get("abilities", {}).get(key)
        if not skill:
            return {"error": f"Ability {key} of {champ.get('name')} not found."}

        cooldowns = skill.get("cooldown", [])
        cd_val = cooldowns[rank - 1] if isinstance(cooldowns, list) and len(cooldowns) >= rank else cooldowns

        profile.update({
            "skill_key": key,
            "skill_name": skill.get("name"),
            "rank": rank,
            "description": skill.get("description", ""),
            "cooldown": cd_val,
            "cost": skill.get("cost", []),
            "costType": skill.get("costType"),
            "range": skill.get("range", []),
            "maxrank": skill.get("maxrank"),
            "scalingEffects": skill.get("scalingEffects", []),
            "effects": skill.get("effects", []),
        })
        return profile

    def get_skill_info(self, name, skill_key):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)
        key = skill_key.upper()
        skill = champ.get("abilities", {}).get(key)
        if not skill:
            return {"error": f"Ability {key} of {champ.get('name')} not found."}

        profile.update({
            "skill_key": key,
            "skill_name": skill.get("name"),
            "description": skill.get("description", ""),
            "cooldown": skill.get("cooldown", []),
            "cost": skill.get("cost", []),
            "costType": skill.get("costType"),
            "range": skill.get("range", []),
            "maxrank": skill.get("maxrank"),
            "scalingEffects": skill.get("scalingEffects", []),
            "effects": skill.get("effects", []),
            "projectile": skill.get("projectile"),
            "projectileType": skill.get("projectileType"),
            "spellshieldable": skill.get("spellshieldable"),
            "onHitEffects": skill.get("onHitEffects"),
            "damageType": skill.get("damageType"),
            "targeting": skill.get("targeting"),
            "notes": skill.get("notes"),
        })
        return profile

    def get_skill_cooldown(self, name, skill_key):
        return self.get_skill_info(name, skill_key)

    def list_skills(self, name):
        champ = self.store.get_champion(name)
        if not champ:
            return {"error": f"Champion '{name}' not found."}

        profile = self.extract_champion_full_profile(champ)
        return profile
