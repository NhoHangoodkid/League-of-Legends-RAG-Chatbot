"""
Champions Exploratory Data Analysis (EDA) Module.

Directly analyzes champion data according to the processing steps in:
1. `ChampionMerger`: Master IDs, multi-source fallbacks (DDragon, CDragon, Meraki, Lore), base & scaling stats.
2. `SpellAnalyzer`: Ability extractions for Crowd Control (CC) types and ability effects.
3. `Enricher`: Strategic playstyle tags, power curves, and win conditions.
"""

import re
from collections import Counter
from typing import Any, Dict, List, Optional

from eda.utils import (
    calculate_stats,
    format_table,
    get_frequency_distribution,
    load_raw_json,
    log,
)

TAG = "ChampionsEDA"

# Processor Keywords (from processors.spell_analyzer)
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


def analyze_champion_merge_inputs():
    """Analyze master champion roster, source availability, and fallback paths used by ChampionMerger."""
    ddragon = load_raw_json("ddragon", "champions.json") or {}
    cdragon = load_raw_json("cdragon", "champions.json") or {}
    meraki = load_raw_json("meraki", "champions.json") or {}
    lore = load_raw_json("lore", "lore.json") or {}

    # Master IDs defined by ChampionMerger: DDragon + non-Jade CDragon
    master_ids = set(ddragon.keys())
    if cdragon:
        for cid in cdragon.keys():
            if not cid.startswith("Jade_"):
                master_ids.add(cid)

    total_master = len(master_ids)

    # Source presence
    in_ddragon = [cid for cid in master_ids if cid in ddragon]
    in_cdragon = [cid for cid in master_ids if cid in cdragon]
    in_meraki = [cid for cid in master_ids if cid in meraki]
    in_lore = [cid for cid in master_ids if cid in lore]

    # Stats priority: Meraki > DDragon
    meraki_stats_count = sum(1 for cid in master_ids if cid in meraki and "stats" in meraki[cid])
    fallback_ddragon = [cid for cid in master_ids if cid not in meraki and cid in ddragon]

    # CDragon tactical & playstyle ratings
    tactical_count = 0
    playstyle_count = 0
    for cid in master_ids:
        entry = cdragon.get(cid, {})
        detail = entry.get("detail", entry) if isinstance(entry, dict) else {}
        if detail.get("tacticalInfo"):
            tactical_count += 1
        if detail.get("playstyleInfo"):
            playstyle_count += 1

    return {
        "total_master_champions": total_master,
        "source_coverage": {
            "ddragon": {"count": len(in_ddragon), "pct": round((len(in_ddragon) / total_master) * 100, 2)},
            "cdragon": {"count": len(in_cdragon), "pct": round((len(in_cdragon) / total_master) * 100, 2)},
            "meraki": {"count": len(in_meraki), "pct": round((len(in_meraki) / total_master) * 100, 2)},
            "lore": {"count": len(in_lore), "pct": round((len(in_lore) / total_master) * 100, 2)},
        },
        "stats_resolution": {
            "from_meraki_count": meraki_stats_count,
            "from_meraki_pct": round((meraki_stats_count / total_master) * 100, 2),
            "fallback_ddragon_count": len(fallback_ddragon),
            "fallback_ddragon_champions": fallback_ddragon,
        },
        "cd_metadata_coverage": {
            "has_tactical_info": tactical_count,
            "has_playstyle_info": playstyle_count,
            "tactical_info_pct": round((tactical_count / total_master) * 100, 2),
        },
    }


