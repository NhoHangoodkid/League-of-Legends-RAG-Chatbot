"""
Items Exploratory Data Analysis (EDA) Module.

Directly analyzes item data according to the processing steps in `ItemMerger`:
- Filtering logic: `purchasable == True` AND `maps['11'] == True` (Summoner's Rift Map 11).
- Economy & cost modeling (`cost.total`, `cost.base`, `cost.sell`).
- Stats extractions (`FlatPhysicalDamageMod`, `FlatMagicDamageMod`, `FlatHPPoolMod`, etc.).
- Tag & category merging (`set(tags + categories)`).
- Recipe graphs and item hierarchy (`buildFrom`, `buildInto`, components vs final items).
"""

from collections import Counter
from typing import Any, Dict, List, Optional

from eda.utils import (
    calculate_stats,
    format_table,
    get_frequency_distribution,
    load_raw_json,
    log,
)

TAG = "ItemsEDA"


def analyze_item_merger_filtering():
    """Simulate exact item filtering performed by ItemMerger."""
    ddragon_items = load_raw_json("ddragon", "items.json") or {}
    cdragon_items = load_raw_json("cdragon", "items.json") or []

    # Map CDragon items by ID
    cd_dict = {}
    if isinstance(cdragon_items, list):
        cd_dict = {str(item.get("id")): item for item in cdragon_items if item.get("id")}
    elif isinstance(cdragon_items, dict):
        cd_dict = cdragon_items

    total_raw = len(ddragon_items)
    retained_items = []
    filtered_non_purchasable = 0
    filtered_non_map11 = 0

    for item_id, item in ddragon_items.items():
        gold = item.get("gold", item.get("cost", {}))
        if not gold.get("purchasable", True):
            filtered_non_purchasable += 1
            continue

        maps = item.get("maps", {})
        if maps and not maps.get("11", True):
            filtered_non_map11 += 1
            continue

        cd = cd_dict.get(str(item_id), {})
        retained_items.append({
            "id": int(item_id) if str(item_id).isdigit() else item_id,
            "name": item.get("name", "") or cd.get("name", ""),
            "gold_total": gold.get("total", cd.get("priceTotal", 0)),
            "gold_base": gold.get("base", cd.get("price", 0)),
            "gold_sell": gold.get("sell", 0),
            "stats": item.get("stats", {}),
            "tags": list(set(item.get("tags", []) + cd.get("categories", []))),
            "buildFrom": item.get("from", item.get("buildFrom", [])),
            "buildInto": item.get("into", item.get("buildInto", [])),
            "has_cdragon": bool(cd),
        })

    total_retained = len(retained_items)

    # Hierarchy classification
    basic_components = [x for x in retained_items if not x["buildFrom"] and x["buildInto"]]
    intermediate_items = [x for x in retained_items if x["buildFrom"] and x["buildInto"]]
    final_items = [x for x in retained_items if x["buildFrom"] and not x["buildInto"]]
    standalone_items = [x for x in retained_items if not x["buildFrom"] and not x["buildInto"]]

    return {
        "total_raw_items": total_raw,
        "retained_count": total_retained,
        "retained_pct": round((total_retained / total_raw) * 100, 2) if total_raw else 0,
        "filtered_non_purchasable": filtered_non_purchasable,
        "filtered_non_map11": filtered_non_map11,
        "retained_items": retained_items,
        "hierarchy": {
            "basic_components_count": len(basic_components),
            "intermediate_items_count": len(intermediate_items),
            "final_items_count": len(final_items),
            "standalone_items_count": len(standalone_items),
        },
    }


def analyze_item_costs_and_stats(filtered_items):
    """Analyze cost distribution and stat affixes for items retained by ItemMerger."""
    total_costs = []
    base_costs = []
    sell_costs = []
    resale_ratios = []

    stat_providers = Counter()
    tag_counter = Counter()

    stat_mapping = {
        "FlatPhysicalDamageMod": "Attack Damage (AD)",
        "FlatMagicDamageMod": "Ability Power (AP)",
        "FlatHPPoolMod": "Health (HP)",
        "FlatArmorMod": "Armor",
        "FlatSpellBlockMod": "Magic Resist (MR)",
        "PercentAttackSpeedMod": "Attack Speed",
        "PercentCritChanceMod": "Crit Chance",
        "FlatMovementSpeedMod": "Movement Speed",
        "PercentMovementSpeedMod": "% Movement Speed",
        "FlatMPPoolMod": "Mana",
        "PercentLifeStealMod": "Life Steal",
    }

    for item in filtered_items:
        tot = item.get("gold_total", 0)
        base = item.get("gold_base", 0)
        sell = item.get("gold_sell", 0)

        if tot > 0:
            total_costs.append(tot)
            base_costs.append(base)
            sell_costs.append(sell)
            resale_ratios.append(round((sell / tot) * 100, 2))

        for stat_key, label in stat_mapping.items():
            if stat_key in item.get("stats", {}) and item["stats"][stat_key] > 0:
                stat_providers[label] += 1

        for tag in item.get("tags", []):
            tag_counter[tag] += 1

    sorted_by_price = sorted(filtered_items, key = lambda x: x["gold_total"], reverse = True)
    total_items = len(filtered_items)

    return {
        "cost_total_stats": calculate_stats(total_costs),
        "cost_base_stats": calculate_stats(base_costs),
        "cost_sell_stats": calculate_stats(sell_costs),
        "resale_ratio_stats": calculate_stats(resale_ratios),
        "top_expensive_items": sorted_by_price[:8],
        "stat_providers_distribution": [
            (label, count, round((count / total_items) * 100, 2))
            for label, count in stat_providers.most_common()
        ],
        "tags_distribution": [
            (tag, count, round((count / total_items) * 100, 2))
            for tag, count in tag_counter.most_common(12)
        ],
    }


