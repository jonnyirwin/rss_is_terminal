"""Tests for configuration loading and saving."""

from pathlib import Path
from unittest.mock import patch

import pytest

from rss_is_terminal.config import AppConfig, config_dir, data_dir, db_path, config_path


class TestPaths:
    def test_config_dir_creates_directory(self, tmp_path):
        fake_dir = tmp_path / "config" / "rss_is_terminal"
        with patch("rss_is_terminal.config.user_config_dir", return_value=str(fake_dir)):
            result = config_dir()
            assert result.is_dir()
            assert result == fake_dir

    def test_data_dir_creates_directory(self, tmp_path):
        fake_dir = tmp_path / "data" / "rss_is_terminal"
        with patch("rss_is_terminal.config.user_data_dir", return_value=str(fake_dir)):
            result = data_dir()
            assert result.is_dir()
            assert result == fake_dir

    def test_db_path_returns_rss_db(self, tmp_path):
        fake_dir = tmp_path / "data"
        with patch("rss_is_terminal.config.user_data_dir", return_value=str(fake_dir)):
            result = db_path()
            assert result.name == "rss.db"
            assert result.parent == fake_dir

    def test_config_path_returns_toml(self, tmp_path):
        fake_dir = tmp_path / "config"
        with patch("rss_is_terminal.config.user_config_dir", return_value=str(fake_dir)):
            result = config_path()
            assert result.name == "config.toml"
            assert result.parent == fake_dir


class TestAppConfig:
    def test_defaults(self):
        config = AppConfig()
        assert config.refresh_interval_minutes == 30
        assert config.default_browser_cmd is None
        assert config.vim_mode is True
        assert config.max_articles_per_feed == 200
        assert config.fetch_timeout_seconds == 30
        assert config.concurrent_fetches == 10

    def test_save_and_load(self, tmp_path):
        config_file = tmp_path / "config.toml"

        with patch("rss_is_terminal.config.config_path", return_value=config_file):
            config = AppConfig(
                refresh_interval_minutes=15,
                vim_mode=False,
                max_articles_per_feed=50,
            )
            config.save()

            loaded = AppConfig.load()
            assert loaded.refresh_interval_minutes == 15
            assert loaded.vim_mode is False
            assert loaded.max_articles_per_feed == 50
            # Defaults preserved for unset values
            assert loaded.fetch_timeout_seconds == 30

    def test_load_creates_default_if_missing(self, tmp_path):
        config_file = tmp_path / "config.toml"
        assert not config_file.exists()

        with patch("rss_is_terminal.config.config_path", return_value=config_file):
            config = AppConfig.load()
            assert config.refresh_interval_minutes == 30
            assert config_file.exists()

    def test_load_ignores_unknown_keys(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text('refresh_interval_minutes = 10\nunknown_key = "value"\n')

        with patch("rss_is_terminal.config.config_path", return_value=config_file):
            config = AppConfig.load()
            assert config.refresh_interval_minutes == 10

    def test_save_comments_out_none_values(self, tmp_path):
        config_file = tmp_path / "config.toml"

        with patch("rss_is_terminal.config.config_path", return_value=config_file):
            config = AppConfig()
            config.save()

            content = config_file.read_text()
            assert "# default_browser_cmd =" in content

    def test_save_string_value(self, tmp_path):
        config_file = tmp_path / "config.toml"

        with patch("rss_is_terminal.config.config_path", return_value=config_file):
            config = AppConfig(default_browser_cmd="firefox")
            config.save()

            loaded = AppConfig.load()
            assert loaded.default_browser_cmd == "firefox"
