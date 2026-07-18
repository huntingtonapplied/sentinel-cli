"""sentinel scan — run a corruption scan against a codebase and report findings.

This is the CLI's core verb: it starts a scan, waits for it to finish, prints a
summary, and — for CI/pre-commit gating — exits with EXIT_FINDINGS (8) when
findings are present. By default it talks to a local Sentinel backend
(http://localhost:8017), which has filesystem access to the path you pass.
"""

import os

import click
from rich.panel import Panel
from rich.table import Table

from sentinel_cli.api import SentinelClient, AuthError, APIError
from sentinel_cli.output import get_console, is_structured, print_structured
from sentinel_cli.exit_codes import EXIT_AUTH, EXIT_GENERAL, EXIT_FINDINGS

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

    abs_path = os.path.abspath(os.path.expanduser(path))
    config = {"path": abs_path, "scanMode": mode}
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
