"""
Utility functions and path configurations for data processors.

Centralizes paths for raw data sources and processed data outputs,
along with common JSON I/O and logging utilities.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional


# Processors directory: src/processors
PROCESSORS_DIR = Path(__file__).resolve().parent

# Source root directory: src/
SRC_DIR = PROCESSORS_DIR.parent

# Project root directory
PROJECT_ROOT = SRC_DIR.parent

# Data directories (Standard output is in src/processors/processed)
PROCESSED_DIR = PROCESSORS_DIR / "processed"


def find_raw_dir() -> Path:
    """
    Locate the raw data directory with fallbacks:
    1. src/collectors/raw (Active storage)
    2. src/pipeline/collectors/raw
    3. data/raw
    """
    candidate_paths = [
        SRC_DIR / "collectors" / "raw",
        SRC_DIR / "pipeline" / "collectors" / "raw",
        PROJECT_ROOT / "data" / "raw",
        SRC_DIR / "data" / "raw",
    ]
    for path in candidate_paths:
        if path.exists() and any(path.iterdir()):
            return path

    # Default to standard collectors raw dir
    return SRC_DIR / "collectors" / "raw"


RAW_DIR = find_raw_dir()

# Raw source subdirectories
DDRAGON_RAW_DIR = RAW_DIR / "ddragon"
CDRAGON_RAW_DIR = RAW_DIR / "cdragon"
MERAKI_RAW_DIR = RAW_DIR / "meraki"
WIKI_RAW_DIR = RAW_DIR / "wiki"


def ensure_dirs():
    """Ensure all processed and raw directories exist."""
    for d in [PROCESSED_DIR, DDRAGON_RAW_DIR, CDRAGON_RAW_DIR, MERAKI_RAW_DIR, WIKI_RAW_DIR]:
        d.mkdir(parents = True, exist_ok = True)


def load_json(path):
    """Load JSON file safely. Returns empty dict/list if not found."""
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log("ProcessorUtils", f"Error reading {path}: {e}")
            return {}
    return {}


def save_json(data, path, indent = 2):
    """Save data to JSON file with automatic directory creation."""
    try:
        path.parent.mkdir(parents = True, exist_ok = True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent = indent, ensure_ascii = False)
        return True
    except Exception as e:
        log("ProcessorUtils", f"Error writing to {path}: {e}")
        return False


def log(tag, message):
    """Print standardized log output with module prefix."""
    print(f"[{tag}] {message}")
