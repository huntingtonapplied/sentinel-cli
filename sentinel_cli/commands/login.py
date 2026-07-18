"""sentinel login — authenticate and store API key."""

import click
from rich.panel import Panel
from sentinel_cli.config import save_config, load_config, get_api_url
from sentinel_cli.api import SentinelClient
from sentinel_cli.output import get_console
from sentinel_cli.exit_codes import EXIT_VALIDATION


@click.command()
@click.option("--key", default=None, help="Your Sentinel API key (skips wizard)")
@click.option("--url", default=None, help="API URL (default: http://localhost:8017)")
@click.pass_context
def login(ctx, key: str, url: str):
    """Authenticate with the Sentinel platform.

    \b
    Examples:
        sentinel login                    # interactive wizard
        sentinel login --key dsk_abc123   # non-interactive
    """
    console = get_console(ctx)
    ci_mode = ctx.obj.get("ci", False) if ctx.obj else False

    if not key and ci_mode:
        click.echo("✗ --key is required in CI mode: sentinel login --key <key>", err=True)
        raise SystemExit(EXIT_VALIDATION)

    if not key:
        # Interactive wizard
        click.echo()
        click.echo("  Welcome to Sentinel!")
        click.echo()
        click.echo("  To get your API key:")
        click.echo("    1. Go to your Sentinel instance /account")
        click.echo("    2. Open the Developer / API Keys tab")
        click.echo("    3. Create a key and copy it (starts with dsk_)")
        click.echo()
        key = click.prompt("  API Key", hide_input=True)
        if not url:
            use_custom = click.confirm("  Use a custom API URL?", default=False)
            if use_custom:
                url = click.prompt("  API URL", default="http://localhost:8017")

    key = key.strip()
    config = load_config()
    config["api_key"] = key
    if url:
        config["api_url"] = url.strip()
    save_config(config)

    api_url = url or get_api_url()
    click.echo("✓ API key saved to ~/.sentinel/config.yaml")
    click.echo(f"  API URL: {api_url}")

    # Verify the key works
    try:
        client = SentinelClient(api_key=key, api_url=api_url)
        scan_list = client.recent_scans()
        console.print(Panel(
            f"✓ Authenticated — {len(scan_list)} recent scan(s) found\n\n"
            "  [dim]sentinel scans[/dim]       list your scans\n"
            "  [dim]sentinel findings[/dim]    view corruption findings\n"
            "  [dim]sentinel reports[/dim]     generate and download reports",
            title="Connected",
            border_style="green",
            expand=False,
        ))
    except Exception as e:
        click.echo(f"⚠ Key saved but verification failed: {e}", err=True)
        click.echo("  Check your key and try again: sentinel login", err=True)
