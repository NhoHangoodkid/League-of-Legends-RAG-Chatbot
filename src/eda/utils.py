"""
Utility functions and data loaders for EDA (Exploratory Data Analysis).

Provides common helper functions across EDA modules:
- Directory paths and data loading from collectors/raw.
- Statistical computation helpers (mean, median, std, quartiles, frequency tables).
- Markdown and ASCII report formatting helpers.
- File saving utilities for reports and summaries.
"""

import json
import math
from pathlib import Path

# Base Directory Resolution
eda_dir = Path(__file__).resolve().parent
project_root = eda_dir.parent.parent
src_dir = project_root / "src"
raw_dir = src_dir / "collectors" / "raw"
output_dir = eda_dir / "output"
plots_dir = output_dir / "plots"


def ensure_eda_dirs():
    """Ensure eda output and plot directories exist."""
    output_dir.mkdir(parents = True, exist_ok = True)
    plots_dir.mkdir(parents = True, exist_ok = True)


def log(tag, message):
    """Print a standardized log message with an EDA tag prefix."""
    print(f"[{tag}] {message}")


def load_raw_json(source, filename):
    """
    Load a raw JSON dataset from src/collectors/raw/<source>/<filename>.
    
    Args:
        source: Subdirectory name under raw/ ('ddragon', 'cdragon', 'meraki', 'lore').
        filename: Name of the JSON file (e.g. 'champions.json', 'items.json').
    
    Returns:
        Loaded JSON structure (dict/list) or None if file not found.
    """
    filepath = raw_dir / source / filename
    if not filepath.exists():
        log("Loader", f"Warning: File not found at {filepath}")
        return None

    try:
        with open(filepath, "r", encoding = "utf-8") as f:
            return json.load(f)
    except Exception as e:
        log("Loader", f"Error reading {filepath}: {e}")
        return None


def load_all_universe_files():
    """
    Load all individual champion universe JSON files from src/collectors/raw/lore/universe/.
    
    Returns:
        Dictionary mapping champion slug/id to parsed JSON content.
    """
    universe_dir = raw_dir / "lore" / "universe"
    results = {}
    if not universe_dir.exists():
        log("Loader", f"Universe directory not found at {universe_dir}")
        return results

    for file_path in universe_dir.glob("*.json"):
        try:
            with open(file_path, "r", encoding = "utf-8") as f:
                data = json.load(f)
                results[file_path.stem] = data
        except Exception as e:
            log("Loader", f"Error reading universe file {file_path.name}: {e}")

    return results


def calculate_stats(numbers):
    """
    Calculate comprehensive descriptive statistics for a list of numerical values.
    
    Returns:
        Dict with count, mean, std, min, q25, median, q75, max.
    """
    clean_nums = [float(x) for x in numbers if x is not None and not math.isnan(x)]
    if not clean_nums:
        return {
            "count": 0,
            "mean": 0.0,
            "std": 0.0,
            "min": 0.0,
            "q25": 0.0,
            "median": 0.0,
            "q75": 0.0,
            "max": 0.0,
        }

    clean_nums.sort()
    n = len(clean_nums)
    mean = sum(clean_nums) / n
    variance = sum((x - mean) ** 2 for x in clean_nums) / (n - 1) if n > 1 else 0.0
    std = math.sqrt(variance)

    def percentile(p):
        idx = p * (n - 1)
        lower = int(math.floor(idx))
        upper = int(math.ceil(idx))
        if lower == upper:
            return clean_nums[lower]
        weight = idx - lower
        return clean_nums[lower] * (1 - weight) + clean_nums[upper] * weight

    return {
        "count": n,
        "mean": round(mean, 2),
        "std": round(std, 2),
        "min": round(clean_nums[0], 2),
        "q25": round(percentile(0.25), 2),
        "median": round(percentile(0.50), 2),
        "q75": round(percentile(0.75), 2),
        "max": round(clean_nums[-1], 2),
    }


def get_frequency_distribution(items, top_n = None):
    """
    Compute frequency distribution and percentage for categorical items.
    
    Returns:
        List of (category, count, percentage).
    """
    from collections import Counter

    valid_items = [x for x in items if x is not None]
    total = len(valid_items)
    if total == 0:
        return []

    counter = Counter(valid_items)
    most_common = counter.most_common(top_n)

    return [(cat, count, round((count / total) * 100, 2)) for cat, count in most_common]


def format_table(headers, rows):
    """
    Format tabular data into a clean ASCII / Markdown compatible table.
    """
    str_headers = [str(h) for h in headers]
    str_rows = [[str(cell) for cell in row] for row in rows]

    col_widths = [len(h) for h in str_headers]
    for row in str_rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(cell))
            else:
                col_widths.append(len(cell))

    # Construct table lines
    header_line = "| " + " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(str_headers)) + " |"
    separator_line = "| " + " | ".join("-" * col_widths[i] for i in range(len(col_widths))) + " |"
    row_lines = ["| " + " | ".join(row[i].ljust(col_widths[i]) if i < len(row) else "".ljust(col_widths[i]) for i in range(len(col_widths))) + " |" for row in str_rows]

    return "\n".join([header_line, separator_line] + row_lines)


def save_report_markdown(content, filename = "eda_report.md"):
    """Save formatted markdown analysis report to eda output directory."""
    ensure_eda_dirs()
    target_path = output_dir / filename
    with open(target_path, "w", encoding = "utf-8") as f:
        f.write(content)
    log("Report", f"Saved full markdown report to {target_path}")
    return target_path


def save_summary_json(data, filename = "eda_summary.json"):
    """Save structured analysis summary to eda output directory in JSON format."""
    ensure_eda_dirs()
    target_path = output_dir / filename
    with open(target_path, "w", encoding = "utf-8") as f:
        json.dump(data, f, indent = 2, ensure_ascii = False)
    log("Report", f"Saved JSON summary to {target_path}")
    return target_path
