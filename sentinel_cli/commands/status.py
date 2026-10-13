"""sentinel status — show account and recent scan activity."""

import click
from rich.panel import Panel
from rich.table import Table
from sentinel_cli.api import SentinelClient, AuthError, APIError
from sentinel_cli.output import get_console, is_json, print_json
from sentinel_cli.exit_codes import EXIT_AUTH


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


@click.command()
@click.pass_context
def status(ctx):
    """Show your Sentinel account and recent scan activity."""
    try:
        client = SentinelClient()
    except AuthError as e:
        click.echo(f"✗ {e}", err=True)
        raise SystemExit(EXIT_AUTH)

    profile = None
    try:
        profile = client.get_profile()
    except APIError:
        profile = None

    scans = client.recent_scans()

    if is_json(ctx):
        print_json({
            "account": profile,
            "recent_scans": scans[:5] if scans else [],
        })
        return

    console = get_console(ctx)

    if profile:
        email = profile.get("email", "")
        name = profile.get("name") or email or "Sentinel user"
        console.print(Panel(
            f"Account: [bold]{name}[/bold]\n"
            f"Email:   [cyan]{email}[/cyan]\n"
            f"API URL: [dim]{client.api_url}[/dim]",
            title="Sentinel",
            expand=False,
        ))
    else:
        console.print(Panel(
            f"API URL: [dim]{client.api_url}[/dim]\n"
            f"Account: [dim](profile unavailable)[/dim]",
            title="Sentinel",
            expand=False,
        ))

    click.echo()
    if scans:
        click.echo("Recent scans:")
        table = Table(show_edge=False, pad_edge=False, box=None, padding=(0, 1, 0, 1))
        table.add_column("Status", min_width=14)
        table.add_column("Findings", justify="right", style="bold")
        table.add_column("Target")
        table.add_column("ID", style="dim")

        for s in scans[:5]:
            st = _status_display(s.get("status", "unknown"))
            findings_count = (
                s.get("findings_count")
                or s.get("total_findings")
                or s.get("findingsCount")
            )
            fc_str = str(findings_count) if findings_count is not None else "-"
            target = (
                s.get("project_path")
                or s.get("target")
                or s.get("path")
                or ""
            )[:48]
            table.add_row(st, fc_str, target, s.get("id", ""))

        console.print(table)
    else:
        click.echo("No scans yet. Start one from the Sentinel app or desktop client.")
