"""Tests for the doctor command."""

import json
import pytest
from unittest.mock import patch
from click.testing import CliRunner

from sentinel_cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestDoctorCommand:
    def test_doctor_runs_without_error(self, runner, tmp_config):
        with patch("sentinel_cli.commands.doctor.get_api_key", return_value=None), \
             patch("sentinel_cli.commands.doctor.get_api_url", return_value="http://localhost:8017"):
            result = runner.invoke(cli, ["doctor"])
            assert result.exit_code == 0
            assert "Python >= 3.9" in result.output

    def test_doctor_json_output(self, runner, tmp_config):
        with patch("sentinel_cli.commands.doctor.get_api_key", return_value=None), \
             patch("sentinel_cli.commands.doctor.get_api_url", return_value="http://localhost:8017"):
            result = runner.invoke(cli, ["-o", "json", "doctor"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "checks" in data
            assert "version" in data

    def test_doctor_detects_missing_api_key(self, runner, tmp_config):
        with patch("sentinel_cli.commands.doctor.get_api_key", return_value=None), \
             patch("sentinel_cli.commands.doctor.get_api_url", return_value="http://localhost:8017"):
            result = runner.invoke(cli, ["doctor"])
            assert "API key configured" in result.output
            assert "not set" in result.output

    def test_doctor_checks_key_format(self, runner, tmp_config):
        with patch("sentinel_cli.commands.doctor.get_api_key", return_value="dsk_abc"), \
             patch("sentinel_cli.commands.doctor.get_api_url", return_value="http://localhost:8017"):
            result = runner.invoke(cli, ["-o", "json", "doctor"])
            data = json.loads(result.output)
            fmt = next(c for c in data["checks"] if c["check"] == "API key format (dsk_)")
            assert fmt["ok"] is True
