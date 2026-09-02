"""
Unit tests for the Collectors module.

Tests YAML configuration, URL builders, session handling, and JSON I/O helpers.
python -m unittest pipeline/collectors/test_collectors.py
"""

import tempfile
import unittest
from pathlib import Path

from collectors import (
    cdragon,
    ddragon,
    lore,
    meraki,
)
from collectors.main import run_all_collectors
from collectors.utils import (
    build_cdragon_url,
    build_ddragon_url,
    build_meraki_url,
    build_universe_url,
    find_config_path,
    get_session,
    get_setting,
    get_source_config,
    has_cached,
    load_collector_config,
    load_json,
    log,
    save_json,
)


class TestCollectorsModule(unittest.TestCase):
    """Test suite for pipeline.collectors module."""

    def test_find_and_load_config(self):
        """Test finding and loading collector.yaml."""
        config_path = find_config_path()
        self.assertTrue(config_path.exists(), "collector.yaml should exist in collectors directory")

        config = load_collector_config()
        self.assertIsInstance(config, dict, "Config should load as a dictionary")
        self.assertIn("settings", config, "Config should contain 'settings'")
        self.assertIn("sources", config, "Config should contain 'sources'")

    def test_settings_extraction(self):
        """Test retrieving global settings from YAML."""
        lang = get_setting("language")
        self.assertEqual(lang, "en_US", "Default language should be 'en_US'")

        timeout = get_setting("request_timeout")
        self.assertIsInstance(timeout, (int, float), "Timeout should be a number")
        self.assertGreater(timeout, 0, "Timeout should be greater than 0")

        delay = get_setting("request_delay")
        self.assertIsInstance(delay, (int, float), "Delay should be a number")

    def test_source_configs(self):
        """Test retrieving source configuration for each provider."""
        sources = ["ddragon", "cdragon", "meraki", "universe"]
        for source in sources:
            conf = get_source_config(source)
            self.assertIsInstance(conf, dict, f"Source '{source}' config should be a dict")
            self.assertIn("base_url", conf, f"Source '{source}' must define 'base_url'")
            self.assertIn("endpoints", conf, f"Source '{source}' must define 'endpoints'")

    def test_ddragon_url_builder(self):
        """Test building Data Dragon URLs."""
        url_list = build_ddragon_url("champions", "15.15.1")
        expected_list = "https://ddragon.leagueoflegends.com/cdn/15.15.1/data/en_US/champion.json"
        self.assertEqual(url_list, expected_list)

        url_detail = build_ddragon_url("champion_detail", "15.15.1", id="Aatrox")
        expected_detail = "https://ddragon.leagueoflegends.com/cdn/15.15.1/data/en_US/champion/Aatrox.json"
        self.assertEqual(url_detail, expected_detail)

        url_items = build_ddragon_url("items", "15.15.1")
        self.assertTrue(url_items.endswith("/item.json"))

        url_runes = build_ddragon_url("runes", "15.15.1")
        self.assertTrue(url_runes.endswith("/runesReforged.json"))

    def test_cdragon_url_builder(self):
        """Test building Community Dragon URLs."""
        url_summary = build_cdragon_url("champion_summary")
        self.assertTrue(url_summary.endswith("/champion-summary.json"))

        url_detail = build_cdragon_url("champion_detail", id=266)
        self.assertTrue(url_detail.endswith("/champions/266.json"))

        url_items = build_cdragon_url("items")
        self.assertTrue(url_items.endswith("/items.json"))

    def test_meraki_url_builder(self):
        """Test building Meraki Analytics URLs."""
        url_champions = build_meraki_url("champions")
        self.assertTrue(url_champions.endswith("/champions.json"))
        self.assertIn("merakianalytics.com", url_champions)

    def test_universe_url_builder(self):
        """Test building Riot Universe URLs."""
        url_browse = build_universe_url("champion_browse")
        self.assertTrue(url_browse.endswith("/champion-browse/index.json"))
        self.assertIn("universe-meeps.leagueoflegends.com", url_browse)

        url_detail = build_universe_url("champion_detail", slug="yasuo")
        self.assertTrue(url_detail.endswith("/champions/yasuo/index.json"))


    def test_session_configuration(self):
        """Test shared session setup and headers."""
        session = get_session()
        self.assertIsNotNone(session)
        self.assertIn("User-Agent", session.headers)
        self.assertIn("LoLKnowledgeBot", session.headers["User-Agent"])
        self.assertEqual(session.headers.get("Accept"), "application/json")

    def test_json_save_and_load(self):
        """Test saving and loading JSON files safely."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "subfolder" / "test_data.json"
            sample_data = {"test_key": "test_value", "number": 42, "list": [1, 2, 3]}

            # Test save_json (creates parent folder automatically)
            saved_path = save_json(sample_data, test_file)
            self.assertTrue(saved_path.exists())
            self.assertTrue(has_cached(test_file))

            # Test load_json
            loaded_data = load_json(test_file)
            self.assertEqual(loaded_data, sample_data)

            # Test load non-existent file returns None
            non_existent = Path(tmpdir) / "not_found.json"
            self.assertIsNone(load_json(non_existent))
            self.assertFalse(has_cached(non_existent))

    def test_collectors_functions_callable(self):
        """Test that all collector entry point functions are defined and callable."""
        self.assertTrue(callable(ddragon.collect_ddragon))
        self.assertTrue(callable(ddragon.collect_champions))
        self.assertTrue(callable(ddragon.collect_items))
        self.assertTrue(callable(ddragon.collect_runes))

        self.assertTrue(callable(cdragon.collect_cdragon))
        self.assertTrue(callable(cdragon.collect_champions))
        self.assertTrue(callable(cdragon.collect_items))

        self.assertTrue(callable(meraki.collect_meraki))
        self.assertTrue(callable(meraki.collect_champions))

        self.assertTrue(callable(lore.collect_lore))
        self.assertTrue(callable(run_all_collectors))


if __name__ == "__main__":
    unittest.main(verbosity = 2)