def analyze_champion_stats_and_attributes():
    """Analyze base stats, growth formulas, attack types, and resource models processed by ChampionMerger."""
    meraki = load_raw_json("meraki", "champions.json") or {}
    ddragon = load_raw_json("ddragon", "champions.json") or {}

    # Extract high-precision stats from Meraki with fallback to DDragon
    stat_collections = {
        "health": [],
        "health_growth": [],
        "mana": [],
        "mana_growth": [],
        "armor": [],
        "armor_growth": [],
        "magic_resist": [],
        "mr_growth": [],
        "attack_damage": [],
        "ad_growth": [],
        "attack_range": [],
        "movement_speed": [],
        "attack_speed": [],
    }

    champion_records = []
    attack_types = []
    adaptive_types = []
    resource_types = []

    for name, champ in ddragon.items():
        mk = meraki.get(name, {})
        mk_stats = mk.get("stats", {})

        # Health
        hp = mk_stats.get("health", {}).get("flat") if isinstance(mk_stats.get("health"), dict) else champ.get("stats", {}).get("hp")
        hp_growth = mk_stats.get("health", {}).get("perLevel") if isinstance(mk_stats.get("health"), dict) else champ.get("stats", {}).get("hpperlevel")

        # Mana
        mp = mk_stats.get("mana", {}).get("flat") if isinstance(mk_stats.get("mana"), dict) else champ.get("stats", {}).get("mp", 0)
        mp_growth = mk_stats.get("mana", {}).get("perLevel") if isinstance(mk_stats.get("mana"), dict) else champ.get("stats", {}).get("mpperlevel", 0)

        # Armor
        arm = mk_stats.get("armor", {}).get("flat") if isinstance(mk_stats.get("armor"), dict) else champ.get("stats", {}).get("armor")
        arm_growth = mk_stats.get("armor", {}).get("perLevel") if isinstance(mk_stats.get("armor"), dict) else champ.get("stats", {}).get("armorperlevel")

        # Magic Resist
        mr = mk_stats.get("magicResistance", {}).get("flat") if isinstance(mk_stats.get("magicResistance"), dict) else champ.get("stats", {}).get("spellblock")
        mr_growth = mk_stats.get("magicResistance", {}).get("perLevel") if isinstance(mk_stats.get("magicResistance"), dict) else champ.get("stats", {}).get("spellblockperlevel")

        # Attack Damage
        ad = mk_stats.get("attackDamage", {}).get("flat") if isinstance(mk_stats.get("attackDamage"), dict) else champ.get("stats", {}).get("attackdamage")
        ad_growth = mk_stats.get("attackDamage", {}).get("perLevel") if isinstance(mk_stats.get("attackDamage"), dict) else champ.get("stats", {}).get("attackdamageperlevel", 0)

        # Range & Speed
        rng = mk_stats.get("attackRange", {}).get("flat") if isinstance(mk_stats.get("attackRange"), dict) else champ.get("stats", {}).get("attackrange")
        ms = mk_stats.get("movespeed", {}).get("flat") if isinstance(mk_stats.get("movespeed"), dict) else champ.get("stats", {}).get("movespeed")
        as_base = mk_stats.get("attackSpeed", {}).get("flat") if isinstance(mk_stats.get("attackSpeed"), dict) else champ.get("stats", {}).get("attackspeed")

        if hp: stat_collections["health"].append(hp)
        if hp_growth: stat_collections["health_growth"].append(hp_growth)
        if mp: stat_collections["mana"].append(mp)
        if mp_growth: stat_collections["mana_growth"].append(mp_growth)
        if arm: stat_collections["armor"].append(arm)
        if arm_growth: stat_collections["armor_growth"].append(arm_growth)
        if mr: stat_collections["magic_resist"].append(mr)
        if mr_growth: stat_collections["mr_growth"].append(mr_growth)
        if ad: stat_collections["attack_damage"].append(ad)
        if ad_growth: stat_collections["ad_growth"].append(ad_growth)
        if rng: stat_collections["attack_range"].append(rng)
        if ms: stat_collections["movement_speed"].append(ms)
        if as_base: stat_collections["attack_speed"].append(as_base)

        champion_records.append({
            "name": name,
            "hp": hp or 0,
            "ad": ad or 0,
            "armor": arm or 0,
            "range": rng or 0,
            "ms": ms or 0,
        })

        # Attributes
        atk_t = mk.get("attackType") or ("MELEE" if (rng or 0) < 300 else "RANGED")
        attack_types.append(atk_t)

        adp_t = mk.get("adaptiveType") or "PHYSICAL"
        adaptive_types.append(adp_t)

        res_t = mk.get("resource") or champ.get("partype") or "Manaless"
        res_t = res_t.strip() if res_t.strip() else "Manaless"
        resource_types.append(res_t)

    # Statistical summaries
    stat_labels = [
        ("health", "Base Health (HP)"),
        ("health_growth", "HP Growth per Level"),
        ("mana", "Base Mana"),
        ("mana_growth", "Mana Growth per Level"),
        ("armor", "Base Armor"),
        ("armor_growth", "Armor Growth per Level"),
        ("magic_resist", "Base Magic Resist (MR)"),
        ("mr_growth", "MR Growth per Level"),
        ("attack_damage", "Base Attack Damage (AD)"),
        ("ad_growth", "AD Growth per Level"),
        ("attack_range", "Attack Range"),
        ("movement_speed", "Movement Speed"),
        ("attack_speed", "Base Attack Speed"),
    ]

    stats_summary = {
        key: {"label": label, "metrics": calculate_stats(stat_collections[key])}
        for key, label in stat_labels
    }

    # Outliers
    def get_outliers(stat_key, n = 5):
        sorted_champs = sorted(champion_records, key = lambda x: x[stat_key], reverse = True)
        return {
            "top": [{"name": x["name"], "value": x[stat_key]} for x in sorted_champs[:n]],
            "bottom": [{"name": x["name"], "value": x[stat_key]} for x in sorted_champs[-n:]],
        }

    return {
        "stats_distribution": stats_summary,
        "attack_types": get_frequency_distribution(attack_types),
        "adaptive_types": get_frequency_distribution(adaptive_types),
        "resource_types": get_frequency_distribution(resource_types),
        "outliers": {
            "hp": get_outliers("hp"),
            "ad": get_outliers("ad"),
            "armor": get_outliers("armor"),
            "range": get_outliers("range"),
        },
    }


