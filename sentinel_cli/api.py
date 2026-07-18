"""Sentinel API client — thin wrapper around httpx."""

import os
import time
from typing import Any, Dict, Optional

import httpx

from sentinel_cli.config import get_api_key, get_api_url, load_config
from sentinel_cli.log import logger

# Retry configuration
MAX_RETRIES = int(os.getenv("SENTINEL_MAX_RETRIES", "3"))
RETRY_BACKOFF_BASE = 1.0  # seconds
RETRY_BACKOFF_MAX = 30.0  # seconds
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
RETRYABLE_EXCEPTIONS = (httpx.ConnectError, httpx.TimeoutException)


# Error suggestion hints keyed by status code + context
_ERROR_HINTS = {
    401: [
        "Run: sentinel login",
        "Or set SENTINEL_API_KEY env var",
    ],
    403: [
        "You may not have access to this resource.",
        "Check your subscription or contact your administrator.",
    ],
    404: [
        "The resource was not found. Check the ID or URL.",
        "Run: sentinel scans   to list available scans",
    ],
    422: [
        "The request data is invalid. Check required fields.",
        "Run: sentinel <command> --help   for usage details",
    ],
    429: [
        "Rate limit exceeded. Wait a moment and try again.",
    ],
    500: [
        "Server error. The Sentinel team has been notified.",
        "Try again in a few minutes.",
    ],
}


def format_error_hint(status_code: int, detail: Optional[str] = None) -> str:
    """Get actionable hint text for an error status code.

    Some endpoints are access-gated (subscription/entitlement). The backend
    returns a 403 with a specific detail string; detect that to avoid
    misleading generic 403 guidance.
    """
    if status_code == 403 and detail and (
        "subscription" in detail.lower() or "access" in detail.lower()
    ):
        hints = [
            "An active subscription or access code is required for this action.",
            "Subscribe or redeem an access code at /checkout.",
        ]
    else:
        hints = _ERROR_HINTS.get(status_code, [])
    if not hints:
        return ""
    return "\n".join(f"  {h}" for h in hints)


