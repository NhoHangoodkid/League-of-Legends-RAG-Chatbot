"""
EDA (Exploratory Data Analysis) Package for LoL Raw Knowledge Datasets.

Modules:
- champions_eda: In-depth analysis of champions across DDragon, CDragon, Meraki, and Lore.
- items_eda: Analysis of items, gold economy, stat distributions, and recipe graphs.
- runes_eda: Analysis of runes, keystones, slots, and perk mechanics.
- lore_eda: Analysis of champion lore, factions, bio lengths, and relationship network.
- quality_eda: Cross-source consistency, data completeness, and discrepancy audit.
- visualizer: Chart and plot generation for visual reports.
- utils: Data loaders, numerical metrics, and report formatting utilities.
"""

from .champions_eda import analyze_champions
from .items_eda import analyze_items
from .lore_eda import analyze_lore
from .quality_eda import audit_data_quality
from .runes_eda import analyze_runes
from .visualizer import generate_all_plots

__all__ = [
    "analyze_champions",
    "analyze_items",
    "analyze_runes",
    "analyze_lore",
    "audit_data_quality",
    "generate_all_plots",
]
