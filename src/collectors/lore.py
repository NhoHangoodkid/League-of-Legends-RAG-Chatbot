"""
Riot Universe Lore Collector (Pure Raw).

Fetches complete raw champion lore and universe relationships from Riot Universe.
Saves raw API payloads directly to pipeline/collectors/raw/lore/ without transformation.
"""

import concurrent.futures
import html
import re
from tqdm import tqdm

from collectors.utils import (
    LORE_raw_dir,
    build_universe_url,
    clean_html,
    fetch_json,
    log,
    save_json,
)


tag = "RiotUniverse"


# Standard faction slug to human-readable region name
faction_map = {
    "bandle-city": "Bandle City",
    "bilgewater": "Bilgewater",
    "demacia": "Demacia",
    "freljord": "Freljord",
    "ionia": "Ionia",
    "ixtal": "Ixtal",
    "noxus": "Noxus",
    "piltover": "Piltover",
    "shadow-isles": "Shadow Isles",
    "shurima": "Shurima",
    "targon": "Mount Targon",
    "void": "The Void",
    "zaun": "Zaun",
    "unaffiliated": "Runeterra (Unaffiliated)",
}

# Mapping Universe champion slugs / names to Canonical DDragon Champion IDs
slug_to_canonical_id = {
    "aatrox": "Aatrox",
    "ahri": "Ahri",
    "akali": "Akali",
    "akshan": "Akshan",
    "alistar": "Alistar",
    "ambessa": "Ambessa",
    "amumu": "Amumu",
    "anivia": "Anivia",
    "annie": "Annie",
    "aphelios": "Aphelios",
    "ashe": "Ashe",
    "aurelion-sol": "AurelionSol",
    "aurora": "Aurora",
    "azir": "Azir",
    "bard": "Bard",
    "belveth": "Belveth",
    "bel-veth": "Belveth",
    "blitzcrank": "Blitzcrank",
    "brand": "Brand",
    "braum": "Braum",
    "briar": "Briar",
    "caitlyn": "Caitlyn",
    "camille": "Camille",
    "cassiopeia": "Cassiopeia",
    "chogath": "Chogath",
    "cho-gath": "Chogath",
    "corki": "Corki",
    "darius": "Darius",
    "diana": "Diana",
    "drmundo": "DrMundo",
    "dr-mundo": "DrMundo",
    "draven": "Draven",
    "ekko": "Ekko",
    "elise": "Elise",
    "evelynn": "Evelynn",
    "ezreal": "Ezreal",
    "fiddlesticks": "Fiddlesticks",
    "fiora": "Fiora",
    "fizz": "Fizz",
    "galio": "Galio",
    "gangplank": "Gangplank",
    "garen": "Garen",
    "gnar": "Gnar",
    "gragas": "Gragas",
    "graves": "Graves",
    "gwen": "Gwen",
    "hecarim": "Hecarim",
    "heimerdinger": "Heimerdinger",
    "hwei": "Hwei",
    "illaoi": "Illaoi",
    "irelia": "Irelia",
    "ivern": "Ivern",
    "janna": "Janna",
    "jarvan-iv": "JarvanIV",
    "jarvaniv": "JarvanIV",
    "jax": "Jax",
    "jayce": "Jayce",
    "jhin": "Jhin",
    "jinx": "Jinx",
    "kaisa": "Kaisa",
    "kai-sa": "Kaisa",
    "kalista": "Kalista",
    "karma": "Karma",
    "karthus": "Karthus",
    "kassadin": "Kassadin",
    "katarina": "Katarina",
    "kayle": "Kayle",
    "kayn": "Kayn",
    "kennen": "Kennen",
    "khazix": "Khazix",
    "kha-zix": "Khazix",
    "kindred": "Kindred",
    "kled": "Kled",
    "kogmaw": "KogMaw",
    "kog-maw": "KogMaw",
    "ksante": "KSante",
    "k-sante": "KSante",
    "leblanc": "Leblanc",
    "lee-sin": "LeeSin",
    "leesin": "LeeSin",
    "leona": "Leona",
    "lillia": "Lillia",
    "lissandra": "Lissandra",
    "lucian": "Lucian",
    "lulu": "Lulu",
    "lux": "Lux",
    "malphite": "Malphite",
    "malzahar": "Malzahar",
    "maokai": "Maokai",
    "master-yi": "MasterYi",
    "masteryi": "MasterYi",
    "milio": "Milio",
    "miss-fortune": "MissFortune",
    "missfortune": "MissFortune",
    "monkeyking": "MonkeyKing",
    "monkey-king": "MonkeyKing",
    "wukong": "MonkeyKing",
    "mordekaiser": "Mordekaiser",
    "morgana": "Morgana",
    "naafiri": "Naafiri",
    "nami": "Nami",
    "nasus": "Nasus",
    "nautilus": "Nautilus",
    "neeko": "Neeko",
    "nidalee": "Nidalee",
    "nilah": "Nilah",
    "nocturne": "Nocturne",
    "nunu": "Nunu",
    "nunu-willump": "Nunu",
    "olaf": "Olaf",
    "orianna": "Orianna",
    "ornn": "Ornn",
    "pantheon": "Pantheon",
    "poppy": "Poppy",
    "pyke": "Pyke",
    "qiyana": "Qiyana",
    "quinn": "Quinn",
    "rakan": "Rakan",
    "rammus": "Rammus",
    "reksai": "RekSai",
    "rek-sai": "RekSai",
    "rell": "Rell",
    "renata": "Renata",
    "renata-glasc": "Renata",
    "renata_glasc": "Renata",
    "renataglasc": "Renata",
    "renekton": "Renekton",
    "rengar": "Rengar",
    "riven": "Riven",
    "rumble": "Rumble",
    "ryze": "Ryze",
    "samira": "Samira",
    "sejuani": "Sejuani",
    "senna": "Senna",
    "seraphine": "Seraphine",
    "sett": "Sett",
    "shaco": "Shaco",
    "shen": "Shen",
    "shyvana": "Shyvana",
    "singed": "Singed",
    "sion": "Sion",
    "sivir": "Sivir",
    "skarner": "Skarner",
    "smolder": "Smolder",
    "sona": "Sona",
    "soraka": "Soraka",
    "swain": "Swain",
    "sylas": "Sylas",
    "syndra": "Syndra",
    "tahm-kench": "TahmKench",
    "tahmkench": "TahmKench",
    "taliyah": "Taliyah",
    "talon": "Talon",
    "taric": "Taric",
    "teemo": "Teemo",
    "thresh": "Thresh",
    "tristana": "Tristana",
    "trundle": "Trundle",
    "tryndamere": "Tryndamere",
    "twisted-fate": "TwistedFate",
    "twistedfate": "TwistedFate",
    "twitch": "Twitch",
    "udyr": "Udyr",
    "urgot": "Urgot",
    "varus": "Varus",
    "vayne": "Vayne",
    "veigar": "Veigar",
    "velkoz": "Velkoz",
    "vel-koz": "Velkoz",
    "vex": "Vex",
    "vi": "Vi",
    "viego": "Viego",
    "viktor": "Viktor",
    "vladimir": "Vladimir",
    "volibear": "Volibear",
    "warwick": "Warwick",
    "xayah": "Xayah",
    "xerath": "Xerath",
    "xin-zhao": "XinZhao",
    "xinzhao": "XinZhao",
    "yasuo": "Yasuo",
    "yone": "Yone",
    "yorick": "Yorick",
    "yuumi": "Yuumi",
    "zac": "Zac",
    "zed": "Zed",
    "zeri": "Zeri",
    "ziggs": "Ziggs",
    "zilean": "Zilean",
    "zoe": "Zoe",
    "zyra": "Zyra",
}


