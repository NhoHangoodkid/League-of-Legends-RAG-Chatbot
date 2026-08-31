import csv
import json
import os
from pathlib import Path
import requests
from tqdm import tqdm


def download_image(session: requests.Session, img_url: str, img_path: Path) -> bool:
    """Download an image from img_url and save it to img_path."""
    try:
        if not img_url:
            return False

        # Skip if image already exists and is non-empty
        if img_path.exists() and img_path.stat().st_size > 0:
            return True

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        }
        response = session.get(img_url, headers=headers, stream=True, timeout=15)
        if response.status_code == 200:
            with open(img_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
        else:
            print(f"[Warning] Failed to download image ({response.status_code}): {img_url}")
            return False
    except Exception as e:
        print(f"[Error] Error downloading image {img_url}: {e}")
        return False


def get_champions_from_local(base_dir: Path) -> list[dict]:
    """Fallback: Load champion data from local Collecte_data/dragon JSON files."""
    local_dir = base_dir / "Collecte_data" / "dragon" / "champions_detail"
    champions = []

    if not local_dir.exists():
        return champions

    for file_path in sorted(local_dir.glob("*.json")):
        if file_path.name.startswith("Jade_"):
            continue  # Skip TFT/Arena variants if any
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = json.load(f)
                data_dict = content.get("data", {})
                for champ_key, champ_info in data_dict.items():
                    champions.append(champ_info)
        except Exception:
            continue

    return champions


def extract_champion_stats(
    output_csv: str = "champion_stats.csv",
    image_dir: str = "champion_images",
    lang: str = "en_US",
    download_images: bool = True,
) -> None:
    """
    Extract League of Legends champions' base statistics and icons.
    Uses Riot's official Data Dragon API (fast, reliable, and no Selenium required).
    """
    project_root = Path(__file__).resolve().parent
    img_dir_path = project_root / image_dir
    csv_file_path = project_root / output_csv

    img_dir_path.mkdir(parents=True, exist_ok=True)
    session = requests.Session()

    print("=" * 60)
    print("  League of Legends - Champion Stats & Image Extractor")
    print("=" * 60)

    # 1. Get latest Data Dragon version
    version = None
    champions_data = {}

    try:
        print("[1/3] Fetching latest Data Dragon version from Riot API...")
        v_res = session.get("https://ddragon.leagueoflegends.com/api/versions.json", timeout=10)
        if v_res.status_code == 200:
            version = v_res.json()[0]
            print(f"      -> Latest version: {version}")

            # Fetch champion list
            print(f"[2/3] Fetching champion data (language: {lang})...")
            champ_url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/{lang}/champion.json"
            champ_res = session.get(champ_url, timeout=15)
            if champ_res.status_code == 200:
                champions_data = champ_res.json().get("data", {})
                print(f"      -> Retrieved {len(champions_data)} champions successfully.")
    except Exception as e:
        print(f"[Warning] Could not fetch from online Data Dragon API: {e}")

    # Fallback to local files if API fetch failed
    if not champions_data:
        print("[Notice] Using local champion data from Collecte_data...")
        local_champs = get_champions_from_local(project_root)
        champions_data = {c["id"]: c for c in local_champs if "id" in c}
        print(f"      -> Loaded {len(champions_data)} champions from local files.")

    if not champions_data:
        print("[Error] No champion data found. Please check your internet connection or local files.")
        return

    # 2. Extract stats and prepare CSV rows
    csv_rows = []
    download_queue = []

    for champ_id, info in champions_data.items():
        name = info.get("name", champ_id)
        title = info.get("title", "")
        stats = info.get("stats", {})
        img_info = info.get("image", {})
        img_file_name = img_info.get("full", f"{champ_id}.png")

        # Stats
        hp = stats.get("hp", "")
        mp = stats.get("mp", "")
        ad = stats.get("attackdamage", "")
        attack_speed = stats.get("attackspeed", "")
        armor = stats.get("armor", "")
        magic_res = stats.get("spellblock", "")
        attack_range = stats.get("attackrange", "")
        move_speed = stats.get("movespeed", "")

        csv_rows.append([
            name,
            title,
            hp,
            mp,
            ad,
            attack_speed,
            armor,
            magic_res,
            attack_range,
            move_speed,
            img_file_name,
        ])

        if version:
            img_url = f"https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{img_file_name}"
            download_queue.append((img_url, img_dir_path / img_file_name))

    # 3. Export to CSV
    header = [
        "Champion",
        "Title",
        "HP",
        "MP",
        "AD",
        "Attack Speed",
        "Armor",
        "Magic Resistance",
        "Attack Range",
        "Move Speed",
        "Image File",
    ]

    with open(csv_file_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(csv_rows)

    print(f"\n[OK] Champion statistics saved to: {csv_file_path.name} ({len(csv_rows)} rows)")

    # 4. Download champion images
    if download_images and download_queue:
        print(f"\n[3/3] Downloading {len(download_queue)} champion images to '{image_dir}/'...")
        success_count = 0
        for img_url, dest_path in tqdm(download_queue, desc="Downloading Images", unit="img"):
            if download_image(session, img_url, dest_path):
                success_count += 1

        print(f"[OK] Completed: {success_count}/{len(download_queue)} images ready in '{image_dir}/'")

    print("\n" + "=" * 60)
    print("  Extraction finished successfully!")
    print("=" * 60)


if __name__ == "__main__":
    extract_champion_stats()