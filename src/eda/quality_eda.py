"""
Data Quality & Cross-Source Consistency Audit Module.

Directly audits the data quality and merge consistency required by all processor pipelines:
- Schema completeness for ChampionMerger, ItemMerger, and RuneMerger.
- Cross-source value consistency (DDragon vs Meraki combat stats comparison).
- Overall Processor Pipeline Readiness Score.
"""

from typing import Any, Dict, List, Optional

from eda.utils import (
    calculate_stats,
    format_table,
    load_raw_json,
    log,
)

TAG = "QualityAudit"


def audit_champion_completeness():
    """Audit field completeness across DDragon, Meraki, and Lore for ChampionMerger."""
    ddragon = load_raw_json("ddragon", "champions.json") or {}
    meraki = load_raw_json("meraki", "champions.json") or {}
    lore = load_raw_json("lore", "lore.json") or {}

    def check_fields(data_dict, required_fields):
        total = len(data_dict)
        field_missing = {f: 0 for f in required_fields}

        for item in data_dict.values():
            for f in required_fields:
                val = item.get(f)
                if val is None or val == "" or val == [] or val == {}:
                    field_missing[f] += 1

        field_completeness = {
            f: {
                "missing": count,
                "completeness_pct": round(((total - count) / total) * 100, 2) if total else 0,
            }
            for f, count in field_missing.items()
        }
        return {
            "total_records": total,
            "field_completeness": field_completeness,
        }

    dd_fields = ["id", "key", "name", "title", "tags", "stats", "spells", "passive", "lore"]
    mk_fields = ["id", "key", "name", "attackType", "adaptiveType", "stats", "abilities"]
    lore_fields = ["id", "name", "title", "region", "lore", "shortLore"]

    return {
        "ddragon": check_fields(ddragon, dd_fields),
        "meraki": check_fields(meraki, mk_fields),
        "lore": check_fields(lore, lore_fields),
    }


def audit_cross_source_stat_consistency():
    """Compare combat stats between DDragon and Meraki Analytics for common champions."""
    ddragon = load_raw_json("ddragon", "champions.json") or {}
    meraki = load_raw_json("meraki", "champions.json") or {}

    common_names = set(ddragon.keys()) & set(meraki.keys())
    discrepancies = []

    for name in common_names:
        dd_stats = ddragon[name].get("stats", {})
        mk_stats = meraki[name].get("stats", {})

        dd_hp = dd_stats.get("hp", 0)
        mk_hp = mk_stats.get("health", {}).get("flat", 0) if isinstance(mk_stats.get("health"), dict) else 0

        dd_armor = dd_stats.get("armor", 0)
        mk_armor = mk_stats.get("armor", {}).get("flat", 0) if isinstance(mk_stats.get("armor"), dict) else 0

        dd_ad = dd_stats.get("attackdamage", 0)
        mk_ad = mk_stats.get("attackDamage", {}).get("flat", 0) if isinstance(mk_stats.get("attackDamage"), dict) else 0

        hp_diff = abs(dd_hp - mk_hp)
        armor_diff = abs(dd_armor - mk_armor)
        ad_diff = abs(dd_ad - mk_ad)

        if hp_diff > 1.0 or armor_diff > 1.0 or ad_diff > 1.0:
            discrepancies.append({
                "champion": name,
                "hp_diff": round(hp_diff, 2),
                "armor_diff": round(armor_diff, 2),
                "ad_diff": round(ad_diff, 2),
            })

    match_rate = round(((len(common_names) - len(discrepancies)) / len(common_names)) * 100, 2) if common_names else 0

    return {
        "champions_compared": len(common_names),
        "perfect_match_count": len(common_names) - len(discrepancies),
        "discrepancies_count": len(discrepancies),
        "stat_consistency_rate_pct": match_rate,
        "sample_discrepancies": discrepancies[:5],
    }


