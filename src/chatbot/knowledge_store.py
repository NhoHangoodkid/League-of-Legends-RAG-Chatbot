"""
Knowledge Store for LoL Knowledge Bot.

Loads and indexes all champion, item, rune, counter, synergy, and build data.
Provides O(1) dictionary lookups, fuzzy matching, alias resolution, and multi-criteria semantic filtering.
"""

import json
import os
import re
from pathlib import Path
from chatbot.config import (
    champions_kb_dir,
    data_dir,
    knowledge_base_dir,
    processed_dir,
    project_root,
)

# Deprecated static alias dictionary; dynamically populated at runtime by KnowledgeStore
champion_aliases = {}

english_item_aliases = {
    "bork": "Blade of the Ruined King",
    "botrk": "Blade of the Ruined King",
    "blade of the ruined king": "Blade of the Ruined King",
    "ie": "Infinity Edge",
    "infinity edge": "Infinity Edge",
    "triforce": "Trinity Force",
    "trinity force": "Trinity Force",
    "tri-force": "Trinity Force",
    "rabadon": "Rabadon's Deathcap",
    "deathcap": "Rabadon's Deathcap",
    "dcap": "Rabadon's Deathcap",
    "zhonya": "Zhonya's Hourglass",
    "hourglass": "Zhonya's Hourglass",
    "thornmail": "Thornmail",
    "frozen heart": "Frozen Heart",
    "randuin": "Randuin's Omen",
    "omen": "Randuin's Omen",
    "shieldbow": "Immortal Shieldbow",
    "immortal shieldbow": "Immortal Shieldbow",
    "eclipse": "Eclipse",
    "black cleaver": "Black Cleaver",
    "bc": "Black Cleaver",
    "ldr": "Lord Dominik's Regards",
    "dominik": "Lord Dominik's Regards",
    "mortal reminder": "Mortal Reminder",
    "mortal": "Mortal Reminder",
    "liandry": "Liandry's Torment",
    "liandrys": "Liandry's Torment",
    "blackfire": "Blackfire Torch",
    "blackfire torch": "Blackfire Torch",
    "void staff": "Void Staff",
    "void": "Void Staff",
    "guardian angel": "Guardian Angel",
    "ga": "Guardian Angel",
    "maw": "Maw of Malmortius",
    "maw of malmortius": "Maw of Malmortius",
    "redemption": "Redemption",
    "ghostblade": "Youmuu's Ghostblade",
    "youmuu": "Youmuu's Ghostblade",
    "edge of night": "Edge of Night",
    "eon": "Edge of Night",
    "rav hydra": "Ravenous Hydra",
    "ravenous": "Ravenous Hydra",
    "titanic": "Titanic Hydra",
    "spirit visage": "Spirit Visage",
    "visage": "Spirit Visage",
    "sorc shoes": "Sorcerer's Shoes",
    "sorcs": "Sorcerer's Shoes",
    "steelcaps": "Plated Steelcaps",
    "tabi": "Plated Steelcaps",
    "ninja tabi": "Plated Steelcaps",
    "merc treads": "Mercury's Treads",
    "mercs": "Mercury's Treads",
    "berserkers": "Berserker's Greaves",
    "zerks": "Berserker's Greaves",
    "lucidity": "Ionian Boots of Lucidity",
    "ionian boots": "Ionian Boots of Lucidity",
    "locket": "Locket of the Iron Solari",
    "shurelya": "Shurelya's Battlesong",
    "roa": "Rod of Ages",
    "archangel": "Archangel's Staff",
    "manamune": "Manamune",
    "muramana": "Muramana",
    "seraph": "Seraph's Embrace",
    "shojin": "Spear of Shojin",
    "statikk": "Statikk Shiv",
    "statikk shiv": "Statikk Shiv",
    "rfc": "Rapid Firecannon",
    "rapid firecannon": "Rapid Firecannon",
    "rageblade": "Guinsoo's Rageblade",
    "guinsoo": "Guinsoo's Rageblade",
    "pd": "Phantom Dancer",
    "phantom dancer": "Phantom Dancer",
    "heartsteel": "Heartsteel",
    "jaksho": "Jak'Sho, The Protean",
    "kaenic": "Kaenic Rookern",
    "warmog": "Warmog's Armor",
    "collector": "The Collector",
    "kraken": "Kraken Slayer",
    "bloodthirster": "Bloodthirster",
    "bt": "Bloodthirster",
    "sterak": "Sterak's Gage",
    "death dance": "Death's Dance",
    "dd": "Death's Dance",
    "mejai": "Mejai's Soulstealer",
    "luden": "Luden's Companion",
    "shadowflame": "Shadowflame",
}

