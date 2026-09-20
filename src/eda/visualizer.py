"""
Visualizer Module for EDA Reports.

Generates polished, modern statistical visualizations and charts:
- Champion role and attack type distributions.
- Base stat distributions and box plots.
- Item gold economy histograms.
- Regional lore distributions and bio length distributions.

All generated plots are saved to the `src/eda/output/plots/` directory.
"""

from pathlib import Path

from eda.utils import (
    plots_dir,
    ensure_eda_dirs,
    load_raw_json,
    log,
)

tag = "Visualizer"


def setup_plot_style(plt):
    """Apply clean, modern dark aesthetic style to matplotlib figures."""
    plt.style.use("seaborn-v0_8-darkgrid" if "seaborn-v0_8-darkgrid" in plt.style.available else "default")
    plt.rcParams.update({
        "font.size": 10,
        "axes.labelsize": 11,
        "axes.titlesize": 13,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "figure.titlesize": 14,
        "figure.autolayout": True,
    })


def plot_champion_roles(output_dir):
    """Generate bar chart for champion primary roles."""
    try:
        import matplotlib.pyplot as plt

        setup_plot_style(plt)

        ddragon = load_raw_json("ddragon", "champions.json") or {}
        roles = [c.get("tags", ["Unknown"])[0] for c in ddragon.values() if c.get("tags")]

        from collections import Counter
        counts = Counter(roles).most_common()

        names = [x[0] for x in counts]
        vals = [x[1] for x in counts]
        colors = ["#4A90E2", "#50E3C2", "#F5A623", "#E94E77", "#9013FE", "#7ED321"][:len(names)]

        fig, ax = plt.subplots(figsize = (8, 5))
        bars = ax.bar(names, vals, color = colors, edgecolor = "#2C3E50", linewidth = 1)
        ax.set_title("League of Legends - Champion Primary Roles Distribution", fontweight = "bold", pad = 15)
        ax.set_xlabel("Role / Class")
        ax.set_ylabel("Number of Champions")

        for bar in bars:
            yval = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2.0, yval + 1, f"{int(yval)}", ha = "center", va = "bottom", fontweight = "bold")

        target = output_dir / "champion_roles.png"
        fig.savefig(target, dpi = 200, bbox_inches = "tight")
        plt.close(fig)
        return target
    except Exception as e:
        log(tag, f"Could not generate champion roles plot: {e}")
        return None


def plot_champion_attack_types(output_dir):
    """Generate pie chart for Melee vs Ranged and Physical vs Magic."""
    try:
        import matplotlib.pyplot as plt

        setup_plot_style(plt)

        meraki = load_raw_json("meraki", "champions.json") or {}
        atk_types = [c.get("attackType", "UNKNOWN") for c in meraki.values() if c.get("attackType")]
        adp_types = [c.get("adaptiveType", "UNKNOWN") for c in meraki.values() if c.get("adaptiveType")]

        from collections import Counter
        atk_counts = Counter(atk_types)
        adp_counts = Counter(adp_types)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize = (10, 5))

        # Attack Type
        ax1.pie(
            atk_counts.values(),
            labels = atk_counts.keys(),
            autopct = "%1.1f%%",
            startangle = 140,
            colors = ["#E74C3C", "#3498DB"],
            wedgeprops = {"edgecolor": "white", "linewidth": 1.5},
        )
        ax1.set_title("Attack Type (Melee vs Ranged)", fontweight = "bold")

        # Adaptive Type
        ax2.pie(
            adp_counts.values(),
            labels = adp_counts.keys(),
            autopct = "%1.1f%%",
            startangle = 140,
            colors = ["#E67E22", "#9B59B6", "#95A5A6"],
            wedgeprops = {"edgecolor": "white", "linewidth": 1.5},
        )
        ax2.set_title("Adaptive Damage Type", fontweight = "bold")

        target = output_dir / "champion_attack_types.png"
        fig.savefig(target, dpi = 200, bbox_inches = "tight")
        plt.close(fig)
        return target
    except Exception as e:
        log(tag, f"Could not generate attack types plot: {e}")
        return None