def analyze_spell_analyzer_extraction():
    """Simulate SpellAnalyzer CC and effect extraction across all abilities."""
    ddragon = load_raw_json("ddragon", "champions.json") or {}

    def extract_keywords(text, keyword_map):
        if not text:
            return set()
        clean = re.sub(r"<[^>]+>", " ", text.lower())
        found = set()
        for label, kw_list in keyword_map.items():
            for kw in kw_list:
                if kw in clean:
                    found.add(label)
                    break
        return found

    cc_counter = Counter()
    effect_counter = Counter()
    champion_cc_counts = []
    champion_effect_counts = []
    champions_zero_cc = []
    champions_high_cc = []

    for name, champ in ddragon.items():
        all_text = champ.get("passive", {}).get("description", "")
        for spell in champ.get("spells", []):
            all_text += " " + spell.get("description", "") + " " + spell.get("tooltip", "")

        ccs = extract_keywords(all_text, CC_KEYWORDS)
        effs = extract_keywords(all_text, EFFECT_KEYWORDS)

        for c in ccs: cc_counter[c] += 1
        for e in effs: effect_counter[e] += 1

        cc_len = len(ccs)
        eff_len = len(effs)
        champion_cc_counts.append(cc_len)
        champion_effect_counts.append(eff_len)

        if cc_len == 0:
            champions_zero_cc.append(name)
        elif cc_len >= 3:
            champions_high_cc.append({"name": name, "cc_count": cc_len, "cc_types": sorted(list(ccs))})

    champions_high_cc.sort(key = lambda x: x["cc_count"], reverse = True)
    total_champs = len(ddragon)

    return {
        "total_champions_analyzed": total_champs,
        "cc_types_distribution": [(k, v, round((v / total_champs) * 100, 2)) for k, v in cc_counter.most_common()],
        "ability_effects_distribution": [(k, v, round((v / total_champs) * 100, 2)) for k, v in effect_counter.most_common()],
        "cc_per_champion_stats": calculate_stats(champion_cc_counts),
        "effects_per_champion_stats": calculate_stats(champion_effect_counts),
        "champions_without_cc": champions_zero_cc,
        "heaviest_cc_champions": champions_high_cc[:6],
    }