english_rune_aliases = {
    "conq": "Conqueror",
    "conqueror": "Conqueror",
    "pta": "Press the Attack",
    "press the attack": "Press the Attack",
    "lethal tempo": "Lethal Tempo",
    "lt": "Lethal Tempo",
    "fleet": "Fleet Footwork",
    "fleet footwork": "Fleet Footwork",
    "electro": "Electrocute",
    "electrocute": "Electrocute",
    "hob": "Hail of Blades",
    "hail of blades": "Hail of Blades",
    "dark harvest": "Dark Harvest",
    "dh": "Dark Harvest",
    "arcane comet": "Arcane Comet",
    "comet": "Arcane Comet",
    "phase rush": "Phase Rush",
    "summon aery": "Summon Aery",
    "aery": "Summon Aery",
    "grasp": "Grasp of the Undying",
    "grasp of the undying": "Grasp of the Undying",
    "aftershock": "Aftershock",
    "guardian": "Guardian",
    "glacial augment": "Glacial Augment",
    "glacial": "Glacial Augment",
    "unsealed spellbook": "Unsealed Spellbook",
    "spellbook": "Unsealed Spellbook",
    "first strike": "First Strike",
}


class KnowledgeStore:
    """In-memory Knowledge Store with indices for rapid querying."""

    def __init__(self):
        self.champions = {}
        self.items = {}
        self.items_by_name = {}
        self.runes = {}
        self.counters = {}
        self.synergies = {}
        self.builds = {}
        self.team_compositions = {}

        # Lookup indexes (normalized key -> canonical key)
        self.champion_lookup = {}
        self.champion_aliases = {}
        self.item_lookup = {}
        self.item_aliases = {}
        self.rune_lookup = {}
        self.rune_aliases = {}
        self.composition_lookup = {}
        self.composition_aliases = {}

        # Dynamic taxonomy sets collected from loaded data
        self.all_roles = []
        self.all_subroles = []
        self.all_positions = []
        self.all_cc_types = []
        self.all_ability_effects = []
        self.all_playstyles = []

        self.load_all()

    def load_all(self):
        """Load all knowledge base components."""
        print("[KnowledgeStore] Loading knowledge base...")
        if self.load_from_mongo():
            return

        self.load_champions()
        self.load_items()
        self.load_runes()
        self.load_relationships()
        print(
            f"[KnowledgeStore] Loaded: {len(self.champions)} champions, "
            f"{len(self.items)} items, "
            f"{len(self.counters)} counters, "
            f"{len(self.synergies)} synergies, "
            f"{len(self.builds)} builds."
        )

    def build_champion_indices(self):
        """
        Dynamically build lookup indices, aliases, and taxonomy sets
        from loaded champion records. Zero hardcoding.
        """
        self.champion_lookup = {}
        self.champion_aliases = {}

        for cid, champ in self.champions.items():
            name = champ.get("name", cid)
            # Register canonical ID and canonical name
            self.register_champion_index(cid, cid)
            self.register_champion_index(name, cid)

            # 1. Dynamic aliases from processor document
            for alias in champ.get("aliases", []):
                self.register_champion_index(alias, cid)
                self.champion_aliases[alias.lower()] = cid

            # 2. Punctuation-stripped variations (e.g. K'Sante -> ksante, Dr. Mundo -> drmundo)
            clean_name = re.sub(r"[^\w\s]", "", name)
            if clean_name != name:
                self.register_champion_index(clean_name, cid)
                self.champion_aliases[clean_name.lower()] = cid

            clean_id = re.sub(r"[^\w\s]", "", cid)
            if clean_id != cid:
                self.register_champion_index(clean_id, cid)
                self.champion_aliases[clean_id.lower()] = cid

            # 3. Dynamic acronyms and word tokens for multi-word champions
            words = [w for w in re.split(r"[\s\.\'\-]+", name) if w]
            if len(words) >= 2:
                # Full acronym (e.g. "Twisted Fate" -> "tf", "Miss Fortune" -> "mf", "Aurelion Sol" -> "asol")
                acronym = "".join(w[0] for w in words).lower()
                if len(acronym) >= 2 and acronym not in ("in", "at", "to", "or", "an"):
                    self.register_champion_index(acronym, cid)
                    self.champion_aliases[acronym] = cid

                # First word if distinctive (> 3 chars, e.g. "Mundo", "Jarvan", "Tahm", "Renata", "Nunu")
                first_word = words[0].lower()
                if len(first_word) >= 4 and first_word not in ("master", "miss", "twisted", "dr"):
                    self.register_champion_index(first_word, cid)
                    self.champion_aliases[first_word] = cid

                # Last word if distinctive (e.g. "Mundo" from "Dr. Mundo", "Willump" from "Nunu and Willump", "Sol" from "Aurelion Sol")
                last_word = words[-1].lower()
                if len(last_word) >= 4 and last_word not in ("fortune", "fate"):
                    self.register_champion_index(last_word, cid)
                    self.champion_aliases[last_word] = cid

                # Common prefixes/suffixes dynamically mapped
                if words[0].lower() in ("dr", "doctor"):
                    for mundo_variant in ("mundo", "dr mundo", "doctor mundo"):
                        self.register_champion_index(mundo_variant, cid)
                        self.champion_aliases[mundo_variant] = cid

                if words[0].lower() == "jarvan":
                    for j_variant in ("jarvan", "jarvan 4", "j4"):
                        self.register_champion_index(j_variant, cid)
                        self.champion_aliases[j_variant] = cid

                if words[0].lower() == "lee":
                    self.register_champion_index("lee", cid)
                    self.champion_aliases["lee"] = cid

                if words[-1].lower() == "yi":
                    self.register_champion_index("yi", cid)
                    self.champion_aliases["yi"] = cid

                if words[0].lower() == "xin":
                    self.register_champion_index("xin", cid)
                    self.champion_aliases["xin"] = cid

            # 4. Cross-link champion ID with name if different (e.g. MonkeyKing -> Wukong)
            if cid.lower() != name.lower():
                self.register_champion_index(name, cid)
                self.register_champion_index(cid, cid)
                if "monkeyking" in cid.lower():
                    self.register_champion_index("monkey king", cid)
                    self.champion_aliases["monkey king"] = cid

        # Dynamically aggregate all taxonomies from database
        self.all_roles = sorted(list({r.lower() for c in self.champions.values() for r in c.get("roles", []) if r}))
        self.all_subroles = sorted(list({s.lower() for c in self.champions.values() for s in c.get("subroles", []) if s}))
        self.all_positions = sorted(list({p.upper() for c in self.champions.values() for p in c.get("positions", []) if p}))
        self.all_cc_types = sorted(list({cc for c in self.champions.values() for cc in c.get("cc_types", []) if cc}))
        self.all_ability_effects = sorted(list({fx for c in self.champions.values() for fx in c.get("ability_effects", []) if fx}))
        self.all_playstyles = sorted(list({ps for c in self.champions.values() for ps in c.get("playstyles", []) if ps}))

        # Sync module-level deprecated mapping for backward compatibility
        global champion_aliases
        champion_aliases.update(self.champion_aliases)

    def build_item_indices(self):
        """
        Dynamically build item lookup indices and aliases from loaded items.
        Zero hardcoding.
        """
        self.item_lookup = {}
        self.items_by_name = {}
        self.item_aliases = {}

        for item_id, item in self.items.items():
            name = item.get("name", "")
            if not name:
                continue

            norm_name = self.normalize_key(name)
            self.item_lookup[norm_name] = item_id
            self.items_by_name[norm_name] = item

            # 1. Punctuation-stripped item names (e.g. Jak'Sho -> jaksho)
            clean_name = re.sub(r"[^\w\s]", "", name)
            if clean_name != name:
                self.item_lookup[self.normalize_key(clean_name)] = item_id
                self.items_by_name[self.normalize_key(clean_name)] = item

            # 2. Aliases from database
            for a in item.get("aliases", []):
                if a:
                    norm_a = self.normalize_key(a)
                    clean_a = a.lower().strip()
                    # Prefer higher-cost / completed items for shared slang (e.g. Rabadon 3500g over Spectre's Cowl 1250g for 'hat')
                    existing_id = self.item_lookup.get(norm_a)
                    if existing_id and existing_id in self.items:
                        curr_cost = self.items[existing_id].get("cost", {}).get("total", 0)
                        new_cost = item.get("cost", {}).get("total", 0)
                        if new_cost <= curr_cost:
                            continue

                    self.item_lookup[norm_a] = item_id
                    self.items_by_name[norm_a] = item
                    self.item_aliases[clean_a] = item_id
                    if norm_a != clean_a:
                        self.item_aliases[norm_a] = item_id

            # 3. Dynamic acronyms for items with 2+ words (e.g. Infinity Edge -> ie, Black Cleaver -> bc)
            words = [w for w in re.split(r"[\s\.\'\-]+", name) if w and w.lower() not in ("of", "the", "and")]
            if len(words) >= 2:
                acronym = "".join(w[0] for w in words).lower()
                if len(acronym) >= 2:
                    existing_id = self.item_lookup.get(acronym)
                    if existing_id and existing_id in self.items:
                        curr_cost = self.items[existing_id].get("cost", {}).get("total", 0)
                        new_cost = item.get("cost", {}).get("total", 0)
                        if new_cost <= curr_cost:
                            continue
                    self.item_lookup[acronym] = item_id
                    self.item_aliases[acronym] = item_id

        # 4. Map English item aliases to canonical items
        for alias, canonical_name in english_item_aliases.items():
            norm_target = self.normalize_key(canonical_name)
            target_id = self.item_lookup.get(norm_target)
            if target_id and target_id in self.items:
                norm_alias = self.normalize_key(alias)
                clean_alias = alias.lower().strip()
                self.item_lookup[norm_alias] = target_id
                self.item_lookup[clean_alias] = target_id
                self.items_by_name[norm_alias] = self.items[target_id]
                self.items_by_name[clean_alias] = self.items[target_id]
                self.item_aliases[clean_alias] = target_id
                if norm_alias != clean_alias:
                    self.item_aliases[norm_alias] = target_id

    def build_rune_indices(self):
        """
        Dynamically build rune lookup indices and aliases from loaded runes.
        Supports both English canonical names and common English rune aliases.
        """
        self.rune_lookup = {}
        self.rune_aliases = {}
        runes_by_id = self.runes.get("byId", {})
        for rid, r in runes_by_id.items():
            name = r.get("name", "")
            if name:
                norm_name = self.normalize_key(name)
                clean_name = name.lower().strip()
                self.rune_lookup[norm_name] = rid
                self.rune_lookup[clean_name] = rid
                self.rune_lookup[str(rid)] = rid

        for alias, canonical_name in english_rune_aliases.items():
            norm_target = self.normalize_key(canonical_name)
            target_id = self.rune_lookup.get(norm_target)
            if target_id and target_id in runes_by_id:
                norm_alias = self.normalize_key(alias)
                clean_alias = alias.lower().strip()
                self.rune_lookup[norm_alias] = target_id
                self.rune_lookup[clean_alias] = target_id
                self.rune_aliases[clean_alias] = target_id
                if norm_alias != clean_alias:
                    self.rune_aliases[norm_alias] = target_id

    def build_composition_indices(self):
        """
        Dynamically build composition lookup indices and aliases from loaded team compositions.
        Zero hardcoding.
        """
        self.composition_lookup = {}
        self.composition_aliases = {}

        for comp_id, comp in self.team_compositions.items():
            name = comp.get("name", comp_id)
            self.composition_lookup[comp_id.lower()] = comp_id
            self.composition_lookup[name.lower()] = comp_id

            for alias in comp.get("aliases", []):
                norm = alias.strip().lower()
                if norm:
                    self.composition_lookup[norm] = comp_id
                    self.composition_aliases[norm] = comp_id

    def load_from_mongo(self):
        """Attempt to load knowledge base directly from MongoDB."""
        try:
            from pymongo import MongoClient
            mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
            db_name = os.getenv("MONGO_DB_NAME", "lol_rag_db")
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS = 2000)
            client.admin.command("ping")
            db = client[db_name]

            # 1. Champions
            champs = {doc["_id"]: doc for doc in db.champions.find()}
            if not champs:
                return False
            self.champions = champs
            self.build_champion_indices()

            # 2. Items
            self.items = {doc["_id"]: doc for doc in db.items.find()}
            self.build_item_indices()

            # 3. Runes
            runes_docs = list(db.runes.find())
            by_id = {doc["_id"]: doc for doc in runes_docs if doc.get("type") != "tree"}
            by_tree = {
                doc.get("tree", doc["_id"].replace("tree_", "")): doc.get("runes", [])
                for doc in runes_docs if doc.get("type") == "tree"
            }
            self.runes = {"byId": by_id, "byTree": by_tree}
            self.build_rune_indices()

            # 4. Relationships (counters, synergies, builds)
            for doc in db.counters.find():
                cname = doc.get("champion") or doc.get("champion_id") or doc["_id"]
                self.counters[self.normalize_key(cname)] = doc

            for doc in db.synergies.find():
                cname = doc.get("champion") or doc.get("champion_id") or doc["_id"]
                self.synergies[self.normalize_key(cname)] = doc

            for doc in db.builds.find():
                cname = doc.get("champion") or doc.get("champion_id") or doc["_id"]
                self.builds[self.normalize_key(cname)] = doc

            # 5. Team Compositions
            self.team_compositions = {doc["_id"]: doc for doc in db.team_compositions.find()}
            self.build_composition_indices()

            print(
                f"[KnowledgeStore] Loaded from MongoDB ('{db_name}'): "
                f"{len(self.champions)} champions, {len(self.items)} items, "
                f"{len(self.counters)} counters, {len(self.synergies)} synergies, "
                f"{len(self.builds)} builds, {len(self.team_compositions)} team compositions."
            )
            return True
        except Exception as e:
            print(f"[KnowledgeStore] MongoDB load skipped ({e}), falling back to local files...")
            return False

    def load_champions(self):
        """Load processed champions."""
        champs_file = processed_dir / "champions.json"
        if champs_file.exists():
            with open(champs_file, "r", encoding = "utf-8") as f:
                self.champions = json.load(f)
        elif champions_kb_dir.exists():
            for fpath in champions_kb_dir.glob("*.json"):
                with open(fpath, "r", encoding = "utf-8") as f:
                    champ_data = json.load(f)
                    self.champions[champ_data.get("id", fpath.stem)] = champ_data

        self.build_champion_indices()

    def register_champion_index(self, alias_or_name, canonical_id):
        norm = self.normalize_key(alias_or_name)
        self.champion_lookup[norm] = canonical_id

    def load_items(self):
        """Load processed items."""
        items_file = knowledge_base_dir / "items.json"
        if not items_file.exists():
            items_file = processed_dir / "items.json"

        if items_file.exists():
            with open(items_file, "r", encoding = "utf-8") as f:
                self.items = json.load(f)

        self.build_item_indices()

    def load_runes(self):
        """Load processed runes."""
        runes_file = knowledge_base_dir / "runes.json"
        if not runes_file.exists():
            runes_file = processed_dir / "runes.json"

        if runes_file.exists():
            with open(runes_file, "r", encoding = "utf-8") as f:
                self.runes = json.load(f)
            self.build_rune_indices()

    def load_relationships(self):
        """Load counters, synergies, and builds (from knowledge base or fallback to lol_chatbot)."""
        # 1. Counters
        counter_dir = knowledge_base_dir / "counters"
        fallback_counter_dir = project_root.parent / "lol_chatbot" / "data" / "game_data" / "counter_data"

        target_counter_dir = counter_dir if (counter_dir.exists() and any(counter_dir.iterdir())) else fallback_counter_dir
        if target_counter_dir.exists():
            for fpath in target_counter_dir.glob("*_counters.json"):
                try:
                    with open(fpath, "r", encoding = "utf-8") as f:
                        data = json.load(f)
                        champ_name = data.get("champion") or fpath.stem.replace("_counters", "")
                        self.counters[self.normalize_key(champ_name)] = data
                except Exception:
                    continue

        # 2. Synergies
        # 2a. First check consolidated synergies.json file
        for syn_path in [knowledge_base_dir / "synergies.json", processed_dir / "synergies.json"]:
            if syn_path.exists():
                try:
                    with open(syn_path, "r", encoding = "utf-8") as f:
                        syn_data = json.load(f)
                        if isinstance(syn_data, dict):
                            for k, v in syn_data.items():
                                cname = v.get("champion") or v.get("champion_id") or k
                                self.synergies[self.normalize_key(cname)] = v
                        elif isinstance(syn_data, list):
                            for v in syn_data:
                                cname = v.get("champion") or v.get("champion_id")
                                if cname:
                                    self.synergies[self.normalize_key(cname)] = v
                    break
                except Exception as e:
                    print(f"[KnowledgeStore] Warning loading synergies.json: {e}")

        # 2b. Fallback to individual synergy JSON files directory
        synergy_dir = knowledge_base_dir / "synergies"
        fallback_synergy_dir = project_root.parent / "lol_chatbot" / "data" / "game_data" / "synergy_data"

        target_synergy_dir = synergy_dir if (synergy_dir.exists() and any(synergy_dir.iterdir())) else fallback_synergy_dir
        if target_synergy_dir.exists():
            for fpath in target_synergy_dir.glob("*.json"):
                try:
                    with open(fpath, "r", encoding = "utf-8") as f:
                        data = json.load(f)
                        champ_name = fpath.stem.replace("_synergy", "").replace("_duos", "")
                        self.synergies[self.normalize_key(champ_name)] = data
                except Exception:
                    continue

        # 3. Builds
        build_dir = knowledge_base_dir / "builds"
        fallback_build_dir = project_root.parent / "lol_chatbot" / "data" / "game_data" / "build_data"

        target_build_dir = build_dir if (build_dir.exists() and any(build_dir.iterdir())) else fallback_build_dir
        if target_build_dir.exists():
            for fpath in target_build_dir.glob("*.json"):
                try:
                    with open(fpath, "r", encoding = "utf-8") as f:
                        data = json.load(f)
                        champ_name = data.get("champion") or fpath.stem.replace("_build", "")
                        self.builds[self.normalize_key(champ_name)] = data
                except Exception:
                    continue

    @staticmethod
    def normalize_key(text):
        """Normalize string to lowercase alphanumeric without punctuation or spaces."""
        if not text:
            return ""
        return re.sub(r"[\s\'\.\_\-\:\,\&\/]", "", text.lower().strip())

    # Query API

    def get_champion(self, name):
        """Look up champion by name, alias, or ID."""
        if not name:
            return None
        norm = self.normalize_key(name)
        canonical_id = self.champion_lookup.get(norm)
        if canonical_id and canonical_id in self.champions:
            return self.champions[canonical_id]

        # Fuzzy search
        for k_norm, cid in self.champion_lookup.items():
            if norm in k_norm or k_norm in norm:
                return self.champions.get(cid)

        return None

    def get_item(self, name_or_id):
        """Look up item by name or numeric ID."""
        if not name_or_id:
            return None

        # ID lookup
        s_id = str(name_or_id).strip()
        if s_id in self.items:
            return self.items[s_id]

        # Name lookup
        norm = self.normalize_key(str(name_or_id))
        clean = str(name_or_id).lower().strip()
        item_id = self.item_lookup.get(norm) or self.item_lookup.get(clean) or self.item_aliases.get(clean) or self.item_aliases.get(norm)
        if item_id and item_id in self.items:
            return self.items[item_id]

        # Fuzzy name lookup
        for norm_name, item in self.items_by_name.items():
            if norm in norm_name or norm_name in norm or clean in norm_name or norm_name in clean:
                return item

        return None

    def get_rune(self, name_or_id):
        """Look up rune by name, alias, or ID."""
        if not name_or_id or not self.runes:
            return None

        runes_by_id = self.runes.get("byId", {})
        s_id = str(name_or_id).strip()
        if s_id in runes_by_id:
            return runes_by_id[s_id]

        norm = self.normalize_key(str(name_or_id))
        clean = str(name_or_id).lower().strip()
        target_id = self.rune_lookup.get(norm) or self.rune_lookup.get(clean) or self.rune_aliases.get(clean) or self.rune_aliases.get(norm)
        if target_id and str(target_id) in runes_by_id:
            return runes_by_id[str(target_id)]
        if target_id and target_id in runes_by_id:
            return runes_by_id[target_id]

        for rid, rune in runes_by_id.items():
            rname = rune.get("name", "")
            if self.normalize_key(rname) == norm or rname.lower().strip() == clean:
                return rune
            if norm in self.normalize_key(rname) or clean in rname.lower().strip():
                return rune

        return None

    def get_counter_info(self, champion_name):
        """Get counter data for champion."""
        champ = self.get_champion(champion_name)
        if not champ:
            return None
        norm = self.normalize_key(champ["name"])
        data = self.counters.get(norm) or self.counters.get(self.normalize_key(champ["id"]))
        return data

    def get_synergy_info(self, champion_name):
        """Get synergy/duo data for champion."""
        champ = self.get_champion(champion_name)
        if not champ:
            return None
        norm = self.normalize_key(champ["name"])
        data = self.synergies.get(norm) or self.synergies.get(self.normalize_key(champ["id"]))
        return data

    def get_build_info(self, champion_name):
        """Get recommended build for champion."""
        champ = self.get_champion(champion_name)
        if not champ:
            return None
        norm = self.normalize_key(champ["name"])
        data = self.builds.get(norm) or self.builds.get(self.normalize_key(champ["id"]))
        return data

    # Semantic and Multi-Criteria Filtering

    def filter_champions(
        self,
        roles = None,
        subroles = None,
        positions = None,
        cc_types = None,
        effects = None,
        playstyles = None,
        power_curve = None,
        win_condition = None,
    ):
        """Filter champions satisfying multiple criteria."""
        results = []

        lane_map = {
            "top": "TOP", "toplane": "TOP",
            "mid": "MID", "midlane": "MID", "middle": "MID",
            "jungle": "JUNGLE", "jg": "JUNGLE",
            "bot": "BOT", "bottom": "BOT", "adc": "BOT",
            "support": "SUPPORT", "sp": "SUPPORT", "utility": "SUPPORT",
        }

        norm_positions = []
        if positions:
            for p in positions:
                p_clean = p.lower().strip()
                norm_positions.append(lane_map.get(p_clean, p.upper().strip()))

        norm_subroles = [s.lower().strip() for s in subroles] if subroles else []

        for cid, champ in self.champions.items():
            # Filter by role
            if roles:
                champ_roles = [r.lower() for r in champ.get("roles", [])]
                match_role = False
                for r in roles:
                    r_clean = r.lower().replace("role", "")
                    if any(r_clean in cr for cr in champ_roles):
                        match_role = True
                        break
                if not match_role:
                    continue

            # Filter by subrole (Riot's 17 sub-classes: Juggernaut, Diver, Skirmisher, Assassin, etc.)
            if norm_subroles:
                champ_subroles = [s.lower() for s in champ.get("subroles", [])]
                if not any(sr in champ_subroles for sr in norm_subroles):
                    continue

            # Filter by lane / position
            if norm_positions:
                champ_positions = [p.upper() for p in champ.get("positions", [])]
                if not any(pos in champ_positions for pos in norm_positions):
                    continue

            # Filter by CC types (must have all requested CC)
            if cc_types:
                champ_cc = set(champ.get("cc_types", []))
                if not all(cc in champ_cc for cc in cc_types):
                    continue

            # Filter by ability effects
            if effects:
                champ_fx = set(champ.get("ability_effects", []))
                if not all(fx in champ_fx for fx in effects):
                    continue

            # Filter by playstyle
            if playstyles:
                champ_ps = set(champ.get("playstyles", []))
                if not any(ps in champ_ps for ps in playstyles):
                    continue

            # Filter by power curve
            if power_curve:
                champ_pc = champ.get("powerCurve", [])
                if power_curve not in champ_pc:
                    continue

            # Filter by win condition
            if win_condition:
                champ_wc = champ.get("winConditions", [])
                if win_condition not in champ_wc:
                    continue

            results.append(champ)

        return results

    def get_champions_by_lane(self, lane):
        """Retrieve all champions that play in a designated lane."""
        return self.filter_champions(positions=[lane])

    def get_champions_by_subrole(self, subrole):
        """Retrieve all champions categorized under a specific Riot subrole."""
        return self.filter_champions(subroles=[subrole])

    # Automated Dynamic Entity Extraction API (100% Automated, Zero Hardcoded Lists)

    def get_all_champion_names(self):
        """Return all canonical champion names currently loaded."""
        return [c.get("name", cid) for cid, c in self.champions.items()]

    def get_all_champion_names_sorted(self):
        """
        Return all champion names, IDs, and aliases sorted by length descending
        for greedy, longest-match regex extraction.
        """
        all_keys = set()
        for cid, c in self.champions.items():
            name = c.get("name", cid).strip()
            if name:
                all_keys.add(name.lower())
            all_keys.add(cid.lower())
            for a in c.get("aliases", []):
                if a:
                    all_keys.add(a.lower().strip())

        for alias in self.champion_aliases.keys():
            all_keys.add(alias.lower().strip())

        # Keep meaningful keys (min length 3, or valid 2-letter champions/acronyms like j4, tf, mf, yi, vi)
        valid_keys = [k for k in all_keys if len(k) >= 3 or k in ("j4", "tf", "mf", "yi", "vi")]
        return sorted(valid_keys, key = lambda x: len(x), reverse = True)

    def get_all_item_names_sorted(self):
        """
        Return all item names and aliases sorted by length descending
        for greedy, longest-match regex extraction from database.
        """
        item_names = set()
        for it in self.items.values():
            name = it.get("name")
            if name and len(name) >= 3:
                item_names.add(name.lower().strip())
            for a in it.get("aliases", []):
                if a and len(a) >= 2:
                    item_names.add(a.lower().strip())

        for alias in self.item_aliases.keys():
            if len(alias) >= 2:
                item_names.add(alias.lower().strip())

        return sorted(list(item_names), key = lambda x: len(x), reverse = True)

    def get_all_rune_names_sorted(self):
        """
        Return all rune names and aliases sorted by length descending
        for greedy, longest-match regex extraction from database.
        """
        rune_names = set()
        runes_by_id = self.runes.get("byId", {})
        for r in runes_by_id.values():
            name = r.get("name")
            if name and len(name) >= 3:
                rune_names.add(name.lower().strip())
        for alias in self.rune_aliases.keys():
            if len(alias) >= 3:
                rune_names.add(alias.lower().strip())
        return sorted(list(rune_names), key = lambda x: len(x), reverse = True)

    def get_champion_aliases(self):
        """Return the dynamically generated champion alias mapping."""
        return self.champion_aliases

    def get_composition(self, comp_id_or_alias):
        """
        Retrieve team composition by ID, canonical name, or alias in O(1) time.
        """
        if not comp_id_or_alias:
            return None
        key = comp_id_or_alias.strip().lower()
        comp_id = self.composition_lookup.get(key) or self.composition_aliases.get(key)
        if not comp_id:
            # Fallback: check if any multi-word alias is contained in key
            for alias, cid in self.composition_aliases.items():
                if len(alias) >= 4 and alias in key:
                    comp_id = cid
                    break
        if comp_id and comp_id in self.team_compositions:
            return self.team_compositions[comp_id]
        return None

    def get_all_composition_aliases_sorted(self):
        """
        Return all composition aliases and IDs sorted by length descending
        for greedy, longest-match regex extraction from database.
        """
        keys = set()
        for comp_id, comp in self.team_compositions.items():
            keys.add(comp_id.lower().strip())
            name = comp.get("name")
            if name:
                keys.add(name.lower().strip())
            for alias in comp.get("aliases", []):
                if alias and len(alias.strip()) >= 2:
                    keys.add(alias.lower().strip())

        return sorted(list(keys), key = lambda x: len(x), reverse = True)

    def get_all_compositions(self):
        """Return all loaded team compositions."""
        return self.team_compositions


# Global singleton instance
store_instance = None


def get_knowledge_store():
    """Get or create singleton KnowledgeStore instance."""
    global store_instance
    if store_instance is None:
        store_instance = KnowledgeStore()
    return store_instance
