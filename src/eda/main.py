"""
Main EDA Runner & Report Generator.

Orchestrates and executes exploratory data analysis across all LoL raw datasets:
1. Champions EDA (DDragon, CDragon, Meraki, Lore)
2. Items EDA (DDragon, CDragon)
3. Runes EDA (DDragon Runes Reforged)
4. Lore & Universe EDA (Regions, Bios, Social graph)
5. Cross-source Data Quality & Consistency Audit
6. Visualization & Plot Generation

Usage:
    python src/eda/main.py             # Run all EDA analyses & generate reports
    python src/eda/main.py --all       # Run all EDA analyses & generate reports
    python src/eda/main.py --champions # Run only champions analysis
    python src/eda/main.py --items     # Run only items analysis
    python src/eda/main.py --runes     # Run only runes analysis
    python src/eda/main.py --lore      # Run only lore analysis
    python src/eda/main.py --quality   # Run only quality audit
    python src/eda/main.py --plots     # Run only plot generation
"""

import argparse
import sys
import time
from pathlib import Path

# Ensure UTF-8 output on Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding = "utf-8")
    except Exception:
        pass

# Add project root to sys.path if run directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from eda.champions_eda import analyze_champions, format_champions_report
from eda.items_eda import analyze_items, format_items_report
from eda.lore_eda import analyze_lore, format_lore_report
from eda.quality_eda import audit_data_quality, format_quality_report
from eda.runes_eda import analyze_runes, format_runes_report
from eda.utils import (
    ensure_eda_dirs,
    log,
    save_report_markdown,
    save_summary_json,
)
from eda.visualizer import generate_all_plots


def run_all_eda(save_reports = True, make_plots = True):
    """
    Run complete exploratory data analysis across all raw data components.
    Directly supports and validates data structures processed by src/processors/.
    """
    ensure_eda_dirs()
    start_time = time.time()
    results = {}
    report_sections = [
        "# BÁO CÁO PHÂN TÍCH KHÁM PHÁ DỮ LIỆU THÔ (EDA REPORT)",
        "",
    ]

    # 1. Champions Analysis (ChampionMerger + SpellAnalyzer + Enricher)
    print("\n[1/6] Analyzing Champions Data (DDragon, CDragon, Meraki, Lore)...")
    t0 = time.time()
    champ_res = analyze_champions()
    results["champions"] = champ_res
    report_sections.append(format_champions_report(champ_res))
    report_sections.append("\n---\n")
    print(f"Champions EDA finished in {time.time() - t0:.2f}s")

    # 2. Items Analysis (ItemMerger)
    print("\n[2/6] Analyzing Items Data (DDragon, CDragon)...")
    t0 = time.time()
    item_res = analyze_items()
    results["items"] = item_res
    report_sections.append(format_items_report(item_res))
    report_sections.append("\n---\n")
    print(f"Items EDA finished in {time.time() - t0:.2f}s")

    # 3. Runes Analysis (RuneMerger)
    print("\n[3/6] Analyzing Runes & Perks Data (DDragon)...")
    t0 = time.time()
    rune_res = analyze_runes()
    results["runes"] = rune_res
    report_sections.append(format_runes_report(rune_res))
    report_sections.append("\n---\n")
    print(f"Runes EDA finished in {time.time() - t0:.2f}s")

    # 4. Lore Analysis (ChampionMerger Lore inputs)
    print("\n[4/6] Analyzing Lore & Universe Data (Bios, Factions, Graph)...")
    t0 = time.time()
    lore_res = analyze_lore()
    results["lore"] = lore_res
    report_sections.append(format_lore_report(lore_res))
    report_sections.append("\n---\n")
    print(f"Lore EDA finished in {time.time() - t0:.2f}s")

    # 5. Data Quality Audit (Processor Data Quality)
    print("\n[5/6] Auditing Data Quality & Pipeline Readiness...")
    t0 = time.time()
    qual_res = audit_data_quality()
    results["quality"] = qual_res
    report_sections.append(format_quality_report(qual_res))
    report_sections.append("\n---\n")
    print(f"Quality Audit finished in {time.time() - t0:.2f}s")

    # 6. Plot Generation
    if make_plots:
        print("\n[6/6] Generating Visual Charts & Plots...")
        t0 = time.time()
        plots = generate_all_plots()
        results["plots_generated"] = [str(p.name) for p in plots]
        print(f"Visualizations finished in {time.time() - t0:.2f}s")

    # Save Output Reports
    if save_reports:
        full_report_text = "\n".join(report_sections)
        save_report_markdown(full_report_text, "eda_report.md")
        save_summary_json(results, "eda_summary.json")

    total_time = time.time() - start_time
    print(f"EDA PIPELINE COMPLETED SUCCESSFULLY IN {total_time:.2f}s")

    return results


def main():
    parser = argparse.ArgumentParser(description = "LoL Knowledge Bot - Raw Data EDA Runner")
    parser.add_argument("--all", action = "store_true", help = "Run full EDA pipeline and save reports & plots (default)")
    parser.add_argument("--champions", action = "store_true", help = "Run only champions EDA")
    parser.add_argument("--items", action = "store_true", help = "Run only items EDA")
    parser.add_argument("--runes", action = "store_true", help = "Run only runes EDA")
    parser.add_argument("--lore", action = "store_true", help = "Run only universe lore EDA")
    parser.add_argument("--quality", action = "store_true", help = "Run only data quality audit")
    parser.add_argument("--plots", action = "store_true", help = "Generate only visualization plots")
    parser.add_argument("--no-plots", action = "store_true", help = "Skip generating plot images")

    args = parser.parse_args()
    ensure_eda_dirs()

    run_all = args.all or not (
        args.champions or args.items or args.runes or args.lore or args.quality or args.plots
    )

    if run_all:
        run_all_eda(save_reports = True, make_plots = not args.no_plots)
        return

    start_time = time.time()

    if args.champions:
        print("\n--- Champions EDA ---")
        res = analyze_champions()
        print(format_champions_report(res))

    if args.items:
        print("\n--- Items EDA ---")
        res = analyze_items()
        print(format_items_report(res))

    if args.runes:
        print("\n--- Runes EDA ---")
        res = analyze_runes()
        print(format_runes_report(res))

    if args.lore:
        print("\n--- Lore EDA ---")
        res = analyze_lore()
        print(format_lore_report(res))

    if args.quality:
        print("\n--- Data Quality Audit ---")
        res = audit_data_quality()
        print(format_quality_report(res))

    if args.plots:
        print("\n--- Generating Plots ---")
        generate_all_plots()

    elapsed = time.time() - start_time
    print(f"\nSelected EDA component(s) finished in {elapsed:.2f}s")


if __name__ == "__main__":
    main()