def analyze_enricher_curation():
    """Audit Enricher strategic playstyle metadata coverage."""
    ddragon = load_raw_json("ddragon", "champions.json") or {}

    try:
        from processors.enricher import CHAMPION_PLAYSTYLES, POWER_CURVES, WIN_CONDITIONS
    except Exception:
        CHAMPION_PLAYSTYLES = {}
        POWER_CURVES = {}
        WIN_CONDITIONS = {}

    master_ids = set(ddragon.keys())
    total_master = len(master_ids)

    missing_playstyles = sorted([cid for cid in master_ids if cid not in CHAMPION_PLAYSTYLES])
    missing_powercurves = sorted([cid for cid in master_ids if cid not in POWER_CURVES])
    missing_winconditions = sorted([cid for cid in master_ids if cid not in WIN_CONDITIONS])

    playstyle_tag_counts = Counter()
    for tags in CHAMPION_PLAYSTYLES.values():
        if isinstance(tags, list):
            for t in tags:
                playstyle_tag_counts[t] += 1

    return {
        "total_master_champions": total_master,
        "playstyles_curated_count": total_master - len(missing_playstyles),
        "playstyles_curated_pct": round(((total_master - len(missing_playstyles)) / total_master) * 100, 2) if total_master else 0,
        "playstyles_fallback_champions": missing_playstyles,
        "powercurves_curated_count": total_master - len(missing_powercurves),
        "winconditions_curated_count": total_master - len(missing_winconditions),
        "top_playstyle_tags": playstyle_tag_counts.most_common(8),
    }


def analyze_champions():
    """Execute complete champion EDA aligned with Processor components."""
    log(TAG, "Starting champion analysis aligned with ChampionMerger, SpellAnalyzer, and Enricher...")

    merge_info = analyze_champion_merge_inputs()
    stats_info = analyze_champion_stats_and_attributes()
    spell_info = analyze_spell_analyzer_extraction()
    enrich_info = analyze_enricher_curation()

    results = {
        "merge_inputs": merge_info,
        "stats_and_attributes": stats_info,
        "spell_analysis": spell_info,
        "enricher_curation": enrich_info,
    }

    log(TAG, f"Analysis complete. Evaluated {merge_info['total_master_champions']} master champions.")
    return results


