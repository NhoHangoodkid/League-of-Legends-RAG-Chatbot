"""
Utility functions for data collectors.

Provides common helper functions across collectors:
- Configuration management (YAML loader, setting extractors, path resolvers).
- HTTP session management (shared session, persistent headers).
- Safe HTTP requests (exponential backoff retry, rate-limiting, error handling).
- Dynamic URL builders for Data Dragon, Community Dragon, and Meraki Analytics.
- JSON file I/O utilities (safe save, load, cache checks).
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests
import yaml


# ============================================================================
# 1. CONFIGURATION MANAGEMENT & PATHS
# ============================================================================

def find_config_path() -> Path:
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
CONFIG_PATH = find_config_path()

# In-memory cached instances.
CONFIG: Optional[Dict[str, Any]] = None
SESSION: Optional[requests.Session] = None
LAST_REQUEST_TIME: float = 0.0


def load_collector_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load and parse configuration from the YAML file. Caches the parsed dictionary in memory."""
    global CONFIG
    if CONFIG is None:
        path = config_path or find_config_path()
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                CONFIG = yaml.safe_load(f) or {}
        else:
            CONFIG = {}
    return CONFIG


def get_setting(key: str, default: Any = None) -> Any:
    """Retrieve a global setting from the 'settings' section of the YAML configuration."""
    config = load_collector_config()
    return config.get("settings", {}).get(key, default)


def get_source_config(source_name: str) -> Dict[str, Any]:
    """Retrieve configuration for a specific data source (e.g., 'ddragon', 'cdragon', 'meraki')."""
    config = load_collector_config()
    return config.get("sources", {}).get(source_name, {})


def get_raw_dir(source_name: Optional[str] = None) -> Path:
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

    target.mkdir(parents=True, exist_ok=True)
    return target


# Direct access to subdirectories in collectors/raw/
DDRAGON_RAW_DIR = get_raw_dir("ddragon")
CDRAGON_RAW_DIR = get_raw_dir("cdragon")
MERAKI_RAW_DIR = get_raw_dir("meraki")
WIKI_RAW_DIR = get_raw_dir("wiki")


# ============================================================================
# 2. SESSION MANAGEMENT & LOGGING
# ============================================================================

def get_session() -> requests.Session:
    """Get or initialize a shared requests.Session singleton."""
    global SESSION
    if SESSION is None:
        user_agent = get_setting("user_agent", "LoLKnowledgeBot/1.0 (Educational Project)")
        SESSION = requests.Session()
        SESSION.headers.update({
            "User-Agent": user_agent,
            "Accept": "application/json",
        })
    return SESSION


def log(tag: str, message: str) -> None:
    """Print a standardized log message with a collector tag prefix."""
    print(f"[{tag}] {message}")


# ============================================================================
# 3. HTTP REQUESTS (RATE LIMITING & RETRY LOGIC)
# ============================================================================

def fetch_json(
    url: str,
    session: Optional[requests.Session] = None,
    retries: Optional[int] = None,
    delay: Optional[float] = None,
    timeout: Optional[int] = None,
    tag: str = "Collector",
) -> Optional[Any]:
    """Fetch and parse JSON from a URL with built-in rate-limiting, retries, and error handling."""
    global LAST_REQUEST_TIME
    sess = session or get_session()

    # Fallback to YAML configuration settings if arguments are omitted.
    retries = retries if retries is not None else get_setting("max_retries", 3)
    delay = delay if delay is not None else get_setting("request_delay", 0.15)
    timeout = timeout if timeout is not None else get_setting("request_timeout", 30)

    for attempt in range(1, retries + 1):
        try:
            # Rate Limiting: enforce minimum delay between successive calls.
            elapsed = time.time() - LAST_REQUEST_TIME
            if elapsed < delay:
                time.sleep(delay - elapsed)

            LAST_REQUEST_TIME = time.time()

            # Perform HTTP GET request.
            response = sess.get(url, timeout=timeout)
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


# ============================================================================
# 4. DYNAMIC URL BUILDERS (Read directly from collector.yaml)
# ============================================================================

def get_latest_ddragon_version() -> str:
    """Fetch the latest Data Dragon patch version string using versions_url from collector.yaml."""
    dd_conf = get_source_config("ddragon")
    versions_url = dd_conf.get("versions_url")
    if not versions_url:
        log("DDragon", "Missing 'versions_url' in collector.yaml")
        return "15.15.1"

    try:
        versions = fetch_json(versions_url, tag="DDragon", retries=2, timeout=10)
        if versions and isinstance(versions, list):
            return str(versions[0])
    except Exception as e:
        log("DDragon", f"Could not fetch latest version: {e}")
    return "15.15.1"


def build_ddragon_url(endpoint_key: str, version: str, **kwargs) -> str:
    """Construct a complete Riot Data Dragon URL strictly from collector.yaml templates."""
    dd_conf = get_source_config("ddragon")
    base_url = dd_conf.get("base_url", "")
    language = get_setting("language", "en_US")
    endpoint_template = dd_conf.get("endpoints", {}).get(endpoint_key, endpoint_key)
    endpoint = endpoint_template.format(**kwargs) if "{" in endpoint_template else endpoint_template
    return f"{base_url}/cdn/{version}/data/{language}/{endpoint}"


def build_cdragon_url(endpoint_key: str, **kwargs) -> str:
    """Construct a complete Community Dragon URL strictly from collector.yaml templates."""
    cd_conf = get_source_config("cdragon")
    base_url = cd_conf.get("base_url", "")
    endpoint_template = cd_conf.get("endpoints", {}).get(endpoint_key, endpoint_key)
    endpoint = endpoint_template.format(**kwargs) if "{" in endpoint_template else endpoint_template
    return f"{base_url}/{endpoint}"


def build_meraki_url(endpoint_key: str, **kwargs) -> str:
    """Construct a complete Meraki Analytics CDN URL strictly from collector.yaml templates."""
    mk_conf = get_source_config("meraki")
    base_url = mk_conf.get("base_url", "")
    endpoint_template = mk_conf.get("endpoints", {}).get(endpoint_key, endpoint_key)
    endpoint = endpoint_template.format(**kwargs) if "{" in endpoint_template else endpoint_template
    return f"{base_url}/{endpoint}"


# ============================================================================
# 5. JSON FILE I/O HELPERS
# ============================================================================

def save_json(data: Any, filepath: Path, indent: int = 2) -> Path:
    """Serialize and save Python data structure to a JSON file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
    return filepath


def load_json(filepath: Path) -> Optional[Any]:
    """Load and deserialize a JSON file from disk. Returns None if file does not exist."""
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def has_cached(filepath: Path) -> bool:
    """Check if a cached file exists at the given path."""
    return filepath.exists()
