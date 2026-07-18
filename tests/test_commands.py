"""Tests for CLI commands using Click's test runner."""

import json
from unittest.mock import patch, MagicMock

from sentinel_cli.main import cli


class TestLoginCommand:
    def test_saves_key_and_verifies(self, runner, tmp_config):
        mock_client = MagicMock()
        mock_client.recent_scans.return_value = [{"id": "s1"}, {"id": "s2"}]
        with patch("sentinel_cli.commands.login.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["login", "--key", "dsk_my_key"])
        assert result.exit_code == 0
        assert "API key saved" in result.output
        assert "2 recent scan(s) found" in result.output

    def test_warns_on_verification_failure(self, runner, tmp_config):
        with patch("sentinel_cli.commands.login.SentinelClient",
                   side_effect=Exception("connection refused")):
            result = runner.invoke(cli, ["login", "--key", "dsk_bad"])
        assert result.exit_code == 0
        assert "API key saved" in result.output
        assert "verification failed" in result.output

    def test_saves_custom_url(self, runner, tmp_config):
        mock_client = MagicMock()
        mock_client.recent_scans.return_value = []
        with patch("sentinel_cli.commands.login.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["login", "--key", "dsk_k", "--url", "http://localhost:9017"])
        assert result.exit_code == 0
        assert "http://localhost:9017" in result.output

    def test_ci_login_requires_key(self, runner, tmp_config):
        result = runner.invoke(cli, ["--ci", "login"])
        assert result.exit_code != 0
        assert "--key is required" in result.output


class TestStatusCommand:
    def test_shows_status(self, runner, mock_client):
        with patch("sentinel_cli.commands.status.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "dev@example.com" in result.output
        assert "scan-1" in result.output

    def test_status_json(self, runner, mock_client):
        with patch("sentinel_cli.commands.status.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["-o", "json", "status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["account"]["email"] == "dev@example.com"
        assert len(data["recent_scans"]) == 2


class TestScansCommand:
    def test_lists_scans(self, runner, mock_client):
        with patch("sentinel_cli.commands.scans.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["scans"])
        assert result.exit_code == 0
        assert "scan-1" in result.output

    def test_scans_json(self, runner, mock_client):
        with patch("sentinel_cli.commands.scans.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["-o", "json", "scans"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["id"] == "scan-1"

    def test_scan_get(self, runner, mock_client):
        with patch("sentinel_cli.commands.scans.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["scans", "get", "scan-1"])
        assert result.exit_code == 0
        assert "scan-1" in result.output

    def test_scan_findings(self, runner, mock_client):
        with patch("sentinel_cli.commands.scans.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["scans", "findings", "scan-1"])
        assert result.exit_code == 0
        assert "src/app.py" in result.output

    def test_scan_cancel(self, runner, mock_client):
        mock_client.cancel_scan.return_value = {"message": "cancelled"}
        with patch("sentinel_cli.commands.scans.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["scans", "cancel", "scan-2"])
        assert result.exit_code == 0
        assert "Cancel requested" in result.output

    def test_empty_scans(self, runner):
        client = MagicMock()
        client.list_scans.return_value = []
        with patch("sentinel_cli.commands.scans.SentinelClient", return_value=client):
            result = runner.invoke(cli, ["scans"])
        assert "No scans found" in result.output


class TestScanCommand:
    def test_scan_reports_findings_and_exits_8(self, runner, mock_client):
        # Default --fail-on=any and the mocked scan returns findings → exit 8.
        with patch("sentinel_cli.commands.scan.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["scan", "."])
        assert result.exit_code == 8
        assert "Scan complete" in result.output
        assert "Critical" in result.output
        # The posted config carries the resolved scan mode.
        config = mock_client.create_scan.call_args.args[0]
        assert config["scanMode"] == "quick"
        assert config["path"].startswith("/")  # absolute path

    def test_scan_clean_exits_0(self, runner, mock_client):
        mock_client.create_scan.return_value = {
            "id": "scan-clean", "status": "completed", "project_path": "/repo/a",
            "files_scanned": 80, "findings_count": 0, "metrics": {"severity_counts": {}},
        }
        with patch("sentinel_cli.commands.scan.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["scan", "."])
        assert result.exit_code == 0

    def test_scan_fail_on_none_never_fails(self, runner, mock_client):
        with patch("sentinel_cli.commands.scan.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["scan", ".", "--fail-on", "none"])
        assert result.exit_code == 0

    def test_scan_fail_on_critical(self, runner, mock_client):
        # Only warnings present → --fail-on critical should pass.
        mock_client.create_scan.return_value = {
            "id": "scan-w", "status": "completed", "project_path": "/repo/a",
            "findings_count": 2, "metrics": {"severity_counts": {"warning": 2}},
        }
        with patch("sentinel_cli.commands.scan.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["scan", ".", "--fail-on", "critical"])
        assert result.exit_code == 0

    def test_scan_failed_status(self, runner, mock_client):
        mock_client.create_scan.return_value = {
            "id": "scan-x", "status": "failed", "error_message": "engine unavailable",
        }
        with patch("sentinel_cli.commands.scan.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["scan", "."])
        assert result.exit_code == 1
        assert "engine unavailable" in result.output

    def test_scan_cancelled_is_not_clean(self, runner, mock_client):
        # A cancelled scan must not be reported as a clean pass (exit 0).
        mock_client.create_scan.return_value = {
            "id": "scan-c", "status": "cancelled", "findings_count": 0,
        }
        with patch("sentinel_cli.commands.scan.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["scan", "."])
        assert result.exit_code == 1
        assert "did not complete" in result.output

    def test_scan_json_output(self, runner, mock_client):
        with patch("sentinel_cli.commands.scan.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["-o", "json", "scan", ".", "--fail-on", "none"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "scan-9"

    def test_scan_mode_sets_timeout(self, runner, mock_client):
        with patch("sentinel_cli.commands.scan.SentinelClient", return_value=mock_client):
            runner.invoke(cli, ["scan", ".", "--mode", "deep", "--fail-on", "none"])
        # deep mode → 900s timeout passed through to the client.
        assert mock_client.create_scan.call_args.kwargs["timeout"] == 900.0


class TestFindingsCommand:
    def test_lists_findings(self, runner, mock_client):
        with patch("sentinel_cli.commands.findings.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["findings"])
        assert result.exit_code == 0
        assert "src/app.py" in result.output
        assert "encoding" in result.output

    def test_findings_json(self, runner, mock_client):
        with patch("sentinel_cli.commands.findings.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["-o", "json", "findings"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["id"] == "find-1"

    def test_finding_fix(self, runner, mock_client):
        with patch("sentinel_cli.commands.findings.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["findings", "fix", "find-1"])
        assert result.exit_code == 0
        assert "fixed" in result.output
        mock_client.fix_finding.assert_called_once_with("find-1")

    def test_finding_ignore(self, runner, mock_client):
        with patch("sentinel_cli.commands.findings.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["findings", "ignore", "find-1"])
        assert result.exit_code == 0
        assert "ignored" in result.output
        mock_client.ignore_finding.assert_called_once_with("find-1")

    def test_finding_get(self, runner, mock_client):
        with patch("sentinel_cli.commands.findings.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["findings", "get", "find-1"])
        assert result.exit_code == 0
        assert "Invalid UTF-8" in result.output


class TestReportsCommand:
    def test_lists_reports(self, runner, mock_client):
        with patch("sentinel_cli.commands.reports.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["reports"])
        assert result.exit_code == 0
        assert "scan-summary" in result.output

    def test_create_report(self, runner, mock_client):
        with patch("sentinel_cli.commands.reports.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["reports", "create", "--scan", "scan-1"])
        assert result.exit_code == 0
        assert "rep-2" in result.output
        mock_client.create_report.assert_called_once()

    def test_download_report(self, runner, mock_client, tmp_path):
        dest = tmp_path / "out.html"
        with patch("sentinel_cli.commands.reports.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["reports", "download", "rep-1", "-o", str(dest)])
        assert result.exit_code == 0
        assert dest.read_bytes() == b"<html>report</html>"


class TestMetricsCommand:
    def test_shows_metrics(self, runner, mock_client):
        with patch("sentinel_cli.commands.metrics.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["metrics"])
        assert result.exit_code == 0
        assert "Total Findings" in result.output
        assert "Critical" in result.output

    def test_metrics_json(self, runner, mock_client):
        with patch("sentinel_cli.commands.metrics.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["-o", "json", "metrics"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dashboard"]["total_findings"] == 100
        assert data["severity"]["critical"] == 5


class TestVersionFlag:
    def test_version(self, runner):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "sentinel" in result.output


class TestGlobalFlags:
    def test_verbose_accepted(self, runner, tmp_config, mock_client):
        with patch("sentinel_cli.commands.scans.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["--verbose", "scans"])
            assert result.exit_code == 0

    def test_debug_accepted(self, runner, tmp_config, mock_client):
        with patch("sentinel_cli.commands.scans.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["--debug", "scans"])
            assert result.exit_code == 0

    def test_ci_auto_detected_from_env(self, runner, tmp_config, mock_client):
        with patch("sentinel_cli.commands.scans.SentinelClient", return_value=mock_client):
            result = runner.invoke(cli, ["scans"], env={"CI": "true"})
            assert result.exit_code == 0