def format_champions_report(results):
    """Format processor-aligned champion EDA results into readable Markdown text."""
    merge_info = results["merge_inputs"]
    stats_info = results["stats_and_attributes"]
    spell_info = results["spell_analysis"]
    enrich_info = results["enricher_curation"]

    sections = [
        "## 1. Phân Tích Dữ Liệu Tướng (Champion Processing Pipeline)",
        "",
        "### 1.1 Champion Merger: Nguồn Dữ Liệu & Cơ Chế Hợp Nhất",
        f"- **Tổng số tướng Master Roster**: {merge_info['total_master_champions']} tướng (DDragon + non-Jade CDragon)",
        f"- **Độ phủ Meraki Stats**: {merge_info['stats_resolution']['from_meraki_count']}/{merge_info['total_master_champions']} tướng ({merge_info['stats_resolution']['from_meraki_pct']}%)",
        f"- **Số tướng dùng Fallback DDragon Stats**: {merge_info['stats_resolution']['fallback_ddragon_count']} ({', '.join(merge_info['stats_resolution']['fallback_ddragon_champions']) if merge_info['stats_resolution']['fallback_ddragon_champions'] else 'Không có'})",
        f"- **Độ phủ CDragon Tactical & Playstyle Info**: {merge_info['cd_metadata_coverage']['has_tactical_info']}/{merge_info['total_master_champions']} tướng ({merge_info['cd_metadata_coverage']['tactical_info_pct']}%)",
        "",
    ]

    # Source coverage table
    src_rows = [
        [src.upper(), info["count"], f"{info['pct']}%"]
        for src, info in merge_info["source_coverage"].items()
    ]
    sections.append("#### Độ phủ các nguồn đối với Master Champion Roster:")
    sections.append(format_table(["Nguồn Dữ Liệu", "Số Tướng Có Mặt", "Tỷ Lệ Bao Phủ"], src_rows))
    sections.append("")

    # Stats distribution table
    sections.append("### 1.2 Phân Bố Chỉ Số Cơ Bản & Tăng Trưởng (Stats & Growth Formulas)")
    stat_rows = []
    for k, info in stats_info["stats_distribution"].items():
        m = info["metrics"]
        stat_rows.append([info["label"], m["min"], m["q25"], m["median"], m["mean"], m["q75"], m["max"], m["std"]])
    sections.append(format_table(["Chỉ Số", "Min", "25%", "Trung Vị", "Trung Bình", "75%", "Max", "Độ Lệch"], stat_rows))
    sections.append("")

    # Outliers
    out = stats_info["outliers"]
    def fmt_outliers(items): return ", ".join([f"{x['name']} ({x['value']})" for x in items])
    sections.append("#### Tướng Ngoại Lai Nổi Bật (Stat Outliers):")
    sections.append(f"- **Tầm Đánh (Range)**: Cao nhất [{fmt_outliers(out['range']['top'])}] | Thấp nhất [{fmt_outliers(out['range']['bottom'])}]")
    sections.append(f"- **Máu Cơ Bản (HP)**: Cao nhất [{fmt_outliers(out['hp']['top'])}] | Thấp nhất [{fmt_outliers(out['hp']['bottom'])}]")
    sections.append(f"- **Sát Thương (AD)**: Cao nhất [{fmt_outliers(out['ad']['top'])}] | Thấp nhất [{fmt_outliers(out['ad']['bottom'])}]")
    sections.append("")

    # Spell Analyzer
    sections.append("### 1.3 Spell Analyzer: Trích Xuất Khống Chế (CC) & Hiệu Ứng Chiêu Thức")
    cc_m = spell_info["cc_per_champion_stats"]
    sections.append(f"- **Số lượng loại CC trên mỗi tướng**: Trung bình {cc_m['mean']} (Max: {cc_m['max']}, Min: {cc_m['min']})")
    sections.append(f"- **Tướng thuần sát thương không có CC**: {len(spell_info['champions_without_cc'])} ({', '.join(spell_info['champions_without_cc'][:6])}...)")
    sections.append("")

    top_cc_rows = [[cc, count, f"{pct}%"] for cc, count, pct in spell_info["cc_types_distribution"][:6]]
    sections.append("#### Top Hiệu Ứng Khống Chế (Crowd Control):")
    sections.append(format_table(["Loại CC", "Số Tướng", "Tỷ Lệ"], top_cc_rows))
    sections.append("")

    top_eff_rows = [[eff, count, f"{pct}%"] for eff, count, pct in spell_info["ability_effects_distribution"][:6]]
    sections.append("#### Top Cơ Chế Kỹ Năng (Ability Effects):")
    sections.append(format_table(["Cơ Chế", "Số Tướng", "Tỷ Lệ"], top_eff_rows))
    sections.append("")

    # Enricher
    sections.append("### 1.4 Enricher: Đánh Giá Siêu Dữ Liệu Chiến Thuật (Strategic Metadata)")
    sections.append(f"- **Độ phủ Playstyles**: {enrich_info['playstyles_curated_count']}/{enrich_info['total_master_champions']} ({enrich_info['playstyles_curated_pct']}%)")
    sections.append(f"- **Số tướng rơi vào Playstyle mặc định ('Flexible')**: {len(enrich_info['playstyles_fallback_champions'])} tướng ({', '.join(enrich_info['playstyles_fallback_champions'][:6])}...)")
    sections.append(f"- **Độ phủ Power Curves đã cấu hình**: {enrich_info['powercurves_curated_count']}/{enrich_info['total_master_champions']} (100% đang dùng Default: early 5, mid 6, late 6)")
    sections.append(f"- **Độ phủ Win Conditions đã cấu hình**: {enrich_info['winconditions_curated_count']}/{enrich_info['total_master_champions']} (100% đang dùng Default: ['Teamfight'])")
    sections.append("")

    return "\n".join(sections)
