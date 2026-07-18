"""Shared fixtures for CLI tests."""

import pytest
from unittest.mock import MagicMock, patch
from click.testing import CliRunner


@pytest.fixture
def runner():
    """Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def tmp_config(tmp_path):
    """Redirect config to a temp directory so tests don't touch ~/.sentinel."""
    config_dir = tmp_path / ".sentinel"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"

    with patch("sentinel_cli.config.CONFIG_DIR", config_dir), \
         patch("sentinel_cli.config.CONFIG_FILE", config_file):
        yield config_file


@pytest.fixture
def mock_client():
    """A mocked SentinelClient that doesn't make real HTTP calls."""
    client = MagicMock()
    client.api_key = "dsk_test_key_123"
    client.api_url = "http://localhost:8017"
    client.get_profile.return_value = {
        "id": "user-1",
        "email": "dev@example.com",
        "name": "Dev User",
    }
    client.recent_scans.return_value = [
        {"id": "scan-1", "status": "completed", "findings_count": 7, "project_path": "/repo/a"},
        {"id": "scan-2", "status": "running", "findings_count": 0, "project_path": "/repo/b"},
    ]
    client.list_scans.return_value = [
        {"id": "scan-1", "status": "completed", "findings_count": 7, "project_path": "/repo/a"},
        {"id": "scan-2", "status": "running", "findings_count": 0, "project_path": "/repo/b"},
    ]
    client.get_scan.return_value = {
        "id": "scan-1", "status": "completed", "project_path": "/repo/a",
        "created_at": "2026-06-28T00:00:00Z",
    }
    client.create_scan.return_value = {
        "id": "scan-9", "status": "completed", "project_path": "/repo/a",
        "files_scanned": 120, "findings_count": 3,
        "metrics": {"severity_counts": {"critical": 1, "warning": 2}},
        "created_at": "2026-06-28T00:00:00Z",
    }
    client.scan_summary.return_value = {"findings_count": 7, "fixed_count": 2}
    client.list_findings.return_value = [
        {"id": "find-1", "severity": "critical", "category": "encoding",
         "file_path": "src/app.py", "line": 42, "status": "open"},
        {"id": "find-2", "severity": "warning", "category": "truncation",
         "file_path": "docs/readme.md", "line": 3, "status": "open"},
    ]
    client.scan_findings.return_value = client.list_findings.return_value
    client.get_finding.return_value = {
        "id": "find-1", "severity": "critical", "category": "encoding",
        "file_path": "src/app.py", "line": 42, "status": "open",
        "message": "Invalid UTF-8 sequence",
    }
    client.fix_finding.return_value = {"id": "find-1", "status": "fixed"}
    client.ignore_finding.return_value = {"id": "find-1", "status": "ignored"}
    client.list_reports.return_value = [
        {"id": "rep-1", "report_type": "scan-summary", "status": "ready",
         "created_at": "2026-06-28T00:00:00Z"},
    ]
    client.get_report.return_value = {"id": "rep-1", "report_type": "scan-summary", "status": "ready"}
    client.create_report.return_value = {"id": "rep-2", "report_type": "scan-summary"}
    client.download_report.return_value = b"<html>report</html>"
    client.dashboard.return_value = {"total_findings": 100, "fixed": 30, "patterns_used": 12}
    client.severity_distribution.return_value = {"critical": 5, "warning": 20, "info": 75}
    return client
