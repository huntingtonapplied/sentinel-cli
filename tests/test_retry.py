"""Tests for retry logic in the API client."""

import pytest
from unittest.mock import patch, MagicMock
import httpx

from sentinel_cli.api import SentinelClient, APIError


def _mock_response(status_code, json_data=None, text="", headers=None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text
    resp.json.return_value = json_data or {}
    resp.headers = headers or {}
    resp.request = MagicMock()
    resp.request.url = "http://localhost:8017/test"
    return resp


class TestRetryLogic:
    def setup_method(self):
        self.client = SentinelClient(api_key="dsk_k", api_url="http://localhost:8017")

    @patch("sentinel_cli.api.time.sleep")
    def test_retries_on_429(self, mock_sleep):
        resp_429 = _mock_response(429)
        resp_200 = _mock_response(200, {"ok": True})
        self.client._client.get = MagicMock(side_effect=[resp_429, resp_200])

        result = self.client.get("/test")
        assert result == {"ok": True}
        assert self.client._client.get.call_count == 2
        mock_sleep.assert_called_once()

    @patch("sentinel_cli.api.time.sleep")
    def test_retries_on_502(self, mock_sleep):
        resp_502 = _mock_response(502, text="Bad Gateway")
        resp_502.json.side_effect = Exception("not json")
        resp_200 = _mock_response(200, {"ok": True})
        self.client._client.get = MagicMock(side_effect=[resp_502, resp_200])
        assert self.client.get("/test") == {"ok": True}

    @patch("sentinel_cli.api.time.sleep")
    def test_does_not_retry_on_400(self, mock_sleep):
        resp_400 = _mock_response(400, {"detail": "bad request"})
        self.client._client.get = MagicMock(return_value=resp_400)
        with pytest.raises(APIError, match="400"):
            self.client.get("/test")
        assert self.client._client.get.call_count == 1
        mock_sleep.assert_not_called()

    @patch("sentinel_cli.api.time.sleep")
    def test_gives_up_after_max_retries(self, mock_sleep):
        resp_500 = _mock_response(500, {"detail": "server error"})
        self.client._client.get = MagicMock(return_value=resp_500)
        with pytest.raises(APIError, match="500"):
            with patch("sentinel_cli.api.MAX_RETRIES", 2):
                self.client.get("/test")

    @patch("sentinel_cli.api.time.sleep")
    def test_retries_on_connect_error(self, mock_sleep):
        resp_200 = _mock_response(200, {"ok": True})
        self.client._client.get = MagicMock(side_effect=[httpx.ConnectError("refused"), resp_200])
        assert self.client.get("/test") == {"ok": True}
        mock_sleep.assert_called_once()

    @patch("sentinel_cli.api.time.sleep")
    def test_connect_error_after_max_retries_actionable(self, mock_sleep):
        self.client._client.get = MagicMock(side_effect=httpx.ConnectError("refused"))
        with patch("sentinel_cli.api.MAX_RETRIES", 0):
            with pytest.raises(APIError, match="Cannot connect"):
                self.client.get("/test")

    @patch("sentinel_cli.api.time.sleep")
    def test_timeout_after_max_retries_actionable(self, mock_sleep):
        self.client._client.get = MagicMock(side_effect=httpx.TimeoutException("timed out"))
        with patch("sentinel_cli.api.MAX_RETRIES", 0):
            with pytest.raises(APIError, match="timed out"):
                self.client.get("/test")

    @patch("sentinel_cli.api.time.sleep")
    def test_respects_retry_after_header(self, mock_sleep):
        resp_429 = _mock_response(429, headers={"Retry-After": "5"})
        resp_200 = _mock_response(200, {"ok": True})
        self.client._client.get = MagicMock(side_effect=[resp_429, resp_200])
        self.client.get("/test")
        assert mock_sleep.call_args[0][0] >= 5.0
