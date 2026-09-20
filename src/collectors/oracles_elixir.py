"""
Oracle's Elixir Collector.

Downloads and manages professional League of Legends esports match data from Oracle's Elixir:
- Official pro match data (LCK, LPL, LEC, LCS, Worlds, MSI).
- Game-level data: gameid, league, year, split, patch, champion, position, team, result (win/loss).
- Powers pro team composition analysis, duo synergies, and meta picks.
"""

import sys
import time
from pathlib import Path
import requests

# Ensure src is in sys.path if run directly
src_root = Path(__file__).resolve().parent.parent
if str(src_root) not in sys.path:
    sys.path.insert(0, str(src_root))

from collectors.utils import (
    ORACLES_ELIXIR_raw_dir,
    get_source_config,
    log,
)


tag = "OraclesElixir"


def collect_oracles_elixir(year = None, force = False):
    """
    Download Oracle's Elixir esports match dataset CSV for a specified year (default 2026).
    
    Args:
        year (int or str): Season year to download (e.g. 2026, 2025, 2024).
        force (bool): If True, re-downloads even if the file already exists.
        
    Returns:
        dict: Summary containing filepath, file size in MB, status, and row count estimate.
    """
    conf = get_source_config("oracles_elixir")
    datasets = conf.get("datasets", {})
    selected_year = str(year or conf.get("default_year", 2026))

    year_conf = datasets.get(selected_year) or datasets.get(int(selected_year) if selected_year.isdigit() else 2026)
    if not year_conf:
        # Fallback to old download_url_2024 if datasets block is missing
        download_url = conf.get(f"download_url_{selected_year}") or conf.get("download_url_2024")
        filename = conf.get(f"filename_{selected_year}", f"{selected_year}_LoL_esports_match_data.csv")
    else:
        download_url = year_conf.get("download_url")
        filename = year_conf.get("filename", f"{selected_year}_LoL_esports_match_data.csv")

    if not download_url:
        raise ValueError(f"Missing download URL for year {selected_year} in collector.yaml under sources.oracles_elixir")

    target_path = ORACLES_ELIXIR_raw_dir / filename

    if target_path.exists() and not force:
        size_mb = target_path.stat().st_size / (1024 * 1024)
        log(tag, f"Cached file exists for {selected_year}: {target_path} ({size_mb:.2f} MB). Skipping download.")
        return {
            "status": "cached",
            "year": selected_year,
            "file": str(target_path),
            "size_mb": round(size_mb, 2)
        }

    log(tag, f"Downloading professional match dataset for {selected_year} from Oracle's Elixir...")
    start_time = time.time()


    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        })

        response = session.get(download_url, stream = True, timeout = 60)
        response.raise_for_status()

        total_downloaded = 0
        chunk_size = 1024 * 1024  # 1MB chunks

        with open(target_path, "wb") as f:
            for chunk in response.iter_content(chunk_size = chunk_size):
                if chunk:
                    f.write(chunk)
                    total_downloaded += len(chunk)
                    if total_downloaded % (10 * 1024 * 1024) == 0:
                        log(tag, f"Downloaded {total_downloaded / (1024 * 1024):.1f} MB...")

        elapsed = time.time() - start_time
        size_mb = total_downloaded / (1024 * 1024)
        log(tag, f"Successfully downloaded {size_mb:.2f} MB in {elapsed:.2f}s to {target_path}")

        # Quick validation of CSV headers
        with open(target_path, "r", encoding = "utf-8", errors = "ignore") as f:
            header_line = f.readline().strip()
            first_row = f.readline().strip()

        log(tag, f"CSV Header preview: {header_line[:120]}...")
        log(tag, f"CSV First row preview: {first_row[:120]}...")

        return {
            "status": "downloaded",
            "file": str(target_path),
            "size_mb": round(size_mb, 2),
            "elapsed_seconds": round(elapsed, 2)
        }

    except Exception as e:
        log(tag, f"Error downloading match data: {e}")
        if target_path.exists() and target_path.stat().st_size == 0:
            target_path.unlink()
        return {
            "status": "error",
            "error": str(e)
        }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description = "Collect Oracle's Elixir Match Data")
    parser.add_argument("--year", type = str, default = None, help = "Year of esports matches (default from collector.yaml)")
    parser.add_argument("--force", action = "store_true", help = "Force re-download")
    args = parser.parse_args()


    res = collect_oracles_elixir(year = args.year, force = args.force)
    print(res)