def resolve_canonical_id(slug, name):
    """Resolve champion slug or name to canonical DDragon/system ID."""
    clean_slug = slug.lower().strip()
    if clean_slug in slug_to_canonical_id:
        return slug_to_canonical_id[clean_slug]

    clean_name = re.sub(r"[^a-zA-Z0-9]", "", name)
    if clean_name.lower() in slug_to_canonical_id:
        return slug_to_canonical_id[clean_name.lower()]

    # Fallback to sanitized capitalized name
    return clean_name or slug.capitalize()


def fetch_champion_universe(slug):
    """Fetch raw champion JSON from Riot Universe Meeps API."""
    url = build_universe_url("champion_detail", slug = slug)
    try:
        return fetch_json(url, tag = tag, retries = 2, timeout = 12)
    except Exception as e:
        log(tag, f"Failed to fetch Universe detail for slug '{slug}': {e}")
        return None


def collect_lore():
    """
    Fetch comprehensive English lore, biographies, regions, and relationships
    for all champions from Riot Universe API.
    """
    log(tag, "Fetching champion browse index from Riot Universe (English)...")
    browse_url = build_universe_url("champion_browse")
    browse_data = fetch_json(browse_url, tag = tag, retries = 3, timeout = 15)

    if not browse_data or "champions" not in browse_data:
        log(tag, "ERROR: Could not fetch champion browse index from Riot Universe!")
        return {}


    champions_meta = browse_data.get("champions", [])
    log(tag, f"Discovered {len(champions_meta)} champions on Riot Universe.")

    universe_raw_dir = LORE_raw_dir / "universe"
    universe_raw_dir.mkdir(parents = True, exist_ok = True)


    consolidated_lore = {}

    # Fetch details concurrently for high throughput
    log(tag, "Downloading complete Universe lore and relationships...")
    slug_list = [c.get("slug") for c in champions_meta if c.get("slug")]

    results_by_slug = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers = 10) as executor:
        future_to_slug = {
            executor.submit(fetch_champion_universe, slug): slug for slug in slug_list
        }
        for future in tqdm(concurrent.futures.as_completed(future_to_slug), total = len(slug_list), desc = "Fetching Universe Lore"):
            slug = future_to_slug[future]
            try:
                data = future.result()
                if data:
                    results_by_slug[slug] = data
                    # Save individual raw JSON
                    save_json(data, universe_raw_dir / f"{slug}.json")
            except Exception as e:
                log(tag, f"Error processing {slug}: {e}")

    log(tag, f"Successfully downloaded detail payloads for {len(results_by_slug)} champions.")

    # Process and build structured lore entries
    for champ_meta in champions_meta:
        slug = champ_meta.get("slug", "")
        name = champ_meta.get("name", "")
        title = champ_meta.get("title", "")
        release_date = champ_meta.get("release-date", "")
        default_faction_slug = champ_meta.get("associated-faction-slug", "unaffiliated")

        canonical_id = resolve_canonical_id(slug, name)
        detail_data = results_by_slug.get(slug, {})

        champ_obj = detail_data.get("champion", {}) if isinstance(detail_data, dict) else {}
        biography = champ_obj.get("biography", {}) if isinstance(champ_obj, dict) else {}

        raw_full_bio = biography.get("full", "") or ""
        raw_short_bio = biography.get("short", "") or ""
        quote = biography.get("quote", "") or ""
        quote_author = biography.get("quote-author", "") or ""

        full_lore = clean_html(raw_full_bio)
        short_lore = clean_html(raw_short_bio)

        faction_slug = champ_obj.get("associated-faction-slug") or default_faction_slug or "unaffiliated"
        faction_name = faction_map.get(faction_slug.lower(), faction_slug.replace("-", " ").title())

        # Extract related champions
        related_list = detail_data.get("related-champions", []) if isinstance(detail_data, dict) else []
        related_champions = []
        for rc in related_list:
            if isinstance(rc, dict) and rc.get("name"):
                related_champions.append({
                    "name": rc.get("name"),
                    "slug": rc.get("slug"),
                    "canonical_id": resolve_canonical_id(rc.get("slug", ""), rc.get("name", "")),
                })

        consolidated_lore[canonical_id] = {
            "id": canonical_id,
            "name": name,
            "title": title,
            "slug": slug,
            "release_date": release_date,
            "region": faction_name,
            "faction_slug": faction_slug,
            "lore": full_lore or short_lore,
            "shortLore": short_lore,
            "quote": clean_html(quote) if quote else "",
            "quote_author": quote_author,
            "related_champions": related_champions,
            "source": "riot_universe_en",
        }

    # Save final consolidated lore JSON
    output_file = LORE_raw_dir / "lore.json"
    save_json(consolidated_lore, output_file)
    log(tag, f"Saved full English Universe lore for {len(consolidated_lore)} champions to {output_file}")

    return consolidated_lore

