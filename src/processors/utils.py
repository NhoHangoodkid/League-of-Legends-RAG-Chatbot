"""
Utility functions and path configurations for data processors.

Centralizes paths for raw data sources and processed data outputs,
along with common JSON I/O, logging, and name normalization utilities.
"""

import json
import re
from pathlib import Path


# Path Configuration

# Processors directory: src/processors
PROCESSORS_DIR = Path(__file__).resolve().parent

# Source root directory: src/
SRC_DIR = PROCESSORS_DIR.parent

# Project root directory
PROJECT_ROOT = SRC_DIR.parent

# Data directories (Standard output is in src/processors/processed)
PROCESSED_DIR = PROCESSORS_DIR / "processed"


def find_raw_dir():
    """
    Locate the raw data directory with fallbacks:
    1. src/collectors/raw (Active storage)
    2. src/pipeline/collectors/raw
    3. data/raw
    """
    candidate_paths = [
        SRC_DIR / "collectors" / "raw",
        SRC_DIR / "pipeline" / "collectors" / "raw",
        PROJECT_ROOT / "data" / "raw",
        SRC_DIR / "data" / "raw",
    ]
    for path in candidate_paths:
        if path.exists() and any(path.iterdir()):
            return path

    # Default to standard collectors raw dir
    return SRC_DIR / "collectors" / "raw"


RAW_DIR = find_raw_dir()

# Raw source subdirectories
DDRAGON_RAW_DIR = RAW_DIR / "ddragon"
CDRAGON_RAW_DIR = RAW_DIR / "cdragon"
MERAKI_RAW_DIR = RAW_DIR / "meraki"
LORE_RAW_DIR = RAW_DIR / "lore"


def ensure_dirs():
    """Ensure all processed and raw directories exist."""
    for d in [PROCESSED_DIR, DDRAGON_RAW_DIR, CDRAGON_RAW_DIR, MERAKI_RAW_DIR, LORE_RAW_DIR]:
        d.mkdir(parents = True, exist_ok = True)


# Champion Name Normalization & Alias Registry

# Maps variant names/IDs → canonical champion ID used in DDragon.
# This handles discrepancies across DDragon, CDragon, Meraki, Lore, and user queries.
CHAMPION_ALIASES = {
    # CDragon capitalization mismatch
    "FiddleSticks": "Fiddlesticks",
    # Lore data key mismatch
    "RenataGlasc": "Renata",
    "Norra": "Norra",  # Lore-only; may not exist in DDragon yet
    # Internal ID vs display name
    "MonkeyKing": "MonkeyKing",  # Canonical DDragon ID; display name is Wukong
    "Wukong": "MonkeyKing",
    # Common user-typed variants → canonical ID
    "Lee Sin": "LeeSin",
    "LeeSin": "LeeSin",
    "LeBlanc": "Leblanc",
    "Leblanc": "Leblanc",
    "Dr. Mundo": "DrMundo",
    "Dr Mundo": "DrMundo",
    "DrMundo": "DrMundo",
    "Mundo": "DrMundo",
    "Twisted Fate": "TwistedFate",
    "TwistedFate": "TwistedFate",
    "Master Yi": "MasterYi",
    "MasterYi": "MasterYi",
    "Miss Fortune": "MissFortune",
    "MissFortune": "MissFortune",
    "MF": "MissFortune",
    "Jarvan IV": "JarvanIV",
    "JarvanIV": "JarvanIV",
    "J4": "JarvanIV",
    "Jarvan": "JarvanIV",
    "Kog'Maw": "KogMaw",
    "KogMaw": "KogMaw",
    "Rek'Sai": "RekSai",
    "RekSai": "RekSai",
    "Cho'Gath": "Chogath",
    "Chogath": "Chogath",
    "ChoGath": "Chogath",
    "Vel'Koz": "Velkoz",
    "Velkoz": "Velkoz",
    "VelKoz": "Velkoz",
    "Kha'Zix": "Khazix",
    "Khazix": "Khazix",
    "KhaZix": "Khazix",
    "Kai'Sa": "Kaisa",
    "Kaisa": "Kaisa",
    "KaiSa": "Kaisa",
    "K'Sante": "KSante",
    "KSante": "KSante",
    "Xin Zhao": "XinZhao",
    "XinZhao": "XinZhao",
    "Aurelion Sol": "AurelionSol",
    "AurelionSol": "AurelionSol",
    "ASol": "AurelionSol",
    "Tahm Kench": "TahmKench",
    "TahmKench": "TahmKench",
    "Bel'Veth": "Belveth",
    "Belveth": "Belveth",
    "BelVeth": "Belveth",
    "Nunu & Willump": "Nunu",
    "Nunu": "Nunu",
    "Renata Glasc": "Renata",
    "Renata": "Renata",
    # Wild Rift prefix filter
    "Jade_": "__SKIP__",
}

# Reverse lookup: canonical ID → list of known aliases (for search enrichment)
_REVERSE_ALIASES = {}
for _alias, _canonical in CHAMPION_ALIASES.items():
    if _canonical == "__SKIP__":
        continue
    if _canonical not in _REVERSE_ALIASES:
        _REVERSE_ALIASES[_canonical] = []
    if _alias != _canonical and _alias not in _REVERSE_ALIASES[_canonical]:
        _REVERSE_ALIASES[_canonical].append(_alias)


