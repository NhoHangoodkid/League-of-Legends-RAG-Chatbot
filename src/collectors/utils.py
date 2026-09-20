"""
Utility functions for data collectors.

Provides common helper functions across collectors:
- Configuration management (YAML loader, setting extractors, path resolvers).
- HTTP session management (shared session, persistent headers).
- Safe HTTP requests (exponential backoff retry, rate-limiting, error handling).
- Dynamic URL builders for Data Dragon, Community Dragon, Meraki Analytics, and Riot Universe.
- JSON file I/O utilities (safe save, load, cache checks).
"""

import html
import json
import re
import time
from pathlib import Path

import requests
import yaml


def find_config_path():
    """Locate the collector configuration file (`collector.yaml` or `config.yaml`)."""
    collectors_dir = Path(__file__).parent
    collector_yaml = collectors_dir / "collector.yaml"
    if collector_yaml.exists():
        return collector_yaml

    config_yaml = collectors_dir / "config.yaml"
    if config_yaml.exists():
        return config_yaml

    raise FileNotFoundError("Neither collector.yaml nor config.yaml was found in collectors directory")


# Path to the active collector configuration.
config_path = find_config_path()

# In-memory cached instances.
config = None
session = None
last_request_time = 0.0
cached_ddragon_version = None


def load_collector_config(config_path = None):
    """Load and parse configuration from the YAML file. Caches the parsed dictionary in memory."""
    global config
    if config is None:
        path = config_path or find_config_path()
        if path.exists():
            with open(path, "r", encoding = "utf-8") as f:
                config = yaml.safe_load(f) or {}
        else:
            config = {}
    return config


def get_setting(key, default = None):
    """Retrieve a global setting from the 'settings' section of the YAML configuration."""
    config = load_collector_config()
    return config.get("settings", {}).get(key, default)


def get_source_config(source_name):
    """Retrieve configuration for a specific data source (e.g., 'ddragon', 'cdragon', 'meraki', 'universe')."""
    config = load_collector_config()
    return config.get("sources", {}).get(source_name, {})


def get_raw_dir(source_name):
    """
    Get the raw data storage directory inside collectors.
    Resolves `paths.raw_dir` from collector.yaml relative to collectors folder.
    """
    config = load_collector_config()
    raw_dir_rel = config.get("paths", {}).get("raw_dir", "./raw")
    collectors_dir = Path(__file__).parent
    base_raw = (collectors_dir / raw_dir_rel).resolve()

    if source_name:
        target = base_raw / source_name
    else:
        target = base_raw

    target.mkdir(parents = True, exist_ok = True)
    return target


# Direct access to subdirectories in collectors/raw/
DDRAGON_raw_dir = get_raw_dir("ddragon")
CDRAGON_raw_dir = get_raw_dir("cdragon")
MERAKI_raw_dir = get_raw_dir("meraki")
LORE_raw_dir = get_raw_dir("lore")
ORACLES_ELIXIR_raw_dir = get_raw_dir("oracles_elixir")
OPGG_SYNERGY_raw_dir = get_raw_dir("opgg_synergy")
BLITZ_raw_dir = get_raw_dir("blitz")


def get_session():
    """Get or initialize a shared requests.Session singleton."""
    global session
    if session is None:
        user_agent = get_setting("user_agent", "LoLKnowledgeBot/1.0 (Educational Project)")
        session = requests.Session()
        session.headers.update({
            "User-Agent": user_agent,
            "Accept": "application/json",
        })
    return session


def log(tag, message):
    """Print a standardized log message with a collector tag prefix."""
    print(f"[{tag}] {message}")


def fetch_json(url, session = None, retries = None, delay = None, timeout = None, tag = "Collector"):
    """Fetch and parse JSON from a URL with built-in rate-limiting, retries, and error handling."""
    global last_request_time
    sess = session or get_session()

    # Fallback to YAML configuration settings if arguments are omitted.
    retries = retries if retries is not None else get_setting("max_retries", 3)
    delay = delay if delay is not None else get_setting("request_delay", 0.15)
    timeout = timeout if timeout is not None else get_setting("request_timeout", 30)

    for attempt in range(1, retries + 1):
        try:
            # Rate Limiting: enforce minimum delay between successive calls.
            elapsed = time.time() - last_request_time
            if elapsed < delay:
                time.sleep(delay - elapsed)

            last_request_time = time.time()

            # Perform HTTP GET request.
            response = sess.get(url, timeout = timeout)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else "?"
            print(f"[{tag}] HTTP {status} for {url} (attempt {attempt}/{retries})")

            # Retry only on rate-limit (429) or transient server errors (5xx).
            if attempt < retries and status in (429, 500, 502, 503):
                wait = 2 ** attempt
                print(f"[{tag}] Retrying in {wait}s...")
                time.sleep(wait)
            else:
                return None

        except requests.exceptions.ConnectionError:
            print(f"[{tag}] Connection error for {url} (attempt {attempt}/{retries})")
            if attempt < retries:
                time.sleep(2 ** attempt)
            else:
                return None

        except requests.exceptions.Timeout:
            print(f"[{tag}] Timeout for {url} (attempt {attempt}/{retries})")
            if attempt < retries:
                time.sleep(2)
            else:
                return None

        except Exception as e:
            print(f"[{tag}] Unexpected error: {e}")
            return None

    return None