def analyze_items():
    """Execute complete item EDA aligned with ItemMerger."""
    log(TAG, "Starting item analysis aligned with ItemMerger...")

    filter_res = analyze_item_merger_filtering()
    costs_and_stats = analyze_item_costs_and_stats(filter_res["retained_items"])

    results = {
        "filtering": filter_res,
        "costs_and_stats": costs_and_stats,
    }

    log(TAG, f"Analysis complete. Evaluated {filter_res['retained_count']} items retained after Map 11 filter.")
    return results


def format_items_report(results):
    """Format item EDA results into readable Markdown text."""
    flt = results["filtering"]
    cs = results["costs_and_stats"]

    sections = [
        "## 2. Phân Tích Dữ Liệu Trang Bị (Item Processing Pipeline)",
        "",
        "### 2.1 Item Merger: Mô Phỏng Bộ Lọc Cửa Hàng & Bản Đồ Summoner's Rift (Map 11)",
        f"- **Tổng số bản ghi trang bị thô**: {flt['total_raw_items']}",
        f"- **Số trang bị được giữ lại sau lọc**: {flt['retained_count']} ({flt['retained_pct']}%)",
        f"- **Số bản ghi bị loại bỏ**: {flt['filtered_non_purchasable']} (Không mua được) | {flt['filtered_non_map11']} (Không thuộc Map 11 SR / Chế độ khác)",
        "",
        "#### Phân loại cấp bậc trang bị sau lọc:",
        f"- **Linh kiện cơ bản (Basic Components)**: {flt['hierarchy']['basic_components_count']} trang bị",
        f"- **Trang bị cấp 2 (Intermediate Recipes)**: {flt['hierarchy']['intermediate_items_count']} trang bị",
        f"- **Trang bị Hoàn Chỉnh / Huyền Thoại (Final Legendary Items)**: {flt['hierarchy']['final_items_count']} trang bị",
        f"- **Trang bị độc lập / Tiêu hao (Consumables/Boots/Trinkets)**: {flt['hierarchy']['standalone_items_count']} trang bị",
        "",
        "### 2.2 Kinh Tế Vàng Trang Bị Trong Trận Đấu (Gold Economy)",
    ]

    c_m = cs["cost_total_stats"]
    sections.append(
        f"- **Giá vàng mua (Total Gold)**: Min {c_m['min']} | 25% {c_m['q25']} | Trung Vị {c_m['median']} | Trung Bình {c_m['mean']} | 75% {c_m['q75']} | Max {c_m['max']} (Std: {c_m['std']})"
    )
    r_m = cs["resale_ratio_stats"]
    sections.append(f"- **Tỷ lệ thu hồi vàng khi bán lại (Resale Ratio)**: Trung bình {r_m['mean']}%")
    sections.append("")

    # Top expensive table
    top_exp_rows = [
        [x["id"], x["name"], f"{x['gold_total']} Vàng", f"{x['gold_sell']} Vàng"]
        for x in cs["top_expensive_items"]
    ]
    sections.append("#### Top Trang Bị Đắt Nhất Trên Bản Đồ Summoner's Rift:")
    sections.append(format_table(["ID", "Tên Trang Bị", "Giá Mua", "Giá Bán"], top_exp_rows))
    sections.append("")

    # Stats provided table
    stat_rows = [[lbl, count, f"{pct}%"] for lbl, count, pct in cs["stat_providers_distribution"]]
    sections.append("### 2.3 Phân Bố Thuộc Tính Cung Cấp Sau Hợp Nhất (Stats Provided)")
    sections.append(format_table(["Thuộc Tính", "Số Trang Bị Cung Cấp", "Tỷ Lệ"], stat_rows))
    sections.append("")

    return "\n".join(sections)
