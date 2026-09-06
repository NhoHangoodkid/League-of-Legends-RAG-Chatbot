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
import os
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Ensure src/ is on path
SRC_DIR = Path(__file__).resolve().parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from dotenv import load_dotenv
    load_dotenv(SRC_DIR.parent / ".env")
except ImportError:
    pass

try:
    from pymongo import MongoClient
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False

from rag.vector.chunker import DocumentChunker


@dataclass
class TrainingTriplet:
    """A single training example for contrastive learning."""

    query: str
    positive: str       # Relevant passage
    negative: str       # Irrelevant passage
    strategy: str       # Which generation strategy produced this


def load_from_mongodb(uri = None, db_name = None):
    """
    Load champions, items, runes, counters, synergies, and builds directly from MongoDB.
    Returns (champions, items, runes, counters, synergies, builds) or None if unavailable.
    """
    if not PYMONGO_AVAILABLE:
        return None

    mongo_uri = uri or os.getenv("MONGO_URI", "mongodb://localhost:27017")
    database_name = db_name or os.getenv("MONGO_DB_NAME", "lol_rag_db")

    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS = 3000)
        client.admin.command("ping")
        db = client[database_name]

        champions = {doc["_id"]: doc for doc in db.champions.find()}
        if not champions:
            return None

        items = {doc["_id"]: doc for doc in db.items.find()}

        runes_docs = list(db.runes.find())
        by_id = {doc["_id"]: doc for doc in runes_docs if doc.get("type") != "tree"}
        by_tree = {
            doc.get("tree", doc["_id"].replace("tree_", "")): doc.get("runes", [])
            for doc in runes_docs if doc.get("type") == "tree"
        }
        runes = {"byId": by_id, "byTree": by_tree}

        counters = {doc["_id"]: doc for doc in db.counters.find()}
        if not counters:
            counters = {
                cid: doc["counters"]
                for cid, doc in champions.items()
                if "counters" in doc and isinstance(doc["counters"], dict)
            }

        synergies = {doc["_id"]: doc for doc in db.synergies.find()}
        if not synergies:
            synergies = {
                cid: {"champion": doc.get("name", cid), "synergies": doc["synergies"]}
                for cid, doc in champions.items()
                if "synergies" in doc and isinstance(doc["synergies"], list)
            }

        builds = {doc["_id"]: doc for doc in db.builds.find()}
        if not builds:
            builds = {
                cid: doc["builds"]
                for cid, doc in champions.items()
                if "builds" in doc and isinstance(doc["builds"], dict)
            }

        for cid, cnt_doc in counters.items():
            champ_doc = champions.get(cid, {})
            tactical = champ_doc.get("tacticalInfo", {})
            if "weaknesses" not in cnt_doc and tactical.get("weaknesses"):
                cnt_doc["weaknesses"] = tactical["weaknesses"]
            if "tactical_tips" not in cnt_doc and tactical.get("tactical_tips"):
                cnt_doc["tactical_tips"] = tactical["tactical_tips"]
            if "counter_items" not in cnt_doc and tactical.get("counter_items"):
                cnt_doc["counter_items"] = tactical["counter_items"]

        print(f"[DataGenerator] Successfully loaded knowledge data from MongoDB ('{database_name}'):")
        print(f"  Champions: {len(champions)}, Items: {len(items)}, Runes: {len(by_id)}")
        print(f"  Counters:  {len(counters)}, Synergies: {len(synergies)}, Builds: {len(builds)}")

        return champions, items, runes, counters, synergies, builds
    except Exception as e:
        print(f"[DataGenerator] MongoDB load unavailable ({e})")
        return None


