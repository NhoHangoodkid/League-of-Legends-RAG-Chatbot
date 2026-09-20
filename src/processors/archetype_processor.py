"""
Archetype and Composition Processor.

100% Automated, Data-Driven Pipeline:
- Analyzes all 173 champions into strategic tactical compositions and archetypes.
- Pure attribute-based classification using champion roles, subroles, attack types,
  adaptive damage types, crowd control, ability effects, ratings, playstyles, and win conditions.
- Zero hardcoded champion names — scales dynamically to any number of champions.
- Zero Vietnamese strings — all aliases, descriptions, reasons, and tips are strictly in English.
- Counter picks, counter items, weaknesses, and tactical exploits are mathematically aggregated
  from member champions' empirical data and synchronized directly to MongoDB 'team_compositions'.
"""

import re
from collections import Counter, defaultdict

from .utils import log

tag = "ArchetypeProcessor"

# Dynamic Archetype Metadata and Classification Registry
# Pure algorithmic classification functions: evaluate champion attributes with ZERO hardcoded names
archetype_configs = [
    # 1. Range Profiles
    {
        "comp_id": "ranged",
        "name": "Ranged Heavy Composition",
        "category": "range_profile",
        "keywords": ["ranged", "long range", "perimeter", "kite", "marksmen"],
        "classifier": lambda r, s, e, cc, hcc, rat, ps, wc, rng, atk, adp: atk == "RANGED" or rng > 300,
    },
    {
        "comp_id": "melee",
        "name": "Melee Heavy Composition",
        "category": "range_profile",
        "keywords": ["melee", "close combat", "brawler", "short range", "close range"],
        "classifier": lambda r, s, e, cc, hcc, rat, ps, wc, rng, atk, adp: atk == "MELEE" or (rng <= 300 and atk != "RANGED"),
    },
    # 2. Damage Profiles
    {
        "comp_id": "full_ad",
        "name": "Full AD (Physical Damage Heavy) Composition",
        "category": "damage_profile",
        "keywords": ["full ad", "all ad", "ad heavy", "physical damage", "pure ad"],
        "classifier": lambda r, s, e, cc, hcc, rat, ps, wc, rng, atk, adp: adp == "PHYSICAL_DAMAGE",
    },
    {
        "comp_id": "full_ap",
        "name": "Full AP (Magic Damage Heavy) Composition",
        "category": "damage_profile",
        "keywords": ["full ap", "all ap", "ap heavy", "magic damage", "pure ap"],
        "classifier": lambda r, s, e, cc, hcc, rat, ps, wc, rng, atk, adp: adp == "MAGIC_DAMAGE",
    },
    # 3. Tactical and Mechanical Profiles
    {
        "comp_id": "dive",
        "name": "Dive and Hard Engage Composition",
        "category": "tactical_profile",
        "keywords": ["dive", "hard engage", "engage", "engaging", "all in", "flank", "backline dive", "diving", "engage comp"],
        "classifier": lambda r, s, e, cc, hcc, rat, ps, wc, rng, atk, adp: (
            "diver" in s
            or ("Dash" in e and rat.get("mobility", 0) >= 2 and bool(r & {"fighter", "assassin", "tank"}))
            or ("Blink" in e and bool(r & {"assassin", "fighter"}))
        ),
    },
    {
        "comp_id": "poke",
        "name": "Poke and Artillery Composition",
        "category": "tactical_profile",
        "keywords": ["poke", "artillery", "siege", "long range poke", "harass"],
        "classifier": lambda r, s, e, cc, hcc, rat, ps, wc, rng, atk, adp: (
            "artillery" in s
            or (atk == "RANGED" and rng >= 550 and ("AOE" in e or "poke" in ps or "Siege" in wc))
            or (bool(s & {"battlemage", "artillery"}) and "poke" in ps)
        ),
    },
    {
        "comp_id": "heavy_cc",
        "name": "Heavy Crowd Control Composition",
        "category": "tactical_profile",
        "keywords": ["heavy cc", "cc heavy", "crowd control", "lockdown", "chain cc", "lots of cc"],
        "classifier": lambda r, s, e, cc, hcc, rat, ps, wc, rng, atk, adp: (
            len(hcc) >= 2
            or (rat.get("control", 0) >= 3 and len(hcc) >= 1)
            or (rat.get("control", 0) >= 2 and len(hcc) >= 1 and bool(r & {"tank", "support"}))
        ),
    },
    {
        "comp_id": "sustain",
        "name": "High Sustain and Healing Composition",
        "category": "tactical_profile",
        "keywords": ["sustain", "heal", "healing", "vamp", "high sustain", "health regen"],
        "classifier": lambda r, s, e, cc, hcc, rat, ps, wc, rng, atk, adp: (
            "Heal" in e or "sustain" in ps or "vamp" in ps
        ),
    },
    {
        "comp_id": "stealth",
        "name": "Stealth and Ambush Composition",
        "category": "tactical_profile",
        "keywords": ["stealth", "invisibility", "camouflage", "ambush", "guerrilla"],
        "classifier": lambda r, s, e, cc, hcc, rat, ps, wc, rng, atk, adp: (
            "Stealth" in e or "stealth" in ps
        ),
    },
    {
        "comp_id": "shield_heavy",
        "name": "Shield and Protective Composition",
        "category": "tactical_profile",
        "keywords": ["shield", "shield heavy", "protect carry", "barrier", "enchanter shield"],
        "classifier": lambda r, s, e, cc, hcc, rat, ps, wc, rng, atk, adp: (
            "Shield" in e and (bool(r & {"support", "tank"}) or bool(s & {"enchanter", "warden"}))
        ),
    },
    {
        "comp_id": "high_mobility",
        "name": "High Mobility and Skirmish Composition",
        "category": "tactical_profile",
        "keywords": ["mobility", "high mobility", "dash", "blink", "slippery", "skirmish"],
        "classifier": lambda r, s, e, cc, hcc, rat, ps, wc, rng, atk, adp: (
            rat.get("mobility", 0) >= 3
            or ("Dash" in e and "Blink" in e)
            or ("Dash" in e and "mobility" in ps)
        ),
    },
    {
        "comp_id": "splitpush",
        "name": "Split-Push and Duelist Composition",
        "category": "tactical_profile",
        "keywords": ["splitpush", "split push", "duelist", "side lane", "isolated split"],
        "classifier": lambda r, s, e, cc, hcc, rat, ps, wc, rng, atk, adp: (
            ("Splitpush" in wc or "splitpush" in ps) and bool(r & {"fighter", "assassin", "skirmisher"})
        ),
    },
    {
        "comp_id": "wombo_combo",
        "name": "Wombo Combo and AoE Teamfight Composition",
        "category": "tactical_profile",
        "keywords": ["wombo combo", "wombo", "aoe teamfight", "catastrophic aoe", "ultimate combo"],
        "classifier": lambda r, s, e, cc, hcc, rat, ps, wc, rng, atk, adp: (
            "AOE" in e and (bool(cc & {"Knockup", "Stun"}) or len(hcc) >= 1) and rat.get("control", 0) >= 2 and "Teamfight" in wc
        ),
    },
    # 4. Role Dominance Profiles
    # 4. Role Dominance Profiles
    {
        "comp_id": "fighter_heavy",
        "name": "Fighter and Bruiser Heavy Composition",
        "category": "role_profile",
        "keywords": ["fighter heavy", "bruiser heavy", "juggernaut heavy", "many fighters", "heavy fighter", "fighter comp", "bruiser comp"],
        "classifier": lambda r, s, e, cc, hcc, rat, ps, wc, rng, atk, adp, pc=None: "fighter" in r or bool(s & {"fighter", "juggernaut", "diver", "skirmisher"}),
    },
    {
        "comp_id": "assassin_heavy",
        "name": "Assassin Heavy Composition",
        "category": "role_profile",
        "keywords": ["assassin heavy", "slayer heavy", "many assassins", "burst assassin comp", "squishy killer comp", "heavy assassin", "assassin comp"],
        "classifier": lambda r, s, e, cc, hcc, rat, ps, wc, rng, atk, adp, pc=None: "assassin" in r or "assassin" in s,
    },
    {
        "comp_id": "mage_heavy",
        "name": "Mage Heavy Composition",
        "category": "role_profile",
        "keywords": ["mage heavy", "spellcaster heavy", "many mages", "burst mage comp", "caster comp", "heavy mage", "ap mage comp"],
        "classifier": lambda r, s, e, cc, hcc, rat, ps, wc, rng, atk, adp, pc=None: "mage" in r or bool(s & {"mage", "battlemage", "artillery"}) or ("MAGIC" in adp and bool(s & {"burst"})),
    },
    {
        "comp_id": "tank_heavy",
        "name": "Tank and Frontline Heavy Composition",
        "category": "role_profile",
        "keywords": ["tank heavy", "frontline heavy", "many tanks", "vanguard comp", "warden comp", "tanky comp", "heavy tank", "tank comp"],
        "classifier": lambda r, s, e, cc, hcc, rat, ps, wc, rng, atk, adp, pc=None: "tank" in r or bool(s & {"tank", "vanguard", "warden"}),
    },
    {
        "comp_id": "marksman_heavy",
        "name": "Marksman and ADC Heavy Composition",
        "category": "role_profile",
        "keywords": ["marksman heavy", "adc heavy", "many marksmen", "multi adc", "ad carry comp", "many adc", "double adc", "adc comp"],
        "classifier": lambda r, s, e, cc, hcc, rat, ps, wc, rng, atk, adp, pc=None: "marksman" in r or "marksman" in s,
    },
    {
        "comp_id": "support_heavy",
        "name": "Enchanter and Utility Support Composition",
        "category": "role_profile",
        "keywords": ["support heavy", "enchanter heavy", "utility comp", "many supports", "catcher comp", "buff comp", "double support", "multi support", "support comp"],
        "classifier": lambda r, s, e, cc, hcc, rat, ps, wc, rng, atk, adp, pc=None: "support" in r or bool(s & {"support", "enchanter", "catcher"}),
    },
    # 5. Hypercarry and Late-Game Scaling Profile
    {
        "comp_id": "hypercarry_protect",
        "name": "Protect the Hypercarry and Late-Game Scaling Composition",
        "category": "tactical_profile",
        "keywords": [
            "hypercarry", "hyper carry", "protect the hypercarry", "protect the carry",
            "hypercarry comp", "protect carry comp", "scaling comp", "late game comp",
            "late game scaling", "late-game scaling", "infinite scaling", "scaling hypercarry",
            "late game hypercarry", "protect hypercarry"
        ],
        "classifier": lambda r, s, e, cc, hcc, rat, ps, wc, rng, atk, adp, pc=None: (
            ("marksman" in r and rat.get("damage", 0) >= 3 and rng >= 550)
            or bool(s & {"hypercarry", "enchanter", "warden"})
            or ("peel" in ps and bool(r & {"support", "tank"}))
            or ("Shield" in e and bool(r & {"support", "tank"}))
            or (pc and "LateGame" in pc and rat.get("damage", 0) >= 3)
        ),
    },
]

