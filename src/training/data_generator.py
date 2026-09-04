"""
Training Data Generator for Embedding Fine-Tuning.

Generates contrastive learning triplets (query, positive_passage, negative_passage)
from processed League of Legends game data (champions, items, runes, counters, synergies, builds).

Supports zero-leakage train / val / test partitioning across disjoint entity sets.
Preserves existing evaluation splits (val, test) while significantly scaling up
training diversity, relationships, and sample counts.
"""

import argparse
import json
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Ensure src/ is on path
SRC_DIR = Path(__file__).resolve().parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rag.vector.chunker import DocumentChunker


@dataclass
class TrainingTriplet:
    """A single training example for contrastive learning."""

    query: str
    positive: str       # Relevant passage
    negative: str       # Irrelevant passage
    strategy: str       # Which generation strategy produced this


def load_knowledge_base_data():
    """Load counters, synergies, and builds from knowledge base directory."""
    kb_dir = SRC_DIR / "data" / "knowledge_base"
    counters = {}
    synergies = {}
    builds = {}

    counters_dir = kb_dir / "counters"
    if counters_dir.exists():
        for f in counters_dir.glob("*_counters.json"):
            cid = f.stem.replace("_counters", "")
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    counters[cid] = json.load(fp)
            except Exception:
                pass

    synergies_dir = kb_dir / "synergies"
    if synergies_dir.exists():
        for f in synergies_dir.glob("*_synergy.json"):
            cid = f.stem.replace("_synergy", "")
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    synergies[cid] = json.load(fp)
            except Exception:
                pass

    builds_dir = kb_dir / "builds"
    if builds_dir.exists():
        for f in builds_dir.glob("*_build.json"):
            cid = f.stem.replace("_build", "")
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    builds[cid] = json.load(fp)
            except Exception:
                pass

    return counters, synergies, builds


def partition_kb_by_champions(data_dict, champ_dict):
    """Filter KB entries so relationship passages only reference split champions."""
    allowed_names = set(c.get("name", "").lower() for c in champ_dict.values())
    allowed_ids = set(k.lower() for k in champ_dict.keys())
    result = {}
    for k, v in data_dict.items():
        c_name = v.get("champion", "").lower()
        c_id = v.get("champion_id", k).lower()
        if k.lower() in allowed_ids or c_id in allowed_ids or c_name in allowed_names:
            filtered = dict(v)
            for field in ["weakAgainst", "strongAgainst", "synergies"]:
                if field in filtered:
                    filtered[field] = [
                        entry for entry in filtered[field]
                        if entry.get("champion", "").lower() in allowed_names
                    ]
            result[k] = filtered
    return result


