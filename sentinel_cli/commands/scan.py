"""sentinel scan — run a corruption scan against a codebase and report findings.

This is the CLI's core verb: it starts a scan, waits for it to finish, prints a
summary, and — for CI/pre-commit gating — exits with EXIT_FINDINGS (8) when
findings are present. Scans run server-side, so the backend must be able to
read PATH: point the CLI at a local backend with SENTINEL_API_URL or
`sentinel login --url`. Against the hosted API (https://api.sentinelscanner.com)
`scan` refuses, because the hosted service cannot read code on your machine
(SENTINEL-HOSTED-SCAN, Bridge decision 2026-10-14).
"""

import os
from urllib.parse import urlparse

import click
from rich.panel import Panel
from rich.table import Table

from sentinel_cli.api import SentinelClient, AuthError, APIError
from sentinel_cli.config import get_api_url
from sentinel_cli.output import get_console, is_structured, print_structured
from sentinel_cli.exit_codes import EXIT_AUTH, EXIT_GENERAL, EXIT_FINDINGS, EXIT_VALIDATION

# Severity ordering used by --fail-on gating (most → least severe).
_SEVERITY_ORDER = ["critical", "warning", "info"]

# Default wait budget per scan mode (seconds). Deep/ecosystem scans run many
# tiers and take minutes; the default 60s request timeout is far too short.
_MODE_TIMEOUTS = {
    "quick": 300.0,
    "ci-cd": 300.0,
    "deep": 900.0,
    "ecosystem": 1200.0,
}


# Hosts where the backend shares this machine's filesystem, so the absolute
# path is meaningful to it. Anything else is a remote API that cannot read
# local files (R-sentinel-cli-scan-upload-1).
_LOCAL_API_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal"}


def _api_is_local(client) -> bool:
    url = getattr(client, "api_url", None)
    if not isinstance(url, str):
        url = get_api_url()
    host = (urlparse(url).hostname or "").lower()
    return host in _LOCAL_API_HOSTS


HOSTED_SCAN_UNSUPPORTED = (
    "Hosted scans of local code aren't supported yet. "
    "Use the desktop app or a local backend "
    "(sentinel login --url http://localhost:<port>, or SENTINEL_API_URL)."
)


def _path_for_api(abs_path: str, local_api: bool) -> str:
    """Path value sent to the API.

    A local backend gets the absolute path (it scans this filesystem). A
    remote API (the hosted default) gets only the directory name: the
    client's absolute path (home directory, username, folder layout) never
    leaves the machine. The hosted API has no upload endpoint, so it cannot
    read local files either way; the README says so.
    """
    if local_api:
        return abs_path
    return os.path.basename(abs_path.rstrip(os.sep)) or "."


def _client_or_exit(ctx):
    structured = is_structured(ctx)
    try:
        return SentinelClient()
    except AuthError as e:
        if structured:
            print_structured(ctx, {"error": str(e)})
        else:
            click.echo(f"✗ {e}", err=True)
        raise SystemExit(EXIT_AUTH)


def _severity_counts(scan: dict, client: SentinelClient) -> dict:
    """Return a normalized {severity: count} map for a completed scan.

    Prefers the inline metrics on the scan response, falling back to the scan
    summary endpoint when the response didn't include a breakdown.
    """
    metrics = scan.get("metrics") or {}
    counts = metrics.get("severity_counts") or metrics.get("severity_breakdown")
    if not counts:
        scan_id = scan.get("id")
        if scan_id:
            try:
                summary = client.scan_summary(scan_id)
                counts = summary.get("severity_breakdown") or {}
            except APIError:
                counts = {}
    return {str(k).lower(): int(v) for k, v in (counts or {}).items() if isinstance(v, (int, float))}


def _should_fail(fail_on: str, findings_count: int, severity_counts: dict) -> bool:
    """Decide whether findings warrant a non-zero (EXIT_FINDINGS) exit."""
    if fail_on == "none":
        return False
    if fail_on == "any":
        return findings_count > 0
    # Severity threshold: fail if any finding at or above `fail_on` exists.
    threshold_index = _SEVERITY_ORDER.index(fail_on)
    triggering = _SEVERITY_ORDER[: threshold_index + 1]
    if severity_counts:
        return any(severity_counts.get(sev, 0) > 0 for sev in triggering)
    # No breakdown available — fall back to the total so we don't silently pass.
    return findings_count > 0


@click.command()
@click.argument("path", default=".", required=False)
@click.option("--mode", "-m", type=click.Choice(["quick", "deep", "ecosystem", "ci-cd"]),
              default="quick", show_default=True,
              help="Scan depth: quick (Tier 1, ~30s), deep (all tiers), "
                   "ecosystem (cross-project), ci-cd (changed files)")
@click.option("--tier", "tiers", multiple=True, type=click.IntRange(1, 4),
              help="Detection tier(s) to run (1-4); repeatable. Overrides --mode.")