# Standalone words reserved for individual champion roles/mechanics to avoid accidental comp hijacking
reserved_role_words = {
    "support", "supports", "supp", "sp", "enchanter", "catcher",
    "tank", "tanks", "vanguard", "warden",
    "mage", "mages", "caster", "casters",
    "marksman", "marksmen", "adc", "adcs",
    "fighter", "fighters", "bruiser", "bruisers", "juggernaut", "skirmisher",
    "assassin", "assassins", "slayer", "slayers",
    "melee", "ranged", "shield", "heal", "healing", "dash", "blink", "kite",
    "top", "mid", "bot", "jungle", "jg"
}


def generate_english_aliases(comp_id, name, keywords):
    """
    Generate natural, comprehensive English query aliases dynamically.
    Guarantees 100% English queries with ZERO hardcoded Vietnamese phrases.
    Excludes standalone single-word roles to avoid hijacking user role queries.
    """
    aliases_set = set()
    if comp_id not in reserved_role_words:
        aliases_set.add(comp_id.replace("_", " "))
        aliases_set.add(comp_id)
    aliases_set.add(name.lower())

    for kw in keywords:
        k = kw.lower().strip()
        variations = {k, k.replace("-", " "), k.replace(" ", "-")}
        for v in variations:
            if v not in reserved_role_words:
                aliases_set.add(v)
            aliases_set.add(f"{v} comp")
            aliases_set.add(f"{v} comps")
            aliases_set.add(f"{v} team")
            aliases_set.add(f"{v} teams")
            aliases_set.add(f"{v} composition")
            aliases_set.add(f"{v} compositions")
            aliases_set.add(f"all {v}")
            aliases_set.add(f"many {v}")
            aliases_set.add(f"full {v}")
            aliases_set.add(f"heavy {v}")
            aliases_set.add(f"{v} heavy")
            aliases_set.add(f"lots of {v}")

    filtered_aliases = [a for a in aliases_set if a not in reserved_role_words]
    return sorted(filtered_aliases, key=lambda x: len(x), reverse=True)


