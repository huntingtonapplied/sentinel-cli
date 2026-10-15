"""sentinel scans — list, inspect, and manage corruption scans."""

import click
from rich.panel import Panel
from rich.table import Table
from sentinel_cli.api import SentinelClient, AuthError, APIError
from sentinel_cli.output import get_console, is_structured, print_structured
from sentinel_cli.exit_codes import EXIT_AUTH, EXIT_GENERAL


SCAN_STATUS_ICONS = {
    "pending": "⏳",
    "queued": "⏳",
    "running": "⚡",
    "in_progress": "⚡",
    "completed": "✅",
    "complete": "✅",
    "failed": "❌",
    "error": "❌",
    "cancelled": "🚫",
    "canceled": "🚫",
}


def _status_display(value: str) -> str:
    icon = SCAN_STATUS_ICONS.get((value or "").lower(), "")
    return f"{icon} {value}" if icon else (value or "unknown")


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


@click.group(invoke_without_command=True)
@click.option("--limit", "-n", default=20, show_default=True, help="Max results to return")
@click.option("--status", "-s", "scan_status", default=None,
              help="Filter by status (pending, running, completed, failed)")
@click.option("--quiet", "-q", is_flag=True, help="Print only scan IDs")
@click.pass_context
def scans(ctx, limit, scan_status, quiet):
    """List corruption scans (default), or use a subcommand.

    \b
    Examples:
        sentinel scans                       # list recent scans
        sentinel scans --status completed    # filter by status
        sentinel scans get <id>              # scan details
        sentinel scans findings <id>         # findings for a scan
        sentinel scans cancel <id>           # cancel a running scan
    """
    if ctx.invoked_subcommand is not None:
        return

    structured = is_structured(ctx)
    client = _client_or_exit(ctx)

    params = {}
    if limit != 20:
        params["limit"] = limit
    if scan_status:
        params["status"] = scan_status

    try:
        scan_list = client.list_scans(params=params or None)
    except APIError as e:
        if structured:
            print_structured(ctx, {"error": str(e)})
        else:
            click.echo(f"✗ {e}", err=True)
        raise SystemExit(EXIT_GENERAL)

    if structured:
        print_structured(ctx, scan_list)
        return

    if not scan_list:
        click.echo("No scans found.")
        return

    if quiet:
        for s in scan_list:
            click.echo(s.get("id", ""))
        return

    console = get_console(ctx)
    table = Table(show_edge=False, pad_edge=False, box=None)
    table.add_column("Status", min_width=14)
    table.add_column("Findings", justify="right", style="bold")
    table.add_column("Target", style="cyan")
    table.add_column("ID", style="dim")

    for s in scan_list:
        st = _status_display(s.get("status", "unknown"))
        findings_count = (
            s.get("findings_count") or s.get("total_findings") or s.get("findingsCount")
        )
        fc_str = str(findings_count) if findings_count is not None else "-"
        target = (s.get("project_path") or s.get("target") or s.get("path") or "")[:40]
        table.add_row(st, fc_str, target, s.get("id", ""))

    console.print(table)

    if len(scan_list) == limit:
        console.print(f"\nShowing first {limit}. Use --limit to see more.", style="dim")


@scans.command("get")
@click.argument("scan_id")
@click.pass_context
def get_scan(ctx, scan_id):
    """Show details and summary for a single scan."""
    structured = is_structured(ctx)
    client = _client_or_exit(ctx)

    try:
        scan = client.get_scan(scan_id)
        summary = None
        try:
            summary = client.scan_summary(scan_id)
        except APIError:
            summary = None
    except APIError as e:
        if structured:
            print_structured(ctx, {"error": str(e)})
        else:
            click.echo(f"✗ {e}", err=True)
        raise SystemExit(EXIT_GENERAL)

    if structured:
        print_structured(ctx, {"scan": scan, "summary": summary})
        return

    console = get_console(ctx)
    target = scan.get("project_path") or scan.get("target") or scan.get("path") or "(unknown)"
    console.print(Panel(
        f"ID:      [dim]{scan.get('id', scan_id)}[/dim]\n"
        f"Status:  {_status_display(scan.get('status', 'unknown'))}\n"
        f"Target:  [cyan]{target}[/cyan]\n"
        f"Created: {scan.get('created_at', '')}",
        title="Scan",
        expand=False,
    ))

    if isinstance(summary, dict) and summary:
        click.echo()
        table = Table(show_edge=False, pad_edge=False, box=None)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="bold")
        for key, value in summary.items():
            if not isinstance(value, (dict, list)):
                table.add_row(key.replace("_", " ").title(), str(value))
        console.print(table)


@scans.command("findings")
@click.argument("scan_id")
@click.option("--severity", default=None, help="Filter by severity (critical, warning, info)")
@click.option("--category", default=None, help="Filter by category")
@click.option("--status", "finding_status", default=None, help="Filter by finding status")
@click.option("--limit", "-n", default=50, show_default=True, help="Max results")
@click.pass_context
def scan_findings(ctx, scan_id, severity, category, finding_status, limit):
    """List findings produced by a scan."""
    from sentinel_cli.commands.findings import _render_findings

    structured = is_structured(ctx)
    client = _client_or_exit(ctx)

    params = {"limit": limit}
    if severity:
        params["severity"] = severity
    if category:
        params["category"] = category
    if finding_status:
        params["status"] = finding_status

    try:
        finding_list = client.scan_findings(scan_id, params=params)
    except APIError as e:
        if structured:
            print_structured(ctx, {"error": str(e)})
        else:
            click.echo(f"✗ {e}", err=True)
        raise SystemExit(EXIT_GENERAL)

    if structured:
        print_structured(ctx, finding_list)
        return

    _render_findings(ctx, finding_list)


@scans.command("cancel")
@click.argument("scan_id")
@click.pass_context
def cancel_scan(ctx, scan_id):
    """Cancel a running scan."""
    structured = is_structured(ctx)
    client = _client_or_exit(ctx)

    try:
        result = client.cancel_scan(scan_id)
    except APIError as e:
        if structured:
            print_structured(ctx, {"error": str(e)})
        else:
            click.echo(f"✗ {e}", err=True)
        raise SystemExit(EXIT_GENERAL)

    if structured:
        print_structured(ctx, result)
    else:
        click.echo(f"✓ Cancel requested for scan {scan_id}")


@scans.command("delete")
@click.argument("scan_id")
@click.option("--yes", "-y", is_flag=True, default=False, help="Skip confirmation prompt")
@click.pass_context
def delete_scan(ctx, scan_id, yes):
    """Delete a scan and its findings."""
    structured = is_structured(ctx)
    ci_mode = ctx.obj.get("ci", False) if ctx.obj else False
    if not structured and not (yes or ci_mode):
        click.confirm(f"Delete scan {scan_id}? This cannot be undone", abort=True)

    client = _client_or_exit(ctx)
    try:
        client.delete_scan(scan_id)
    except APIError as e:
        if structured:
            print_structured(ctx, {"error": str(e)})
        else:
            click.echo(f"✗ {e}", err=True)
        raise SystemExit(EXIT_GENERAL)

    if structured:
        print_structured(ctx, {"deleted": scan_id})
    else:
        click.echo(f"✓ Deleted scan {scan_id}")
