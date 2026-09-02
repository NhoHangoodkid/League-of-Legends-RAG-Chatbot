"""
Lore & Universe Exploratory Data Analysis (EDA) Module.

Directly analyzes Universe lore datasets feeding into `ChampionMerger`:
- Regional and faction classifications (`region`, `faction_slug`).
- Biography text lengths and corpus metrics for RAG chunking (`lore`, `shortLore`).
- Social and relationship graphs (`related_champions` connections between champions).
"""

from collections import Counter
from typing import Any, Dict, List, Optional, Set, Tuple

from eda.utils import (
    calculate_stats,
    format_table,
    get_frequency_distribution,
    load_all_universe_files,
    load_raw_json,
    log,
)

TAG = "LoreEDA"


def analyze_lore_for_processor():
    """Analyze lore fields specifically merged into ChampionMerger output."""
    lore_data = load_raw_json("lore", "lore.json") or {}
    universe_data = load_all_universe_files()

    regions = []
    faction_slugs = []
    has_quote_count = 0
    short_lore_words = []
    full_lore_words = []
    longest_bios = []

    for name, champ in lore_data.items():
        reg = champ.get("region") or "Runeterra (Unaffiliated)"
        f_slug = champ.get("faction_slug") or "unaffiliated"
        quote = champ.get("quote", "")

        regions.append(reg)
        faction_slugs.append(f_slug)
        if quote and quote.strip():
            has_quote_count += 1

        s_words = len((champ.get("shortLore") or "").split())
        f_words = len((champ.get("lore") or "").split())

        short_lore_words.append(s_words)
        full_lore_words.append(f_words)

        longest_bios.append({
            "name": name,
            "region": reg,
            "words": f_words,
        })

    longest_bios.sort(key = lambda x: x["words"], reverse = True)

    # Social graph / related champions analysis
    connections = []
    all_edges = set()
    for slug, data in universe_data.items():
        related_list = data.get("related-champions", []) or []
        rel_slugs = [r.get("slug", "") if isinstance(r, dict) else str(r) for r in related_list if r]
        rel_count = len(rel_slugs)
        connections.append(rel_count)
        for r in rel_slugs:
            if r:
                all_edges.add(tuple(sorted([slug, r])))

    return {
        "total_champions": len(lore_data),
        "has_quote_count": has_quote_count,
        "region_distribution": get_frequency_distribution(regions),
        "faction_slug_distribution": get_frequency_distribution(faction_slugs),
        "short_lore_stats": calculate_stats(short_lore_words),
        "full_lore_stats": calculate_stats(full_lore_words),
        "total_corpus_words": sum(full_lore_words),
        "top_longest_bios": longest_bios[:5],
        "social_graph": {
            "total_nodes": len(universe_data),
            "total_unique_edges": len(all_edges),
            "connections_per_champ_stats": calculate_stats(connections),
        },
    }


def analyze_lore():
    """Execute complete lore EDA aligned with ChampionMerger."""
    log(TAG, "Starting lore analysis aligned with ChampionMerger...")

    lore_info = analyze_lore_for_processor()

    results = {
        "lore_summary": lore_info,
    }

    log(TAG, f"Analysis complete. Evaluated {lore_info['total_champions']} lore entries.")
    return results


def format_lore_report(results):
    """Format lore EDA results into readable Markdown text."""
    ls = results["lore_summary"]

    sections = [
        "## 4. Phân Tích Dữ Liệu Cốt Truyện (Lore Enrichment Pipeline)",
        "",
        "### 4.1 Phân Bố Khu Vực & Faction (Regions & Factions)",
        f"- **Tổng số tướng có tiểu sử**: {ls['total_champions']}",
        f"- **Số tướng có câu trích dẫn đặc trưng (Quote)**: {ls['has_quote_count']}/{ls['total_champions']}",
        "",
    ]

    # Regions table
    reg_rows = [[r, count, f"{pct}%"] for r, count, pct in ls["region_distribution"]]
    sections.append(format_table(["Khu Vực (Region)", "Số Tướng Trực Thuộc", "Tỷ Lệ"], reg_rows))
    sections.append("")

    # Bio Word Count
    sections.append("### 4.2 Thống Kê Dung Lượng Văn Bản Tiểu Sử")
    sections.append(f"- **Tổng số từ trong toàn bộ kho tiểu sử**: {ls['total_corpus_words']:,} từ")
    f_m = ls["full_lore_stats"]
    sections.append(
        f"- **Độ dài Full Bio (Số từ)**: Min {f_m['min']} | 25% {f_m['q25']} | Trung Vị {f_m['median']} | Trung Bình {f_m['mean']} | 75% {f_m['q75']} | Max {f_m['max']} (Std: {f_m['std']})"
    )
    sections.append("")

    top_bio_rows = [[x["name"], x["region"], f"{x['words']} từ"] for x in ls["top_longest_bios"]]
    sections.append("#### Top Tướng Có Tiểu Sử Dài Nhất:")
    sections.append(format_table(["Tên Tướng", "Khu Vực", "Số Từ"], top_bio_rows))
    sections.append("")

    # Social graph
    sg = ls["social_graph"]
    c_m = sg["connections_per_champ_stats"]
    sections.append("### 4.3 Đồ Thị Quan Hệ Giữa Các Tướng (Related Champions Graph)")
    sections.append(f"- **Tổng số liên kết độc nhất giữa các tướng**: {sg['total_unique_edges']} cạnh")
    sections.append(f"- **Số liên hệ trên mỗi tướng**: Trung bình {c_m['mean']} mối quan hệ (Max: {c_m['max']})")
    sections.append("")

    return "\n".join(sections)
