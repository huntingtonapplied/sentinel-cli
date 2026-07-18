"""Tests for config module."""

import os
import pytest
from unittest.mock import patch

from sentinel_cli.config import (
    load_config,
    save_config,
    get_api_key,
    get_api_url,
    set_api_key,
    set_api_url,
    validate_config,
    DEFAULT_API_URL,
)


class TestLoadConfig:
    def test_returns_empty_dict_when_no_file(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        with patch("sentinel_cli.config.CONFIG_FILE", config_file):
            assert load_config() == {}

    def test_loads_existing_config(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("api_key: dsk_x\napi_url: http://localhost:8017\n")
        with patch("sentinel_cli.config.CONFIG_FILE", config_file):
            config = load_config()
            assert config["api_key"] == "dsk_x"
            assert config["api_url"] == "http://localhost:8017"

    def test_handles_empty_file(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        with patch("sentinel_cli.config.CONFIG_FILE", config_file):
            assert load_config() == {}


class TestSaveConfig:
    def test_creates_config_file(self, tmp_path):
        config_dir = tmp_path / ".sentinel"
        config_file = config_dir / "config.yaml"
        with patch("sentinel_cli.config.CONFIG_DIR", config_dir), \
             patch("sentinel_cli.config.CONFIG_FILE", config_file):
            save_config({"api_key": "dsk_test"})
            assert config_file.exists()
            assert "dsk_test" in config_file.read_text()

    def test_overwrites_existing(self, tmp_path):
        config_dir = tmp_path / ".sentinel"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text("api_key: old\n")
        with patch("sentinel_cli.config.CONFIG_DIR", config_dir), \
             patch("sentinel_cli.config.CONFIG_FILE", config_file):
            save_config({"api_key": "new"})
            content = config_file.read_text()
            assert "new" in content
            assert "old" not in content


class TestGetApiKey:
    def test_env_var_takes_precedence(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("api_key: file-key\n")
        with patch("sentinel_cli.config.CONFIG_FILE", config_file), \
             patch.dict(os.environ, {"SENTINEL_API_KEY": "env-key"}):
            assert get_api_key() == "env-key"

    def test_falls_back_to_config(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("api_key: file-key\n")
        with patch("sentinel_cli.config.CONFIG_FILE", config_file):
            env = os.environ.copy()
            env.pop("SENTINEL_API_KEY", None)
            with patch.dict(os.environ, env, clear=True):
                assert get_api_key() == "file-key"

    def test_returns_none_when_unset(self, tmp_path):
        config_file = tmp_path / "nonexistent.yaml"
        with patch("sentinel_cli.config.CONFIG_FILE", config_file):
            env = os.environ.copy()
            env.pop("SENTINEL_API_KEY", None)
            with patch.dict(os.environ, env, clear=True):
                assert get_api_key() is None


class TestGetApiUrl:
    def test_returns_default_when_unset(self, tmp_path):
        config_file = tmp_path / "nonexistent.yaml"
        with patch("sentinel_cli.config.CONFIG_FILE", config_file):
            env = os.environ.copy()
            env.pop("SENTINEL_API_URL", None)
            with patch.dict(os.environ, env, clear=True):
                assert get_api_url() == DEFAULT_API_URL

    def test_env_var_overrides(self):
        with patch.dict(os.environ, {"SENTINEL_API_URL": "http://custom"}):
            assert get_api_url() == "http://custom"


class TestSetters:
    def test_persists_key(self, tmp_path):
        config_dir = tmp_path / ".sentinel"
        config_file = config_dir / "config.yaml"
        with patch("sentinel_cli.config.CONFIG_DIR", config_dir), \
             patch("sentinel_cli.config.CONFIG_FILE", config_file):
            set_api_key("dsk_new")
            assert load_config()["api_key"] == "dsk_new"

    def test_preserves_other_fields(self, tmp_path):
        config_dir = tmp_path / ".sentinel"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text("api_url: http://custom\n")
        with patch("sentinel_cli.config.CONFIG_DIR", config_dir), \
             patch("sentinel_cli.config.CONFIG_FILE", config_file):
            set_api_key("dsk_key")
            config = load_config()
            assert config["api_key"] == "dsk_key"
            assert config["api_url"] == "http://custom"

    def test_set_api_url(self, tmp_path):
        config_dir = tmp_path / ".sentinel"
        config_file = config_dir / "config.yaml"
        with patch("sentinel_cli.config.CONFIG_DIR", config_dir), \
             patch("sentinel_cli.config.CONFIG_FILE", config_file):
            set_api_url("http://localhost:9000")
            assert load_config()["api_url"] == "http://localhost:9000"


class TestValidateConfig:
    def test_warns_on_unknown_key(self):
        warnings = validate_config({"api_key": "x", "typo_key": "y"})
        assert len(warnings) == 1
        assert "Unknown config key: 'typo_key'" in warnings[0]

    def test_suggests_close_match(self):
        warnings = validate_config({"api_kye": "x"})
        assert "did you mean 'api_key'" in warnings[0]

    def test_warns_on_bad_url(self):
        warnings = validate_config({"api_url": "ftp://example.com"})
        assert any("http://" in w for w in warnings)

    def test_passes_for_valid_config(self):
        warnings = validate_config({"api_key": "k", "api_url": "https://api.sentinelscanner.com"})
        assert warnings == []

    def test_empty(self):
        assert validate_config({}) == []
