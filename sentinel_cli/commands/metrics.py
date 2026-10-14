"""sentinel metrics — show dashboard analytics and corruption metrics."""

import click
from rich.table import Table
from sentinel_cli.api import SentinelClient, AuthError, APIError
from sentinel_cli.output import get_console, is_structured, print_structured
from sentinel_cli.exit_codes import EXIT_AUTH, EXIT_GENERAL


@click.command()
@click.option("--days", "-d", type=int, default=None,
              help="Window for the dashboard metrics (7-365 days)")
@click.pass_context
def metrics(ctx, days):
    """Show dashboard analytics: findings, fixes, severity breakdown.

    \b
    Examples:
        sentinel metrics                # current dashboard
        sentinel metrics --days 30      # last 30 days
        sentinel -o json metrics        # machine-readable
    """
    structured = is_structured(ctx)

    try:
        client = SentinelClient()
    except AuthError as e:
        if structured:
            print_structured(ctx, {"error": str(e)})
        else:
            click.echo(f"✗ {e}", err=True)
        raise SystemExit(EXIT_AUTH)

    params = {}
    if days is not None:
        params["days"] = days

    try:
        dashboard = client.dashboard(params=params or None)
        severity = client.severity_distribution()
    except APIError as e:
        if structured:
            print_structured(ctx, {"error": str(e)})
        else:
            click.echo(f"✗ {e}", err=True)
        raise SystemExit(EXIT_GENERAL)

    if structured:
        print_structured(ctx, {"dashboard": dashboard, "severity": severity})
        return

    console = get_console(ctx)

    table = Table(show_edge=False, pad_edge=False, box=None)
    table.add_column("Metric", style="cyan", min_width=24)
    table.add_column("Value", justify="right", style="bold")

    if isinstance(dashboard, dict):
        for key, value in dashboard.items():
            if isinstance(value, (dict, list)):
                continue
            label = key.replace("_", " ").title()
            table.add_row(label, str(value))

    console.print(table)

    if isinstance(severity, dict) and severity:
        click.echo()
        click.echo("Severity distribution:")
        sev_table = Table(show_edge=False, pad_edge=False, box=None)
        sev_table.add_column("Severity", min_width=12)
        sev_table.add_column("Count", justify="right", style="bold")
        for key in ("critical", "warning", "info"):
            if key in severity:
                sev_table.add_row(key.title(), str(severity[key]))
        # include any other keys not covered above
        for key, value in severity.items():
            if key not in ("critical", "warning", "info") and not isinstance(value, (dict, list)):
                sev_table.add_row(key.title(), str(value))
        console.print(sev_table)