def get_champion_aliases(canonical_id):
    """Get all known aliases for a canonical champion ID."""
    return _REVERSE_ALIASES.get(canonical_id, [])


def normalize_champion_id(raw_key):
    """
    Normalize any champion name/key variant to the canonical DDragon ID.

    Handles:
    - CDragon: FiddleSticks → Fiddlesticks
    - Lore: RenataGlasc → Renata
    - User queries: 'Lee Sin' → 'LeeSin', 'Wukong' → 'MonkeyKing'
    - Wild Rift: Jade_* → None (skip)

    Returns None if the key should be skipped (e.g. Wild Rift entries).
    """
    if not raw_key:
        return None

    # Skip Wild Rift Jade_ entries
    if raw_key.startswith("Jade_"):
        return None

    # Direct alias lookup
    if raw_key in CHAMPION_ALIASES:
        result = CHAMPION_ALIASES[raw_key]
        if result == "__SKIP__":
            return None
        return result

    # Already a clean canonical ID (no spaces, no special chars)
    return raw_key


def build_lore_key_map(lore_keys, master_ids):
    """
    Build a mapping from lore data keys to canonical champion IDs.

    Handles mismatches like RenataGlasc → Renata.
    Returns dict of {lore_key: canonical_id}.
    """
    lore_map = {}
    for lk in lore_keys:
        canonical = normalize_champion_id(lk)
        if canonical and canonical in master_ids:
            lore_map[lk] = canonical
        elif lk in master_ids:
            lore_map[lk] = lk
    return lore_map


# Item Stat Key Normalization

# Maps Riot's internal stat property names to human-readable keys.
ITEM_STAT_MAPPING = {
    # Flat stats
    "FlatPhysicalDamageMod": "attack_damage",
    "FlatMagicDamageMod": "ability_power",
    "FlatHPPoolMod": "health",
    "FlatMPPoolMod": "mana",
    "FlatArmorMod": "armor",
    "FlatSpellBlockMod": "magic_resist",
    "FlatHPRegenMod": "health_regen",
    "FlatMPRegenMod": "mana_regen",
    "FlatCritChanceMod": "crit_chance",
    "FlatMovementSpeedMod": "flat_move_speed",
    # Percent stats
    "PercentAttackSpeedMod": "attack_speed",
    "PercentMovementSpeedMod": "move_speed",
    "PercentLifeStealMod": "life_steal",
    "PercentArmorPenetrationMod": "armor_pen_pct",
    "PercentMagicPenetrationMod": "magic_pen_pct",
    # Common CDragon keys (already clean-ish)
    "attack_damage": "attack_damage",
    "ability_power": "ability_power",
    "health": "health",
    "mana": "mana",
    "armor": "armor",
    "magic_resist": "magic_resist",
    "attack_speed": "attack_speed",
    "ability_haste": "ability_haste",
    "crit_chance": "crit_chance",
    "move_speed": "move_speed",
    "lethality": "lethality",
    "life_steal": "life_steal",
    "omnivamp": "omnivamp",
    "magic_penetration": "magic_penetration",
    "armor_penetration": "armor_penetration",
    "heal_and_shield_power": "heal_and_shield_power",
}


def normalize_item_stats(raw_stats):
    """
    Normalize Riot's internal stat keys to human-readable form.

    Example: {'FlatPhysicalDamageMod': 40} → {'attack_damage': 40}
    Filters out zero-value stats.
    """
    normalized = {}
    for key, value in raw_stats.items():
        if value == 0 or value is None:
            continue
        clean_key = ITEM_STAT_MAPPING.get(key, key)
        normalized[clean_key] = value
    return normalized


# Text Cleaning Utilities

def clean_html(text):
    """
    Remove HTML/XML tags from game descriptions.
    Handles Riot-specific tags like <mainText>, <stats>, <font color>, etc.
    """
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def clean_text(text):
    """
    Comprehensive text cleaner: strips HTML, normalizes whitespace,
    removes Riot placeholder tokens like {{ e1 }}, @Effect1Amount@.
    """
    if not text:
        return ""
    # Remove HTML tags
    cleaned = re.sub(r"<[^>]+>", "", text)
    # Remove Riot formula placeholders: {{ e1 }}, @Effect1Amount@, etc.
    cleaned = re.sub(r"\{\{[^}]+\}\}", "", cleaned)
    cleaned = re.sub(r"@[^@]+@", "", cleaned)
    # Normalize whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


# JSON I/O

def load_json(path):
    """Load JSON file safely. Returns empty dict/list if not found."""
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log("ProcessorUtils", f"Error reading {path}: {e}")
            return {}
    return {}


def save_json(data, path, indent = 2):
    """Save data to JSON file with automatic directory creation."""
    try:
        path.parent.mkdir(parents = True, exist_ok = True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent = indent, ensure_ascii = False)
        return True
    except Exception as e:
        log("ProcessorUtils", f"Error writing to {path}: {e}")
        return False


def log(tag, message):
    """Print standardized log output with module prefix."""
    print(f"[{tag}] {message}")