def plot_champion_stats_boxplots(output_dir):
    """Generate box plots for core champion base stats."""
    try:
        import matplotlib.pyplot as plt

        setup_plot_style(plt)

        ddragon = load_raw_json("ddragon", "champions.json") or {}
        hps = [c["stats"]["hp"] for c in ddragon.values() if "stats" in c and "hp" in c["stats"]]
        armors = [c["stats"]["armor"] for c in ddragon.values() if "stats" in c and "armor" in c["stats"]]
        ads = [c["stats"]["attackdamage"] for c in ddragon.values() if "stats" in c and "attackdamage" in c["stats"]]
        ranges = [c["stats"]["attackrange"] for c in ddragon.values() if "stats" in c and "attackrange" in c["stats"]]

        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize = (10, 8))

        ax1.boxplot(hps, patch_artist = True, boxprops = dict(facecolor = "#2ECC71"))
        ax1.set_title("Base Health (HP)", fontweight = "bold")

        ax2.boxplot(armors, patch_artist = True, boxprops = dict(facecolor = "#3498DB"))
        ax2.set_title("Base Armor", fontweight = "bold")

        ax3.boxplot(ads, patch_artist = True, boxprops = dict(facecolor = "#E74C3C"))
        ax3.set_title("Base Attack Damage (AD)", fontweight = "bold")

        ax4.boxplot(ranges, patch_artist = True, boxprops = dict(facecolor = "#F39C12"))
        ax4.set_title("Attack Range", fontweight = "bold")

        target = output_dir / "champion_stats_boxplots.png"
        fig.savefig(target, dpi = 200, bbox_inches = "tight")
        plt.close(fig)
        return target
    except Exception as e:
        log(tag, f"Could not generate stats boxplots: {e}")
        return None


def plot_item_gold_distribution(output_dir):
    """Generate histogram of item total gold prices."""
    try:
        import matplotlib.pyplot as plt

        setup_plot_style(plt)

        items = load_raw_json("ddragon", "items.json") or {}
        costs = [
            i["gold"]["total"]
            for i in items.values()
            if i.get("gold", {}).get("purchasable", False) and i.get("gold", {}).get("total", 0) > 0
        ]

        fig, ax = plt.subplots(figsize = (8, 5))
        ax.hist(costs, bins = 25, color = "#F1C40F", edgecolor = "#2C3E50", alpha = 0.85)
        ax.set_title("League of Legends - Purchasable Items Gold Cost Distribution", fontweight = "bold", pad = 15)
        ax.set_xlabel("Total Gold Cost")
        ax.set_ylabel("Number of Items")

        target = output_dir / "item_gold_distribution.png"
        fig.savefig(target, dpi = 200, bbox_inches = "tight")
        plt.close(fig)
        return target
    except Exception as e:
        log(tag, f"Could not generate item gold plot: {e}")
        return None


def plot_lore_factions(output_dir):
    """Generate horizontal bar chart for champion counts per region/faction."""
    try:
        import matplotlib.pyplot as plt

        setup_plot_style(plt)

        lore = load_raw_json("lore", "lore.json") or {}
        regions = [
            c.get("region") if c.get("region") and c.get("region").strip() else "Runeterra"
            for c in lore.values()
        ]

        from collections import Counter
        counts = Counter(regions).most_common()

        names = [x[0] for x in counts][::-1]
        vals = [x[1] for x in counts][::-1]

        fig, ax = plt.subplots(figsize = (9, 7))
        bars = ax.barh(names, vals, color = "#16A085", edgecolor = "#1ABC9C")
        ax.set_title("Champions by Runeterra Region and Faction", fontweight = "bold", pad = 15)
        ax.set_xlabel("Number of Champions")

        for bar in bars:
            w = bar.get_width()
            ax.text(w + 0.3, bar.get_y() + bar.get_height() / 2.0, f"{int(w)}", ha = "left", va = "center", fontweight = "bold")

        target = output_dir / "lore_factions.png"
        fig.savefig(target, dpi = 200, bbox_inches = "tight")
        plt.close(fig)
        return target
    except Exception as e:
        log(tag, f"Could not generate lore factions plot: {e}")
        return None


