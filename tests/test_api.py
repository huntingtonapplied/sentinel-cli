"""Tests for the API client."""

import pytest
from unittest.mock import patch, MagicMock
import httpx

from sentinel_cli.api import (
    SentinelClient,
    AuthError,
    APIError,
    _unwrap_list,
    format_error_hint,
)


def _mock_response(status_code, json_data=None, text=""):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text
    resp.json.return_value = json_data or {}
    return resp


class TestSentinelClient:
    def test_sets_auth_header(self):
        client = SentinelClient(api_key="dsk_test", api_url="http://localhost:8017")
        headers = client._headers()
        assert headers["Authorization"] == "ApiKey dsk_test"

    def test_raises_auth_error_without_key(self):
        with patch("sentinel_cli.api.get_api_key", return_value=None), \
             patch("sentinel_cli.api.get_api_url", return_value="http://localhost:8017"):
            with pytest.raises(AuthError, match="Not authenticated"):
                SentinelClient()


class TestHandleResponse:
    def setup_method(self):
        self.client = SentinelClient(api_key="dsk_k", api_url="http://localhost:8017")

    def test_returns_json_on_success(self):
        resp = _mock_response(200, {"data": "ok"})
        assert self.client._handle_response(resp) == {"data": "ok"}

    def test_raises_auth_error_on_401(self):
        resp = _mock_response(401)
        with pytest.raises(AuthError):
            self.client._handle_response(resp)

    def test_raises_api_error_on_500(self):
        resp = _mock_response(500, {"detail": "Internal error"})
        with pytest.raises(APIError, match="500"):
            self.client._handle_response(resp)

    def test_raises_api_error_on_404(self):
        resp = _mock_response(404, {"detail": "Not found"})
        with pytest.raises(APIError, match="404"):
            self.client._handle_response(resp)

    def test_handles_non_json_error_body(self):
        resp = _mock_response(502, text="Bad Gateway")
        resp.json.side_effect = Exception("not json")
        with pytest.raises(APIError, match="Bad Gateway"):
            self.client._handle_response(resp)

    def test_403_subscription_gate_hint(self):
        resp = _mock_response(403, {"detail": "Active subscription required."})
        with pytest.raises(APIError) as exc_info:
            self.client._handle_response(resp)
        assert "/checkout" in str(exc_info.value)


class TestUnwrapList:
    def test_bare_list(self):
        assert _unwrap_list([{"id": "a"}]) == [{"id": "a"}]

    def test_data_envelope(self):
        assert _unwrap_list({"data": [{"id": "a"}], "total": 1}) == [{"id": "a"}]

    def test_items_envelope(self):
        assert _unwrap_list({"items": [{"id": "b"}]}) == [{"id": "b"}]

    def test_none(self):
        assert _unwrap_list(None) == []


class TestListMethods:
    def test_list_scans_unwraps(self):
        client = SentinelClient(api_key="dsk_k", api_url="http://localhost:8017")
        with patch.object(client, "get", return_value={"data": [{"id": "s1"}], "total": 1}):
            assert client.list_scans() == [{"id": "s1"}]

    def test_recent_scans_returns_empty_on_error(self):
        client = SentinelClient(api_key="dsk_k", api_url="http://localhost:8017")
        with patch.object(client, "get", side_effect=APIError("fail")):
            assert client.recent_scans() == []

    def test_list_findings(self):
        client = SentinelClient(api_key="dsk_k", api_url="http://localhost:8017")
        with patch.object(client, "get", return_value=[{"id": "f1"}]):
            assert client.list_findings() == [{"id": "f1"}]


class TestErrorHint:
    def test_404_hint_mentions_scans(self):
        assert "sentinel scans" in format_error_hint(404)

    def test_401_hint_mentions_login(self):
        assert "sentinel login" in format_error_hint(401)
