"""
Spell Analyzer.

Analyzes champion ability descriptions to extract:
- Crowd Control (CC) types: Stun, Slow, Root, Knockup, etc.
- Ability effects: Dash, Shield, Heal, Stealth, etc.
- CC classification: hard_cc vs soft_cc

Referenced from lol_chatbot's ontology_enricher.py
(scripts/scraping/ontology_enricher.py)
"""

import json
import re
from pathlib import Path

from .utils import processed_dir, load_json, save_json, log, clean_html


# CC Keywords — tightened to reduce false positives
cc_keywords = {
    "Stun": [r"\bstuns?\b", r"\bstunned\b", r"\bstunning\b"],
    "Slow": [r"\bslows?\b", r"\bslowed\b", r"\bslowing\b"],
    "Root": [r"\broots?\b", r"\brooted\b", r"\brooting\b", r"\bimmobilize[sd]?\b", r"\bsnare[sd]?\b"],
    "Knockup": [r"\bknock(?:s|ed|ing)?\s*up\b", r"\bairborne\b", r"\bknock(?:s|ed)?\s*back\b", r"\bknockback\b"],
    "Silence": [r"\bsilence[sd]?\b", r"\bsilencing\b"],
    "Blind": [r"\bblinds?\b", r"\bblinded\b", r"\bblinding(?!\s+speed)\b", r"\bnearsight(?:ed)?\b"],
    "Charm": [r"\bcharms?\b", r"\bcharmed\b", r"\bcharming\b"],
    "Fear": [r"(?<!their\s)\bfears?\b", r"\bfeared\b", r"\bfearing\b", r"\bflee(?:ing|s)?\b", r"\bterrif(?:y|ied|ies)\b"],
    "Taunt": [r"\btaunts?\b", r"\btaunted\b", r"\btaunting\b"],
    "Suppress": [r"\bsuppress(?:es|ed|ing|ion)?\b"],
    "Knockdown": [r"\bknock(?:s|ed|ing)?\s*down\b", r"\bgrounded\s+enemies\b", r"\bground(?:s|ing)\b(?:\s+and\s+\w+)?\s+enemies\b"],
    "Sleep": [r"\bsleep(?:s|ing)?\b", r"\bdrowsy\b", r"\basleep\b"],
    "Polymorph": [r"\bpolymorph(?:s|ed)?\b"],
}

# Hard CC: interrupts channels and prevents all actions (offensive crowd control on enemies)
hard_cc_types = {"Stun", "Knockup", "Suppress", "Charm", "Fear", "Taunt", "Sleep", "Polymorph"}
# Soft CC: limits actions but doesn't fully disable
soft_cc_types = {"Slow", "Root", "Silence", "Blind", "Knockdown"}


# Effect Keywords — tightened to reduce false positives