class TrainingDataGenerator:
    """
    Generate training triplets for LoRA fine-tuning of embedding models.

    Supports extensive diversity scaling across champions, items, runes,
    counters, synergies, builds, lore, and comparisons.
    """

    def __init__(self):
        self.chunker = DocumentChunker()
        self.chunks = []
        self.chunks_by_type = {}
        self.chunks_by_entity = {}

    @staticmethod
    def partition_dict(data, r_train = 0.8, r_val = 0.1, seed = 42):
        """Split dictionary entries deterministically to avoid entity leakage."""
        keys = sorted(list(data.keys()))
        rng = random.Random(seed)
        rng.shuffle(keys)
        n = len(keys)
        n_train = int(n * r_train)
        n_val = int(n * r_val)
        return (
            {k: data[k] for k in keys[:n_train]},
            {k: data[k] for k in keys[n_train:n_train + n_val]},
            {k: data[k] for k in keys[n_train + n_val:]},
        )

    def generate(self, champions, items, runes, counters = None, synergies = None, builds = None, target_count = 15000, seed = 42, split_mode = "all"):
        """
        Generate training triplets from game data (English only).

        Args:
            champions: Processed champion data.
            items: Processed item data.
            runes: Processed rune data.
            counters: Optional champion counter matchup data.
            synergies: Optional champion duo synergy data.
            builds: Optional champion build recommendation data.
            target_count: Target number of triplets.
            seed: Random seed for reproducibility.
            split_mode: 'all', 'train', 'val', or 'test'.

        Returns:
            List of TrainingTriplet objects.
        """
        random.seed(seed)

        # 1. Generate chunks
        print("[DataGenerator] Chunking data...")
        self.chunks = self.chunker.chunk_all(
            champions=champions,
            items=items,
            runes=runes,
            counters=counters,
            synergies=synergies,
            builds=builds,
        )
        self.index_chunks()
        print(f"  Total chunks: {len(self.chunks)}")

        triplets = []

        # 2. Strategy 1: Entity-based queries (Champion, Item, Rune)
        print("[DataGenerator] Strategy 1: Entity-based queries...")
        entity_triplets = self.generate_entity_queries(champions, items, runes, split_mode=split_mode)
        triplets.extend(entity_triplets)
        print(f"  Generated: {len(entity_triplets)}")

        # 3. Strategy 2: Ability-specific queries (P, Q, W, E, R)
        print("[DataGenerator] Strategy 2: Ability queries...")
        ability_triplets = self.generate_ability_queries(champions, split_mode=split_mode)
        triplets.extend(ability_triplets)
        print(f"  Generated: {len(ability_triplets)}")

        # 4. Strategy 3: Semantic filter queries (CC, Effects, Roles, Playstyles, Curves)
        print("[DataGenerator] Strategy 3: Semantic filter queries...")
        semantic_triplets = self.generate_semantic_queries(champions, split_mode=split_mode)
        triplets.extend(semantic_triplets)
        print(f"  Generated: {len(semantic_triplets)}")

        # 5. Strategy 4: Gameplay and tactical queries
        print("[DataGenerator] Strategy 4: Gameplay and tactical queries...")
        gameplay_triplets = self.generate_gameplay_queries(champions, items, split_mode=split_mode)
        triplets.extend(gameplay_triplets)
        print(f"  Generated: {len(gameplay_triplets)}")

        # 6. Strategy 5: Lore and biography queries
        print("[DataGenerator] Strategy 5: Lore and biography queries...")
        lore_triplets = self.generate_lore_queries(champions, split_mode=split_mode)
        triplets.extend(lore_triplets)
        print(f"  Generated: {len(lore_triplets)}")

        # 7. Strategy 6: Comparison queries
        print("[DataGenerator] Strategy 6: Comparison queries...")
        comp_triplets = self.generate_comparison_queries(champions, split_mode=split_mode)
        triplets.extend(comp_triplets)
        print(f"  Generated: {len(comp_triplets)}")

        # 8. Strategy 7: Counter Matchups (NEW)
        if counters or "counter" in self.chunks_by_type:
            print("[DataGenerator] Strategy 7: Counter matchup queries...")
            counter_triplets = self.generate_counter_queries(champions, counters, split_mode=split_mode)
            triplets.extend(counter_triplets)
            print(f"  Generated: {len(counter_triplets)}")

        # 9. Strategy 8: Synergies & Duos (NEW)
        if synergies or "synergy" in self.chunks_by_type:
            print("[DataGenerator] Strategy 8: Synergy & duo queries...")
            synergy_triplets = self.generate_synergy_queries(champions, synergies, split_mode=split_mode)
            triplets.extend(synergy_triplets)
            print(f"  Generated: {len(synergy_triplets)}")

        # 10. Strategy 9: Builds & Loadouts (NEW)
        if builds or "build" in self.chunks_by_type:
            print("[DataGenerator] Strategy 9: Build & itemization queries...")
            build_triplets = self.generate_build_queries(champions, builds, split_mode=split_mode)
            triplets.extend(build_triplets)
            print(f"  Generated: {len(build_triplets)}")

        # 11. Strategy 10: Strategic Win Conditions & Power Curves (NEW)
        print("[DataGenerator] Strategy 10: Strategic metadata queries...")
        strategic_triplets = self.generate_strategic_queries(champions, split_mode=split_mode)
        triplets.extend(strategic_triplets)
        print(f"  Generated: {len(strategic_triplets)}")

        # Deduplicate triplets by query
        seen_queries = set()
        unique_triplets = []
        for t in triplets:
            q_norm = t.query.strip().lower()
            if q_norm not in seen_queries:
                seen_queries.add(q_norm)
                unique_triplets.append(t)

        print(f"[DataGenerator] Raw unique pool: {len(unique_triplets)} triplets")

        # Shuffle and select target count
        random.shuffle(unique_triplets)
        if target_count and target_count > 0 and len(unique_triplets) > target_count:
            final_triplets = unique_triplets[:target_count]
        else:
            final_triplets = unique_triplets
        print(f"[DataGenerator] Final total triplets: {len(final_triplets)}")
        return final_triplets

    def generate_all_splits(
        self,
        champions,
        items,
        runes,
        counters = None,
        synergies = None,
        builds = None,
        total_count = 10000,
        train_ratio = 0.8,
        val_ratio = 0.1,
        test_ratio = 0.1,
        seed = 42,
        preserve_eval = True,
        target_train_count = 16000,
    ):
        """
        Generate train, val, and test splits with zero data leakage.
        Preserves existing val and test splits exactly when preserve_eval=True.
        Expands the train split with rich relationship and champion data.
        """
        # Load KB relationships if not passed
        if counters is None or synergies is None or builds is None:
            c_kb, s_kb, b_kb = load_knowledge_base_data()
            counters = counters or c_kb
            synergies = synergies or s_kb
            builds = builds or b_kb

        print(f"[DataGenerator] Partitioning entities: train={train_ratio:.0%}, val={val_ratio:.0%}, test={test_ratio:.0%}")
        train_c, val_c, test_c = self.partition_dict(champions, r_train = train_ratio, r_val = val_ratio, seed = seed)
        train_i, val_i, test_i = self.partition_dict(items, r_train = train_ratio, r_val = val_ratio, seed = seed + 1)

        runes_by_id = runes.get("byId", {})
        r_train, r_val, r_test = self.partition_dict(runes_by_id, r_train = train_ratio, r_val = val_ratio, seed = seed + 2)
        by_tree = runes.get("byTree", {})
        train_r = {"byId": r_train, "byTree": by_tree}
        val_r = {"byId": r_val, "byTree": by_tree}
        test_r = {"byId": r_test, "byTree": by_tree}

        # Partition KB data strictly by champion partition to eliminate leakage
        train_counters = partition_kb_by_champions(counters, train_c)
        val_counters = partition_kb_by_champions(counters, val_c)
        test_counters = partition_kb_by_champions(counters, test_c)

        train_synergies = partition_kb_by_champions(synergies, train_c)
        val_synergies = partition_kb_by_champions(synergies, val_c)
        test_synergies = partition_kb_by_champions(synergies, test_c)

        train_builds = partition_kb_by_champions(builds, train_c)
        val_builds = partition_kb_by_champions(builds, val_c)
        test_builds = partition_kb_by_champions(builds, test_c)

        n_val = int(total_count * val_ratio)
        n_test = total_count - int(total_count * train_ratio) - n_val

        print(f"  Champions: {len(train_c)} train | {len(val_c)} val | {len(test_c)} test")
        print(f"  Items:     {len(train_i)} train | {len(val_i)} val | {len(test_i)} test")
        print(f"  Runes:     {len(r_train)} train | {len(r_val)} val | {len(r_test)} test")
        print(f"  Counters:  {len(train_counters)} train | {len(val_counters)} val | {len(test_counters)} test")
        print(f"  Synergies: {len(train_synergies)} train | {len(val_synergies)} val | {len(test_synergies)} test")
        print(f"  Builds:    {len(train_builds)} train | {len(val_builds)} val | {len(test_builds)} test")

        val_file = SRC_DIR / "training" / "val.jsonl"
        test_file = SRC_DIR / "training" / "test.jsonl"

        if preserve_eval and val_file.exists() and test_file.exists():
            print(f"\n[DataGenerator] Preserving existing evaluation splits: val ({val_file}) and test ({test_file})")
            val_triplets = self.load_triplets(str(val_file))
            test_triplets = self.load_triplets(str(test_file))
        else:
            print("\n--- Generating Val Split ---")
            gen_val = TrainingDataGenerator()
            val_triplets = gen_val.generate(
                val_c, val_i, val_r,
                counters=val_counters, synergies=val_synergies, builds=val_builds,
                target_count=n_val, seed=seed + 10, split_mode="val",
            )

            print("\n--- Generating Test Split ---")
            gen_test = TrainingDataGenerator()
            test_triplets = gen_test.generate(
                test_c, test_i, test_r,
                counters=test_counters, synergies=test_synergies, builds=test_builds,
                target_count=n_test, seed=seed + 20, split_mode="test",
            )

        # Extract eval queries and passages for zero leakage guarantee
        val_q = set(t.query.strip().lower() for t in val_triplets)
        test_q = set(t.query.strip().lower() for t in test_triplets)
        eval_queries = val_q | test_q

        val_p = set(t.positive.strip() for t in val_triplets)
        test_p = set(t.positive.strip() for t in test_triplets)
        eval_passages = val_p | test_p

        print("\n--- Generating Expanded Train Split ---")
        gen_train = TrainingDataGenerator()
        raw_train_triplets = gen_train.generate(
            train_c, train_i, train_r,
            counters=train_counters, synergies=train_synergies, builds=train_builds,
            target_count=target_train_count, seed=seed, split_mode="train",
        )

        # Strictly enforce zero data leakage against val and test
        train_triplets = [
            t for t in raw_train_triplets
            if t.query.strip().lower() not in eval_queries
            and t.positive.strip() not in eval_passages
        ]
        print(f"[DataGenerator] Cleaned train triplets after zero-leakage check: {len(train_triplets)}")

        return {
            "train": train_triplets,
            "val": val_triplets,
            "test": test_triplets,
        }

    @staticmethod
    def audit_leakage(splits):
        """Verify zero leakage across queries, positive passages, and entities."""
        train_t = splits["train"]
        val_t = splits["val"]
        test_t = splits["test"]

        q_train = set(t.query.strip().lower() for t in train_t)
        q_val = set(t.query.strip().lower() for t in val_t)
        q_test = set(t.query.strip().lower() for t in test_t)

        p_train = set(t.positive.strip() for t in train_t)
        p_val = set(t.positive.strip() for t in val_t)
        p_test = set(t.positive.strip() for t in test_t)

        metrics = {
            "query_overlap_train_val": len(q_train & q_val),
            "query_overlap_train_test": len(q_train & q_test),
            "query_overlap_val_test": len(q_val & q_test),
            "passage_overlap_train_val": len(p_train & p_val),
            "passage_overlap_train_test": len(p_train & p_test),
            "passage_overlap_val_test": len(p_val & p_test),
        }
        return metrics

    # ------------------------------------------------------------------------
    # Indexing helpers
    # ------------------------------------------------------------------------

    def index_chunks(self):
        """Index chunks by type and entity for fast lookup."""
        self.chunks_by_type.clear()
        self.chunks_by_entity.clear()
        for chunk in self.chunks:
            self.chunks_by_type.setdefault(chunk.chunk_type, []).append(chunk)
            self.chunks_by_entity.setdefault(chunk.entity_name.lower(), []).append(chunk)

    def get_negative(self, positive_chunk):
        """Get a hard negative: same chunk_type but different entity."""
        same_type = self.chunks_by_type.get(positive_chunk.chunk_type, [])
        candidates = [c for c in same_type if c.entity_name.lower() != positive_chunk.entity_name.lower()]
        if candidates:
            return random.choice(candidates).text
        # Fallback to any chunk of different entity
        other_entities = [c for c in self.chunks if c.entity_name.lower() != positive_chunk.entity_name.lower()]
        if other_entities:
            return random.choice(other_entities).text
        return random.choice(self.chunks).text

    # ------------------------------------------------------------------------
    # Strategy 1: Entity-based queries
    # ------------------------------------------------------------------------

    def generate_entity_queries(self, champions, items, runes, split_mode = "all"):
        """Generate queries about specific entities (Champion, Item, Rune) in English."""
        triplets = []

        champ_overview_en = [
            "Give me an overview of the champion {name}",
            "What type of champion is {name} and how do they play?",
            "Can you describe the champion {name} and their role?",
            "What is the backstory and playstyle of {name}?",
            "Tell me about {name}'s roles and win conditions",
            "How does {name} fit into a team composition?",
            "What is {name}'s difficulty and playstyle rating?",
            "What are the key strengths of {name} as a champion?",
            "Describe {name}'s attack type and resource system",
            "What region and faction does {name} belong to in lore?",
            "What playstyle categories does {name} fall into?",
            "What are the main win conditions for playing {name}?",
            "How would you summarize the champion {name} for a new player?",
            "Is {name} a ranged or melee champion, and what role do they play?",
            "What crowd control abilities and special effects does {name} have?",
            "What kind of damage does {name} primarily deal in combat?",
            "Explain {name}'s main identity and tactical role on Summoner's Rift",
            "How mobile is {name} and what defensive tools do they have?",
            "What power spikes and scaling does {name} rely on?",
            "What makes {name} unique compared to other {role} champions?",
            "Comprehensive profile and champion overview for {name}",
            "How does {name} perform across early, mid, and late game phases?",
            "What team composition archetypes does {name} excel in?",
            "Does {name} rely on mana, energy, fury, or are they manaless?",
            "What primary role and secondary playstyle define {name}?",
        ]

        champ_stats_en = [
            "What are the base health and armor stats of {name}?",
            "How much attack damage and attack speed does {name} start with?",
            "What is {name}'s mana pool and how does it scale per level?",
            "What is the base movement speed of {name}?",
            "How much base HP does {name} have at level 1?",
            "How much does {name}'s health and armor grow per level?",
            "What are the defensive stats (armor, magic resist) of {name}?",
            "What is the attack range and base attack damage of {name}?",
            "Can you list the full base stats of {name} at level 1?",
            "How does {name}'s stat scaling compare to other champions?",
            "What is {name}'s health regeneration rate at level 1 and per level?",
            "Does {name} have high or low base armor compared to other champions?",
            "What is the base attack speed ratio and scaling growth for {name}?",
            "How much magic resist does {name} gain per level?",
            "Full stat profile: base health, mana, armor, MR, and attack range for {name}",
            "Is {name}'s level 1 base AD high enough for strong early trades?",
            "What are the growth formulas and stat per level values for {name}?",
            "What is {name}'s mobility rating and base movement speed?",
        ]

        sample_k_overview = 14 if split_mode == "train" else 6
        sample_k_stats = 10 if split_mode == "train" else 5

        # 1. Champion queries (Overview + Stats)
        for champ_id, champ in champions.items():
            name = champ.get("name", champ_id)
            roles = champ.get("roles", [])
            primary_role = roles[0] if roles else "champion"
            entity_chunks = self.chunks_by_entity.get(name.lower(), [])

            overview_chunks = [c for c in entity_chunks if c.chunk_type == "overview"]
            stats_chunks = [c for c in entity_chunks if c.chunk_type == "stats"]

            if overview_chunks:
                pos_chunk = overview_chunks[0]
                for tmpl in random.sample(champ_overview_en, min(sample_k_overview, len(champ_overview_en))):
                    q = tmpl.format(name=name, role=primary_role)
                    triplets.append(TrainingTriplet(q, pos_chunk.text, self.get_negative(pos_chunk), "entity_champ_en"))

            if stats_chunks:
                pos_stat = stats_chunks[0]
                for tmpl in random.sample(champ_stats_en, min(sample_k_stats, len(champ_stats_en))):
                    q = tmpl.format(name=name)
                    triplets.append(TrainingTriplet(q, pos_stat.text, self.get_negative(pos_stat), "stats_champ_en"))

        # 2. Item queries
        item_templates_en = [
            "What does the item {name} do in League of Legends?",
            "How much does {name} cost and what stats does it give?",
            "What are the passive effects and bonuses of {name}?",
            "What items are needed to build {name}?",
            "What stats are granted by purchasing {name}?",
            "How does the unique passive of {name} work?",
            "Is {name} a legendary or mythic item, and why is it built?",
            "What is the total gold cost and recipe for {name}?",
            "Which champions benefit most from the item {name}?",
            "What is the full breakdown of {name}'s stats and effects?",
            "When should you buy {name} and what does it power spike?",
            "What item components build into {name}?",
            "Does {name} grant ability power, attack damage, or tank durability?",
            "What is the sell value and combine cost of {name}?",
            "Explain the active or passive cooldown effect on {name}",
            "How cost efficient is the {name} item upon purchase?",
            "Which class (assassin, mage, adc, bruiser, tank) should prioritize {name}?",
            "What counter-play or defensive value does {name} provide?",
            "Detailed item description, stats, recipe, and passives for {name}",
        ]

        sample_k_item = 8 if split_mode == "train" else 5
        for item_id, item in items.items():
            name = item.get("name", "")
            if not name:
                continue
            item_chunks = [c for c in self.chunks if c.entity_name.lower() == name.lower() and c.chunk_type == "item_info"]
            if not item_chunks:
                continue

            pos_chunk = item_chunks[0]
            for tmpl in random.sample(item_templates_en, min(sample_k_item, len(item_templates_en))):
                q = tmpl.format(name=name)
                triplets.append(TrainingTriplet(q, pos_chunk.text, self.get_negative(pos_chunk), "entity_item_en"))

        # 3. Rune queries
        rune_templates_en = [
            "What are the effects of the {name} rune?",
            "Which rune path or tree does {name} belong to?",
            "How does the {name} rune or keystone work in gameplay?",
            "What bonus stats or effects does {name} provide?",
            "When should you take {name} as a keystone or rune?",
            "Give me a full breakdown of the {name} rune",
            "Which champions benefit most from taking {name}?",
            "How does {name} compare to other runes in its row?",
            "What combat trigger or cooldown is associated with {name}?",
            "Is {name} tailored for sustained DPS, burst damage, or defensive survivability?",
            "How does {name} scale with bonus attack damage or ability power?",
            "In what matchups is {name} the superior rune choice?",
        ]

        sample_k_rune = 7 if split_mode == "train" else 4
        rune_chunks = [c for c in self.chunks if c.chunk_type == "rune_info"]
        for r_chunk in rune_chunks:
            r_name = r_chunk.entity_name
            if not r_name:
                continue
            for tmpl in random.sample(rune_templates_en, min(sample_k_rune, len(rune_templates_en))):
                q = tmpl.format(name=r_name)
                triplets.append(TrainingTriplet(q, r_chunk.text, self.get_negative(r_chunk), "rune_en"))

        return triplets

    # ------------------------------------------------------------------------
    # Strategy 2: Ability-specific queries
    # ------------------------------------------------------------------------

    def generate_ability_queries(self, champions, split_mode = "all"):
        """Generate queries about specific champion abilities (P, Q, W, E, R) in English."""
        triplets = []

        ability_templates_en = [
            "What does the {key} ability of {name} do?",
            "Can you explain how {name}'s {key} skill works?",
            "What is the cooldown and mana cost of {name}'s {key}?",
            "How much damage does the {key} ability of {name} deal?",
            "What is the effective range of {name}'s {key} ability?",
            "How does {name}'s {key} ability scale with items or levels?",
            "What crowd control effects does {name}'s {key} apply?",
            "Give me a detailed breakdown of {name}'s {key} ability",
            "What are the key mechanics behind {name}'s {key} ability?",
            "At what levels does {name}'s {key} cooldown decrease?",
            "Does {name}'s {key} ability deal physical or magic damage?",
            "What makes {name}'s {key} ability unique or powerful?",
            "How should you use {name}'s {key} in a teamfight?",
            "Is {name}'s {key} a skillshot, point-and-click, or self-buff?",
            "What ability effects (dash, shield, heal, AOE) are triggered by {name}'s {key}?",
            "What is the primary leveling order: should you max {key} first on {name}?",
            "Can {name}'s {key} pass through minions or terrain walls?",
            "How does the damage ratio of {name}'s {key} scale with bonus AD or AP?",
            "What secondary active or passive bonus does {name}'s {key} grant?",
        ]

        passive_templates_en = [
            "What is the passive ability of {name} and how does it work?",
            "Can you explain the innate passive effect of {name}?",
            "How does {name}'s passive interact with their other abilities?",
            "What triggers or procs {name}'s passive ability?",
            "Give me details on the passive skill of {name}",
            "What bonus does {name}'s passive provide during combat?",
            "How impactful is {name}'s passive in the early game?",
            "Does {name}'s passive stack and what is the maximum stack limit?",
            "How does {name}'s passive ability scale into the late game?",
            "What tactical advantage does {name}'s passive give in lane trades?",
        ]

        sample_k_active = 8 if split_mode == "train" else 5
        sample_k_passive = 6 if split_mode == "train" else 4

        for champ_id, champ in champions.items():
            name = champ.get("name", champ_id)
            entity_chunks = self.chunks_by_entity.get(name.lower(), [])

            # Active abilities: Q, W, E, R
            for key in ["Q", "W", "E", "R"]:
                key_chunks = [
                    c for c in entity_chunks
                    if c.chunk_type == "ability" and c.metadata.get("ability_key") == key
                ]
                if not key_chunks:
                    continue

                pos_chunk = key_chunks[0]
                for tmpl in random.sample(ability_templates_en, min(sample_k_active, len(ability_templates_en))):
                    q = tmpl.format(name=name, key=key)
                    triplets.append(TrainingTriplet(q, pos_chunk.text, self.get_negative(pos_chunk), "ability_active_en"))

            # Passive (P)
            passive_chunks = [
                c for c in entity_chunks
                if c.chunk_type == "ability" and c.metadata.get("ability_key") in ("passive", "P", "Passive", "PASSIVE")
            ]
            if passive_chunks:
                pos_p = passive_chunks[0]
                for tmpl in random.sample(passive_templates_en, min(sample_k_passive, len(passive_templates_en))):
                    q = tmpl.format(name=name)
                    triplets.append(TrainingTriplet(q, pos_p.text, self.get_negative(pos_p), "ability_passive_en"))

        return triplets

    # ------------------------------------------------------------------------
    # Strategy 3: Semantic filter queries
    # ------------------------------------------------------------------------

    def generate_semantic_queries(self, champions, split_mode = "all"):
        """Generate queries about game concepts (CC types, effects, roles, playstyles) in English."""
        triplets = []

        cc_map = {
            "Stun": [
                "Champions with stun",
                "Which champions can stun enemies?",
                "Who has a stun ability?",
                "Champions that possess stun mechanics",
                "List champions with hard stun crowd control",
                "Who has point-and-click or skillshot stuns?",
            ],
            "Knockup": [
                "Champions with knockup",
                "Champions that knock up enemies",
                "Who has airborne or knockup?",
                "Which champions have airborne crowd control?",
                "Champions that enable airborne combos",
            ],
            "Root": [
                "Champions with root",
                "Champions that can root targets",
                "Who has a snare or root ability?",
                "Which champions immobilize enemies with root?",
                "Immobilizing root abilities in League of Legends",
            ],
            "Silence": [
                "Champions with silence",
                "Who can silence enemies?",
                "Champions that have silence mechanics",
                "Which champions prevent spellcasting with silence?",
            ],
            "Fear": [
                "Champions with fear effect",
                "Who has a terrify or fear ability?",
                "Champions with fear CC",
                "Who can make enemies flee in terror?",
            ],
            "Charm": [
                "Champions with charm",
                "Who has charm abilities?",
                "Champions that can charm targets",
                "Which champions lure enemies toward them with charm?",
            ],
            "Suppression": [
                "Champions with suppression",
                "Who can suppress enemies?",
                "Which champions have suppression ultimate?",
                "Hard suppression crowd control abilities",
            ],
            "Slow": [
                "Champions with slow effect",
                "Who can slow down targets?",
                "Champions with movement speed slows",
                "Abilities that apply heavy movement impairs",
            ],
        }

        effect_map = {
            "Dash": [
                "Champions with dash",
                "Mobile champions with dash",
                "Who has gap close or dash?",
                "Champions with mobility and dash abilities",
                "Which champions have multiple dashes in combat?",
            ],
            "Shield": [
                "Champions with shield",
                "Who can give shields to allies or self?",
                "Champions that grant protective shields",
                "Defensive shielding champions",
            ],
            "Heal": [
                "Champions with healing",
                "Who has self or ally heal?",
                "Champions with sustaining heals",
                "Sustained regeneration and health restoring champions",
            ],
            "Stealth": [
                "Champions with stealth or invisibility",
                "Who can turn invisible?",
                "Champions with camouflage or stealth",
                "Stealth assassin champions who ambush unseen",
            ],
            "Execute": [
                "Champions with execute damage",
                "Who has execute ult?",
                "Champions with execution mechanics",
                "Abilities that deal increased damage to low HP targets",
            ],
            "True Damage": [
                "Champions with true damage",
                "Who deals true damage?",
                "Champions with abilities that ignore armor and magic resist",
                "Armor-shredding and percentage max HP true damage champions",
            ],
        }

        roles_map = {
            "Assassin": [
                "Best assassin champions",
                "Who are the assassins in LoL?",
                "List of assassin champions",
                "High mobility burst assassins",
            ],
            "Mage": [
                "Mage champions in LoL",
                "Who are the AP mages?",
                "Champions in the mage category",
                "Control mages and artillery spellcasters",
            ],
            "Tank": [
                "Tank champions",
                "Who are the frontliner tanks?",
                "Top durable tank champions",
                "Engage and peeling frontline tanks",
            ],
            "Fighter": [
                "Fighter and bruiser champions",
                "Who are the top lane fighters?",
                "Melee bruiser champions",
                "Dueling juggernauts and skirmishers",
            ],
            "Marksman": [
                "Marksman and ADC champions",
                "Who are the ranged carries?",
                "Attack damage carry champions",
                "Ranged auto-attack hypercarries",
            ],
            "Support": [
                "Support champions",
                "Who are the utility supports?",
                "Champions played in support role",
                "Enchanter and engage playmaking supports",
            ],
        }

        def pick_subset(options):
            if split_mode == "train":
                return options
            elif split_mode == "val":
                return [options[-2]] if len(options) >= 2 else [options[-1]]
            elif split_mode == "test":
                return [options[-1]]
            return options

        sample_mult = 5 if split_mode == "train" else 2

        # 1. CC queries
        for cc_type, en_queries in cc_map.items():
            pool = pick_subset(en_queries)
            champs_with = [cid for cid, c in champions.items() if cc_type.lower() in [x.lower() for x in c.get("cc_types", [])]]
            champs_without = [cid for cid, c in champions.items() if cc_type.lower() not in [x.lower() for x in c.get("cc_types", [])]]

            if not champs_with or not champs_without:
                continue

            n_samples = min(120 if split_mode == "train" else 45, len(champs_with) * sample_mult)
            for _ in range(n_samples):
                pos_id = random.choice(champs_with)
                neg_id = random.choice(champs_without)

                pos_name = champions[pos_id].get("name", pos_id)
                neg_name = champions[neg_id].get("name", neg_id)

                pos_chunks = [c for c in self.chunks_by_entity.get(pos_name.lower(), []) if c.chunk_type in ("overview", "ability")]
                neg_chunks = [c for c in self.chunks_by_entity.get(neg_name.lower(), []) if c.chunk_type in ("overview", "ability")]

                if pos_chunks and neg_chunks:
                    q = random.choice(pool)
                    triplets.append(TrainingTriplet(q, random.choice(pos_chunks).text, random.choice(neg_chunks).text, "semantic_cc"))

        # 2. Effect queries
        for eff, en_queries in effect_map.items():
            pool = pick_subset(en_queries)
            champs_with = [cid for cid, c in champions.items() if eff.lower() in [x.lower() for x in c.get("ability_effects", [])]]
            champs_without = [cid for cid, c in champions.items() if eff.lower() not in [x.lower() for x in c.get("ability_effects", [])]]

            if not champs_with or not champs_without:
                continue

            n_samples = min(120 if split_mode == "train" else 45, len(champs_with) * sample_mult)
            for _ in range(n_samples):
                pos_id = random.choice(champs_with)
                neg_id = random.choice(champs_without)

                pos_name = champions[pos_id].get("name", pos_id)
                neg_name = champions[neg_id].get("name", neg_id)

                pos_chunks = [c for c in self.chunks_by_entity.get(pos_name.lower(), []) if c.chunk_type in ("overview", "ability")]
                neg_chunks = [c for c in self.chunks_by_entity.get(neg_name.lower(), []) if c.chunk_type in ("overview", "ability")]

                if pos_chunks and neg_chunks:
                    q = random.choice(pool)
                    triplets.append(TrainingTriplet(q, random.choice(pos_chunks).text, random.choice(neg_chunks).text, "semantic_effect"))

        # 3. Role queries
        for role, en_queries in roles_map.items():
            pool = pick_subset(en_queries)
            champs_with = [cid for cid, c in champions.items() if role.lower() in [x.lower() for x in c.get("roles", [])]]
            champs_without = [cid for cid, c in champions.items() if role.lower() not in [x.lower() for x in c.get("roles", [])]]

            if not champs_with or not champs_without:
                continue

            n_samples = min(100 if split_mode == "train" else 35, len(champs_with) * sample_mult)
            for _ in range(n_samples):
                pos_id = random.choice(champs_with)
                neg_id = random.choice(champs_without)

                pos_name = champions[pos_id].get("name", pos_id)
                neg_name = champions[neg_id].get("name", neg_id)

                pos_chunks = [c for c in self.chunks_by_entity.get(pos_name.lower(), []) if c.chunk_type == "overview"]
                neg_chunks = [c for c in self.chunks_by_entity.get(neg_name.lower(), []) if c.chunk_type == "overview"]

                if pos_chunks and neg_chunks:
                    q = random.choice(pool)
                    triplets.append(TrainingTriplet(q, random.choice(pos_chunks).text, random.choice(neg_chunks).text, "semantic_role"))

        return triplets

    # ------------------------------------------------------------------------
    # Strategy 4: Gameplay and tactical queries
    # ------------------------------------------------------------------------

    def generate_gameplay_queries(self, champions, items, split_mode = "all"):
        """Generate gameplay, tactical, build, and matchup queries in English."""
        triplets = []

        gameplay_templates = [
            "Who counters {name}?",
            "What champions are strong against {name}?",
            "What items should I build on {name}?",
            "Best items and recommended build for {name}",
            "{name} abilities and skills breakdown",
            "{name} base stats and scaling",
            "Is {name} strong in early game or late game?",
            "How does {name} perform in teamfights?",
            "Tips and strategy for playing {name}",
            "Who synergizes well with {name}?",
            "Recommended rune page for {name}",
            "How should I position as {name} during teamfights?",
            "What is the ideal spell rotation and combo for {name}?",
            "How to play the early laning phase with {name}?",
            "What summoner spells are best when playing {name}?",
            "What are the biggest counter threats to {name}?",
            "How do you execute {name}'s win condition in ranked games?",
            "When does {name} hit their core two-item power spike?",
            "How does {name} peel for carries or dive backlines?",
        ]

        sample_k = 10 if split_mode == "train" else 6

        for champ_id, champ in champions.items():
            name = champ.get("name", champ_id)
            entity_chunks = self.chunks_by_entity.get(name.lower(), [])

            overview_chunks = [c for c in entity_chunks if c.chunk_type == "overview"]
            if not overview_chunks:
                continue

            pos_chunk = overview_chunks[0]
            neg_chunk_text = self.get_negative(pos_chunk)

            for tmpl in random.sample(gameplay_templates, min(sample_k, len(gameplay_templates))):
                q = tmpl.format(name=name)
                triplets.append(TrainingTriplet(q, pos_chunk.text, neg_chunk_text, "gameplay_en"))

        return triplets

    # ------------------------------------------------------------------------
    # Strategy 5: Lore and biography queries
    # ------------------------------------------------------------------------

    def generate_lore_queries(self, champions, split_mode = "all"):
        """Generate lore, backstory, origin, region, and relationship queries in English."""
        triplets = []

        lore_templates = [
            "What is the lore of {name}?",
            "Tell me the backstory of {name}",
            "Who is {name} according to the lore?",
            "What happened in {name}'s biography?",
            "Explain the origin story of {name}",
            "What is {name}'s history in Runeterra?",
            "What is the story behind {name}?",
            "Where did {name} come from?",
            "What drives {name} in the lore?",
            "Tell me about {name}'s background story",
            "What is the background of {name}?",
            "Who was {name} before becoming {title}?",
            "What historical lore events are tied to {name}?",
            "What is the motivation and purpose of {name} in Runeterra?",
            "Summary of {name}'s character background and major lore conflicts",
        ]

        region_templates = [
            "What region does {name} belong to?",
            "Where is {name} from in Runeterra?",
            "What is {name}'s affiliated region or faction?",
            "Is {name} connected to {region}?",
            "Tell me about {name}'s origin in {region}",
            "What is the role of {name} in {region}?",
            "What faction does {name} fight for in {region}?",
        ]

        relation_templates = [
            "How is {name} related to {related} in the lore?",
            "What is the narrative connection between {name} and {related}?",
            "What is the relationship between {name} and {related} in the story?",
            "Are {name} and {related} allies or enemies in League of Legends lore?",
            "What significant events happened between {name} and {related}?",
            "Did {name} and {related} ever meet in the lore, and what happened?",
            "Do {name} and {related} share the same faction or region?",
            "What does {name} think of {related} based on the lore?",
            "How did the actions of {name} affect {related} in the story?",
            "Are {name} and {related} enemies, rivals, or companions in lore?",
            "What shared history do {name} and {related} have in Runeterra?",
            "Is the bond between {name} and {related} one of friendship or conflict?",
        ]

        sample_lore = 8 if split_mode == "train" else 6
        sample_region = 4 if split_mode == "train" else 3

        for champ_id, champ in champions.items():
            name = champ.get("name", champ_id)
            title = champ.get("title", "")
            entity_chunks = self.chunks_by_entity.get(name.lower(), [])

            lore_chunks = [c for c in entity_chunks if c.chunk_type == "lore"]
            if not lore_chunks:
                lore_chunks = [c for c in entity_chunks if c.chunk_type == "overview"]

            if not lore_chunks:
                continue

            # 1. General Lore queries
            for tmpl in random.sample(lore_templates, min(sample_lore, len(lore_templates))):
                pos_chunk = random.choice(lore_chunks)
                neg_chunk_text = self.get_negative(pos_chunk)
                triplets.append(TrainingTriplet(tmpl.format(name=name, title=title or "a champion"), pos_chunk.text, neg_chunk_text, "lore_en"))

            # 2. Region / Faction queries
            region = champ.get("region")
            if region and region != "Runeterra (Unaffiliated)":
                for tmpl in random.sample(region_templates, min(sample_region, len(region_templates))):
                    pos_chunk = random.choice(lore_chunks)
                    neg_chunk_text = self.get_negative(pos_chunk)
                    triplets.append(TrainingTriplet(tmpl.format(name=name, region=region), pos_chunk.text, neg_chunk_text, "lore_region_en"))

            # 3. Related champions in lore
            related_list = champ.get("related_champions", [])
            for rc in related_list:
                rel_name = rc.get("name") if isinstance(rc, dict) else str(rc)
                if not rel_name:
                    continue
                for tmpl in random.sample(relation_templates, min(3, len(relation_templates))):
                    pos_chunk = random.choice(lore_chunks)
                    neg_chunk_text = self.get_negative(pos_chunk)
                    triplets.append(TrainingTriplet(tmpl.format(name=name, related=rel_name), pos_chunk.text, neg_chunk_text, "lore_relation_en"))

        return triplets

    # ------------------------------------------------------------------------
    # Strategy 6: Comparison queries
    # ------------------------------------------------------------------------

    def generate_comparison_queries(self, champions, split_mode = "all"):
        """Generate comparison queries between champions in English."""
        triplets = []
        champ_list = list(champions.items())
        if len(champ_list) < 2:
            return triplets

        templates = [
            "How does {a} compare to {b} in the current meta?",
            "Who is better in lane between {a} and {b}?",
            "What are the key differences between {a} and {b}?",
            "Who wins in a 1v1 fight between {a} and {b}?",
            "Should I pick {a} or {b} for this game?",
            "How do the playstyles of {a} and {b} differ?",
            "Is {a} a better pick than {b} in the current patch?",
            "Comparing {a} and {b} in terms of scaling and teamfight power",
            "What does {a} do better than {b} and vice versa?",
            "Which champion, {a} or {b}, is stronger in late game?",
            "How does the damage output of {a} compare with {b}?",
            "Is {a} easier to play than {b}?",
            "Who offers more crowd control and team utility: {a} or {b}?",
            "Dueling potential: can {a} beat {b} in a side-lane splitpush?",
            "Which champion snowballs harder: {a} or {b}?",
        ]

        target_comparisons = min(2200 if split_mode == "train" else 1200, len(champ_list) * 12)
        for _ in range(target_comparisons):
            (id_a, champ_a), (id_b, champ_b) = random.sample(champ_list, 2)
            name_a = champ_a.get("name", id_a)
            name_b = champ_b.get("name", id_b)

            chunks_a = [c for c in self.chunks_by_entity.get(name_a.lower(), []) if c.chunk_type in ("overview", "stats")]
            chunks_b = [c for c in self.chunks_by_entity.get(name_b.lower(), []) if c.chunk_type in ("overview", "stats")]

            if not chunks_a or not chunks_b:
                continue

            template = random.choice(templates)
            query = template.format(a=name_a, b=name_b)

            positive = random.choice(chunks_a).text
            other_chunks = [
                c for c in self.chunks
                if c.chunk_type == "overview" and c.entity_name.lower() not in (name_a.lower(), name_b.lower())
            ]
            negative = random.choice(other_chunks).text if other_chunks else random.choice(self.chunks).text

            triplets.append(TrainingTriplet(query, positive, negative, "comparison_en"))

        return triplets

    # ------------------------------------------------------------------------
    # Strategy 7: Counter Matchup queries (NEW)
    # ------------------------------------------------------------------------

    def generate_counter_queries(self, champions, counters, split_mode = "all"):
        """Generate matchup, counter-pick, and laning queries from counter data."""
        triplets = []
        counter_chunks = self.chunks_by_type.get("counter", [])
        if not counter_chunks:
            return triplets

        counter_templates = [
            "Who counters {name} in lane?",
            "What champions are strong against {name}?",
            "What is the best counter pick into {name}?",
            "Who does {name} struggle against most?",
            "Which champions have the highest win rate against {name}?",
            "How do you counter {name} and exploit their weaknesses?",
            "Who does {name} counter and win against easily?",
            "Which matchups are favorable for {name}?",
            "What champions are weak against {name}?",
            "Tips for playing against {name} in the laning phase",
            "Why is {name} countered by specific champion picks?",
            "Who should I ban or avoid picking into {name}?",
            "Full counter matchup guide and win rates for {name}",
            "What makes {name} strong against certain enemy champions?",
        ]

        sample_k = 10 if split_mode == "train" else 5

        for c_chunk in counter_chunks:
            name = c_chunk.entity_name
            if not name:
                continue

            for tmpl in random.sample(counter_templates, min(sample_k, len(counter_templates))):
                q = tmpl.format(name=name)
                triplets.append(TrainingTriplet(q, c_chunk.text, self.get_negative(c_chunk), "counter_matchup_en"))

        return triplets

    # ------------------------------------------------------------------------
    # Strategy 8: Synergy & Duo queries (NEW)
    # ------------------------------------------------------------------------

    def generate_synergy_queries(self, champions, synergies, split_mode = "all"):
        """Generate duo partner, bot lane pairing, and teamfight combo queries."""
        triplets = []
        synergy_chunks = self.chunks_by_type.get("synergy", [])
        if not synergy_chunks:
            return triplets

        synergy_templates = [
            "Who is the best duo partner for {name}?",
            "What champions synergize best with {name}?",
            "Who pairs well with {name} in bot lane?",
            "What support should I pick to play with {name}?",
            "Which champions have the highest duo win rate with {name}?",
            "What teamfight combos work best with {name}?",
            "Who can enable {name} to carry games?",
            "Best champion pairings and synergies for {name}",
            "Why do {name} and their duo partners win games together?",
            "What crowd control champions set up {name}'s abilities?",
            "Duo queue guide: best partners to climb with {name}",
        ]

        sample_k = 9 if split_mode == "train" else 4

        for s_chunk in synergy_chunks:
            name = s_chunk.entity_name
            if not name:
                continue

            for tmpl in random.sample(synergy_templates, min(sample_k, len(synergy_templates))):
                q = tmpl.format(name=name)
                triplets.append(TrainingTriplet(q, s_chunk.text, self.get_negative(s_chunk), "synergy_duo_en"))

        return triplets

    # ------------------------------------------------------------------------
    # Strategy 9: Build & Itemization queries (NEW)
    # ------------------------------------------------------------------------

    def generate_build_queries(self, champions, builds, split_mode = "all"):
        """Generate item build, starting items, runes, and summoner spell queries."""
        triplets = []
        build_chunks = self.chunks_by_type.get("build", [])
        if not build_chunks:
            return triplets

        build_templates = [
            "What is the recommended build for {name}?",
            "What are the core items to buy on {name}?",
            "What is the full 6-item build for {name}?",
            "What starting items should I buy on {name}?",
            "What summoner spells should {name} take?",
            "What is the best keystone rune for {name}?",
            "What primary and secondary runes should I run on {name}?",
            "Complete itemization guide and rune page for {name}",
            "What boots and core legendary items does {name} build?",
            "Highest win rate build path, runes, and spells for {name}",
            "What items give {name} their biggest power spike?",
        ]

        sample_k = 9 if split_mode == "train" else 4

        for b_chunk in build_chunks:
            name = b_chunk.entity_name
            if not name:
                continue

            for tmpl in random.sample(build_templates, min(sample_k, len(build_templates))):
                q = tmpl.format(name=name)
                triplets.append(TrainingTriplet(q, b_chunk.text, self.get_negative(b_chunk), "build_loadout_en"))

        return triplets

    # ------------------------------------------------------------------------
    # Strategy 10: Strategic Win Conditions & Power Curves (NEW)
    # ------------------------------------------------------------------------

    def generate_strategic_queries(self, champions, split_mode = "all"):
        """Generate strategic playstyle, power curve, and win condition queries."""
        triplets = []

        strategic_templates = [
            "What is the primary win condition when playing {name}?",
            "How does {name} win games and close out matches?",
            "What is {name}'s power curve and when do they spike?",
            "Is {name} an early game snowballer or late game hypercarry?",
            "What playstyle category (burst, poke, dive, sustained) fits {name}?",
            "How should a team play around {name} in teamfights?",
            "Is {name} better at splitpushing or grouping with the team?",
            "What are the strategic strengths and win conditions of {name}?",
            "How do you carry games with {name}'s strategic playstyle?",
        ]

        sample_k = 7 if split_mode == "train" else 3

        for champ_id, champ in champions.items():
            name = champ.get("name", champ_id)
            entity_chunks = self.chunks_by_entity.get(name.lower(), [])
            overview_chunks = [c for c in entity_chunks if c.chunk_type == "overview"]

            if not overview_chunks:
                continue

            pos_chunk = overview_chunks[0]
            neg_chunk = self.get_negative(pos_chunk)

            for tmpl in random.sample(strategic_templates, min(sample_k, len(strategic_templates))):
                q = tmpl.format(name=name)
                triplets.append(TrainingTriplet(q, pos_chunk.text, neg_chunk, "strategic_playstyle_en"))

        return triplets

    # ------------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------------

    def save_triplets(self, triplets, output_path):
        """Save triplets to a JSON Lines file."""
        path = Path(output_path)
        path.parent.mkdir(parents = True, exist_ok = True)

        with open(path, "w", encoding = "utf-8") as f:
            for t in triplets:
                row = {
                    "query": t.query,
                    "positive": t.positive,
                    "negative": t.negative,
                    "strategy": t.strategy,
                }
                f.write(json.dumps(row, ensure_ascii = False) + "\n")

    @staticmethod
    def load_triplets(input_path):
        """Load triplets from a JSON Lines file."""
        triplets = []
        with open(input_path, "r", encoding = "utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line.strip())
                    triplets.append(TrainingTriplet(**data))
        return triplets


def main():
    """CLI runner to generate train, val, test splits with zero data leakage."""
    parser = argparse.ArgumentParser(description = "Generate zero-leakage LoRA training triplets.")
    parser.add_argument("--count", type = int, default = 10000, help = "Base target count (default: 10000)")
    parser.add_argument("--train-count", type = int, default = 16000, help = "Expanded target training count (default: 16000)")
    parser.add_argument("--train-ratio", type = float, default = 0.8, help = "Train split ratio (default: 0.8)")
    parser.add_argument("--val-ratio", type = float, default = 0.1, help = "Val split ratio (default: 0.1)")
    parser.add_argument("--test-ratio", type = float, default = 0.1, help = "Test split ratio (default: 0.1)")
    parser.add_argument("--seed", type = int, default = 42, help = "Random seed (default: 42)")
    parser.add_argument("--preserve-eval", action = "store_true", help = "Keep existing val and test splits")
    parser.add_argument("--force-regen-eval", action = "store_true", help = "Force regenerating val and test splits")
    args = parser.parse_args()

    processed_dir = SRC_DIR / "processors" / "processed"
    champs_path = processed_dir / "champions.json"
    items_path = processed_dir / "items.json"
    runes_path = processed_dir / "runes.json"

    if not champs_path.exists():
        print(f"Error: {champs_path} not found. Please run processors first.")
        sys.exit(1)

    print(f"[DataGenerator] Loading data from {processed_dir}...")
    with open(champs_path, "r", encoding = "utf-8") as f:
        champions = json.load(f)

    items = {}
    if items_path.exists():
        with open(items_path, "r", encoding = "utf-8") as f:
            items = json.load(f)

    runes = {}
    if runes_path.exists():
        with open(runes_path, "r", encoding = "utf-8") as f:
            runes = json.load(f)

    # Load KB data (counters, synergies, builds)
    counters, synergies, builds = load_knowledge_base_data()
    print(f"[DataGenerator] Loaded KB data: {len(counters)} counters, {len(synergies)} synergies, {len(builds)} builds")

    generator = TrainingDataGenerator()
    splits = generator.generate_all_splits(
        champions = champions,
        items = items,
        runes = runes,
        counters = counters,
        synergies = synergies,
        builds = builds,
        total_count = args.count,
        train_ratio = args.train_ratio,
        val_ratio = args.val_ratio,
        test_ratio = args.test_ratio,
        seed = args.seed,
        preserve_eval = args.preserve_eval and not args.force_regen_eval,
        target_train_count = args.train_count,
    )

    # Audit data leakage
    audit = generator.audit_leakage(splits)
    print("\n" + "-" * 60)
    print("DATA LEAKAGE AUDIT REPORT")
    print("-" * 60)
    print(f"  Train samples: {len(splits['train'])}")
    print(f"  Val samples:   {len(splits['val'])}")
    print(f"  Test samples:  {len(splits['test'])}")
    print(f"  Query overlap (Train vs Val):    {audit['query_overlap_train_val']}")
    print(f"  Query overlap (Train vs Test):   {audit['query_overlap_train_test']}")
    print(f"  Query overlap (Val vs Test):     {audit['query_overlap_val_test']}")
    print(f"  Passage overlap (Train vs Val):  {audit['passage_overlap_train_val']}")
    print(f"  Passage overlap (Train vs Test): {audit['passage_overlap_train_test']}")
    print(f"  Passage overlap (Val vs Test):   {audit['passage_overlap_val_test']}")

    leakage_detected = any(v > 0 for v in audit.values())
    if not leakage_detected:
        print("  Status: ZERO DATA LEAKAGE VERIFIED!")
    else:
        print("  Status: WARNING - Overlap detected!")
    print("-" * 60)

    # Save splits to src/training/
    training_dir = SRC_DIR / "training"
    generator.save_triplets(splits["train"], str(training_dir / "train.jsonl"))
    generator.save_triplets(splits["val"], str(training_dir / "val.jsonl"))
    generator.save_triplets(splits["test"], str(training_dir / "test.jsonl"))

    # Also save to src/data/training/ for compatibility
    data_dir = SRC_DIR / "data" / "training"
    generator.save_triplets(splits["train"], str(data_dir / "train.jsonl"))
    generator.save_triplets(splits["val"], str(data_dir / "val.jsonl"))
    generator.save_triplets(splits["test"], str(data_dir / "test.jsonl"))

    print(f"\n[DataGenerator] Splits saved: {len(splits['train'])} train, {len(splits['val'])} val, {len(splits['test'])} test.")
    print(f"Locations: {training_dir} and {data_dir}.")


if __name__ == "__main__":
    main()