class SentinelClient:
    """HTTP client for the Sentinel API."""

    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None):
        self.api_key = api_key or get_api_key()
        self.api_url = api_url or get_api_url()

        if not self.api_key:
            raise AuthError(
                "Not authenticated.\n"
                "  Run: sentinel login\n"
                "  Or set SENTINEL_API_KEY env var"
            )

        config = load_config()
        self._timeout = float(os.getenv("SENTINEL_TIMEOUT", config.get("timeout", 60)))
        self._client = httpx.Client(
            base_url=self.api_url,
            timeout=self._timeout,
        )
        logger.debug("API client initialized: %s (timeout=%.0fs)", self.api_url, self._timeout)

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"ApiKey {self.api_key}"
        return headers

    def _request_with_retry(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Execute an HTTP request with retry logic for transient failures."""
        last_exc = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = getattr(self._client, method)(path, headers=self._headers(), **kwargs)
                if resp.status_code not in RETRYABLE_STATUS_CODES or attempt == MAX_RETRIES:
                    return resp
                # Retryable status — back off and retry
                retry_after = 0.0
                try:
                    retry_after = float(resp.headers.get("Retry-After", 0))
                except (ValueError, TypeError):
                    pass
                delay = max(retry_after, RETRY_BACKOFF_BASE * (2 ** attempt))
                delay = min(delay, RETRY_BACKOFF_MAX)
                logger.info(
                    "Retrying %s %s (status %d, attempt %d/%d, waiting %.1fs)",
                    method.upper(), path, resp.status_code, attempt + 1, MAX_RETRIES, delay,
                )
                time.sleep(delay)
            except RETRYABLE_EXCEPTIONS as exc:
                last_exc = exc
                if attempt == MAX_RETRIES:
                    if isinstance(exc, httpx.ConnectError):
                        raise APIError(
                            f"Cannot connect to {self.api_url}\n"
                            "  Check your network connection\n"
                            "  Verify API URL: sentinel doctor",
                            status_code=0,
                        ) from exc
                    if isinstance(exc, httpx.TimeoutException):
                        raise APIError(
                            f"Request timed out after {self._timeout:.0f}s\n"
                            "  Try: SENTINEL_TIMEOUT=120 sentinel <command>\n"
                            "  Or add 'timeout: 120' to ~/.sentinel/config.yaml",
                            status_code=0,
                        ) from exc
                    raise
                delay = min(RETRY_BACKOFF_BASE * (2 ** attempt), RETRY_BACKOFF_MAX)
                logger.info(
                    "Retrying %s %s (%s, attempt %d/%d, waiting %.1fs)",
                    method.upper(), path, exc.__class__.__name__, attempt + 1, MAX_RETRIES, delay,
                )
                time.sleep(delay)
        # Should not reach here, but just in case
        raise last_exc or APIError(f"Request failed after {MAX_RETRIES} retries")

    def get(self, path: str, params: Optional[Dict] = None) -> Any:
        logger.debug("GET %s params=%s", path, params)
        resp = self._request_with_retry("get", path, params=params)
        return self._handle_response(resp)

    def get_raw(self, path: str, params: Optional[Dict] = None) -> bytes:
        """GET that returns the raw response body (for file downloads)."""
        logger.debug("GET (raw) %s params=%s", path, params)
        resp = self._request_with_retry("get", path, params=params)
        if resp.status_code >= 400:
            self._handle_response(resp)  # raises with a helpful message
        return resp.content

    def post(self, path: str, data: Optional[Dict] = None) -> Any:
        logger.debug("POST %s", path)
        resp = self._request_with_retry("post", path, json=data)
        return self._handle_response(resp)

    def patch(self, path: str, data: Optional[Dict] = None) -> Any:
        logger.debug("PATCH %s", path)
        resp = self._request_with_retry("patch", path, json=data)
        return self._handle_response(resp)

    def put(self, path: str, data: Optional[Dict] = None) -> Any:
        logger.debug("PUT %s", path)
        resp = self._request_with_retry("put", path, json=data)
        return self._handle_response(resp)

    def delete(self, path: str) -> Any:
        logger.debug("DELETE %s", path)
        resp = self._request_with_retry("delete", path)
        if resp.status_code == 204:
            return None
        return self._handle_response(resp)

    def _handle_response(self, resp: httpx.Response) -> Any:
        logger.debug("Response %d (%s)", resp.status_code, resp.request.url)
        if resp.status_code == 401:
            raise AuthError(
                "Not authenticated.\n"
                "  Run: sentinel login\n"
                "  Or set SENTINEL_API_KEY env var"
            )
        if resp.status_code >= 400:
            detail = ""
            try:
                body = resp.json()
                detail = body.get("detail", "")
                if isinstance(detail, dict):
                    detail = detail.get("message", str(detail))
                if not detail:
                    detail = resp.text
            except Exception:
                detail = resp.text

            hint = format_error_hint(resp.status_code, detail=detail)
            msg = f"API error {resp.status_code}: {detail}"
            if hint:
                msg += f"\n{hint}"
            raise APIError(msg, status_code=resp.status_code)

        if resp.status_code == 204:
            return None
        return resp.json()

    # --- Account / auth ---

    def get_profile(self) -> Dict:
        """Get the current user's account profile."""
        return self.get("/v1/account/profile")

    def whoami(self) -> Dict:
        """Get the current authenticated user from the token."""
        return self.get("/v1/auth/me")

    def access_status(self) -> Dict:
        """Get the current user's access/entitlement status."""
        return self.get("/v1/payments/access-status")

    # --- Scans ---

    def create_scan(self, config: Dict, timeout: Optional[float] = None) -> Dict:
        """Start a new scan.

        The backend processes the scan synchronously and only responds once it
        finishes, which can take several minutes (deep/ecosystem modes). So this
        uses a caller-supplied timeout and deliberately does NOT go through the
        retry path: re-issuing the request on a timeout would start a *second*
        scan of the same path (the backend rejects that with 409, but the first
        scan keeps running). The returned ScanResponse carries the final status,
        findings_count, and metrics.
        """
        logger.debug("POST /v1/scans (create, timeout=%s)", timeout)
        resp = self._client.post(
            "/v1/scans",
            headers=self._headers(),
            json={"config": config},
            timeout=timeout or self._timeout,
        )
        return self._handle_response(resp)

    def list_scans(self, params: Optional[Dict] = None) -> list:
        """List scans. Raises APIError on failure."""
        data = self.get("/v1/scans", params=params)
        return _unwrap_list(data)

    def recent_scans(self, limit: int = 5) -> list:
        """Get the most recent scans (safe — returns [] on error)."""
        try:
            data = self.get("/v1/scans/recent", params={"limit": limit})
            return _unwrap_list(data)
        except APIError:
            return []

    def get_scan(self, scan_id: str) -> Dict:
        return self.get(f"/v1/scans/{scan_id}")

    def scan_summary(self, scan_id: str) -> Dict:
        return self.get(f"/v1/scans/{scan_id}/summary")

    def scan_findings(self, scan_id: str, params: Optional[Dict] = None) -> list:
        return _unwrap_list(self.get(f"/v1/scans/{scan_id}/findings", params=params))

    def cancel_scan(self, scan_id: str) -> Dict:
        return self.post(f"/v1/scans/{scan_id}/cancel")

    def delete_scan(self, scan_id: str) -> Any:
        return self.delete(f"/v1/scans/{scan_id}")

    # --- Findings ---

    def list_findings(self, params: Optional[Dict] = None) -> list:
        return _unwrap_list(self.get("/v1/findings", params=params))

    def get_finding(self, finding_id: str) -> Dict:
        return self.get(f"/v1/findings/{finding_id}")

    def update_finding(self, finding_id: str, payload: Dict) -> Dict:
        return self.patch(f"/v1/findings/{finding_id}", payload)

    def fix_finding(self, finding_id: str) -> Dict:
        return self.post(f"/v1/findings/{finding_id}/fix")

    def ignore_finding(self, finding_id: str) -> Dict:
        return self.post(f"/v1/findings/{finding_id}/ignore")

    # --- Reports ---

    def list_reports(self, params: Optional[Dict] = None) -> list:
        return _unwrap_list(self.get("/v1/reports", params=params))

    def get_report(self, report_id: str) -> Dict:
        return self.get(f"/v1/reports/{report_id}")

    def create_report(self, payload: Dict) -> Dict:
        return self.post("/v1/reports", payload)

    def delete_report(self, report_id: str) -> Any:
        return self.delete(f"/v1/reports/{report_id}")

    def download_report(self, report_id: str) -> bytes:
        return self.get_raw(f"/v1/reports/{report_id}/download")

    # --- Analytics / metrics ---

    def dashboard(self, params: Optional[Dict] = None) -> Dict:
        return self.get("/v1/analytics/dashboard", params=params)

    def severity_distribution(self, params: Optional[Dict] = None) -> Dict:
        return self.get("/v1/analytics/severity", params=params)


def _unwrap_list(data: Any) -> list:
    """Normalize paginated/list responses to a plain list.

    Sentinel endpoints return either a bare list or a paginated object with a
    ``data`` (or ``items``) array. Accept both.
    """
    if isinstance(data, dict):
        for key in ("data", "items", "results"):
            if key in data and isinstance(data[key], list):
                return data[key]
        return [data]
    return data or []


class AuthError(Exception):
    pass


class APIError(Exception):
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code