effect_keywords = {
    "Dash": [r"\bdash(?:es|ing)?\b", r"\bleap(?:s|ing)?(?!\s+to\s+(?:an?\s+)?enemy)\b", r"\bjump(?:s|ing)?(?!\s+to\s+(?:an?\s+)?enemy)\b", r"\blunge(?:s|ing)?\b"],
    "Blink": [r"\bblink(?:s|ing)?\b", r"\bteleport(?:s|ing)?\b"],
    "Shield": [r"\bshield(?:s|ing|ed)?\b", r"\bbarrier\b"],
    # Fixed: only match actual healing, not "restores mana" or "restores energy"
    "Heal": [r"\bheal(?:s|ing|ed)?\b", r"\brestores?\s+(?:\d+\s*(?:%\s*(?:of\s+)?)?)?(?:missing\s+|maximum\s+|max\s+|total\s+|bonus\s+)?health\b", r"\bregenerat(?:es?|ing)\s+health\b", r"\blife\s*steal\b"],
    "Stealth": [r"\bstealth\b", r"\binvisib(?:le|ility)\b", r"\bcamouflage[d]?\b"],
    "Invulnerability": [r"\binvulnerab(?:le|ility)\b", r"\buntargetab(?:le|ility)\b"],
    "SpellBlock": [r"\bspell\s*shield\b", r"\bblocks?\s+(?:the\s+next\s+)?abilit(?:y|ies)\b"],
    "Revive": [r"\brevive[sd]?\b", r"\bresurrect(?:s|ed|ion)?\b"],
    "Clone": [r"\bclone(?:s|d)?\b", r"\bdecoy(?:s)?\b"],
    "Pull": [r"\bpull(?:s|ing|ed)?\b", r"\bhook(?:s|ed|ing)?\b", r"\bgrab(?:s|bed|bing)?\b"],
    # Fixed: strictly match actual player-made terrain creation (excludes shields, windwalls, and existing terrain)
    "Terrain": [
        r"\b(?:impassable\s+terrain|terraforms?\b)",
        r"\b(?:create|summon|erect)(?:s|ing|ed)?\s+[\w\s]{0,30}?(?:destructible\s+wall|wall\s+of\s+ice|wall\s+of\s+soldiers|magma\s+pillar|very\s+long\s+wall)\b",
        r"\bmagma\s+pillar\s+forms\b",
    ],
    "Execute": [r"\bexecut(?:e[sd]?|ing|ion)\b"],
    "Reset": [r"\breset(?:s)?\b", r"\brefund(?:s|ed)?\b"],
    # Fixed: tightened AOE to require explicit area-of-effect language
    "AOE": [r"\barea\s+of\s+effect\b", r"\benemies?\s+in\s+(?:a|an|the)\s+(?:area|cone|circle|line)\b", r"\ball\s+(?:nearby\s+)?enemies\b", r"\bnearby\s+enemies\b"],
    "GlobalRange": [r"\bglobal(?:\s+range)?\b", r"\banywhere\s+on\s+the\s+map\b", r"\bunlimited\s+range\b"],
    "Unstoppable": [r"\bunstoppable\b"],
}


class SpellAnalyzer:
    """Analyze champion ability descriptions to extract CC types and effects."""

    def analyze(self, champions = None):
        """
        Analyze champion ability descriptions to extract CC types and effects.
        Accepts in-memory champion dict or loads from disk as fallback.
        """
        if not champions:
            print("[SpellAnalyzer] Loading champion data from disk...")
            champions = self.load_champions()

        if not champions:
            print("[SpellAnalyzer] ERROR: No champion data found!")
            return {}

        print(f"[SpellAnalyzer] Analyzing {len(champions)} champions...")

        total_cc = 0
        total_effects = 0

        for champ_id, champ in champions.items():
            cc_types, effects = self.analyze_champion(champ)

            # Classify CC into hard and soft
            hard_cc = sorted([cc for cc in cc_types if cc in hard_cc_types])
            soft_cc = sorted([cc for cc in cc_types if cc in soft_cc_types])

            champ["cc_types"] = cc_types
            champ["hard_cc"] = hard_cc
            champ["soft_cc"] = soft_cc
            champ["ability_effects"] = effects
            total_cc += len(cc_types)
            total_effects += len(effects)

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
        """Extract CC types from ability text using word-boundary regex patterns."""
        if not text:
            return set()
        # Strip HTML and lowercase
        text_clean = re.sub(r"<[^>]+>", " ", text.lower())
        found = set()
        for cc_type, patterns in cc_keywords.items():
            for pattern in patterns:
                if re.search(pattern, text_clean):
                    found.add(cc_type)
                    break
        return found

    @staticmethod
    def extract_effects(text):
        """Extract ability effects from text using word-boundary regex patterns."""
        if not text:
            return set()
        text_clean = re.sub(r"<[^>]+>", " ", text.lower())
        found = set()
        for effect_type, patterns in effect_keywords.items():
            for pattern in patterns:
                if re.search(pattern, text_clean):
                    found.add(effect_type)
                    break
        return found

    @staticmethod
    def load_champions():
        """Load processed champion data."""
        return load_json(processed_dir / "champions.json")

    @staticmethod
    def save_champions(data):
        """Save updated champion data."""
        return save_json(data, processed_dir / "champions.json")