@click.option("--name", default=None, help="Project name for reporting")
@click.option("--preset", default=None, help="Named preset configuration")
@click.option("--fail-on", type=click.Choice(["any", "critical", "warning", "info", "none"]),
              default="any", show_default=True,
              help="Exit 8 when findings at or above this severity are present "
                   "('any' = any finding, 'none' = never fail the command)")
@click.option("--timeout", "scan_timeout", type=float, default=None,
              help="Max seconds to wait for the scan (default: per-mode, up to 1200s)")
@click.pass_context
def scan(ctx, path, mode, tiers, name, preset, fail_on, scan_timeout):
    """Scan a codebase for corruption and report findings.

    Runs a scan against PATH (default: current directory), waits for it to
    complete, prints a summary, and exits with code 8 when findings are present
    so it can gate CI pipelines and pre-commit hooks.

    Scans run on a local backend that can read PATH. Hosted scans of local
    code aren't supported yet: against the hosted API this command refuses.
    Use the desktop app or a local backend (sentinel login --url).

    \b
    Examples:
        sentinel scan                         # scan the current directory
        sentinel scan ./src --mode deep       # deep analysis of ./src
        sentinel scan . --mode ci-cd --fail-on critical
        sentinel -o json scan . --fail-on none   # report only, never fail
    """
    structured = is_structured(ctx)
    ci_mode = ctx.obj.get("ci", False) if ctx.obj else False
    client = _client_or_exit(ctx)

    # SENTINEL-HOSTED-SCAN (Bridge 2026-10-14, option c): the hosted API has no
    # upload route and cannot read this machine's files, so refuse honestly
    # instead of submitting a scan of a path the server cannot see.
    if not _api_is_local(client):
        if structured:
            print_structured(ctx, {"error": HOSTED_SCAN_UNSUPPORTED})
        else:
            click.echo(f"✗ {HOSTED_SCAN_UNSUPPORTED}", err=True)
        raise SystemExit(EXIT_VALIDATION)

    abs_path = os.path.abspath(os.path.expanduser(path))
    config = {"path": _path_for_api(abs_path, True), "scanMode": mode}
    if tiers:
        config["tiers"] = list(tiers)
    if name:
        config["project_name"] = name
    if preset:
        config["preset"] = preset

    timeout = scan_timeout or _MODE_TIMEOUTS.get(mode, 300.0)

    try:
        if structured or ci_mode:
            result = client.create_scan(config, timeout=timeout)
        else:
            console = get_console(ctx)
            with console.status(f"Scanning {abs_path} ({mode})…", spinner="dots"):
                result = client.create_scan(config, timeout=timeout)
    except APIError as e:
        if structured:
            print_structured(ctx, {"error": str(e)})
        else:
            click.echo(f"✗ {e}", err=True)
        raise SystemExit(EXIT_GENERAL)

    status = (result.get("status") or "unknown").lower()
    findings_count = (
        result.get("findings_count")
        or result.get("total_findings")
        or 0
    )
    severity_counts = _severity_counts(result, client)

    # A scan that failed or was cancelled produced no trustworthy result — never
    # report it as a clean pass. Only "completed"/"complete" are gating-final.
    if status in ("failed", "error", "cancelled", "canceled"):
        err = result.get("error_message") or f"scan {status}"
        if structured:
            print_structured(ctx, result)
        else:
            click.echo(f"✗ Scan did not complete ({status}): {err}", err=True)
        raise SystemExit(EXIT_GENERAL)

    if structured:
        print_structured(ctx, result)
    else:
        console = get_console(ctx)
        files_scanned = result.get("files_scanned", 0)
        body = (
            f"ID:       [dim]{result.get('id', '')}[/dim]\n"
            f"Target:   [cyan]{result.get('project_path', abs_path)}[/cyan]\n"
            f"Status:   {status}\n"
            f"Files:    {files_scanned}\n"
            f"Findings: [bold]{findings_count}[/bold]"
        )
        border = "yellow" if findings_count else "green"
        title = "Scan complete" if status in ("completed", "complete") else "Scan"
        console.print(Panel(body, title=title, border_style=border, expand=False))

        if severity_counts:
            table = Table(show_edge=False, pad_edge=False, box=None)
            table.add_column("Severity", style="cyan")
            table.add_column("Count", justify="right", style="bold")
            for sev in _SEVERITY_ORDER:
                if sev in severity_counts:
                    table.add_row(sev.title(), str(severity_counts[sev]))
            console.print(table)

        scan_id = result.get("id")
        if findings_count and scan_id:
            console.print(
                f"\nInspect: [dim]sentinel scans findings {scan_id}[/dim]", style="dim"
            )

    if _should_fail(fail_on, findings_count, severity_counts):
        raise SystemExit(EXIT_FINDINGS)