def load_knowledge_base_data():
    """Load counters, synergies, and builds from MongoDB (or knowledge base directory as fallback)."""
    # 1. Primary: load directly from MongoDB
    try:
        from pymongo import MongoClient
        uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        database_name = os.getenv("MONGO_DB_NAME", "lol_rag_db")
        client = MongoClient(uri, serverSelectionTimeoutMS = 2000)
        client.admin.command("ping")
        db = client[database_name]

        counters = {doc["_id"]: doc for doc in db.counters.find()}
        synergies = {doc["_id"]: doc for doc in db.synergies.find()}
        builds = {doc["_id"]: doc for doc in db.builds.find()}

        if counters or synergies or builds:
            try:
                champs_lookup = {
                    doc["_id"]: doc.get("tacticalInfo", {})
                    for doc in db.champions.find({}, {"tacticalInfo": 1})
                }
                for cid, cnt_doc in counters.items():
                    tactical = champs_lookup.get(cid, {})
                    if "weaknesses" not in cnt_doc and tactical.get("weaknesses"):
                        cnt_doc["weaknesses"] = tactical["weaknesses"]
                    if "tactical_tips" not in cnt_doc and tactical.get("tactical_tips"):
                        cnt_doc["tactical_tips"] = tactical["tactical_tips"]
                    if "counter_items" not in cnt_doc and tactical.get("counter_items"):
                        cnt_doc["counter_items"] = tactical["counter_items"]
            except Exception:
                pass
            return counters, synergies, builds
    except Exception:
        pass

    # 2. Fallback: local directory if present
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
    """Filter KB entries so only champions in champ_dict have their KB chunks included."""
    allowed_names = set(c.get("name", "").lower() for c in champ_dict.values())
    allowed_ids = set(k.lower() for k in champ_dict.keys())
    result = {}
    for k, v in data_dict.items():
        c_name = v.get("champion", "").lower()
        c_id = v.get("champion_id", k).lower()
        if k.lower() in allowed_ids or c_id in allowed_ids or c_name in allowed_names:
            result[k] = v
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
    def partition_dict(data, r_train = 0.8, r_val = 0.1, seed = 42, group_by_name = False):
        """Split dictionary entries deterministically to avoid entity leakage."""
        if group_by_name:
            name_to_keys = {}
            for k, v in data.items():
                name = v.get("name", str(k)).strip().lower() if isinstance(v, dict) else str(k).strip().lower()
                name_to_keys.setdefault(name, []).append(k)

            names = sorted(list(name_to_keys.keys()))
            rng = random.Random(seed)
            rng.shuffle(names)
            n = len(names)
            n_train = int(n * r_train)
            n_val = int(n * r_val)

            train_names = set(names[:n_train])
            val_names = set(names[n_train:n_train + n_val])
            test_names = set(names[n_train + n_val:])

            train_d = {k: data[k] for name in train_names for k in name_to_keys[name]}
            val_d = {k: data[k] for name in val_names for k in name_to_keys[name]}
            test_d = {k: data[k] for name in test_names for k in name_to_keys[name]}
            return train_d, val_d, test_d

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

        # 11. Strategy 10: Strategic Win Conditions & Power Curves
        print("[DataGenerator] Strategy 10: Strategic metadata queries...")
        strategic_triplets = self.generate_strategic_queries(champions, split_mode=split_mode)
        triplets.extend(strategic_triplets)
        print(f"  Generated: {len(strategic_triplets)}")

        # 12. Strategy 11: Champion Subrole & Position queries (NEW)
        print("[DataGenerator] Strategy 11: Champion subrole and position queries...")
        subrole_pos_triplets = self.generate_subrole_and_position_queries(champions, split_mode=split_mode)
        triplets.extend(subrole_pos_triplets)
        print(f"  Generated: {len(subrole_pos_triplets)}")

        # 13. Strategy 12: Item Recipe & Build Path queries (NEW)
        if items or "item_info" in self.chunks_by_type:
            print("[DataGenerator] Strategy 12: Item recipe and build path queries...")
            item_recipe_triplets = self.generate_item_recipe_queries(items, split_mode=split_mode)
            triplets.extend(item_recipe_triplets)
            print(f"  Generated: {len(item_recipe_triplets)}")

        # 14. Strategy 13: Rune Tree & Keystone queries (NEW)
        if runes or "rune_info" in self.chunks_by_type:
            print("[DataGenerator] Strategy 13: Rune tree and keystone queries...")
            rune_tree_triplets = self.generate_rune_queries(runes, split_mode=split_mode)
            triplets.extend(rune_tree_triplets)
            print(f"  Generated: {len(rune_tree_triplets)}")

        # 15. Strategy 14: CC Mechanics & Combat Effect queries (NEW)
        print("[DataGenerator] Strategy 14: CC mechanics and combat effect queries...")
        cc_effect_triplets = self.generate_cc_and_effect_queries(champions, split_mode=split_mode)
        triplets.extend(cc_effect_triplets)
        print(f"  Generated: {len(cc_effect_triplets)}")

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
        total_count = 12000,
        train_ratio = 0.8,
        val_ratio = 0.1,
        test_ratio = 0.1,
        seed = 42,
        preserve_eval = False,
        target_train_count = 12000,
        target_val_count = 1200,
        target_test_count = 1200,
    ):
        """
        Generate train, val, and test splits with zero data leakage.
        Preserves existing val and test splits only when preserve_eval=True.
        Expands all splits with rich relationships (Region, Lore Connections, Subroles, Positions).
        """
        # Load KB relationships if not passed
        if counters is None or synergies is None or builds is None:
            c_kb, s_kb, b_kb = load_knowledge_base_data()
            counters = counters or c_kb
            synergies = synergies or s_kb
            builds = builds or b_kb

        print(f"[DataGenerator] Partitioning entities: train={train_ratio:.0%}, val={val_ratio:.0%}, test={test_ratio:.0%}")
        train_c, val_c, test_c = self.partition_dict(champions, r_train = train_ratio, r_val = val_ratio, seed = seed)
        train_i, val_i, test_i = self.partition_dict(items, r_train = train_ratio, r_val = val_ratio, seed = seed + 1, group_by_name = True)

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

        n_val = target_val_count if target_val_count and target_val_count > 0 else int(total_count * val_ratio)
        n_test = target_test_count if target_test_count and target_test_count > 0 else int(total_count * test_ratio)
        effective_train_count = target_train_count if target_train_count and target_train_count > 0 else total_count

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
            target_count=effective_train_count + 8000, seed=seed, split_mode="train",
        )

        # Strictly enforce zero data leakage against val and test
        clean_train = [
            t for t in raw_train_triplets
            if t.query.strip().lower() not in eval_queries
            and t.positive.strip() not in eval_passages
        ]
        if effective_train_count and len(clean_train) > effective_train_count:
            train_triplets = clean_train[:effective_train_count]
        else:
            train_triplets = clean_train
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
        candidates = [c for c in same_type if c.entity_name.lower() != positive_chunk.entity_name.lower()]
        if candidates:
            return random.choice(candidates).text
        # Fallback to any chunk of different entity
        other_entities = [c for c in self.chunks if c.entity_name.lower() != positive_chunk.entity_name.lower()]
        if other_entities:
            return random.choice(other_entities).text
        return random.choice(self.chunks).text

    # Strategy 1: Entity-based queries

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

        champ_overview_extra_en = [
            "Complete breakdown of {name}: role, abilities, and playstyle",
            "What kind of champion is {name} in League of Legends?",
            "Combat characteristics and core playstyle of {name}",
            "Summary of {name}'s strengths, primary role, and difficulty",
            "Is {name} a ranged or melee champion, and what resource do they use?",
            "What crowd control and special mechanics does {name} feature?",
            "What champion archetype is {name} and what compositions suit them best?",
        ]

        champ_stats_extra_en = [
            "What are {name}'s level 1 base stats: health, armor, MR, and AD?",
            "What is {name}'s movement speed and basic attack range?",
            "How do {name}'s health and armor scale per level?",
            "Does {name} start with high or low base durability in lane?",
            "What are {name}'s base health regen and mana pool values?",
        ]

        combined_overview = champ_overview_en + champ_overview_extra_en
        combined_stats = champ_stats_en + champ_stats_extra_en

        sample_k_overview = 9 if split_mode == "train" else 6
        sample_k_stats = 6 if split_mode == "train" else 4

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
                for tmpl in random.sample(combined_overview, min(sample_k_overview, len(combined_overview))):
                    q = tmpl.format(name=name, role=primary_role)
                    triplets.append(TrainingTriplet(q, pos_chunk.text, self.get_negative(pos_chunk), "entity_champ"))

            if stats_chunks:
                pos_stat = stats_chunks[0]
                for tmpl in random.sample(combined_stats, min(sample_k_stats, len(combined_stats))):
                    q = tmpl.format(name=name)
                    triplets.append(TrainingTriplet(q, pos_stat.text, self.get_negative(pos_stat), "stats_champ"))

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
            "What are the stats, passives, and active effects of {name}?",
            "How much does {name} cost in gold and what bonuses does it grant?",
            "How does the unique passive on {name} function in combat?",
            "Which champion classes and roles prioritize building {name}?",
            "What tactical advantages does purchasing {name} provide in skirmishes?",
        ]

        sample_k_item = 5 if split_mode == "train" else 4
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
                triplets.append(TrainingTriplet(q, pos_chunk.text, self.get_negative(pos_chunk), "entity_item"))

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
            "What does the {name} rune do and how is it triggered?",
            "Which rune tree contains {name} and what stats does it provide?",
            "How does keystone {name} function during teamfight combat?",
            "Which champion archetypes should run {name} as their primary rune?",
        ]

        sample_k_rune = 4 if split_mode == "train" else 3
        rune_chunks = [c for c in self.chunks if c.chunk_type == "rune_info"]
        for r_chunk in rune_chunks:
            r_name = r_chunk.entity_name
            if not r_name:
                continue
            for tmpl in random.sample(rune_templates_en, min(sample_k_rune, len(rune_templates_en))):
                q = tmpl.format(name=r_name)
                triplets.append(TrainingTriplet(q, r_chunk.text, self.get_negative(r_chunk), "rune"))

        return triplets

    # Strategy 2: Ability-specific queries

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

        ability_templates_extra_en = [
            "What are the damage, cooldown, and mana cost of {name}'s {key}?",
            "How does {name}'s {key} ability work in detail?",
            "Does {name}'s {key} apply crowd control or utility effects?",
            "How to use {name}'s {key} effectively during teamfights?",
            "Is {name}'s {key} a skillshot, targeted ability, or self-buff?",
            "At what ability ranks does {name}'s {key} power spike?",
        ]

        passive_templates_extra_en = [
            "How does {name}'s innate passive work and what does it do?",
            "What triggers {name}'s passive stacks and how does it refresh?",
            "Detailed mechanics of {name}'s passive ability in combat",
            "How does {name}'s passive synergize with their active QWER abilities?",
        ]

        combined_active = ability_templates_en + ability_templates_extra_en
        combined_passive = passive_templates_en + passive_templates_extra_en

        sample_k_active = 4 if split_mode == "train" else 3
        sample_k_passive = 3 if split_mode == "train" else 2

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
                for tmpl in random.sample(combined_active, min(sample_k_active, len(combined_active))):
                    q = tmpl.format(name=name, key=key)
                    triplets.append(TrainingTriplet(q, pos_chunk.text, self.get_negative(pos_chunk), "ability_active"))

            # Passive (P)
            passive_chunks = [
                c for c in entity_chunks
                if c.chunk_type == "ability" and c.metadata.get("ability_key") in ("passive", "P", "Passive", "PASSIVE")
            ]
            if passive_chunks:
                pos_p = passive_chunks[0]
                for tmpl in random.sample(combined_passive, min(sample_k_passive, len(combined_passive))):
                    q = tmpl.format(name=name)
                    triplets.append(TrainingTriplet(q, pos_p.text, self.get_negative(pos_p), "ability_passive"))

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

        subroles_map = {
            "Artillery": [
                "Artillery mages in League of Legends",
                "Who are the long range artillery champions?",
                "Champions classified as Artillery subclass",
                "Long range siege and poke artillery champions",
            ],
            "Assassin": [
                "Assassin champions in LoL",
                "Who are the slayer burst assassins?",
                "Champions with Assassin subrole",
                "Mobile flankers and burst damage assassins",
            ],
            "Battlemage": [
                "Battlemage champions in League",
                "Who are the short-range sustained DPS mages?",
                "Champions in the Battlemage subclass",
                "Ramp-up sustained damage battlemages",
            ],
            "Burst": [
                "Burst mage champions in League of Legends",
                "Who are the high burst damage spellcasters?",
                "Champions categorized under the Burst subrole",
                "Single target and AoE burst mages",
            ],
            "Catcher": [
                "Catcher support champions",
                "Who are the pick-potential catcher champions?",
                "Champions in the Catcher subclass",
                "Lockdown pick and crowd control catchers",
            ],
            "Diver": [
                "Diver fighter champions in League",
                "Who are the diving bruisers in LoL?",
                "Champions categorized as Divers",
                "All-in backline access diving fighters",
            ],
            "Enchanter": [
                "Enchanter support champions",
                "Who are the defensive protective enchanters?",
                "Champions with Enchanter subrole",
                "Shielding, healing, and buffing utility enchanters",
            ],
            "Juggernaut": [
                "Juggernaut champions in League of Legends",
                "Who are the immobile durable juggernauts?",
                "Champions with Juggernaut subrole",
                "High damage raid-boss tanky juggernauts",
            ],
            "Marksman": [
                "Marksman subclass champions",
                "Who are the sustained auto-attack marksmen?",
                "Champions classified as Marksman",
                "Ranged DPS marksman champions",
            ],
            "Skirmisher": [
                "Skirmisher champions in LoL",
                "Who are the duelist skirmishers?",
                "Champions in the Skirmisher subclass",
                "Melee DPS duelist skirmishers",
            ],
            "Specialist": [
                "Specialist champions in League of Legends",
                "Who are the unique specialist champions?",
                "Champions categorized as Specialists",
                "Unique kit and niche playstyle specialists",
            ],
            "Vanguard": [
                "Vanguard tank champions",
                "Who are the primary frontline engage vanguards?",
                "Champions with Vanguard subrole",
                "Hard-engage teamfight frontline vanguards",
            ],
            "Warden": [
                "Warden defensive tank champions",
                "Who are the peeling warden tanks?",
                "Champions categorized as Wardens",
                "Defensive backline protector wardens",
            ],
        }

        positions_map = {
            "TOP": [
                "Top lane champions in League of Legends",
                "Who can be played in Top lane?",
                "Champions for the Top position",
                "List of top lane solo champions",
                "Viable Top laners on Summoner's Rift",
            ],
            "JUNGLE": [
                "Jungle champions in League of Legends",
                "Who are the junglers in LoL?",
                "Champions suited for the Jungle role",
                "Viable jungle champions on Summoner's Rift",
                "Who can jungle effectively?",
            ],
            "MID": [
                "Mid lane champions in LoL",
                "Who plays in the Mid lane?",
                "Champions for the Middle lane position",
                "Solo mid lane carry champions",
                "Viable Mid laners on Summoner's Rift",
            ],
            "BOT": [
                "Bot lane ADC carry champions",
                "Who can be played in the Bot position?",
                "Champions for the Bottom lane role",
                "Ranged bot laners and duo carries",
                "Bot lane carry champions",
            ],
            "SUPPORT": [
                "Support champions in League of Legends",
                "Who can play the Support role?",
                "Champions for the Support position",
                "Duo lane utility support champions",
                "Viable Support champions on Summoner's Rift",
            ],
        }

        def pick_subset(options):
            if split_mode == "train":
                return options[:-2] if len(options) > 2 else options[:1]
            elif split_mode == "val":
                return [options[-2]] if len(options) >= 2 else [options[-1]]
            elif split_mode == "test":
                return [options[-1]]
            return options

        sample_mult = 4 if split_mode == "train" else 2

        # 1. CC queries
        for cc_type, en_queries in cc_map.items():
            pool = pick_subset(en_queries)
            champs_with = [cid for cid, c in champions.items() if cc_type.lower() in [x.lower() for x in c.get("cc_types", [])]]
            champs_without = [cid for cid, c in champions.items() if cc_type.lower() not in [x.lower() for x in c.get("cc_types", [])]]

            if not champs_with or not champs_without:
                continue

            n_samples = min(45 if split_mode == "train" else 12, len(champs_with) * sample_mult)
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

            n_samples = min(45 if split_mode == "train" else 12, len(champs_with) * sample_mult)
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

            n_samples = min(45 if split_mode == "train" else 12, len(champs_with) * sample_mult)
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

        # 4. Subrole queries (NEW)
        for subrole, en_queries in subroles_map.items():
            pool = pick_subset(en_queries)
            champs_with = [cid for cid, c in champions.items() if subrole.lower() in [x.lower() for x in c.get("subroles", [])]]
            champs_without = [cid for cid, c in champions.items() if subrole.lower() not in [x.lower() for x in c.get("subroles", [])]]

            if not champs_with or not champs_without:
                continue

            n_samples = min(35 if split_mode == "train" else 10, len(champs_with) * sample_mult)
            for _ in range(n_samples):
                pos_id = random.choice(champs_with)
                neg_id = random.choice(champs_without)

                pos_name = champions[pos_id].get("name", pos_id)
                neg_name = champions[neg_id].get("name", neg_id)

                pos_chunks = [c for c in self.chunks_by_entity.get(pos_name.lower(), []) if c.chunk_type == "overview"]
                neg_chunks = [c for c in self.chunks_by_entity.get(neg_name.lower(), []) if c.chunk_type == "overview"]

                if pos_chunks and neg_chunks:
                    q = random.choice(pool)
                    triplets.append(TrainingTriplet(q, random.choice(pos_chunks).text, random.choice(neg_chunks).text, "semantic_subrole"))

        # 5. Position / Lane queries (NEW)
        for pos_lane, en_queries in positions_map.items():
            pool = pick_subset(en_queries)
            champs_with = [cid for cid, c in champions.items() if pos_lane.upper() in [x.upper() for x in c.get("positions", [])]]
            champs_without = [cid for cid, c in champions.items() if pos_lane.upper() not in [x.upper() for x in c.get("positions", [])]]

            if not champs_with or not champs_without:
                continue

            n_samples = min(60 if split_mode == "train" else 16, len(champs_with) * sample_mult)
            for _ in range(n_samples):
                pos_id = random.choice(champs_with)
                neg_id = random.choice(champs_without)

                pos_name = champions[pos_id].get("name", pos_id)
                neg_name = champions[neg_id].get("name", neg_id)

                pos_chunks = [c for c in self.chunks_by_entity.get(pos_name.lower(), []) if c.chunk_type == "overview"]
                neg_chunks = [c for c in self.chunks_by_entity.get(neg_name.lower(), []) if c.chunk_type == "overview"]

                if pos_chunks and neg_chunks:
                    q = random.choice(pool)
                    triplets.append(TrainingTriplet(q, random.choice(pos_chunks).text, random.choice(neg_chunks).text, "semantic_position"))

        return triplets

    # Strategy 4: Gameplay and tactical queries

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

        sample_k = 5 if split_mode == "train" else 4

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

    # Strategy 5: Lore and biography queries

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
            "What is the complete backstory and biography of {name}?",
            "Tell me the full legend and origin of {name} in Runeterra",
            "Background history and early origins of {name} in the lore",
            "Who was {name} before becoming known as {title}?",
            "Major historical conflicts and lore events involving {name}",
            "What is {name}'s overarching motivation and narrative purpose?",
        ]

        region_templates = [
            "What region does {name} belong to?",
            "Where is {name} from in Runeterra?",
            "What is {name}'s affiliated region or faction?",
            "Is {name} connected to {region}?",
            "Tell me about {name}'s origin in {region}",
            "What is the role of {name} in {region}?",
            "What faction does {name} fight for in {region}?",
            "What region in the League of Legends universe does {name} originate from?",
            "What is the home region and lore territory of {name}?",
            "Is {name} affiliated with or native to {region}?",
            "What is {name}'s role and influence in the region of {region}?",
            "Which faction does {name} represent within {region}?",
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
            "What lore relationship exists between {name} and {related}?",
            "In the Runeterra universe, how are {name} and {related} connected?",
            "Are {name} and {related} sworn allies or bitter enemies in the lore?",
            "What major historical event involved both {name} and {related}?",
            "Do {name} and {related} share the same faction, realm, or family lineage?",
            "What grudge, rivalry, or bond ties {name} to {related} in the story?",
        ]

        sample_lore = 4 if split_mode == "train" else 4
        sample_region = 3 if split_mode == "train" else 3

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
            if region:
                for tmpl in random.sample(region_templates, min(sample_region, len(region_templates))):
                    pos_chunk = random.choice(lore_chunks)
                    neg_chunk_text = self.get_negative(pos_chunk)
                    triplets.append(TrainingTriplet(tmpl.format(name=name, region=region), pos_chunk.text, neg_chunk_text, "lore_region_en"))

            # 3. Related champions in lore
            related_list = champ.get("related_champions", [])
            if related_list:
                who_related_templates = [
                    "Who is related to {name} in the lore?",
                    "Which champions are connected to {name}'s story?",
                    "What champions have backstory ties with {name}?",
                    "Does {name} have narrative connections to other champions?",
                    "Which champions are narrative ties or related to {name} in lore?",
                    "Who are the canonical allies, enemies, or relatives of {name}?",
                ]
                for tmpl in random.sample(who_related_templates, min(2 if split_mode == "train" else 2, len(who_related_templates))):
                    pos_chunk = random.choice(lore_chunks)
                    neg_chunk_text = self.get_negative(pos_chunk)
                    triplets.append(TrainingTriplet(tmpl.format(name=name), pos_chunk.text, neg_chunk_text, "lore_relation_en"))

            for rc in related_list:
                rel_name = rc.get("name") if isinstance(rc, dict) else str(rc)
                if not rel_name:
                    continue
                sample_rel = 2 if split_mode == "train" else 2
                for tmpl in random.sample(relation_templates, min(sample_rel, len(relation_templates))):
                    pos_chunk = random.choice(lore_chunks)
                    neg_chunk_text = self.get_negative(pos_chunk)
                    triplets.append(TrainingTriplet(tmpl.format(name=name, related=rel_name), pos_chunk.text, neg_chunk_text, "lore_relation_en"))

        # 4. Regional Champion Listing queries (NEW)
        region_list_templates = [
            "Which champions belong to {region}?",
            "List of champions from {region} in League of Legends",
            "Who are the champions originating from {region}?",
            "Champions associated with {region} in lore",
            "Tell me about the champions of {region}",
            "Who belongs to the region of {region} in Runeterra?",
            "List of all champions hailing from the region of {region}",
            "Which champions originate from {region} in League of Legends lore?",
            "What notable champions are native to {region} in Runeterra?",
        ]

        def pick_subset_reg(options):
            if split_mode == "train":
                return options[:-2] if len(options) > 2 else options[:1]
            elif split_mode == "val":
                return [options[-2]] if len(options) >= 2 else [options[-1]]
            elif split_mode == "test":
                return [options[-1]]
            return options

        reg_pool = pick_subset_reg(region_list_templates)

        champs_by_region = {}
        for cid, c in champions.items():
            r = c.get("region")
            if r:
                champs_by_region.setdefault(r, []).append(cid)

        for reg, cids in champs_by_region.items():
            if len(cids) >= 1 and len(cids) < len(champions):
                other_cids = [cid for cid in champions if cid not in cids]
                if not other_cids:
                    continue
                n_samples = min(25 if split_mode == "train" else 10, len(cids) * 3)
                for _ in range(n_samples):
                    pos_id = random.choice(cids)
                    neg_id = random.choice(other_cids)
                    pos_name = champions[pos_id].get("name", pos_id)
                    neg_name = champions[neg_id].get("name", neg_id)

                    pos_chunks = [c for c in self.chunks_by_entity.get(pos_name.lower(), []) if c.chunk_type in ("overview", "lore")]
                    neg_chunks = [c for c in self.chunks_by_entity.get(neg_name.lower(), []) if c.chunk_type in ("overview", "lore")]
                    if pos_chunks and neg_chunks:
                        tmpl = random.choice(reg_pool)
                        q = tmpl.format(region=reg)
                        triplets.append(TrainingTriplet(q, random.choice(pos_chunks).text, random.choice(neg_chunks).text, "lore_region_en"))

        return triplets

    # Strategy 6: Comparison queries

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

        target_comparisons = min(1000 if split_mode == "train" else 220, len(champ_list) * 14)
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

    # Strategy 7: Counter Matchup queries (Enriched Bilingual & Entity Pairs)

    def generate_counter_queries(self, champions, counters = None, split_mode = "all"):
        """Generate matchup, counter-pick, laning, and specific champion pair queries (EN & VI)."""
        triplets = []
        counter_chunks = self.chunks_by_type.get("counter", [])
        if not counter_chunks:
            return triplets

        c_chunks_by_name = {c.entity_name.lower(): c for c in counter_chunks}

        counter_templates_en = [
            "Who counters {name} in lane?",
            "What champions are strong counter picks into {name}?",
            "What is the best counter pick into {name}?",
            "Who does {name} struggle against most in lane?",
            "How do you counter {name} and exploit their tactical weaknesses?",
            "Who does {name} counter and beat easily in lane?",
            "Which champion matchups are favorable for {name}?",
            "What champions are weak against {name}?",
            "Tactical tips for playing against {name} in the laning phase",
            "Why is {name} countered by specific champion archetypes?",
            "Who should I ban or avoid picking into {name}?",
            "Complete tactical counter matchup guide for {name}",
            "What makes {name} strong against certain enemy champions?",
            "What mechanical advantages allow enemy champions to counter {name}?",
            "How should you trade, space, and punish {name} in lane?",
        ]

        tactical_weakness_templates_en = [
            "What are {name}'s core tactical weaknesses in combat?",
            "What are the main combat vulnerabilities of {name}?",
            "How do you punish and exploit {name}'s cooldowns and mobility?",
            "What makes {name} vulnerable to ganks and burst damage?",
            "What are the biggest weaknesses to exploit when facing {name}?",
        ]

        tactical_tip_templates_en = [
            "What tactical tips help you play against and beat {name}?",
            "How should you space, trade, and position against {name} in lane?",
            "How do you interrupt or neutralize {name}'s channeled abilities and engage?",
            "What strategic advice helps shut down {name} in teamfights?",
            "How to play around {name}'s abilities and engagement perimeter?",
        ]

        counter_item_templates_en = [
            "What items should I build to counter {name}?",
            "Which defensive counter items are most effective against {name}?",
            "What items counter {name}'s damage profile?",
            "How do you itemize defensively against {name}?",
            "What counter items neutralize {name}'s healing, armor, or burst?",
        ]

        pair_weak_en = [
            "Why does {enemy} counter {name} in lane?",
            "How does {enemy} win the matchup against {name}?",
            "What makes {enemy}'s kit so effective against {name}?",
            "How to play as {name} against {enemy} in lane?",
            "Why is {enemy} such a hard counter into {name}?",
            "How does {enemy} win trades and beat {name} in lane?",
            "What specific advantages and CC make {enemy} dominate {name}?",
            "How does {enemy}'s crowd control and durability shut down {name}?",
            "How should you play the lane matchup as {name} against {enemy}?",
            "Why does {enemy}'s kit directly counter {name}'s combat pattern?",
        ]

        pair_strong_en = [
            "Why is {name} a strong counter pick against {victim}?",
            "How does {name} dominate {victim} in lane?",
            "What gives {name} the winning edge against {victim}?",
            "Can {name} beat {victim} in a 1v1 matchup?",
            "Why does {name} counter and win lane against {victim}?",
            "Is {name} an effective counter pick when the enemy drafts {victim}?",
            "What kit advantages allow {name} to overwhelm {victim}?",
            "In a 1v1 lane matchup between {name} and {victim}, who has the advantage?",
            "How does {name}'s range or mobility counter {victim}?",
        ]

        # Merge counters source if dict passed or embedded
        all_counters = {}
        if counters:
            all_counters.update(counters)
        for cid, c in champions.items():
            if cid not in all_counters and "counters" in c and isinstance(c["counters"], dict):
                all_counters[cid] = c["counters"]

        sample_k_gen = 4 if split_mode == "train" else 3
        sample_k_pair = 2 if split_mode == "train" else 2

        for champ_key, data in all_counters.items():
            champ_name = data.get("champion", champ_key)
            c_chunk = c_chunks_by_name.get(champ_name.lower())
            if not c_chunk:
                continue

            neg_text = self.get_negative(c_chunk)

            # 1. General counter templates
            for tmpl in random.sample(counter_templates_en, min(sample_k_gen, len(counter_templates_en))):
                q = tmpl.format(name=champ_name)
                triplets.append(TrainingTriplet(q, c_chunk.text, neg_text, "counter_matchup"))

            # 2. Tactical weaknesses & tips templates
            if data.get("weaknesses"):
                tmpl = random.choice(tactical_weakness_templates_en)
                q = tmpl.format(name=champ_name)
                triplets.append(TrainingTriplet(q, c_chunk.text, neg_text, "counter_weakness"))

            if data.get("tactical_tips"):
                tmpl = random.choice(tactical_tip_templates_en)
                q = tmpl.format(name=champ_name)
                triplets.append(TrainingTriplet(q, c_chunk.text, neg_text, "counter_tips"))

            # 3. Counter item templates
            if data.get("counter_items"):
                for tmpl in random.sample(counter_item_templates_en, min(2, len(counter_item_templates_en))):
                    q = tmpl.format(name=champ_name)
                    triplets.append(TrainingTriplet(q, c_chunk.text, neg_text, "counter_items"))

            # 4. Specific weakAgainst pair queries
            weak_against = data.get("weakAgainst", [])
            for m in weak_against[:4]:
                enemy = m.get("champion")
                if not enemy:
                    continue
                for tmpl in random.sample(pair_weak_en, min(sample_k_pair, len(pair_weak_en))):
                    q = tmpl.format(name=champ_name, enemy=enemy)
                    triplets.append(TrainingTriplet(q, c_chunk.text, neg_text, "counter_pair_weak"))

            # 5. Specific strongAgainst pair queries
            strong_against = data.get("strongAgainst", [])
            for m in strong_against[:3]:
                victim = m.get("champion")
                if not victim:
                    continue
                for tmpl in random.sample(pair_strong_en, min(sample_k_pair, len(pair_strong_en))):
                    q = tmpl.format(name=champ_name, victim=victim)
                    triplets.append(TrainingTriplet(q, c_chunk.text, neg_text, "counter_pair_strong"))

        return triplets

    # Strategy 8: Synergy & Duo queries (Enriched Bilingual & Entity Pairs)

    def generate_synergy_queries(self, champions, synergies = None, split_mode = "all"):
        """Generate duo partner, bot lane pairing, and teamfight combo queries (EN & VI)."""
        triplets = []
        synergy_chunks = self.chunks_by_type.get("synergy", [])
        if not synergy_chunks:
            return triplets

        s_chunks_by_name = {c.entity_name.lower(): c for c in synergy_chunks}

        synergy_templates_en = [
            "Who is the best duo partner for {name}?",
            "What champions synergize best with {name}?",
            "Who pairs well with {name} in lane?",
            "What support or partner should I pick with {name}?",
            "What teamfight combos work best with {name}?",
            "Who can peel, shield, or enable {name} to carry games?",
            "Best champion pairings and synergies for {name}",
            "Why do {name} and their duo partners win games together?",
            "What crowd control champions set up {name}'s abilities and ultimate?",
            "Duo queue guide: best champion pairings to climb with {name}",
            "Which champions provide knockups or hard CC to enable {name}?",
            "Who provides the best engage or buffs when playing {name}?",
            "What ability synergies maximize {name}'s impact in teamfights?",
        ]

        pair_synergy_en = [
            "Why do {name} and {partner} work so well together?",
            "How do {name} and {partner} combo their abilities in lane?",
            "What is the duo synergy between {name} and {partner}?",
            "Why is {partner} one of the best duo partners for {name}?",
            "How should {name} and {partner} play 2v2 skirmishes and teamfights?",
            "Why are {name} and {partner} such an effective duo partnership?",
            "How do {name} and {partner} chain crowd control and abilities together in combat?",
            "What makes {partner} an ideal engage, peel, or damage partner for {name}?",
            "How do {name} and {partner} coordinate their abilities for teamfight impact?",
        ]

        all_synergies = {}
        if synergies:
            all_synergies.update(synergies)
        for cid, c in champions.items():
            if cid not in all_synergies and "synergies" in c:
                syn_val = c["synergies"]
                all_synergies[cid] = {
                    "champion": c.get("name", cid),
                    "synergies": syn_val if isinstance(syn_val, list) else syn_val.get("synergies", [])
                }

        sample_k_gen = 4 if split_mode == "train" else 3
        sample_k_pair = 2 if split_mode == "train" else 2

        for champ_key, data in all_synergies.items():
            champ_name = data.get("champion", champ_key) if isinstance(data, dict) else champ_key
            s_chunk = s_chunks_by_name.get(champ_name.lower())
            if not s_chunk:
                continue

            neg_text = self.get_negative(s_chunk)

            # 1. General templates
            for tmpl in random.sample(synergy_templates_en, min(sample_k_gen, len(synergy_templates_en))):
                q = tmpl.format(name=champ_name)
                triplets.append(TrainingTriplet(q, s_chunk.text, neg_text, "synergy_duo"))

            # 2. Specific duo pair queries
            duo_list = data.get("synergies", []) if isinstance(data, dict) else []
            for duo in duo_list[:4]:
                partner = duo.get("champion")
                if not partner:
                    continue
                for tmpl in random.sample(pair_synergy_en, min(sample_k_pair, len(pair_synergy_en))):
                    q = tmpl.format(name=champ_name, partner=partner)
                    triplets.append(TrainingTriplet(q, s_chunk.text, neg_text, "synergy_pair"))

        return triplets

    # Strategy 9: Build & Itemization queries (Enriched Bilingual & Specifics)

    def generate_build_queries(self, champions, builds = None, split_mode = "all"):
        """Generate item build, starting items, runes, and summoner spell queries (EN & VI)."""
        triplets = []
        build_chunks = self.chunks_by_type.get("build", [])
        if not build_chunks:
            return triplets

        b_chunks_by_name = {c.entity_name.lower(): c for c in build_chunks}

        build_templates_en = [
            "What is the recommended build for {name}?",
            "What are the core items to buy on {name}?",
            "What is the full 6-item build for {name}?",
            "What starting items should I buy on {name}?",
            "What summoner spells should {name} take?",
            "What is the best keystone rune for {name}?",
            "What primary and secondary runes should I run on {name}?",
            "Complete itemization guide, starting items, and rune page for {name}",
            "What boots and core legendary items does {name} build?",
            "Optimal build path, runes, and summoner spells for {name}",
            "What items give {name} their biggest power spike?",
            "What starting items and summoner spells are optimal for {name}?",
            "What does a full 6-item late game build look like for {name}?",
            "What is the optimal primary and secondary rune setup for {name}?",
            "Which items provide {name} with their most critical power spikes?",
        ]

        item_specific_en = [
            "Why is {item} a core item on {name}?",
            "Does {name} always rush {item} in their build path?",
            "How does {item} synergize with {name}'s kit?",
            "Why is {item} an essential core item for {name}?",
            "What benefits does purchasing {item} give {name} in combat?",
            "How does {item} synergize with {name}'s ability kit and playstyle?",
        ]

        keystone_specific_en = [
            "Why do players take {keystone} on {name}?",
            "What makes {keystone} the optimal keystone rune for {name}?",
            "Why is {keystone} the preferred keystone rune on {name}?",
            "What makes {keystone} the most optimal rune choice for {name}?",
        ]

        all_builds = {}
        if builds:
            all_builds.update(builds)
        for cid, c in champions.items():
            if cid not in all_builds and "builds" in c and isinstance(c["builds"], dict):
                all_builds[cid] = c["builds"]

        sample_k_gen = 5 if split_mode == "train" else 4
        sample_k_item = 2 if split_mode == "train" else 2

        for champ_key, data in all_builds.items():
            champ_name = data.get("champion", champ_key)
            b_chunk = b_chunks_by_name.get(champ_name.lower())
            if not b_chunk:
                continue

            neg_text = self.get_negative(b_chunk)

            # 1. General templates
            for tmpl in random.sample(build_templates_en, min(sample_k_gen, len(build_templates_en))):
                q = tmpl.format(name=champ_name)
                triplets.append(TrainingTriplet(q, b_chunk.text, neg_text, "build_loadout"))

            # 2. Specific core item queries
            core_items = data.get("coreItems", data.get("core_items", []))
            for item in core_items[:3]:
                if not item:
                    continue
                for tmpl in random.sample(item_specific_en, min(sample_k_item, len(item_specific_en))):
                    q = tmpl.format(name=champ_name, item=item)
                    triplets.append(TrainingTriplet(q, b_chunk.text, neg_text, "build_item_specific"))

            # 3. Specific keystone rune queries
            keystone = data.get("keystone")
            if keystone:
                tmpl = random.choice(keystone_specific_en)
                q = tmpl.format(name=champ_name, keystone=keystone)
                triplets.append(TrainingTriplet(q, b_chunk.text, neg_text, "build_keystone_specific"))

        return triplets

    # Strategy 10: Strategic Win Conditions & Power Curves (Bilingual EN/VI)

    def generate_strategic_queries(self, champions, split_mode = "all"):
        """Generate strategic playstyle, power curve, and win condition queries in English."""
        triplets = []

        strategic_templates_en = [
            "What is the primary win condition when playing {name}?",
            "How does {name} win games and close out matches?",
            "What is {name}'s power curve and when do they spike?",
            "Is {name} an early game snowballer or late game hypercarry?",
            "What playstyle category (burst, poke, dive, sustained) fits {name}?",
            "How should a team play around {name} in teamfights?",
            "Is {name} better at splitpushing or grouping with the team?",
            "What are the strategic strengths and win conditions of {name}?",
            "How do you carry games with {name}'s strategic playstyle?",
            "What is the key win condition when playing as {name}?",
            "How does {name} close out games and secure victory?",
            "At what point in the game does {name} reach peak power spikes?",
            "Is {name} an early game snowballer or a scaling late game powerhouse?",
            "What playstyle archetype (dive, poke, skirmish, frontline) suits {name}?",
            "How should the team coordinate and fight teamfights around {name}?",
            "Should {name} focus on splitpushing side lanes or grouping with the team?",
            "What are {name}'s strategic win conditions and core macro strengths?",
            "How to carry ranked games and execute {name}'s win condition?",
        ]

        sample_k = 5 if split_mode == "train" else 4

        for champ_id, champ in champions.items():
            name = champ.get("name", champ_id)
            entity_chunks = self.chunks_by_entity.get(name.lower(), [])
            overview_chunks = [c for c in entity_chunks if c.chunk_type == "overview"]

            if not overview_chunks:
                continue

            pos_chunk = overview_chunks[0]
            neg_chunk = self.get_negative(pos_chunk)

            for tmpl in random.sample(strategic_templates_en, min(sample_k, len(strategic_templates_en))):
                q = tmpl.format(name=name)
                triplets.append(TrainingTriplet(q, pos_chunk.text, neg_chunk, "strategic_playstyle"))

        return triplets

    # Strategy 11: Champion Subrole & Position queries

    def generate_subrole_and_position_queries(self, champions, split_mode = "all"):
        """Generate champion-specific queries about their subroles and lane positions in English."""
        triplets = []

        subrole_templates_en = [
            "What subrole does {name} belong to in League of Legends?",
            "What class subclass is {name}?",
            "Is {name} categorized as {subrole}?",
            "What tactical archetype and subrole describe {name}?",
            "What kind of playstyle subclass is {name}?",
            "What subclass and subrole does {name} fall under in LoL?",
            "How is {name} classified within champion classes and subroles?",
            "Is {name} considered a {subrole} champion?",
            "What tactical archetype and combat role describe {name}?",
        ]

        position_templates_en = [
            "What positions and lanes can {name} play?",
            "What is {name}'s primary lane on Summoner's Rift?",
            "Can {name} be played in {pos}?",
            "What roles and lanes are recommended for {name}?",
            "Is {name} played Top, Jungle, Mid, Bot, or Support?",
            "What lanes and map roles is {name} viable in?",
            "What is {name}'s primary lane and role on Summoner's Rift?",
            "Can {name} be effectively played in the {pos} position?",
            "What roles and positions are recommended for {name}?",
            "Does {name} play Top, Jungle, Mid, Bot, or Support?",
        ]

        sample_k_sub = 3 if split_mode == "train" else 3
        sample_k_pos = 3 if split_mode == "train" else 3

        for champ_id, champ in champions.items():
            name = champ.get("name", champ_id)
            entity_chunks = self.chunks_by_entity.get(name.lower(), [])
            overview_chunks = [c for c in entity_chunks if c.chunk_type == "overview"]
            if not overview_chunks:
                continue

            pos_chunk = overview_chunks[0]
            neg_chunk = self.get_negative(pos_chunk)

            subroles = champ.get("subroles", [])
            subrole_str = subroles[0] if subroles else "Fighter"
            for tmpl in random.sample(subrole_templates_en, min(sample_k_sub, len(subrole_templates_en))):
                q = tmpl.format(name=name, subrole=subrole_str)
                triplets.append(TrainingTriplet(q, pos_chunk.text, neg_chunk, "champ_subrole"))

            positions = champ.get("positions", [])
            pos_str = positions[0] if positions else "TOP"
            for tmpl in random.sample(position_templates_en, min(sample_k_pos, len(position_templates_en))):
                q = tmpl.format(name=name, pos=pos_str)
                triplets.append(TrainingTriplet(q, pos_chunk.text, neg_chunk, "champ_position"))

        return triplets

    # Strategy 12: Item Recipe & Build Path queries (NEW)

    def generate_item_recipe_queries(self, items, split_mode = "all"):
        """Generate recipe, build-from, build-into, and item stat queries in English."""
        triplets = []
        item_chunks = [c for c in self.chunks if c.chunk_type == "item_info"]
        if not item_chunks:
            return triplets

        item_chunks_by_name = {c.entity_name.lower(): c for c in item_chunks}

        recipe_templates_en = [
            "What items are needed to build {name}?",
            "What is the recipe and build path for {name}?",
            "What item components combine into {name}?",
            "What does {name} build into in League of Legends?",
            "How much does {name} cost in gold and what are its stats?",
            "What component items are required to craft {name}?",
            "What is the crafting recipe and component path for the item {name}?",
            "Which base items combine together to create {name}?",
            "What higher-tier or legendary items does {name} build into?",
            "How much total gold is required to buy {name} and what stats does it offer?",
        ]

        sample_k = 4 if split_mode == "train" else 3

        for item_id, item in items.items():
            name = item.get("name")
            if not name:
                continue
            chunk = item_chunks_by_name.get(name.lower())
            if not chunk:
                continue

            pos_chunk = chunk
            neg_chunk = self.get_negative(pos_chunk)

            for tmpl in random.sample(recipe_templates_en, min(sample_k, len(recipe_templates_en))):
                q = tmpl.format(name=name)
                triplets.append(TrainingTriplet(q, pos_chunk.text, neg_chunk, "item_recipe"))

        return triplets

    # Strategy 13: Rune Tree & Keystone queries (NEW)

    def generate_rune_queries(self, runes, split_mode = "all"):
        """Generate rune tree, keystone, and mechanical effect queries in English."""
        triplets = []
        rune_chunks = [c for c in self.chunks if c.chunk_type == "rune_info"]
        if not rune_chunks:
            return triplets

        rune_chunks_by_name = {c.entity_name.lower(): c for c in rune_chunks}

        rune_templates_en = [
            "Which rune path or tree does {name} belong to?",
            "What are the effects and gameplay mechanics of {name}?",
            "How does the keystone or rune {name} work in combat?",
            "What bonuses does {name} grant and who should take it?",
            "Which rune path or tree does the {name} rune belong to?",
            "What are the mechanical effects and bonuses granted by {name}?",
            "How does keystone {name} trigger and scale during skirmishes?",
            "What bonus stats does {name} grant and which champions benefit most?",
        ]

        sample_k = 3 if split_mode == "train" else 2

        by_id = runes.get("byId", runes)
        for r_id, rune in by_id.items():
            name = rune.get("name")
            if not name:
                continue
            chunk = rune_chunks_by_name.get(name.lower())
            if not chunk:
                continue

            pos_chunk = chunk
            neg_chunk = self.get_negative(pos_chunk)

            for tmpl in random.sample(rune_templates_en, min(sample_k, len(rune_templates_en))):
                q = tmpl.format(name=name)
                triplets.append(TrainingTriplet(q, pos_chunk.text, neg_chunk, "rune_tree_effect"))

        return triplets

    # Strategy 14: CC Mechanics & Combat Effect queries (NEW)

    def generate_cc_and_effect_queries(self, champions, split_mode = "all"):
        """Generate champion-specific crowd control and combat mechanics queries in English."""
        triplets = []

        cc_templates_en = [
            "What crowd control (CC) abilities does {name} have in their kit?",
            "Does {name} have hard crowd control like stun, knockup, or suppression?",
            "Does {name} have soft CC such as slows or roots?",
            "What mobility, defensive, or offensive effects (dash, shield, heal, execute) does {name} possess?",
            "What special mechanics or ability effects are unique to {name}?",
            "What crowd control (CC) mechanics does {name} have in their kit?",
            "Does {name} have hard CC like stuns, airborne knockups, or suppression?",
            "Does {name} have soft CC abilities such as slows or grounding effects?",
            "What ability effects (dash, shield, heal, execute, true damage) does {name} have?",
            "What unique mechanics or special ability effects characterize {name}?",
        ]

        sample_k = 4 if split_mode == "train" else 3

        for champ_id, champ in champions.items():
            name = champ.get("name", champ_id)
            entity_chunks = self.chunks_by_entity.get(name.lower(), [])
            overview_chunks = [c for c in entity_chunks if c.chunk_type == "overview"]
            if not overview_chunks:
                continue

            pos_chunk = overview_chunks[0]
            neg_chunk = self.get_negative(pos_chunk)

            for tmpl in random.sample(cc_templates_en, min(sample_k, len(cc_templates_en))):
                q = tmpl.format(name=name)
                triplets.append(TrainingTriplet(q, pos_chunk.text, neg_chunk, "champ_cc_effects"))

        return triplets

    # Persistence

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
    parser.add_argument("--count", type = int, default = 12000, help = "Base target count (default: 12000)")
    parser.add_argument("--train-count", type = int, default = 12000, help = "Target training count (default: 12000)")
    parser.add_argument("--val-count", type = int, default = 1200, help = "Target validation count (default: 1200)")
    parser.add_argument("--test-count", type = int, default = 1200, help = "Target test count (default: 1200)")
    parser.add_argument("--train-ratio", type = float, default = 0.8, help = "Train split ratio (default: 0.8)")
    parser.add_argument("--val-ratio", type = float, default = 0.1, help = "Val split ratio (default: 0.1)")
    parser.add_argument("--test-ratio", type = float, default = 0.1, help = "Test split ratio (default: 0.1)")
    parser.add_argument("--seed", type = int, default = 42, help = "Random seed (default: 42)")
    parser.add_argument("--preserve-eval", action = "store_true", help = "Keep existing val and test splits")
    parser.add_argument("--force-regen-eval", action = "store_true", default = True, help = "Force regenerating val and test splits")
    parser.add_argument(
        "--source",
        choices = ["mongo", "auto", "files"],
        default = "mongo",
        help = "Data source: 'mongo' (default), 'auto', or 'files'",
    )
    parser.add_argument("--mongo-uri", type = str, default = None, help = "MongoDB connection URI (default: from .env)")
    parser.add_argument("--mongo-db", type = str, default = None, help = "MongoDB database name (default: from .env)")
    args = parser.parse_args()

    champions = None
    items = None
    runes = None
    counters = None
    synergies = None
    builds = None

    # 1. Attempt loading from MongoDB if requested or auto
    if args.source in ("auto", "mongo"):
        mongo_data = load_from_mongodb(uri = args.mongo_uri, db_name = args.mongo_db)
        if mongo_data:
            champions, items, runes, counters, synergies, builds = mongo_data
        elif args.source == "mongo":
            print("[DataGenerator] ERROR: MongoDB source requested ('mongo') but connection/data was unavailable.")
            print("                Please check that MongoDB is running at mongodb://localhost:27017 and database 'lol_rag_db' exists.")
            sys.exit(1)

    # 2. Fallback to local files if MongoDB data was not loaded
    if not champions:
        processed_dir = SRC_DIR / "processors" / "processed"
        champs_path = processed_dir / "champions.json"
        items_path = processed_dir / "items.json"
        runes_path = processed_dir / "runes.json"

        if not champs_path.exists():
            print(f"Error: {champs_path} not found. Please run processors first or start MongoDB.")
            sys.exit(1)

        print(f"[DataGenerator] Loading data from files ({processed_dir})...")
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

        counters, synergies, builds = load_knowledge_base_data()
        print(f"[DataGenerator] Loaded KB data from files: {len(counters)} counters, {len(synergies)} synergies, {len(builds)} builds")

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
        target_val_count = args.val_count,
        target_test_count = args.test_count,
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

    # Save splits to src/training/ (overwrites existing files)
    training_dir = SRC_DIR / "training"
    generator.save_triplets(splits["train"], str(training_dir / "train.jsonl"))
    generator.save_triplets(splits["val"], str(training_dir / "val.jsonl"))
    generator.save_triplets(splits["test"], str(training_dir / "test.jsonl"))

    print(f"\n[DataGenerator] Splits saved: {len(splits['train'])} train, {len(splits['val'])} val, {len(splits['test'])} test.")
    print(f"Location: {training_dir}")


if __name__ == "__main__":
    main()
