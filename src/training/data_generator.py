"""
Training Data Generator for Embedding Fine-Tuning.

Generates contrastive learning triplets (query, positive_passage, negative_passage)
from processed League of Legends game data (champions, items, runes).

Supports zero-leakage train / val / test partitioning across disjoint entity sets.
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


class TrainingDataGenerator:
    """
    Generate training triplets for LoRA fine-tuning of embedding models.

    Target: ~5000-10000 triplets for effective domain adaptation.
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

    def generate(self, champions, items, runes, target_count = 8000, seed = 42, split_mode = "all"):
        """
        Generate training triplets from game data (English only).

        Args:
            champions: Processed champion data.
            items: Processed item data.
            runes: Processed rune data.
            target_count: Target number of triplets.
            seed: Random seed for reproducibility.
            split_mode: 'all', 'train', 'val', or 'test'.

        Returns:
            List of TrainingTriplet objects.
        """
        random.seed(seed)

        # 1. Generate chunks
        print("[DataGenerator] Chunking data...")
        self.chunks = self.chunker.chunk_all(champions, items, runes)
        self.index_chunks()
        print(f"  Total chunks: {len(self.chunks)}")

        triplets = []

        # 2. Strategy 1: Entity-based queries (Champion, Item, Rune)
        print("[DataGenerator] Strategy 1: Entity-based queries...")
        entity_triplets = self.generate_entity_queries(champions, items, runes)
        triplets.extend(entity_triplets)
        print(f"  Generated: {len(entity_triplets)}")

        # 3. Strategy 2: Ability-specific queries (P, Q, W, E, R)
        print("[DataGenerator] Strategy 2: Ability queries...")
        ability_triplets = self.generate_ability_queries(champions)
        triplets.extend(ability_triplets)
        print(f"  Generated: {len(ability_triplets)}")

        # 4. Strategy 3: Semantic filter queries (CC, Effects, Roles)
        print("[DataGenerator] Strategy 3: Semantic filter queries...")
        semantic_triplets = self.generate_semantic_queries(champions, split_mode=split_mode)
        triplets.extend(semantic_triplets)
        print(f"  Generated: {len(semantic_triplets)}")

        # 5. Strategy 4: Gameplay and tactical queries
        print("[DataGenerator] Strategy 4: Gameplay and tactical queries...")
        gameplay_triplets = self.generate_gameplay_queries(champions, items)
        triplets.extend(gameplay_triplets)
        print(f"  Generated: {len(gameplay_triplets)}")

        # 6. Strategy 5: Lore and biography queries
        print("[DataGenerator] Strategy 5: Lore and biography queries...")
        lore_triplets = self.generate_lore_queries(champions)
        triplets.extend(lore_triplets)
        print(f"  Generated: {len(lore_triplets)}")

        # 7. Strategy 6: Comparison queries
        print("[DataGenerator] Strategy 6: Comparison queries...")
        comp_triplets = self.generate_comparison_queries(champions)
        triplets.extend(comp_triplets)
        print(f"  Generated: {len(comp_triplets)}")

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
        if len(unique_triplets) > target_count:
            final_triplets = unique_triplets[:target_count]
        else:
            final_triplets = unique_triplets
        print(f"[DataGenerator] Final total triplets: {len(final_triplets)}")
        return final_triplets

    def generate_all_splits(self, champions, items, runes, total_count = 10000, train_ratio = 0.8, val_ratio = 0.1, test_ratio = 0.1, seed = 42):
        """
        Generate train, val, and test splits with zero data leakage.
        Partitions champions, items, runes and semantic phrasing templates.
        """
        print(f"[DataGenerator] Partitioning entities: train={train_ratio:.0%}, val={val_ratio:.0%}, test={test_ratio:.0%}")
        train_c, val_c, test_c = self.partition_dict(champions, r_train = train_ratio, r_val = val_ratio, seed = seed)
        train_i, val_i, test_i = self.partition_dict(items, r_train = train_ratio, r_val = val_ratio, seed = seed + 1)

        runes_by_id = runes.get("byId", {})
        r_train, r_val, r_test = self.partition_dict(runes_by_id, r_train = train_ratio, r_val = val_ratio, seed = seed + 2)
        by_tree = runes.get("byTree", {})
        train_r = {"byId": r_train, "byTree": by_tree}
        val_r = {"byId": r_val, "byTree": by_tree}
        test_r = {"byId": r_test, "byTree": by_tree}

        n_train = int(total_count * train_ratio)
        n_val = int(total_count * val_ratio)
        n_test = total_count - n_train - n_val

        print(f"  Champions: {len(train_c)} train | {len(val_c)} val | {len(test_c)} test")
        print(f"  Items:     {len(train_i)} train | {len(val_i)} val | {len(test_i)} test")
        print(f"  Runes:     {len(r_train)} train | {len(r_val)} val | {len(r_test)} test")

        print("\n--- Generating Train Split ---")
        gen_train = TrainingDataGenerator()
        train_triplets = gen_train.generate(train_c, train_i, train_r, target_count = n_train, seed = seed, split_mode = "train")

        print("\n--- Generating Val Split ---")
        gen_val = TrainingDataGenerator()
        val_triplets = gen_val.generate(val_c, val_i, val_r, target_count = n_val, seed = seed + 10, split_mode = "val")

        print("\n--- Generating Test Split ---")
        gen_test = TrainingDataGenerator()
        test_triplets = gen_test.generate(test_c, test_i, test_r, target_count = n_test, seed = seed + 20, split_mode = "test")

        # Zero leakage filter: guarantee disjoint queries
        train_q = set(t.query.strip().lower() for t in train_triplets)
        val_triplets = [t for t in val_triplets if t.query.strip().lower() not in train_q]
        val_q = set(t.query.strip().lower() for t in val_triplets)
        test_triplets = [t for t in test_triplets if t.query.strip().lower() not in train_q and t.query.strip().lower() not in val_q]

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

    # Indexing helpers

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
        candidates = [c for c in same_type if c.entity_name != positive_chunk.entity_name]
        if candidates:
            return random.choice(candidates).text
        return random.choice(self.chunks).text

    # Strategy 1: Entity-based queries

    def generate_entity_queries(self, champions, items, runes):
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
        ]

        # 1. Champion queries (Overview + Stats)
        for champ_id, champ in champions.items():
            name = champ.get("name", champ_id)
            entity_chunks = self.chunks_by_entity.get(name.lower(), [])

            overview_chunks = [c for c in entity_chunks if c.chunk_type == "overview"]
            stats_chunks = [c for c in entity_chunks if c.chunk_type == "stats"]

            if overview_chunks:
                pos_chunk = overview_chunks[0]
                for tmpl in random.sample(champ_overview_en, min(6, len(champ_overview_en))):
                    q = tmpl.format(name=name)
                    triplets.append(TrainingTriplet(q, pos_chunk.text, self.get_negative(pos_chunk), "entity_champ_en"))

            if stats_chunks:
                pos_stat = stats_chunks[0]
                for tmpl in random.sample(champ_stats_en, min(5, len(champ_stats_en))):
                    q = tmpl.format(name=name)
                    triplets.append(TrainingTriplet(q, pos_stat.text, self.get_negative(pos_stat), "stats_champ_en"))

        # 2. Item queries across items in this partition
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
        ]

        for item_id, item in items.items():
            name = item.get("name", "")
            if not name:
                continue
            item_chunks = [c for c in self.chunks if c.entity_name.lower() == name.lower() and c.chunk_type == "item"]
            if not item_chunks:
                continue

            pos_chunk = item_chunks[0]
            for tmpl in random.sample(item_templates_en, min(5, len(item_templates_en))):
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
        ]

        rune_chunks = [c for c in self.chunks if c.chunk_type == "rune"]
        for r_chunk in rune_chunks:
            r_name = r_chunk.entity_name
            if not r_name:
                continue
            for tmpl in random.sample(rune_templates_en, min(4, len(rune_templates_en))):
                q = tmpl.format(name=r_name)
                triplets.append(TrainingTriplet(q, r_chunk.text, self.get_negative(r_chunk), "rune_en"))

        return triplets

    # Strategy 2: Ability-specific queries

    def generate_ability_queries(self, champions):
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
        ]

        passive_templates_en = [
            "What is the passive ability of {name} and how does it work?",
            "Can you explain the innate passive effect of {name}?",
            "How does {name}'s passive interact with their other abilities?",
            "What triggers or procs {name}'s passive ability?",
            "Give me details on the passive skill of {name}",
            "What bonus does {name}'s passive provide during combat?",
            "How impactful is {name}'s passive in the early game?",
        ]

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
                for tmpl in random.sample(ability_templates_en, min(5, len(ability_templates_en))):
                    q = tmpl.format(name=name, key=key)
                    triplets.append(TrainingTriplet(q, pos_chunk.text, self.get_negative(pos_chunk), "ability_active_en"))

            # Passive (P)
            passive_chunks = [
                c for c in entity_chunks
                if c.chunk_type == "ability" and c.metadata.get("ability_key") in ("P", "Passive", "PASSIVE")
            ]
            if passive_chunks:
                pos_p = passive_chunks[0]
                for tmpl in random.sample(passive_templates_en, min(4, len(passive_templates_en))):
                    q = tmpl.format(name=name)
                    triplets.append(TrainingTriplet(q, pos_p.text, self.get_negative(pos_p), "ability_passive_en"))

        return triplets

    # Strategy 3: Semantic filter queries

    def generate_semantic_queries(self, champions, split_mode = "all"):
        """Generate queries about game concepts (CC types, effects, roles, playstyles) in English."""
        triplets = []

        cc_map = {
            "Stun": [
                "Champions with stun",
                "Which champions can stun enemies?",
                "Who has a stun ability?",
                "Champions that possess stun mechanics",
            ],
            "Knockup": [
                "Champions with knockup",
                "Champions that knock up enemies",
                "Who has airborne or knockup?",
                "Which champions have airborne crowd control?",
            ],
            "Root": [
                "Champions with root",
                "Champions that can root targets",
                "Who has a snare or root ability?",
                "Which champions immobilize enemies with root?",
            ],
            "Silence": [
                "Champions with silence",
                "Who can silence enemies?",
                "Champions that have silence mechanics",
            ],
            "Fear": [
                "Champions with fear effect",
                "Who has a terrify or fear ability?",
                "Champions with fear CC",
            ],
            "Charm": [
                "Champions with charm",
                "Who has charm abilities?",
                "Champions that can charm targets",
            ],
            "Suppression": [
                "Champions with suppression",
                "Who can suppress enemies?",
                "Which champions have suppression ultimate?",
            ],
            "Slow": [
                "Champions with slow effect",
                "Who can slow down targets?",
                "Champions with movement speed slows",
            ],
        }

        effect_map = {
            "Dash": [
                "Champions with dash",
                "Mobile champions with dash",
                "Who has gap close or dash?",
                "Champions with mobility and dash abilities",
            ],
            "Shield": [
                "Champions with shield",
                "Who can give shields to allies or self?",
                "Champions that grant protective shields",
            ],
            "Heal": [
                "Champions with healing",
                "Who has self or ally heal?",
                "Champions with sustaining heals",
            ],
            "Stealth": [
                "Champions with stealth or invisibility",
                "Who can turn invisible?",
                "Champions with camouflage or stealth",
            ],
            "Execute": [
                "Champions with execute damage",
                "Who has execute ult?",
                "Champions with execution mechanics",
            ],
            "True Damage": [
                "Champions with true damage",
                "Who deals true damage?",
                "Champions with abilities that ignore armor and magic resist",
            ],
        }

        roles_map = {
            "Assassin": [
                "Best assassin champions",
                "Who are the assassins in LoL?",
                "List of assassin champions",
            ],
            "Mage": [
                "Mage champions in LoL",
                "Who are the AP mages?",
                "Champions in the mage category",
            ],
            "Tank": [
                "Tank champions",
                "Who are the frontliner tanks?",
                "Top durable tank champions",
            ],
            "Fighter": [
                "Fighter and bruiser champions",
                "Who are the top lane fighters?",
                "Melee bruiser champions",
            ],
            "Marksman": [
                "Marksman and ADC champions",
                "Who are the ranged carries?",
                "Attack damage carry champions",
            ],
            "Support": [
                "Support champions",
                "Who are the utility supports?",
                "Champions played in support role",
            ],
        }

        def pick_subset(options):
            if split_mode == "train":
                return options[:max(1, len(options) - 2)]
            elif split_mode == "val":
                return [options[-2]] if len(options) >= 2 else [options[-1]]
            elif split_mode == "test":
                return [options[-1]]
            return options

        # 1. CC queries
        for cc_type, en_queries in cc_map.items():
            pool = pick_subset(en_queries)
            champs_with = [cid for cid, c in champions.items() if cc_type.lower() in [x.lower() for x in c.get("cc_types", [])]]
            champs_without = [cid for cid, c in champions.items() if cc_type.lower() not in [x.lower() for x in c.get("cc_types", [])]]

            if not champs_with or not champs_without:
                continue

            for _ in range(min(45, len(champs_with) * 3)):
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

            for _ in range(min(45, len(champs_with) * 3)):
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

            for _ in range(min(35, len(champs_with) * 2)):
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

    # Strategy 4: Gameplay and tactical queries

    def generate_gameplay_queries(self, champions, items):
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
        ]

        for champ_id, champ in champions.items():
            name = champ.get("name", champ_id)
            entity_chunks = self.chunks_by_entity.get(name.lower(), [])

            overview_chunks = [c for c in entity_chunks if c.chunk_type == "overview"]
            if not overview_chunks:
                continue

            pos_chunk = overview_chunks[0]
            neg_chunk_text = self.get_negative(pos_chunk)

            for tmpl in random.sample(gameplay_templates, min(6, len(gameplay_templates))):
                q = tmpl.format(name=name)
                triplets.append(TrainingTriplet(q, pos_chunk.text, neg_chunk_text, "gameplay_en"))

        return triplets

    # Strategy 5: Lore and biography queries

    def generate_lore_queries(self, champions):
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
        ]

        region_templates = [
            "What region does {name} belong to?",
            "Where is {name} from in Runeterra?",
            "What is {name}'s affiliated region or faction?",
            "Is {name} connected to {region}?",
            "Tell me about {name}'s origin in {region}",
            "What is the role of {name} in {region}?",
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
            for tmpl in random.sample(lore_templates, min(6, len(lore_templates))):
                pos_chunk = random.choice(lore_chunks)
                neg_chunk_text = self.get_negative(pos_chunk)
                triplets.append(TrainingTriplet(tmpl.format(name=name, title=title or "a champion"), pos_chunk.text, neg_chunk_text, "lore_en"))

            # 2. Region / Faction queries
            region = champ.get("region")
            if region and region != "Runeterra (Unaffiliated)":
                for tmpl in random.sample(region_templates, min(3, len(region_templates))):
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

    # Strategy 6: Comparison queries

    def generate_comparison_queries(self, champions):
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
        ]

        target_comparisons = min(1200, len(champ_list) * 7)
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
                data = json.loads(line.strip())
                triplets.append(TrainingTriplet(**data))
        return triplets


def main():
    """CLI runner to generate train, val, test splits with zero data leakage."""
    parser = argparse.ArgumentParser(description = "Generate zero-leakage LoRA training triplets.")
    parser.add_argument("--count", type = int, default = 10000, help = "Total target triplets (default: 10000)")
    parser.add_argument("--train-ratio", type = float, default = 0.8, help = "Train split ratio (default: 0.8)")
    parser.add_argument("--val-ratio", type = float, default = 0.1, help = "Val split ratio (default: 0.1)")
    parser.add_argument("--test-ratio", type = float, default = 0.1, help = "Test split ratio (default: 0.1)")
    parser.add_argument("--seed", type = int, default = 42, help = "Random seed (default: 42)")
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

    generator = TrainingDataGenerator()
    splits = generator.generate_all_splits(
        champions = champions,
        items = items,
        runes = runes,
        total_count = args.count,
        train_ratio = args.train_ratio,
        val_ratio = args.val_ratio,
        test_ratio = args.test_ratio,
        seed = args.seed,
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

    print(f"\n[DataGenerator] Splits (train, val, test) saved to {training_dir} and {data_dir}.")


if __name__ == "__main__":
    main()
