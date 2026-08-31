"""
Spell Analyzer.

Analyzes champion ability descriptions to extract:
- Crowd Control (CC) types: Stun, Slow, Root, Knockup, etc.
- Ability effects: Dash, Shield, Heal, Stealth, etc.

Referenced from lol_chatbot's ontology_enricher.py
(scripts/scraping/ontology_enricher.py)
"""

import json
import re
from pathlib import Path

try:
    from .utils import PROCESSED_DIR, load_json, save_json, log
except ImportError:
    try:
        from processors.utils import PROCESSED_DIR, load_json, save_json, log
    except ImportError:
        from utils import PROCESSED_DIR, load_json, save_json, log



CC_KEYWORDS = {
    "Stun": ["stun", "stunned", "stunning"],
    "Slow": ["slow", "slowed", "slowing"],
    "Root": ["root", "rooted", "rooting", "immobilize", "snare", "snared"],
    "Knockup": ["knock up", "knocked up", "knocking up", "airborne", "knock back", "knockback"],
    "Silence": ["silence", "silenced", "silencing"],
    "Blind": ["blind", "blinded", "blinding", "nearsight", "nearsighted"],
    "Charm": ["charm", "charmed", "charming"],
    "Fear": ["fear", "feared", "fearing", "flee", "fleeing", "terrify"],
    "Taunt": ["taunt", "taunted", "taunting"],
    "Suppress": ["suppress", "suppressed", "suppressing", "suppression"],
    "Knockdown": ["knock down", "knocked down", "ground", "grounded", "grounding"],
    "Sleep": ["sleep", "drowsy", "asleep"],
    "Polymorph": ["polymorph", "polymorphed"],
    "Stasis": ["stasis"],
}

EFFECT_KEYWORDS = {
    "Dash": ["dash", "dashes", "dashing", "leap", "leaps", "leaping", "jump", "jumps", "lunge", "lunges"],
    "Blink": ["blink", "blinks", "teleport", "teleports"],
    "Shield": ["shield", "shields", "shielding", "barrier"],
    "Heal": ["heal", "heals", "healing", "restore", "restores", "restoring health", "regenerate"],
    "Stealth": ["stealth", "invisible", "invisibility", "camouflage", "camouflaged"],
    "Invulnerability": ["invulnerable", "invulnerability", "untargetable", "immune"],
    "SpellBlock": ["spell shield", "spellshield", "blocks ability"],
    "Revive": ["revive", "revived", "resurrection", "resurrect"],
    "Clone": ["clone", "clones", "decoy"],
    "Pull": ["pull", "pulls", "pulling", "hook", "hooks", "grab", "grabs"],
    "Terrain": ["terrain", "wall", "create terrain", "impassable"],
    "Execute": ["execute", "executes", "execution"],
    "Reset": ["reset", "resets cooldown", "refund"],
    "AOE": ["area", "enemies in", "all enemies", "nearby enemies", "around"],
    "GlobalRange": ["global", "anywhere on the map", "unlimited range"],
    "Unstoppable": ["unstoppable"],
}


class SpellAnalyzer:
    """Analyze champion ability descriptions to extract CC types and effects."""

    def analyze(self):
        """
        Read processed champions data and add cc_types + ability_effects.
        Updates src/processors/processed/champions.json in-place.
        """
        print("[SpellAnalyzer] Loading champion data...")
        champions = self.load_champions()

        if not champions:
            print("[SpellAnalyzer] ERROR: No champion data found!")
            return {}

        print(f"[SpellAnalyzer] Analyzing {len(champions)} champions...")

        total_cc = 0
        total_effects = 0

        for champ_id, champ in champions.items():
            cc_types, effects = self.analyze_champion(champ)
            champ["cc_types"] = cc_types
            champ["ability_effects"] = effects
            total_cc += len(cc_types)
            total_effects += len(effects)

        self.save_champions(champions)
        print(f"[SpellAnalyzer] Total CC annotations: {total_cc}")
        print(f"[SpellAnalyzer] Total effect annotations: {total_effects}")
        return champions

    def analyze_champion(self, champ):
        """Analyze all abilities of a champion."""
        all_cc = set()
        all_effects = set()

        abilities = champ.get("abilities", {})
        for key in ["passive", "Q", "W", "E", "R"]:
            ability = abilities.get(key, {})
            description = ability.get("description", "")
            tooltip = ability.get("tooltip", "")
            full_text = f"{description} {tooltip}"

            all_cc.update(self.extract_cc(full_text))
            all_effects.update(self.extract_effects(full_text))

        return sorted(list(all_cc)), sorted(list(all_effects))

    @staticmethod
    def extract_cc(text):
        """Extract CC types from ability text."""
        if not text:
            return set()
        text_lower = re.sub(r"<[^>]+>", "", text.lower())
        found = set()
        for cc_type, keywords in CC_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    found.add(cc_type)
                    break
        return found

    @staticmethod
    def extract_effects(text):
        """Extract ability effects from text."""
        if not text:
            return set()
        text_lower = re.sub(r"<[^>]+>", "", text.lower())
        found = set()
        for effect_type, keywords in EFFECT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    found.add(effect_type)
                    break
        return found

    @staticmethod
    def load_champions():
        """Load processed champion data."""
        return load_json(PROCESSED_DIR / "champions.json")

    @staticmethod
    def save_champions(data):
        """Save updated champion data."""
        return save_json(data, PROCESSED_DIR / "champions.json")