# Archetype Processor Class
class ArchetypeProcessor:
    """
    Analyzes all champions into archetype compositions and calculates
    comprehensive counter matrices using 100% automated, data-driven algorithms.
    """

    def __init__(self):
        pass

    def process(self, champions, counters = None, items = None):
        """
        Process all champions into strategic archetypes and compute counter matrices.
        Returns a dictionary of archetype documents formatted for MongoDB persistence.
        """
        log(tag, f"Analyzing {len(champions)} champions into archetype compositions...")
        counters = counters or {}
        items = items or {}
        item_lookup = {it.get("name"): it for it in items.values() if isinstance(it, dict) and it.get("name")}

        compositions = {}

        for cfg in archetype_configs:
            comp_id = cfg["comp_id"]
            name = cfg["name"]
            category = cfg["category"]
            classifier = cfg["classifier"]
            keywords = cfg["keywords"]

            # 1. Dynamically evaluate all champions using pure attribute classification
            member_ids = []
            member_champs = []

            for cid, c in champions.items():
                roles = set(x.lower() for x in c.get("roles", []))
                subroles = set(x.lower() for x in c.get("subroles", []))
                effects = set(c.get("ability_effects", []))
                cc_types = set(c.get("cc_types", []))
                hard_cc = set(c.get("hard_cc", []))
                ratings = c.get("attributeRatings", {})
                playstyles = set(x.lower() for x in c.get("playstyles", []))
                win_conditions = set(c.get("winConditions", []))
                power_curves = set(c.get("powerCurve", []))
                stats = c.get("stats", {})
                ar_val = stats.get("attackrange", 0)
                rng = ar_val.get("base", 0) if isinstance(ar_val, dict) else (ar_val or 0)
                atk = (c.get("attackType") or "").upper()
                adp = (c.get("adaptiveType") or "").upper()

                try:
                    is_member = classifier(roles, subroles, effects, cc_types, hard_cc, ratings, playstyles, win_conditions, rng, atk, adp, power_curves)
                except TypeError:
                    is_member = classifier(roles, subroles, effects, cc_types, hard_cc, ratings, playstyles, win_conditions, rng, atk, adp)

                if is_member:
                    member_ids.append(cid)
                    member_champs.append(c)

            total_members = len(member_ids)
            if total_members == 0:
                continue

            member_names = [c.get("name", cid) for cid, c in zip(member_ids, member_champs)]

            # 2. Mathematically Aggregate Weaknesses from Member Champions
            weakness_counts = Counter()
            tip_counts = Counter()
            item_counts = Counter()
            counter_counts = Counter()
            counter_reasons = defaultdict(list)

            for cid, c in zip(member_ids, member_champs):
                t_info = c.get("tacticalInfo", {})
                if isinstance(t_info, dict):
                    for w in t_info.get("weaknesses", []):
                        weakness_counts[w.strip()] += 1
                    for t in t_info.get("tactical_tips", []):
                        tip_counts[t.strip()] += 1
                    for it in t_info.get("counter_items", []):
                        item_counts[it.strip()] += 1

                c_counters = counters.get(cid) or c.get("counters", {})
                if isinstance(c_counters, dict):
                    for entry in c_counters.get("weakAgainst", []):
                        if isinstance(entry, dict):
                            p_champ = entry.get("champion")
                            reason = entry.get("reason", "")
                            if p_champ:
                                counter_counts[p_champ] += 1
                                if reason:
                                    counter_reasons[p_champ].append(reason.strip())

            # Top 3-4 core weaknesses aggregated by frequency
            top_weaknesses = [w for w, _ in weakness_counts.most_common(4)]

            # Top 4-5 tactical gameplay exploit tips aggregated by frequency
            top_tips = [t for t, _ in tip_counts.most_common(5)]

            # 3. Top Counter Picks Aggregation
            top_counter_picks = []
            for counter_name, count in counter_counts.most_common(8):
                pct = round((count / total_members) * 100, 1)
                reasons = counter_reasons.get(counter_name, [])
                distinct_clauses = []
                for r in reasons:
                    for clause in r.split(";"):
                        c_clean = clause.strip()
                        if c_clean and c_clean not in distinct_clauses:
                            distinct_clauses.append(c_clean)
                        if len(distinct_clauses) >= 2:
                            break
                    if len(distinct_clauses) >= 2:
                        break
                synthesized_reason = "; ".join(distinct_clauses) if distinct_clauses else f"High matchup advantage against {pct}% of champions in this archetype."

                top_counter_picks.append({
                    "champion": counter_name,
                    "counter_frequency": count,
                    "archetype_coverage_pct": pct,
                    "tactical_reason": synthesized_reason,
                })

            # 4. Determine Dominant Damage Profile
            ad_count = sum(1 for c in member_champs if "PHYSICAL" in (c.get("adaptiveType") or "").upper())
            ap_count = sum(1 for c in member_champs if "MAGIC" in (c.get("adaptiveType") or "").upper())
            dominant_damage = "Physical Damage" if ad_count > ap_count else ("Magic Damage" if ap_count > ad_count else "Mixed Damage")

            # 5. Top Counter Items Aggregation with Damage-Type Gating and Dynamic Stats
            top_counter_items = []
            for item_name, count in item_counts.most_common(16):
                item_obj = item_lookup.get(item_name, {})
                stats_dict = item_obj.get("stats", {})
                item_ar = stats_dict.get("armor", 0)
                item_mr = stats_dict.get("magic_resist", 0)

                # Damage type gating: do not recommend pure armor items against pure magic damage comps
                if dominant_damage == "Magic Damage" and item_ar > 0 and item_mr == 0:
                    continue
                # Do not recommend pure MR items against pure physical damage comps
                if dominant_damage == "Physical Damage" and item_mr > 0 and item_ar == 0:
                    continue

                pct = round((count / total_members) * 100, 1)
                plaintext = (item_obj.get("plaintext") or "").strip()
                raw_desc = item_obj.get("description", "")
                clean_desc = re.sub(r"<[^>]+>", " ", raw_desc).strip()
                clean_desc = " ".join(clean_desc.split())

                stats_summary = ", ".join(
                    f"{val} {k.replace('flat_', '').replace('_', ' ').title()}"
                    for k, val in stats_dict.items() if val
                )

                item_effect = plaintext if plaintext else clean_desc
                if stats_summary and item_effect:
                    purpose = f"{stats_summary}. {item_effect}"
                elif stats_summary:
                    purpose = stats_summary
                elif item_effect:
                    purpose = item_effect
                else:
                    purpose = f"Statistically itemized counter against {count} ({pct}%) champions in this archetype."

                top_counter_items.append({
                    "item": item_name,
                    "recommended_count": count,
                    "archetype_coverage_pct": pct,
                    "tactical_purpose": purpose,
                })
                if len(top_counter_items) >= 8:
                    break

            # 6. Synthesize Dynamic English Description
            sample_preview = ", ".join(member_names[:6])

            role_counter = Counter(r for c in member_champs for r in c.get("roles", []))
            top_roles_str = ", ".join(r.capitalize() for r, _ in role_counter.most_common(2))

            ps_counter = Counter(ps for c in member_champs for ps in c.get("playstyles", []) if ps)
            top_ps = [p.capitalize() for p, _ in ps_counter.most_common(2) if p]
            playstyle_desc = f" utilizing {', '.join(top_ps)} playstyles" if top_ps else ""

            description = (
                f"Tactical composition comprising {total_members} champions (such as {sample_preview}) "
                f"characterized primarily by {top_roles_str} combat dynamics{playstyle_desc} and {dominant_damage} output. "
                f"Countering this profile requires strategic drafting and tailored itemization targeting its structural limitations."
            )

            # 6. Generate 100% English Query Aliases
            english_aliases = generate_english_aliases(comp_id, name, keywords)

            comp_doc = {
                "_id": comp_id,
                "comp_id": comp_id,
                "name": name,
                "category": category,
                "description": description,
                "aliases": english_aliases,
                "total_member_count": total_members,
                "sample_champions": member_names[:15],
                "member_champions": member_names,
                "all_champions": member_names,
                "counter_picks": top_counter_picks,
                "counter_items": top_counter_items,
                "core_weaknesses": top_weaknesses,
                "tactical_tips": top_tips,
            }

            compositions[comp_id] = comp_doc

        log(tag, f"Generated {len(compositions)} 100% automated English archetype profiles for MongoDB.")
        return compositions


__all__ = ["ArchetypeProcessor", "archetype_configs"]
