"""
Document Chunker for LoL Knowledge Bot.

Splits processed game data (champions, items, runes) into semantic chunks
optimized for embedding and retrieval. Each chunk is a self-contained text passage
with metadata for filtering and tracing.

Chunking Strategies:
1. Champion Overview — roles, playstyles, power curve, lore
2. Ability Chunks — one per ability (P, Q, W, E, R)
3. Stats Chunk — base stats and growth
4. Counter/Synergy Chunks — matchup data
5. Build Chunk — items, runes, spells
6. Item Chunks — cost, stats, description, build path
7. Rune Chunks — description, tree
"""

import json
from pathlib import Path


class DocumentChunk:
    """A single chunk of text with metadata for indexing."""

    def __init__(self, chunk_id, text, entity_type, entity_name, chunk_type, metadata = None):
        self.chunk_id = chunk_id
        self.text = text
        self.entity_type = entity_type
        self.entity_name = entity_name
        self.chunk_type = chunk_type
        self.metadata = metadata or {}

    def __repr__(self):
        return f"DocumentChunk(id='{self.chunk_id}', type='{self.chunk_type}')"


class DocumentChunker:
    """
    Splits LoL knowledge base data into embedding-optimized text chunks.

    Each chunk is designed to:
    - Be self-contained (understandable without extra context)
    - Stay within 200-500 tokens for optimal embedding quality
    - Include entity name for disambiguation
    - Carry metadata for post-retrieval filtering
    """

    def chunk_all(self, champions, items, runes, counters = None, synergies = None, builds = None, team_compositions = None):
        """
        Generate all document chunks from processed data.

        Returns:
            List of DocumentChunk objects ready for embedding.
        """
        chunks = []

        # Champion chunks
        for champ_id, champ in champions.items():
            chunks.extend(self.chunk_champion(champ_id, champ))

        # Item chunks
        for item_id, item in items.items():
            chunks.extend(self.chunk_item(item_id, item))

        # Rune chunks
        runes_by_id = runes.get("byId", {})
        for rune_id, rune in runes_by_id.items():
            chunks.extend(self.chunk_rune(rune_id, rune))

        # Counter chunks
        if counters:
            for champ_key, data in counters.items():
                chunks.extend(self.chunk_counters(champ_key, data))

        # Synergy chunks
        if synergies:
            for champ_key, data in synergies.items():
                chunks.extend(self.chunk_synergies(champ_key, data))

        # Build chunks
        if builds:
            for champ_key, data in builds.items():
                chunks.extend(self.chunk_build(champ_key, data))

        # Team composition chunks
        if team_compositions:
            for comp_id, data in team_compositions.items():
                chunks.extend(self.chunk_team_composition(comp_id, data))

        # Role-Level Tactical chunks (Support, Tank, Marksman, Mage, Assassin, Fighter)
        chunks.extend(self.chunk_roles(champions))

        print(f"[Chunker] Generated {len(chunks)} chunks")
        return chunks

    # Champion Chunking

    def chunk_champion(self, champ_id, champ):
        """Generate chunks for a single champion."""
        chunks = []
        name = champ.get("name", champ_id)

        # 1. Overview chunk
        roles = ", ".join(champ.get("roles", []))
        subroles = ", ".join(champ.get("subroles", []))
        positions = ", ".join(champ.get("positions", []))
        region = champ.get("region", "Runeterra")
        playstyles = ", ".join(champ.get("playstyles", []))
        power_curve = ", ".join(champ.get("powerCurve", []))
        win_conditions = ", ".join(champ.get("winConditions", []))
        cc_types = ", ".join(champ.get("cc_types", []))
        effects = ", ".join(champ.get("ability_effects", []))
        short_lore = champ.get("shortLore", "")
        related = champ.get("related_champions", [])
        related_names = [rc.get("name") if isinstance(rc, dict) else str(rc) for rc in related if rc]
        related_str = ", ".join(related_names)

        overview_text = (
            f"{name} — {champ.get('title', '')}. "
            f"Region: {region}. "
            f"Roles: {roles or 'Unknown'}. "
            f"Subroles: {subroles or 'Unknown'}. "
            f"Positions: {positions or 'Unknown'}. "
            f"Resource: {champ.get('resource', 'Mana')}. "
            f"Attack Type: {champ.get('attackType', 'Unknown')}. "
            f"Playstyles: {playstyles or 'Unknown'}. "
            f"Power Curve: {power_curve or 'Unknown'}. "
            f"Win Conditions: {win_conditions or 'Unknown'}. "
            f"Crowd Control: {cc_types or 'None'}. "
            f"Ability Effects: {effects or 'None'}. "
            f"Difficulty: {champ.get('difficulty', 0)}/10."
        )
        if related_str:
            overview_text += f" Related Champions: {related_str}."
        if short_lore:
            overview_text += f" Lore: {short_lore[:300]}"

        chunks.append(DocumentChunk(
            chunk_id=f"champion:{champ_id}:overview",
            text=overview_text.strip(),
            entity_type="champion",
            entity_name=name,
            chunk_type="overview",
            metadata={
                "champion_id": champ_id,
                "roles": champ.get("roles", []),
                "subroles": champ.get("subroles", []),
                "positions": champ.get("positions", []),
                "region": region,
                "related_champions": related_names,
                "cc_types": champ.get("cc_types", []),
                "effects": champ.get("ability_effects", []),
                "playstyles": champ.get("playstyles", []),
            },
        ))

        # 2. Ability chunks (one per ability)
        abilities = champ.get("abilities", {})
        for key in ["passive", "Q", "W", "E", "R"]:
            ability = abilities.get(key, {})
            if not ability or not ability.get("name"):
                continue

            ability_text = (
                f"{name} ability [{key}] — {ability.get('name', '')}: "
                f"{ability.get('description', '')}"
            )

            if key != "passive":
                cd = ability.get("cooldown", [])
                cost = ability.get("cost", [])
                rng = ability.get("range", [])
                if cd:
                    ability_text += f" Cooldown: {cd}s."
                if cost:
                    ability_text += f" Cost: {cost}."
                if rng:
                    ability_text += f" Range: {rng}."

            if ability.get("projectile") is not None:
                p_val = "Yes" if ability.get("projectile") else "No"
                p_type = f" ({ability.get('projectileType')})" if ability.get("projectileType") else ""
                ability_text += f" Projectile: {p_val}{p_type}."
            if ability.get("spellshieldable") is not None:
                s_val = "Yes" if ability.get("spellshieldable") else "No"
                ability_text += f" Spellshieldable: {s_val}."
            if ability.get("onHitEffects") is not None:
                o_val = "Yes" if ability.get("onHitEffects") else "No"
                ability_text += f" Applies On-Hit Effects: {o_val}."
            if ability.get("damageType"):
                ability_text += f" Damage Type: {ability.get('damageType')}."

            chunks.append(DocumentChunk(
                chunk_id=f"champion:{champ_id}:ability:{key}",
                text=ability_text.strip(),
                entity_type="ability",
                entity_name=name,
                chunk_type="ability",
                metadata={
                    "champion_id": champ_id,
                    "ability_key": key,
                    "ability_name": ability.get("name", ""),
                    "projectile": ability.get("projectile"),
                    "spellshieldable": ability.get("spellshieldable"),
                    "onHitEffects": ability.get("onHitEffects"),
                },
            ))

        # 3. Stats chunk
        stats = champ.get("stats", {})
        if stats:
            stat_lines = [f"{name} base stats (Level 1):"]
            for stat_name, stat_val in stats.items():
                if isinstance(stat_val, dict):
                    base = stat_val.get("base", 0)
                    growth = stat_val.get("perLevel", 0)
                    stat_lines.append(f"  {stat_name}: {base} (+{growth} per level)")
                else:
                    stat_lines.append(f"  {stat_name}: {stat_val}")

            chunks.append(DocumentChunk(
                chunk_id=f"champion:{champ_id}:stats",
                text="\n".join(stat_lines),
                entity_type="champion",
                entity_name=name,
                chunk_type="stats",
                metadata={"champion_id": champ_id, "stats": stats},
            ))

        # 4. Lore chunk (if long enough for a separate chunk)
        lore = champ.get("lore", "")
        if lore and len(lore) > 100:
            lore_text = f"{name} lore — Region: {region}."
            if related_str:
                lore_text += f" Related champions in lore: {related_str}."
            lore_text += f" Story: {lore[:800]}"
            stories = champ.get("stories", [])
            if stories:
                story_titles = [s.get("title") for s in stories if isinstance(s, dict) and s.get("title")]
                if story_titles:
                    lore_text += f" Canon Universe Stories: {', '.join(story_titles[:8])}."

            chunks.append(DocumentChunk(
                chunk_id=f"champion:{champ_id}:lore",
                text=lore_text.strip(),
                entity_type="champion",
                entity_name=name,
                chunk_type="lore",
                metadata={
                    "champion_id": champ_id,
                    "region": region,
                    "related_champions": related_names,
                },
            ))

        # 5. Combat Mechanics chunk (projectile, spell shield, on-hit summary)
        mech = champ.get("mechanicsSummary", {})
        proj_list = mech.get("projectileAbilities", [])
        spell_list = mech.get("spellshieldableAbilities", [])
        onhit_list = mech.get("onHitAbilities", [])
        dmg_types = mech.get("abilityDamageTypes", [])

        if proj_list or spell_list or onhit_list or dmg_types:
            mech_lines = [f"{name} combat mechanics, projectile, and spell shield interactions:"]
            if proj_list:
                mech_lines.append(f"  Projectile abilities (blocked by Yasuo W Wind Wall / Samira W): {', '.join(proj_list)}.")
            else:
                mech_lines.append("  Projectile abilities: None (No abilities blocked by Wind Wall).")
            if spell_list:
                mech_lines.append(f"  Spellshieldable abilities (absorbed by Banshee's Veil / Edge of Night / Sivir E): {', '.join(spell_list)}.")
            if onhit_list:
                mech_lines.append(f"  Abilities triggering on-hit effects: {', '.join(onhit_list)}.")
            if dmg_types:
                mech_lines.append(f"  Ability damage types: {', '.join(dmg_types)}.")

            chunks.append(DocumentChunk(
                chunk_id=f"champion:{champ_id}:mechanics",
                text="\n".join(mech_lines),
                entity_type="champion",
                entity_name=name,
                chunk_type="mechanics",
                metadata={
                    "champion_id": champ_id,
                    "projectile_abilities": proj_list,
                    "spellshieldable_abilities": spell_list,
                },
            ))

        # 6. Skins and cosmetics catalog chunk
        skins = champ.get("skins", [])
        if skins:
            skin_names = [s.get("name") for s in skins if isinstance(s, dict) and s.get("name") and s.get("name").lower() != "default"]
            skin_text = f"{name} skins and cosmetics catalog: Total skins: {len(skins)}. Available skins include: {', '.join(skin_names[:25])}."
            chunks.append(DocumentChunk(
                chunk_id=f"champion:{champ_id}:skins",
                text=skin_text,
                entity_type="champion",
                entity_name=name,
                chunk_type="skins",
                metadata={"champion_id": champ_id, "skin_count": len(skins)},
            ))

        # 7. ARAM balance modifiers chunk
        aram = champ.get("aramStats", {})
        if aram:
            aram_parts = []
            if aram.get("aramDamageDealt") is not None:
                aram_parts.append(f"Damage Dealt: {aram.get('aramDamageDealt')}%")
            if aram.get("aramDamageTaken") is not None:
                aram_parts.append(f"Damage Taken: {aram.get('aramDamageTaken')}%")
            if aram.get("aramAbilityHaste") is not None:
                aram_parts.append(f"Ability Haste: {aram.get('aramAbilityHaste')}")
            if aram.get("aramHealing") is not None:
                aram_parts.append(f"Healing: {aram.get('aramHealing')}%")
            if aram.get("aramShielding") is not None:
                aram_parts.append(f"Shielding: {aram.get('aramShielding')}%")

            if aram_parts:
                aram_text = f"{name} Howling Abyss (ARAM) balance modifiers: {', '.join(aram_parts)}. These balance adjustments dictate durability and power spikes in ARAM."
                chunks.append(DocumentChunk(
                    chunk_id=f"champion:{champ_id}:aram",
                    text=aram_text,
                    entity_type="champion",
                    entity_name=name,
                    chunk_type="aram",
                    metadata={"champion_id": champ_id, "aram_stats": aram},
                ))

        return chunks

    # Item Chunking

    def chunk_item(self, item_id, item):
        """Generate chunks for a single item."""
        name = item.get("name", f"Item_{item_id}")
        cost = item.get("cost", {})
        stats = item.get("stats", {})
        desc = item.get("description", "")
        plaintext = item.get("plaintext", "")
        build_from = item.get("buildFrom", [])
        build_into = item.get("buildInto", [])
        colloquial = item.get("colloquial", []) or item.get("aliases", [])

        cost_total = cost.get("total", 0) if isinstance(cost, dict) else 0
        cost_sell = cost.get("sell", 0) if isinstance(cost, dict) else 0

        stat_parts = []
        for stat_name, stat_val in stats.items():
            if stat_val and stat_val != 0:
                stat_parts.append(f"{stat_name}: +{stat_val}")

        text = f"Item: {name}. Cost: {cost_total} gold (Sell: {cost_sell} gold)."
        if stat_parts:
            text += f" Stats: {', '.join(stat_parts)}."
        if colloquial:
            if isinstance(colloquial, list):
                colloquial_str = ", ".join(str(c) for c in colloquial)
            else:
                colloquial_str = str(colloquial)
            text += f" Community Slang and Aliases: {colloquial_str}."
        if desc:
            text += f" Description: {desc[:300]}."
        if plaintext:
            text += f" {plaintext}"
        if build_from:
            text += f" Builds from: {', '.join(str(b) for b in build_from)}."
        if build_into:
            text += f" Builds into: {', '.join(str(b) for b in build_into)}."

        return [DocumentChunk(
            chunk_id=f"item:{item_id}",
            text=text.strip(),
            entity_type="item",
            entity_name=name,
            chunk_type="item_info",
            metadata={"item_id": str(item_id), "cost_total": cost_total, "aliases": colloquial},
        )]

    # Rune Chunking

    def chunk_rune(self, rune_id, rune):
        """Generate chunks for a single rune."""
        name = rune.get("name", f"Rune_{rune_id}")
        tree = rune.get("tree", "")
        desc = rune.get("description", "")
        long_desc = rune.get("longDescription", "")

        text = f"Rune: {name} (Tree: {tree}). {long_desc or desc}"

        return [DocumentChunk(
            chunk_id=f"rune:{rune_id}",
            text=text.strip(),
            entity_type="rune",
            entity_name=name,
            chunk_type="rune_info",
            metadata={"rune_id": str(rune_id), "tree": tree},
        )]

    # Matchup Chunking

    def chunk_counters(self, champ_key, data):
        """Generate counter matchup chunks."""
        champ_name = data.get("champion", champ_key)

        weak_against = data.get("weakAgainst", [])[:5]
        strong_against = data.get("strongAgainst", [])[:5]
        weaknesses = data.get("weaknesses", [])
        tactical_tips = data.get("tactical_tips", [])
        counter_items = data.get("counter_items", [])
        enemy_tips = data.get("official_enemytips", [])
        ally_tips = data.get("official_allytips", [])
        proj_abilities = data.get("projectile_abilities", [])
        spell_abilities = data.get("spellshieldable_abilities", [])

        if not weak_against and not strong_against and not weaknesses and not tactical_tips and not enemy_tips and not ally_tips:
            return []

        lines = [f"Opponent Matchup Guide: How to Play Against and Counter {champ_name} (Weaknesses, Tactics and Matchup Counters):"]

        if weaknesses:
            lines.append(f"  Tactical Weaknesses of Opponent {champ_name}:")
            for w in weaknesses:
                lines.append(f"    - {w}")

        if tactical_tips:
            lines.append(f"  Tactical Tips and Exploits When Facing {champ_name}:")
            for tip in tactical_tips:
                lines.append(f"    - {tip}")

        if enemy_tips:
            lines.append("  Official Tips When Playing Against:")
            for et in enemy_tips[:3]:
                lines.append(f"    - {et}")

        if ally_tips:
            lines.append("  Official Tips When Playing As:")
            for at in ally_tips[:3]:
                lines.append(f"    - {at}")

        if counter_items:
            items_str = ", ".join(counter_items) if isinstance(counter_items, list) else str(counter_items)
            lines.append(f"  Recommended Counter Items Against {champ_name}: {items_str}.")

        if proj_abilities:
            lines.append(f"  Projectile abilities (blocked by Wind Wall): {', '.join(proj_abilities)}.")

        if spell_abilities:
            lines.append(f"  Spellshieldable abilities: {', '.join(spell_abilities)}.")

        if weak_against:
            lines.append(f"  Top Champions that Counter {champ_name} (favorable matchups against {champ_name}):")
            for m in weak_against:
                wr_part = f" (Win rate: {m['winRate']}%)" if m.get("winRate") is not None else ""
                reason = f" — {m.get('reason')}" if m.get("reason") else ""
                lines.append(f"    - {m.get('champion', '?')}{wr_part}{reason}")

        if strong_against:
            lines.append(f"  Champions Countered by {champ_name} (unfavorable matchups against {champ_name}):")
            for m in strong_against:
                wr_part = f" (Win rate: {m['winRate']}%)" if m.get("winRate") is not None else ""
                reason = f" — {m.get('reason')}" if m.get("reason") else ""
                lines.append(f"    - {m.get('champion', '?')}{wr_part}{reason}")

        return [DocumentChunk(
            chunk_id=f"matchup:{champ_key}:counters",
            text="\n".join(lines),
            entity_type="matchup",
            entity_name=champ_name,
            chunk_type="counter",
            metadata={"champion": champ_name, "guide_type": "opponent_counter_guide"},
        )]

    def chunk_synergies(self, champ_key, data):
        """Generate synergy/duo chunks."""
        synergies = data.get("best_duos") or data.get("synergies", data if isinstance(data, list) else [])
        if isinstance(synergies, dict):
            synergies = synergies.get("best_duos") or synergies.get("synergies", [])

        champ_name = data.get("champion", champ_key) if isinstance(data, dict) else champ_key
        lines = [f"{champ_name} best duo partners and synergies:"]
        for duo in (synergies if isinstance(synergies, list) else [])[:5]:
            p_name = duo.get("partner") or duo.get("champion", "?")
            p_role = duo.get("role", "")
            role_str = f" ({p_role})" if p_role else ""
            wr_val = duo.get("win_rate") or duo.get("duo_win_rate") or duo.get("winRate")
            games = duo.get("sample_games") or duo.get("games")
            wr_part = f" (Win rate: {wr_val}% over {games} matches)" if wr_val is not None and games else (f" (Win rate: {wr_val}%)" if wr_val is not None else "")
            tag = f" [{duo.get('synergy_tag')}]" if duo.get("synergy_tag") else ""
            reason = f" — {duo.get('synergy_reason') or duo.get('reason')}" if (duo.get("synergy_reason") or duo.get("reason")) else ""
            lines.append(f"  - {p_name}{role_str}{wr_part}{tag}{reason}")

        best_comps = data.get("best_team_compositions", []) if isinstance(data, dict) else []
        if best_comps:
            top_c = best_comps[0]
            c_name = top_c.get("comp_name") or top_c.get("archetype_name", "Team Lineup")
            lu = top_c.get("lineup", {})
            wr = top_c.get("win_rate")
            lines.append(f"Top 5-Man Team Composition: {c_name} (Top: {lu.get('top')}, Jungle: {lu.get('jungle')}, Mid: {lu.get('mid')}, Bot: {lu.get('bot')}, Support: {lu.get('support')}) - Win Rate: {wr}%.")
            if top_c.get("win_condition"):
                lines.append(f"Win Condition: {top_c.get('win_condition')}")

        if len(lines) <= 1:
            return []

        return [DocumentChunk(
            chunk_id=f"matchup:{champ_key}:synergies",
            text="\n".join(lines),
            entity_type="matchup",
            entity_name=champ_name,
            chunk_type="synergy",
            metadata={"champion": champ_name},
        )]

    def chunk_build(self, champ_key, data):
        """Generate build recommendation chunks."""
        champ_name = data.get("champion", champ_key)
        boots = data.get("boots", "")
        core = data.get("coreItems", data.get("core_items", []))
        full = data.get("fullBuild", data.get("full_build", []))
        start = data.get("startingItems", data.get("starting_items", []))
        spells = data.get("summonerSpells", data.get("summoner_spells", []))
        keystone = data.get("keystone", "")
        p_runes = data.get("primaryRunes", data.get("primary_runes", []))
        s_runes = data.get("secondaryRunes", data.get("secondary_runes", []))

        text = (
            f"Recommended build for {champ_name}: "
            f"Starting items: {', '.join(start) if start else 'N/A'}. "
            f"Boots: {boots or 'N/A'}. "
            f"Core items: {', '.join(core) if core else 'N/A'}. "
            f"Full build: {', '.join(full) if full else 'N/A'}. "
            f"Summoner spells: {', '.join(spells) if spells else 'Flash + ?'}. "
            f"Keystone rune: {keystone or 'N/A'}. "
            f"Primary runes: {', '.join(p_runes) if p_runes else 'N/A'}. "
            f"Secondary runes: {', '.join(s_runes) if s_runes else 'N/A'}."
        )

        return [DocumentChunk(
            chunk_id=f"build:{champ_key}",
            text=text.strip(),
            entity_type="build",
            entity_name=champ_name,
            chunk_type="build",
            metadata={"champion": champ_name, "keystone": keystone},
        )]

    def chunk_team_composition(self, comp_id, data):
        """Generate team composition chunks with both drafting and counter tactics."""
        # Check if champion-centric pro composition
        if data.get("focus_champion") or data.get("lineup"):
            focus_champ = data.get("focus_champion", "")
            comp_name = data.get("comp_name") or data.get("name", comp_id)
            arch = data.get("archetype_name") or data.get("archetype", "Teamfight")
            lu = data.get("lineup", {})
            wr = data.get("win_rate", 0)
            games = data.get("games_played", 0)
            team_syn = data.get("teammate_synergies", {})
            win_cond = data.get("win_condition", "")

            lines = [f"5-Man Team Composition Centered on {focus_champ}: {comp_name}."]
            lines.append(f"Tactical Archetype: {arch} | Win Rate: {wr}% ({games} matches).")
            lines.append(f"Lineup: Top={lu.get('top')}, Jungle={lu.get('jungle')}, Mid={lu.get('mid')}, Bot={lu.get('bot')}, Support={lu.get('support')}.")
            if team_syn:
                lines.append("Role Synergies with Focus Champion:")
                for rk, syn in team_syn.items():
                    lines.append(f"  - {rk.upper()}: {syn}")
            if win_cond:
                lines.append(f"Win Condition and Teamfight Execution: {win_cond}")

            return [DocumentChunk(
                chunk_id=f"composition:{comp_id}",
                text="\n".join(lines),
                entity_type="composition",
                entity_name=focus_champ or comp_name,
                chunk_type="composition",
                metadata={"comp_id": comp_id, "focus_champion": focus_champ, "archetype": data.get("archetype"), "category": "champion_composition"},
            )]

        # General archetype composition
        name = data.get("name", comp_id)
        category = data.get("category", "")
        desc = data.get("description", "")
        weaknesses = data.get("core_weaknesses", [])
        tips = data.get("tactical_tips", [])
        counter_picks = data.get("counter_picks", [])
        counter_items = data.get("counter_items", [])
        sample_champs = data.get("sample_champions", [])

        lines = [f"Team Composition Guide: {name} (Category: {category})."]
        if desc:
            lines.append(f"Strategic Overview: {desc}")
        if sample_champs:
            lines.append(f"Drafting Core Champions: {', '.join(sample_champs[:12])}. These champions form the primary identity, synergy, and power spike foundation for this composition.")
        if weaknesses:
            lines.append("Composition Vulnerabilities and Core Weaknesses:")
            for w in weaknesses:
                lines.append(f"  - {w}")
        if tips:
            lines.append("Tactical Tips When Playing Against this Composition:")
            for t in tips:
                lines.append(f"  - {t}")
        if counter_picks:
            lines.append("Top Counter Picks Against this Composition:")
            for cp in counter_picks[:6]:
                cname = cp.get("champion", "")
                cov = cp.get("archetype_coverage_pct", 0)
                reason = cp.get("tactical_reason", "")
                lines.append(f"  - {cname} ({cov}% coverage against this comp): {reason}")
        if counter_items:
            lines.append("Top Counter Items Against this Composition:")
            for ci in counter_items[:6]:
                iname = ci.get("item", "")
                cov = ci.get("archetype_coverage_pct", 0)
                purpose = ci.get("tactical_purpose", "")
                lines.append(f"  - {iname} ({cov}% coverage): {purpose}")

        text = "\n".join(lines)
        return [DocumentChunk(
            chunk_id=f"composition:{comp_id}",
            text=text.strip(),
            entity_type="composition",
            entity_name=name,
            chunk_type="composition",
            metadata={"comp_id": comp_id, "category": category},
        )]

    def chunk_roles(self, champions):
        """
        Generate authoritative, strategic role-level tactical chunks.
        Provides macro-level answers for questions like:
        - Which support should I pick to counter dive and assassins?
        - Which marksmen are late-game scaling hypercarries?
        - How do tanks operate against poke vs dive?
        """
        chunks = []

        # 1. Support Role Tactical Guide
        support_text = (
            "Support Role Tactical Guide: Archetypes, Drafting and Counter Strategies in League of Legends.\n\n"
            "1. Peel and Disengage Supports (Wardens and Enchanters) — The Ultimate Anti-Dive and Anti-Assassin Picks:\n"
            "   - Key Champions: Janna, Lulu, Braum, Alistar, Taric, Poppy, Milio, Renata Glasc, Tahm Kench, Thresh.\n"
            "   - Tactical Purpose: Specifically picked to counter backline dive, assassins (Zed, Talon, Akali, Katarina, Fizz, Kha'Zix), and aggressive bruisers (Camille, Irelia, Hecarim, Vi, Jarvan IV).\n"
            "   - Key Counter Mechanics:\n"
            "     * Janna: Q (Howling Gale) knocks up diving enemies mid-dash; R (Monsoon) provides massive AOE knockback and health restoration, completely resetting enemy teamfight engages.\n"
            "     * Lulu: W (Polymorph) offers immediate point-and-click disable, rendering diving assassins completely helpless and unable to cast abilities or attack; R (Wild Growth) grants bonus health, an instant knockup, and a slow aura around the protected carry.\n"
            "     * Braum: E (Unbreakable) intercepts and negates incoming projectiles and burst; Passive (Concussive Blows) stuns divers; R (Glacial Fissure) creates a massive knockup and slow zone.\n"
            "     * Alistar: W-Q (Headbutt-Pulverize) knocks away or locks down divers; R (Unbreakable Will) cleanses crowd control and grants immense damage reduction to frontline body-block.\n"
            "     * Taric: E (Dazzle) provides reliable AOE stuns; W armor tether reinforces carry durability; R (Cosmic Radiance) grants team-wide invulnerability against burst rotations.\n"
            "     * Poppy: W (Steadfast Presence) halts all enemy dashes with grounded debuffs, completely shutting down leap/dash engages.\n"
            "   - Essential Anti-Dive Counter Items: Locket of the Iron Solari (AOE shielding against burst), Knight's Vow (redirects carry damage to support), Redemption (AOE heal), Mikael's Blessing (cleanses lethal CC).\n\n"
            "2. Hard Engage and Catcher Supports:\n"
            "   - Key Champions: Leona, Nautilus, Blitzcrank, Pyke, Rell.\n"
            "   - Tactical Purpose: Counter fragile, immobile champions (Lux, Brand, Xerath, Kog'Maw, Jinx) and artillery poke comps through rapid pick creation and lock-down chain crowd control.\n\n"
            "3. Poke and Harass Supports:\n"
            "   - Key Champions: Karma, Lux, Zyra, Brand, Vel'Koz, Senna.\n"
            "   - Tactical Purpose: Counter low-range, immobile melee supports through relentless ranged auto-attack and spell harassment."
        )
        chunks.append(DocumentChunk(
            chunk_id="role:support:tactical_guide",
            text=support_text.strip(),
            entity_type="role",
            entity_name="Support",
            chunk_type="role_guide",
            metadata={"role": "Support", "archetype": "peel_anti_dive_engage"},
        ))

        # 2. Marksman (ADC) Role Tactical Guide
        marksman_text = (
            "Marksman (ADC) Role Tactical Guide: Archetypes, Scaling and Drafting Strategy in League of Legends.\n\n"
            "1. Late-Game Scaling Hypercarries:\n"
            "   - Key Champions: Jinx, Kog'Maw, Vayne, Smolder, Twitch, Tristana, Aphelios, Kai'Sa.\n"
            "   - Tactical Profile: Characterized by exponential attack damage, attack speed, and % maximum health scaling. Excel in late-game front-to-back 5v5 teamfights.\n"
            "   - Ideal Team Composition: Protect the Hypercarry compositions with peel enchanters (Lulu, Janna, Milio) and sturdy frontline wardens/vanguards (Ornn, Braum, Shen, Galio).\n"
            "   - Power Spike: Weak in early laning; reach peak combat dominance at 3+ completed legendary items (Infinity Edge, Lord Dominik's Regards, Runaan's Hurricane).\n\n"
            "2. Early-Game Lane Bullies and Skirmishers:\n"
            "   - Key Champions: Draven, Kalista, Lucian, Miss Fortune, Samira, Caitlyn.\n"
            "   - Tactical Profile: High base attack damage, early burst, and dominant laning pressure. Aim to snowball early tower plates and dragon control.\n\n"
            "3. Utility and Long-Range Marksmen:\n"
            "   - Key Champions: Ashe, Jhin, Varus, Sivir.\n"
            "   - Tactical Profile: Provide long-range pick initiation (Ashe R Enchanted Crystal Arrow, Jhin R Curtain Call, Varus R Chain of Corruption) and teamwide utility."
        )
        chunks.append(DocumentChunk(
            chunk_id="role:marksman:tactical_guide",
            text=marksman_text.strip(),
            entity_type="role",
            entity_name="Marksman",
            chunk_type="role_guide",
            metadata={"role": "Marksman", "archetype": "hypercarry_scaling_bully"},
        ))

        # 3. Tank Role Tactical Guide
        tank_text = (
            "Tank Role Tactical Guide: Archetypes and Defensive Frontline Strategy in League of Legends.\n\n"
            "1. Vanguards (Hard Engage Tanks):\n"
            "   - Key Champions: Malphite, Ornn, Sion, Sejuani, Zac, Amumu, Rell.\n"
            "   - Tactical Purpose: Primary teamfight initiators with massive AOE hard crowd control (Unstoppable Force, Call of the Forge God). Counter squishy, immobile teams and poke compositions by forcing immediate 5v5 teamfights.\n\n"
            "2. Wardens (Defensive and Peel Tanks):\n"
            "   - Key Champions: Braum, Shen, Taric, Poppy, Tahm Kench, K'Sante, Galio.\n"
            "   - Tactical Purpose: Counter dive, assassins, and burst compositions. Excel at standing next to allied hypercarries to absorb damage, intercept projectiles, and peel away diving threats.\n\n"
            "3. Essential Tank Counter Itemization:\n"
            "   - Against Physical/Auto-Attackers: Plated Steelcaps, Frozen Heart, Thornmail, Randuin's Omen.\n"
            "   - Against Magic/Burst: Kaenic Rookern, Hollow Radiance, Force of Nature, Abyssal Mask.\n"
            "   - Team Protection: Locket of the Iron Solari, Knight's Vow."
        )
        chunks.append(DocumentChunk(
            chunk_id="role:tank:tactical_guide",
            text=tank_text.strip(),
            entity_type="role",
            entity_name="Tank",
            chunk_type="role_guide",
            metadata={"role": "Tank", "archetype": "vanguard_warden_anti_dive"},
        ))

        # 4. Assassin Role Tactical Guide
        assassin_text = (
            "Assassin Role Tactical Guide: Archetypes, Threat Profiles and Counterplay in League of Legends.\n\n"
            "1. Assassin Archetypes:\n"
            "   - AD Assassins: Zed, Talon, Kha'Zix, Rengar, Kayn (Shadow Assassin), Naafiri, Qiyana, Pyke.\n"
            "   - AP Assassins: Akali, Katarina, Evelynn, Fizz, Ekko, LeBlanc, Diana.\n"
            "   - Combat Dynamics: Leverage stealth, blinks, and high burst damage rotations to eliminate squishy backline targets (ADCs and Mages) before teamfights develop.\n\n"
            "2. How to Counter Assassins (Team Strategy and Itemization):\n"
            "   - Team Drafting Counter: Pick Peel and Disengage Supports (Lulu with Polymorph, Janna with Monsoon, Braum with Unbreakable) and point-and-click crowd control (Malzahar, Warwick, Lissandra, Vi).\n"
            "   - Positioning Counter: Avoid face-checking fog of war alone; group tightly with frontline tanks and supports.\n"
            "   - Counter Items: Zhonya's Hourglass (invulnerability stalls burst), Sterak's Gage (anti-burst shield), Maw of Malmortius (magic shield), Plated Steelcaps, Death's Dance."
        )
        chunks.append(DocumentChunk(
            chunk_id="role:assassin:tactical_guide",
            text=assassin_text.strip(),
            entity_type="role",
            entity_name="Assassin",
            chunk_type="role_guide",
            metadata={"role": "Assassin", "archetype": "flank_burst_counterplay"},
        ))

        # 5. Mage Role Tactical Guide
        mage_text = (
            "Mage Role Tactical Guide: Archetypes, Control and Scaling in League of Legends.\n\n"
            "1. Mage Class Breakdown:\n"
            "   - Artillery / Long-Range Poke Mages: Xerath, Ziggs, Vel'Koz, Lux. Dominate siege scenarios from extreme distance; fragile to flank dive.\n"
            "   - Burst Mages: Syndra, Veigar, Annie, Vex, Ahri, Zoe. Single-target deletion; countered by spell shields and magic resist.\n"
            "   - Battlemages and Control Mages: Anivia, Cassiopeia, Viktor, Ryze, Aurelion Sol, Swain, Orianna. Zone control and sustained teamfight magic damage.\n\n"
            "2. Counter Tactics:\n"
            "   - Counter Items: Kaenic Rookern, Mercury's Treads, Maw of Malmortius, Banshee's Veil, Force of Nature."
        )
        chunks.append(DocumentChunk(
            chunk_id="role:mage:tactical_guide",
            text=mage_text.strip(),
            entity_type="role",
            entity_name="Mage",
            chunk_type="role_guide",
            metadata={"role": "Mage", "archetype": "artillery_burst_battlemage"},
        ))

        # 6. Fighter (Bruiser) Role Tactical Guide
        fighter_text = (
            "Fighter and Bruiser Role Tactical Guide: Archetypes, Dueling and Splitpushing in League of Legends.\n\n"
            "1. Juggernauts (High Durability, Immobile Melee Titans):\n"
            "   - Key Champions: Darius, Garen, Mordekaiser, Illaoi, Sett, Volibear, Nasus, Urgot.\n"
            "   - Tactical Profile: Overwhelming close-range dueling and sustained damage. Vulnerable to continuous ranged kiting, slows, and perimeter control.\n\n"
            "2. Divers and Skirmishers (Mobile Dualists and Flankers):\n"
            "   - Key Champions: Camille, Irelia, Jax, Fiora, Riven, Hecarim, Vi, Jarvan IV, Renekton, Xin Zhao.\n"
            "   - Tactical Profile: High gap-closing mobility and target access; flank side lanes and dive enemy backlines."
        )
        chunks.append(DocumentChunk(
            chunk_id="role:fighter:tactical_guide",
            text=fighter_text.strip(),
            entity_type="role",
            entity_name="Fighter",
            chunk_type="role_guide",
            metadata={"role": "Fighter", "archetype": "juggernaut_diver_skirmisher"},
        ))

        return chunks