def plot_lore_bio_lengths(output_dir):
    """Generate histogram of biography word count lengths."""
    try:
        import matplotlib.pyplot as plt

        setup_plot_style(plt)

        lore = load_raw_json("lore", "lore.json") or {}
        words = [len(c.get("lore", "").split()) for c in lore.values() if c.get("lore")]

        fig, ax = plt.subplots(figsize = (8, 5))
        ax.hist(words, bins = 20, color = "#8E44AD", edgecolor = "#2C3E50", alpha = 0.85)
        ax.set_title("Champion Universe Full Biography Word Count Distribution", fontweight = "bold", pad = 15)
        ax.set_xlabel("Word Count per Champion Bio")
        ax.set_ylabel("Frequency")

        target = output_dir / "lore_bio_lengths.png"
        fig.savefig(target, dpi = 200, bbox_inches = "tight")
        plt.close(fig)
        return target
    except Exception as e:
        log(tag, f"Could not generate bio lengths plot: {e}")
        return None


def plot_spell_cc_effects(output_dir):
    """Generate bar chart for SpellAnalyzer CC and ability effects frequency."""
    try:
        import matplotlib.pyplot as plt
        from eda.champions_eda import analyze_spell_analyzer_extraction

        setup_plot_style(plt)

        sim = analyze_spell_analyzer_extraction()
        cc_data = sim["cc_types_distribution"][:6]
        eff_data = sim["ability_effects_distribution"][:6]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize = (12, 5))

        # Top CC Types
        cc_names = [x[0] for x in cc_data]
        cc_vals = [x[1] for x in cc_data]
        bars1 = ax1.bar(cc_names, cc_vals, color = "#E74C3C", edgecolor = "#C0392B")
        ax1.set_title("Top Crowd Control (CC) Types Detected", fontweight = "bold")
        ax1.set_ylabel("Champions Count")
        for b in bars1:
            y = b.get_height()
            ax1.text(b.get_x() + b.get_width() / 2.0, y + 1, f"{int(y)}", ha = "center", va = "bottom", fontweight = "bold")

        # Top Effects
        eff_names = [x[0] for x in eff_data]
        eff_vals = [x[1] for x in eff_data]
        bars2 = ax2.bar(eff_names, eff_vals, color = "#3498DB", edgecolor = "#2980B9")
        ax2.set_title("Top Ability Effects Detected", fontweight = "bold")
        ax2.set_ylabel("Champions Count")
        for b in bars2:
            y = b.get_height()
            ax2.text(b.get_x() + b.get_width() / 2.0, y + 1, f"{int(y)}", ha = "center", va = "bottom", fontweight = "bold")

        target = output_dir / "processor_cc_effects.png"
        fig.savefig(target, dpi = 200, bbox_inches = "tight")
        plt.close(fig)
        return target
    except Exception as e:
        log(tag, f"Could not generate CC and effects plot: {e}")
        return None


def generate_all_plots(output_dir = None):
    """Generate and save all exploratory data visualization charts."""
    ensure_eda_dirs()
    target_dir = output_dir or plots_dir
    target_dir.mkdir(parents = True, exist_ok = True)

    log(tag, f"Generating statistical plots to {target_dir}...")
    generated_plots = []

    plots_funcs = [
        ("Champion Roles", plot_champion_roles),
        ("Champion Attack Types", plot_champion_attack_types),
        ("Champion Stats Boxplots", plot_champion_stats_boxplots),
        ("Item Gold Distribution", plot_item_gold_distribution),
        ("Lore Factions", plot_lore_factions),
        ("Lore Bio Lengths", plot_lore_bio_lengths),
        ("Processor CC and Effects", plot_spell_cc_effects),
    ]

    for label, fn in plots_funcs:
        p = fn(target_dir)
        if p and p.exists():
            generated_plots.append(p)
            log(tag, f" Generated {label} -> {p.name}")

    log(tag, f"Plot generation finished. Created {len(generated_plots)} visual charts.")
    return generated_plots