def get_latest_ddragon_version():
    """Fetch and cache the latest Data Dragon patch version string from Riot API or collector.yaml."""
    global cached_ddragon_version
    if cached_ddragon_version is not None:
        return cached_ddragon_version

    dd_conf = get_source_config("ddragon")
    versions_url = dd_conf.get("versions_url")
    default_version = dd_conf.get("default_version")

    if versions_url:
        try:
            versions = fetch_json(versions_url, tag = "DDragon", retries = 2, timeout = 10)
            if versions and isinstance(versions, list) and len(versions) > 0:
                cached_ddragon_version = str(versions[0])
                return cached_ddragon_version
        except Exception as e:
            log("DDragon", f"Could not fetch latest version from Riot API: {e}")

    cached_ddragon_version = default_version
    return cached_ddragon_version


def build_ddragon_url(endpoint_key, version, **kwargs):
    """Construct a complete Riot Data Dragon URL strictly from collector.yaml templates."""
    dd_conf = get_source_config("ddragon")
    base_url = dd_conf.get("base_url", "")
    language = get_setting("language", "en_US")
    endpoint_template = dd_conf.get("endpoints", {}).get(endpoint_key, endpoint_key)
    endpoint = endpoint_template.format(**kwargs) if "{" in endpoint_template else endpoint_template
    return f"{base_url}/cdn/{version}/data/{language}/{endpoint}"


def build_cdragon_url(endpoint_key, **kwargs):
    """Construct a complete Community Dragon URL strictly from collector.yaml templates."""
    cd_conf = get_source_config("cdragon")
    base_url = cd_conf.get("base_url", "")
    endpoint_template = cd_conf.get("endpoints", {}).get(endpoint_key, endpoint_key)
    endpoint = endpoint_template.format(**kwargs) if "{" in endpoint_template else endpoint_template
    return f"{base_url}/{endpoint}"


def build_meraki_url(endpoint_key, **kwargs):
    """Construct a complete Meraki Analytics CDN URL strictly from collector.yaml templates."""
    mk_conf = get_source_config("meraki")
    base_url = mk_conf.get("base_url", "")
    endpoint_template = mk_conf.get("endpoints", {}).get(endpoint_key, endpoint_key)
    endpoint = endpoint_template.format(**kwargs) if "{" in endpoint_template else endpoint_template
    return f"{base_url}/{endpoint}"


def build_universe_url(endpoint_key, **kwargs):
    """Construct a complete Riot Universe URL strictly from collector.yaml templates."""
    uv_conf = get_source_config("universe")
    base_url = uv_conf.get("base_url", "")
    endpoint_template = uv_conf.get("endpoints", {}).get(endpoint_key, endpoint_key)
    endpoint = endpoint_template.format(**kwargs) if "{" in endpoint_template else endpoint_template
    return f"{base_url}/{endpoint}"


def save_json(data, filepath, indent = 2):
    """Serialize and save Python data structure to a JSON file."""
    filepath.parent.mkdir(parents = True, exist_ok = True)
    with open(filepath, "w", encoding = "utf-8") as f:
        json.dump(data, f, indent = indent, ensure_ascii = False)
    return filepath


def load_json(filepath):
    """Load and deserialize a JSON file from disk. Returns None if file does not exist."""
    if filepath.exists():
        with open(filepath, "r", encoding = "utf-8") as f:
            return json.load(f)
    return None


def has_cached(filepath):
    """Check if a cached file exists at the given path."""
    return filepath.exists()


# Text and Data Cleaning Utilities

def clean_html(text):
    """
    Strip HTML/XML tags and unescape entities into clean plain text.
    Handles standard HTML tags as well as Riot-specific tags (<mainText>, <stats>, <font color>, etc.).
    """
    if not text:
        return ""
    # Replace paragraph and line breaks with newlines
    text = re.sub(r"<\s*/?\s*p\s*>", "\n\n", text, flags = re.IGNORECASE)
    text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags = re.IGNORECASE)
    # Remove all other XML/HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Unescape HTML entities (&amp;, &quot;, &#39;, etc.)
    text = html.unescape(text)
    # Normalize multiple newlines and spaces
    paragraphs = [re.sub(r"\s+", " ", p).strip() for p in text.split("\n") if p.strip()]
    return "\n\n".join(paragraphs)


def clean_riot_tokens(text):
    """
    Convert Riot internal formula tokens and spell references to readable text.
    E.g. @spell_P@ -> 'Passive', @spell_Q@ -> 'Q', {{ e1 }} -> ''
    """
    if not text:
        return ""
    # Convert spell slot placeholders
    replacements = {
        r"@spell_P@": "Passive",
        r"@spell_Q@": "Q",
        r"@spell_W@": "W",
        r"@spell_E@": "E",
        r"@spell_R@": "R",
    }
    for pattern, rep in replacements.items():
        text = re.sub(pattern, rep, text, flags = re.IGNORECASE)

    # Remove lingering formula placeholders like {{ e1 }}, @Effect1Amount@
    text = re.sub(r"\{\{[^}]+\}\}", " ", text)
    text = re.sub(r"@[^@]+@", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_text(text):
    """
    Comprehensive text cleaner: strips HTML, unescapes entities,
    resolves Riot spell tokens, and normalizes whitespace.
    """
    if not text:
        return ""
    text = clean_html(text)
    text = clean_riot_tokens(text)
    return text

