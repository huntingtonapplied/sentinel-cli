"""sentinel reports — generate, list, and download reports."""

import os

import click
from rich.table import Table
from sentinel_cli.api import SentinelClient, AuthError, APIError
from sentinel_cli.output import get_console, is_structured, print_structured
from sentinel_cli.exit_codes import EXIT_AUTH, EXIT_GENERAL


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
@click.option("--type", "report_type", default=None, help="Filter by report type")
@click.option("--quiet", "-q", is_flag=True, help="Print only report IDs")
@click.pass_context
def reports(ctx, limit, report_type, quiet):
    """List reports (default), or use a subcommand.

    \b
    Examples:
        sentinel reports                          # list reports
        sentinel reports create --scan <id>       # generate a report
        sentinel reports get <id>                 # report detail
        sentinel reports download <id> -o out.html
    """
    if ctx.invoked_subcommand is not None:
        return

    structured = is_structured(ctx)
    client = _client_or_exit(ctx)

    params = {}
    if limit != 20:
        params["limit"] = limit
    if report_type:
        params["report_type"] = report_type

    try:
        report_list = client.list_reports(params=params or None)
    except APIError as e:
        if structured:
            print_structured(ctx, {"error": str(e)})
        else:
            click.echo(f"✗ {e}", err=True)
        raise SystemExit(EXIT_GENERAL)

    if structured:
        print_structured(ctx, report_list)
        return

    if not report_list:
        click.echo("No reports found.")
        return

    if quiet:
        for r in report_list:
            click.echo(r.get("id", ""))
        return

    console = get_console(ctx)
    table = Table(show_edge=False, pad_edge=False, box=None)
    table.add_column("Type", style="cyan", min_width=16)
    table.add_column("Status", min_width=12)
    table.add_column("Created", style="dim")
    table.add_column("ID", style="dim")

    for r in report_list:
        rtype = r.get("report_type") or r.get("type") or r.get("template") or "report"
        rstatus = r.get("status", "")
        created = r.get("created_at") or r.get("createdAt") or ""
        table.add_row(str(rtype), str(rstatus), str(created), r.get("id", ""))

    console.print(table)


@reports.command("get")
@click.argument("report_id")
@click.pass_context
def get_report(ctx, report_id):
    """Show details for a single report."""
    structured = is_structured(ctx)
    client = _client_or_exit(ctx)

    try:
        report = client.get_report(report_id)
    except APIError as e:
        if structured:
            print_structured(ctx, {"error": str(e)})
        else:
            click.echo(f"✗ {e}", err=True)
        raise SystemExit(EXIT_GENERAL)

    if structured:
        print_structured(ctx, report)
        return

    console = get_console(ctx)
    table = Table(show_edge=False, pad_edge=False, box=None)
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    for key, value in report.items():
        if not isinstance(value, (dict, list)):
            table.add_row(key.replace("_", " ").title(), str(value))
    console.print(table)


@reports.command("create")
@click.option("--scan", "scan_id", default=None, help="Scan ID to report on")
@click.option("--type", "report_type", default="scan-summary", show_default=True,
              help="Report type (e.g. scan-summary, trend-analysis, pattern-report)")
@click.option("--template", default=None, help="Optional report template name")
@click.pass_context
def create_report(ctx, scan_id, report_type, template):
    """Generate a new report."""
    structured = is_structured(ctx)
    client = _client_or_exit(ctx)

    payload = {"report_type": report_type}
    if scan_id:
        payload["scan_id"] = scan_id
    if template:
        payload["template"] = template

    try:
        result = client.create_report(payload)
    except APIError as e:
        if structured:
            print_structured(ctx, {"error": str(e)})
        else:
            click.echo(f"✗ {e}", err=True)
        raise SystemExit(EXIT_GENERAL)

    if structured:
        print_structured(ctx, result)
        return

    rid = result.get("id", "")
    click.echo(f"✓ Created report: {result.get('report_type', report_type)}")
    click.echo(f"  Report ID: {rid}")
    if rid:
        click.echo(f"  Download:  sentinel reports download {rid} -o report.html")


@reports.command("download")
@click.argument("report_id")
@click.option("--output", "-o", "out_path", default=None,
              help="Output file path (default: <report_id>.html)")
@click.pass_context
def download_report(ctx, report_id, out_path):
    """Download a report file."""
    client = _client_or_exit(ctx)

    try:
        content = client.download_report(report_id)
    except APIError as e:
        click.echo(f"✗ {e}", err=True)
        raise SystemExit(EXIT_GENERAL)

    dest = out_path or f"{report_id}.html"
    with open(dest, "wb") as f:
        f.write(content)
    click.echo(f"✓ Saved report to {os.path.abspath(dest)} ({len(content)} bytes)")


@reports.command("delete")
@click.argument("report_id")
@click.option("--yes", "-y", is_flag=True, default=False, help="Skip confirmation prompt")
@click.pass_context
def delete_report(ctx, report_id, yes):
    """Delete a report."""
    structured = is_structured(ctx)
    ci_mode = ctx.obj.get("ci", False) if ctx.obj else False
    if not structured and not (yes or ci_mode):
        click.confirm(f"Delete report {report_id}?", abort=True)

    client = _client_or_exit(ctx)
    try:
        client.delete_report(report_id)
    except APIError as e:
        if structured:
            print_structured(ctx, {"error": str(e)})
        else:
            click.echo(f"✗ {e}", err=True)
        raise SystemExit(EXIT_GENERAL)

    if structured:
        print_structured(ctx, {"deleted": report_id})
    else:
        click.echo(f"✓ Deleted report {report_id}")
