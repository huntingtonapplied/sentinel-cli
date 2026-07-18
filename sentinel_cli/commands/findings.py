"""sentinel findings — list and triage corruption findings."""

import click
from rich.panel import Panel
from rich.table import Table
from sentinel_cli.api import SentinelClient, AuthError, APIError
from sentinel_cli.output import get_console, is_structured, print_structured
from sentinel_cli.exit_codes import EXIT_AUTH, EXIT_GENERAL


SEVERITY_ICONS = {
    "critical": "🔴",
    "warning": "🟡",
    "info": "🔵",
}


def _severity_display(value: str) -> str:
    icon = SEVERITY_ICONS.get((value or "").lower(), "")
    return f"{icon} {value}" if icon else (value or "")


def _render_findings(ctx, finding_list):
    """Shared table renderer used by `findings` and `scans findings`."""
    if not finding_list:
        click.echo("No findings.")
        return

    console = get_console(ctx)
    table = Table(show_edge=False, pad_edge=False, box=None)
    table.add_column("Severity", min_width=12)
    table.add_column("Category", style="cyan", min_width=14)
    table.add_column("File", min_width=24)
    table.add_column("Line", justify="right")
    table.add_column("Status", min_width=10)
    table.add_column("ID", style="dim")

    for f in finding_list:
        severity = _severity_display(f.get("severity", ""))
        category = (f.get("category") or "")[:18]
        file_path = (f.get("file_path") or f.get("filePath") or f.get("path") or "")
        if len(file_path) > 36:
            file_path = "…" + file_path[-35:]
        line = f.get("line") or f.get("line_number") or f.get("lineNumber")
        line_str = str(line) if line is not None else "-"
        st = f.get("status", "")
        table.add_row(severity, category, file_path, line_str, st, f.get("id", ""))

    console.print(table)


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
@click.option("--scan", "scan_id", default=None, help="Filter findings by scan ID")
@click.option("--severity", default=None, help="Filter by severity (critical, warning, info)")
@click.option("--category", default=None, help="Filter by category")
@click.option("--status", "finding_status", default=None, help="Filter by status")
@click.option("--limit", "-n", default=50, show_default=True, help="Max results to return")
@click.option("--quiet", "-q", is_flag=True, help="Print only finding IDs")
@click.pass_context
def findings(ctx, scan_id, severity, category, finding_status, limit, quiet):
    """List corruption findings (default), or use a subcommand.

    \b
    Examples:
        sentinel findings                      # list recent findings
        sentinel findings --severity critical  # only critical
        sentinel findings --scan <id>          # findings for a scan
        sentinel findings get <id>             # finding detail
        sentinel findings fix <id>             # mark as fixed
        sentinel findings ignore <id>          # mark as ignored
    """
    if ctx.invoked_subcommand is not None:
        return

    structured = is_structured(ctx)
    client = _client_or_exit(ctx)

    params = {"limit": limit}
    if scan_id:
        params["scan_id"] = scan_id
    if severity:
        params["severity"] = severity
    if category:
        params["category"] = category
    if finding_status:
        params["status"] = finding_status

    try:
        finding_list = client.list_findings(params=params)
    except APIError as e:
        if structured:
            print_structured(ctx, {"error": str(e)})
        else:
            click.echo(f"✗ {e}", err=True)
        raise SystemExit(EXIT_GENERAL)

    if structured:
        print_structured(ctx, finding_list)
        return

    if quiet:
        for f in finding_list:
            click.echo(f.get("id", ""))
        return

    _render_findings(ctx, finding_list)

    if len(finding_list) == limit:
        get_console(ctx).print(f"\nShowing first {limit}. Use --limit to see more.", style="dim")


@findings.command("get")
@click.argument("finding_id")
@click.pass_context
def get_finding(ctx, finding_id):
    """Show details for a single finding."""
    structured = is_structured(ctx)
    client = _client_or_exit(ctx)

    try:
        finding = client.get_finding(finding_id)
    except APIError as e:
        if structured:
            print_structured(ctx, {"error": str(e)})
        else:
            click.echo(f"✗ {e}", err=True)
        raise SystemExit(EXIT_GENERAL)

    if structured:
        print_structured(ctx, finding)
        return

    console = get_console(ctx)
    file_path = finding.get("file_path") or finding.get("filePath") or finding.get("path") or ""
    line = finding.get("line") or finding.get("line_number") or finding.get("lineNumber") or ""
    console.print(Panel(
        f"ID:       [dim]{finding.get('id', finding_id)}[/dim]\n"
        f"Severity: {_severity_display(finding.get('severity', ''))}\n"
        f"Category: [cyan]{finding.get('category', '')}[/cyan]\n"
        f"File:     {file_path}:{line}\n"
        f"Status:   {finding.get('status', '')}\n"
        f"Message:  {finding.get('message') or finding.get('description') or ''}",
        title="Finding",
        expand=False,
    ))


@findings.command("fix")
@click.argument("finding_id")
@click.pass_context
def fix_finding(ctx, finding_id):
    """Mark a finding as fixed."""
    _transition(ctx, finding_id, "fix")


@findings.command("ignore")
@click.argument("finding_id")
@click.pass_context
def ignore_finding(ctx, finding_id):
    """Mark a finding as ignored."""
    _transition(ctx, finding_id, "ignore")


def _transition(ctx, finding_id, action):
    structured = is_structured(ctx)
    client = _client_or_exit(ctx)

    try:
        result = client.fix_finding(finding_id) if action == "fix" else client.ignore_finding(finding_id)
    except APIError as e:
        if structured:
            print_structured(ctx, {"error": str(e)})
        else:
            click.echo(f"✗ {e}", err=True)
        raise SystemExit(EXIT_GENERAL)

    if structured:
        print_structured(ctx, result)
    else:
        verb = "fixed" if action == "fix" else "ignored"
        click.echo(f"✓ Marked finding {finding_id} as {verb}")
