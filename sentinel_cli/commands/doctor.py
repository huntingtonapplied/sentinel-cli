"""sentinel doctor — check CLI setup and diagnose issues."""

import os
import sys

import click
import httpx

from sentinel_cli import __version__
from sentinel_cli.config import CONFIG_FILE, load_config, validate_config, get_api_key, get_api_url
from sentinel_cli.output import is_json, print_json
from sentinel_cli.log import logger


def _check(label: str, ok: bool, detail: str = "", json_mode: bool = False) -> dict:
    """Print a check result and return it as a dict."""
    result = {"check": label, "ok": ok}
    if detail:
        result["detail"] = detail
    if not json_mode:
        icon = "✓" if ok else "✗"
        msg = f"  {icon} {label}"
        if detail:
            msg += f"  ({detail})"
        click.echo(msg, err=not ok)
    return result


@click.command()
@click.pass_context
def doctor(ctx):
    """Check your Sentinel CLI setup and diagnose issues."""
    json_mode = is_json(ctx)
    results = []

    if not json_mode:
        click.echo(f"Sentinel CLI v{__version__}")
        click.echo()

    # 1. Python version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 9)
    results.append(_check("Python >= 3.9", py_ok, py_ver, json_mode))

    # 2. Config file exists
    config_exists = CONFIG_FILE.exists()
    results.append(_check("Config file exists", config_exists, str(CONFIG_FILE), json_mode))

    # 3. Config is valid
    config = load_config()
    config_warnings = validate_config(config) if config else []
    config_valid = len(config_warnings) == 0
    detail = "; ".join(config_warnings) if config_warnings else "ok"
    results.append(_check("Config is valid", config_valid, detail, json_mode))

    # 4. API key configured
    api_key = get_api_key()
    has_key = api_key is not None
    source = "env var" if os.getenv("SENTINEL_API_KEY") else ("config file" if has_key else "not set")
    results.append(_check("API key configured", has_key, source, json_mode))

    # 5. API key format
    key_format_ok = bool(api_key and api_key.startswith("dsk_")) if has_key else False
    fmt_detail = "ok" if key_format_ok else ("missing dsk_ prefix" if has_key else "not set")
    results.append(_check("API key format (dsk_)", key_format_ok, fmt_detail, json_mode))

    # 6. API reachable
    api_url = get_api_url()
    api_reachable = False
    try:
        resp = httpx.get(f"{api_url}/health", timeout=5.0)
        api_reachable = resp.status_code < 500
    except Exception as e:
        logger.debug("API health check failed: %s", e)
    results.append(_check("API reachable", api_reachable, api_url, json_mode))

    # 7. API key valid
    key_valid = False
    if has_key and api_reachable:
        try:
            from sentinel_cli.api import SentinelClient
            client = SentinelClient(api_key=api_key, api_url=api_url)
            client.recent_scans()
            key_valid = True
        except Exception as e:
            logger.debug("API key validation failed: %s", e)
    results.append(_check(
        "API key valid", key_valid,
        "" if not has_key else ("verified" if key_valid else "invalid or expired"),
        json_mode,
    ))

    # 8. Shell completion installed
    shell = os.environ.get("SHELL", "")
    completion_installed = False
    marker = "# sentinel shell completion"
    if "zsh" in shell:
        rc = os.path.expanduser("~/.zshrc")
        if os.path.isfile(rc):
            with open(rc) as f:
                completion_installed = marker in f.read()
    elif "bash" in shell:
        rc = os.path.expanduser("~/.bashrc")
        if os.path.isfile(rc):
            with open(rc) as f:
                completion_installed = marker in f.read()
    results.append(_check(
        "Shell completion installed", completion_installed,
        "run: sentinel completion --install" if not completion_installed else "ok",
        json_mode,
    ))

    if json_mode:
        print_json({"version": __version__, "checks": results})
        return

    # Summary
    click.echo()
    passed = sum(1 for r in results if r["ok"])
    total = len(results)
    if passed == total:
        click.echo(f"All {total} checks passed.")
    else:
        click.echo(f"{passed}/{total} checks passed.")
