<div align="center">
  <img src=".readme/logo.png" alt="Sentinel CLI" width="360"><br><br>
</div>

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![Status](https://img.shields.io/badge/status-v0.1.2-informational.svg)](#)

-----------------

**Sentinel CLI** is the standalone product client for Sentinel — scan your codebases for corruption from the terminal, wired into CI/CD and pre-commit workflows.

This is a **thin API client** over the Sentinel REST backend (distinct from the engine's built-in `sentinel` CLI). It authenticates with an API key, submits scans that run server-side, and streams findings, fixes, and reports back to your terminal — so it fits cleanly into automation, CI gates, and bulk operations against a hosted or self-hosted backend.

## Install & authenticate

```bash
# Published binary (recommended)
curl -fsSL https://downloads.sentinelscanner.com/cli/install.sh | bash

# Or from source (a clone of this repo; the `sentinel-cli` name on PyPI is an unrelated project)
pip install -e .

# Authenticate (interactive, or pass the key directly)
sentinel login                      # or: sentinel login --key dsk_abc123
```

Get an API key (prefix `dsk_`) from the app under **Account → API Keys**. Config lives at `~/.sentinel/config.yaml`; override via env:

| Variable | Purpose | Default |
|----------|---------|---------|
| `SENTINEL_API_KEY` | API key | — |
| `SENTINEL_API_URL` | Backend base URL | `https://api.sentinelscanner.com` |
| `SENTINEL_TIMEOUT` | Request timeout | — |
| `SENTINEL_MAX_RETRIES` | Retry count | — |
| `SENTINEL_NO_UPDATE_CHECK` | Disable update check | — |

## Commands

| Command | Description |
|---------|-------------|
| `login` / `status` / `doctor` | Authenticate, show session, diagnose connectivity |
| `scan <path>` | Core verb — submits a scan (blocks to completion; exits **8** when findings present). Tune `--mode`, `--tier`, `--fail-on`, `--timeout` |
| `scans` | `list` / `get` / `findings` / `cancel` / `delete` |
| `findings` | `list` / `get` / `fix` / `ignore` |
| `reports` | `list` / `get` / `create` / `download` / `delete` |
| `metrics` / `completion` | Analytics; shell completion install |

Structured output via `-o json|yaml`. **Exit codes**: `0` ok · `2` auth · `3` not-found · `4` validation · `5` network · `6` server · `8` findings · `130` SIGINT · `143` SIGTERM.

```bash
sentinel scan ./src --fail-on high -o json > results.json
```

> `sentinel scan` runs **server-side** — the backend reads the path you pass, so point the CLI at a local/self-hosted backend (`SENTINEL_API_URL`) when scanning local code.

## Development

```bash
make install      # editable install into .venv
make test         # pytest
make build-binary # PyInstaller standalone binary -> dist/sentinel
make smoke        # build + run --help
```

## Documentation & resources

- Release history — [CHANGELOG](CHANGELOG.md) (CLI v0.1.2)
- Hosted product: [sentinelscanner.com](https://sentinelscanner.com) · binaries: `https://downloads.sentinelscanner.com`

## License

This project is licensed under the MIT License.
