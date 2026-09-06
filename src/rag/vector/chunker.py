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

    def __init__(self, chunk_id, text, entity_type, entity_name, chunk_type, metadata=None):
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

    def chunk_all(self, champions, items, runes, counters=None, synergies=None, builds=None):
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

        cost_total = cost.get("total", 0) if isinstance(cost, dict) else 0
        cost_sell = cost.get("sell", 0) if isinstance(cost, dict) else 0

        stat_parts = []
        for stat_name, stat_val in stats.items():
            if stat_val and stat_val != 0:
                stat_parts.append(f"{stat_name}: +{stat_val}")

        text = f"Item: {name}. Cost: {cost_total} gold (Sell: {cost_sell} gold)."
        if stat_parts:
            text += f" Stats: {', '.join(stat_parts)}."
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
            metadata={"item_id": str(item_id), "cost_total": cost_total},
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

        if not weak_against and not strong_against and not weaknesses and not tactical_tips:
            return []

        lines = [f"{champ_name} counter matchups & tactical guide:"]

        if weaknesses:
            lines.append("  Tactical Weaknesses:")
            for w in weaknesses:
                lines.append(f"    - {w}")

        if tactical_tips:
            lines.append("  Tactical Tips & Exploits:")
            for tip in tactical_tips:
                lines.append(f"    - {tip}")

        if counter_items:
            items_str = ", ".join(counter_items) if isinstance(counter_items, list) else str(counter_items)
            lines.append(f"  Recommended Counter Items: {items_str}.")

        if weak_against:
            lines.append("  Weak against (countered by):")
            for m in weak_against:
                wr_part = f" (Win rate: {m['winRate']}%)" if m.get("winRate") is not None else ""
                reason = f" — {m.get('reason')}" if m.get("reason") else ""
                lines.append(f"    - {m.get('champion', '?')}{wr_part}{reason}")

        if strong_against:
            lines.append("  Strong against (favorable matchup):")
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
            metadata={"champion": champ_name},
        )]

    def chunk_synergies(self, champ_key, data):
        """Generate synergy/duo chunks."""
        synergies = data.get("synergies", data if isinstance(data, list) else [])
        if isinstance(synergies, dict):
            synergies = synergies.get("synergies", [])

        champ_name = data.get("champion", champ_key) if isinstance(data, dict) else champ_key
        lines = [f"{champ_name} best duo partners & synergies:"]
        for duo in (synergies if isinstance(synergies, list) else [])[:5]:
            wr_val = duo.get("duo_win_rate") or duo.get("winRate")
            wr_part = f" (Duo win rate: {wr_val}%)" if wr_val is not None else ""
            reason = f" — {duo.get('reason')}" if duo.get("reason") else ""
            lines.append(f"  - {duo.get('champion', '?')}{wr_part}{reason}")

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
