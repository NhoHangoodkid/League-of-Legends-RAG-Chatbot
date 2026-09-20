"""
Runes and Perks Exploratory Data Analysis (EDA) Module.

Directly analyzes rune data according to the processing steps in `RuneMerger`:
- Structuring raw DDragon runesReforged into `byId` (flat map) and `byTree` (5 trees).
- Keystones (Slot 0) vs Minor Runes (Slots 1, 2, 3) configuration.
- Text description cleanings (`shortDesc`, `longDesc`) and keyword mechanical indicators.
"""

import re
from collections import Counter

from eda.utils import (
    calculate_stats,
    format_table,
    get_frequency_distribution,
    load_raw_json,
    log,
)

tag = "RunesEDA"


def strip_html_tags(text):
    """Strip HTML formatting tags often embedded in Riot description strings."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def analyze_rune_merger_structure():
    """Simulate RuneMerger byId and byTree structuring and analyze perk distribution."""
    raw_runes = load_raw_json("ddragon", "runes.json") or []

    runes_by_tree = {}
    runes_flat = {}
    keystones = []
    minor_runes = []
    short_desc_lengths = []
    long_desc_lengths = []

    keyword_counter = Counter()
    target_keywords = [
        "damage", "heal", "shield", "attack speed", "movement speed",
        "cooldown", "stack", "bonus", "mana", "gold", "takedown", "adaptive",
    ]

    for tree in raw_runes:
        tree_name = tree.get("name", "")
        tree_id = tree.get("id", 0)
        runes_by_tree[tree_name] = []

        for slot_idx, slot in enumerate(tree.get("slots", [])):
            for r in slot.get("runes", []):
                rune_id = str(r.get("id", ""))
                short_d = strip_html_tags(r.get("shortDesc", ""))
                long_d = strip_html_tags(r.get("longDesc", ""))

                short_desc_lengths.append(len(short_d.split()))
                long_desc_lengths.append(len(long_d.split()))

                combined = (short_d + " " + long_d).lower()
                for kw in target_keywords:
                    if kw in combined:
                        keyword_counter[kw] += 1

                rune_obj = {
                    "id": r.get("id", 0),
                    "name": r.get("name", ""),
                    "tree": tree_name,
                    "treeId": tree_id,
                    "slot": slot_idx,
                    "is_keystone": (slot_idx == 0),
                    "short_desc_words": len(short_d.split()),
                    "long_desc_words": len(long_d.split()),
                }

                runes_flat[rune_id] = rune_obj
                runes_by_tree[tree_name].append(rune_obj)

                if slot_idx == 0:
                    keystones.append(rune_obj)
                else:
                    minor_runes.append(rune_obj)

    tree_breakdown = [
        {
            "name": tname,
            "keystones": sum(1 for x in r_list if x["is_keystone"]),
            "minor_runes": sum(1 for x in r_list if not x["is_keystone"]),
            "total": len(r_list),
        }
        for tname, r_list in runes_by_tree.items()
    ]

    return {
        "total_trees": len(runes_by_tree),
        "total_runes_flat": len(runes_flat),
        "total_keystones": len(keystones),
        "total_minor_runes": len(minor_runes),
        "tree_breakdown": tree_breakdown,
        "short_desc_stats": calculate_stats(short_desc_lengths),
        "long_desc_stats": calculate_stats(long_desc_lengths),
        "keyword_mechanics": keyword_counter.most_common(10),
    }


def analyze_runes():
    """Execute complete rune EDA aligned with RuneMerger."""
    log(tag, "Starting runes analysis aligned with RuneMerger...")

    structure_info = analyze_rune_merger_structure()

    results = {
        "structure": structure_info,
    }

    log(tag, f"Analysis complete. Evaluated {structure_info['total_runes_flat']} runes across {structure_info['total_trees']} trees.")
    return results


def format_runes_report(results):
    """Format rune EDA results into readable Markdown text."""
    st = results["structure"]

    sections = [
        "## 3. Phân Tích Dữ Liệu Bảng Ngọc (Rune Processing Pipeline)",
        "",
        "### 3.1 Rune Merger: Cấu Trúc Bảng Ngọc byTree and byId",
        f"- **Tổng số hệ ngọc chính (Trees)**: {st['total_trees']}",
        f"- **Tổng số ngọc siêu cấp (Keystones - Slot 0)**: {st['total_keystones']}",
        f"- **Tổng số ngọc sơ cấp (Minor Runes - Slots 1, 2, 3)**: {st['total_minor_runes']}",
        f"- **Tổng số bản ghi ngọc phẳng (byId Map)**: {st['total_runes_flat']}",
        "",
    ]

    # Tree breakdown table
    tree_rows = [
        [t["name"], t["keystones"], t["minor_runes"], t["total"]]
        for t in st["tree_breakdown"]
    ]
    sections.append(format_table(["Hệ Ngọc", "Ngọc Siêu Cấp", "Ngọc Sơ Cấp", "Tổng Số"], tree_rows))
    sections.append("")

    # Text and Keywords
    s_m = st["short_desc_stats"]
    l_m = st["long_desc_stats"]
    sections.append("### 3.2 Phân Tích Văn Bản Mô Tả and Cơ Chế Hiệu Ứng")
    sections.append(f"- **Độ dài mô tả ngắn (Short Desc)**: Trung bình {s_m['mean']} từ (Max: {s_m['max']} từ)")
    sections.append(f"- **Độ dài mô tả chi tiết (Long Desc)**: Trung bình {l_m['mean']} từ (Max: {l_m['max']} từ)")
    sections.append("")

    kw_rows = [[kw.title(), count] for kw, count in st["keyword_mechanics"]]
    sections.append("#### Tần Suất Cơ Chế Xuất Hiện Trong Bảng Ngọc:")
    sections.append(format_table(["Cơ Chế / Từ Khóa", "Số Lượng Ngọc Áp Dụng"], kw_rows))
    sections.append("")

    return "\n".join(sections)