def audit_item_and_rune_completeness():
    """Audit field completeness for ItemMerger and RuneMerger inputs."""
    ddragon_items = load_raw_json("ddragon", "items.json") or {}
    raw_runes = load_raw_json("ddragon", "runes.json") or []

    # Items
    total_items = len(ddragon_items)
    item_missing_gold = sum(1 for x in ddragon_items.values() if not x.get("gold"))
    item_missing_maps = sum(1 for x in ddragon_items.values() if not x.get("maps"))

    # Runes
    total_runes = 0
    runes_missing_desc = 0
    for tree in raw_runes:
        for slot in tree.get("slots", []):
            for r in slot.get("runes", []):
                total_runes += 1
                if not r.get("shortDesc"):
                    runes_missing_desc += 1

    return {
        "items": {
            "total": total_items,
            "gold_completeness_pct": round(((total_items - item_missing_gold) / total_items) * 100, 2) if total_items else 0,
            "maps_completeness_pct": round(((total_items - item_missing_maps) / total_items) * 100, 2) if total_items else 0,
        },
        "runes": {
            "total": total_runes,
            "desc_completeness_pct": round(((total_runes - runes_missing_desc) / total_runes) * 100, 2) if total_runes else 0,
        },
    }


def audit_data_quality():
    """Execute complete data quality audit across all processor inputs."""
    log(TAG, "Starting cross-source processor data quality audit...")

    champ_comp = audit_champion_completeness()
    stat_cons = audit_cross_source_stat_consistency()
    it_rn_comp = audit_item_and_rune_completeness()

    readiness_score = round((
        champ_comp["ddragon"]["field_completeness"]["stats"]["completeness_pct"] * 0.3
        + champ_comp["lore"]["field_completeness"]["lore"]["completeness_pct"] * 0.3
        + it_rn_comp["items"]["gold_completeness_pct"] * 0.2
        + stat_cons["stat_consistency_rate_pct"] * 0.2
    ), 2)

    results = {
        "champion_completeness": champ_comp,
        "stat_consistency": stat_cons,
        "item_and_rune_completeness": it_rn_comp,
        "overall_processor_readiness_score": readiness_score,
    }

    log(TAG, f"Audit complete. Overall Pipeline Readiness Score: {readiness_score}%")
    return results


def format_quality_report(results):
    """Format quality audit results into readable Markdown text."""
    ch_comp = results["champion_completeness"]
    stat_c = results["stat_consistency"]
    score = results["overall_processor_readiness_score"]

    sections = [
        "## 5. Đánh Giá Chất Lượng Dữ Liệu & Độ Sẵn Sàng Pipeline (Data Quality Audit)",
        "",
        f"### ⭐ Điểm Sẵn Sàng Cho Processor Pipeline (Readiness Score): **{score}%**",
        "",
        "### 5.1 Độ Đầy Đủ Trường Dữ Liệu Tướng Đầu Vào",
    ]

    dd_rows = [
        [f, info["missing"], f"{info['completeness_pct']}%"]
        for f, info in ch_comp["ddragon"]["field_completeness"].items()
    ]
    sections.append("#### Riot Data Dragon:")
    sections.append(format_table(["Trường Dữ Liệu", "Số Bản Ghi Thiếu", "Độ Đầy Đủ"], dd_rows))
    sections.append("")

    # Cross source consistency
    sections.append("### 5.2 Kiểm Tra Độ Lệch Chỉ Số DDragon vs Meraki")
    sections.append(f"- **Số tướng đối chiếu**: {stat_c['champions_compared']} tướng")
    sections.append(f"- **Số tướng khớp chỉ số hoàn hảo (HP/Armor/AD)**: {stat_c['perfect_match_count']}")
    sections.append(f"- **Tỷ lệ đồng bộ chỉ số**: {stat_c['stat_consistency_rate_pct']}%")
    sections.append("")

    return "\n".join(sections)
