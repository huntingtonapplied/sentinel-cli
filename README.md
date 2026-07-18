# Sentinel CLI

Scan codebases for corruption from your terminal. This is the standalone **product client**
— a thin API client over the Sentinel REST backend (distinct from the engine's built-in CLI).

## Install & authenticate

```bash
# Published binary (recommended)
curl -fsSL https://downloads.sentinelscanner.com/sentinel/cli/install.sh | bash -s -- --version 0.1.0
# Or from source
cd ~/ahl/sentinel/cli && pip install -e .

sentinel login                    # interactive; or: sentinel login --key dsk_abc123
```

Uses an API key (prefix `dsk_`) from the app under **Account → API Keys**. Config lives at
`~/.sentinel/config.yaml`; override via `SENTINEL_API_KEY`, `SENTINEL_API_URL` (default
`http://localhost:8017`), `SENTINEL_TIMEOUT`, `SENTINEL_MAX_RETRIES`, `SENTINEL_NO_UPDATE_CHECK`.

## Commands (quick reference)

`login` · `status` · `doctor` · `metrics` · `completion` · `scan <path>` (core verb; blocks to
completion, exits **8** when findings present — tune `--mode`, `--tier`, `--fail-on`,
`--timeout`) · `scans` (list/get/findings/cancel/delete) · `findings`
(list/get/fix/ignore) · `reports` (list/get/create/download/delete). Structured output via
`-o json|yaml`. Exit codes: 0 ok · 2 auth · 3 not-found · 4 validation · 5 network · 6 server ·
8 findings · 130 SIGINT · 143 SIGTERM.

> `sentinel scan` runs **server-side**: the backend reads the path you pass, so point the CLI
> at a local/self-hosted backend when scanning local code.

## Canonical documentation

This README is a pointer. Full, versioned docs live in `../docs/`:

- **CLI User Guide** — [`../docs/CLI_USER_GUIDE.md`](../docs/CLI_USER_GUIDE.md).
- **CLI Command Reference** — [`../docs/CLI_COMMAND_REFERENCE.md`](../docs/CLI_COMMAND_REFERENCE.md).
- **Deployment Guide** (incl. CI/CD, pre-commit) — [`../docs/DEPLOYMENT_GUIDE.md`](../docs/DEPLOYMENT_GUIDE.md).
- Release history — [`../CHANGELOG.md`](../CHANGELOG.md) (CLI v0.1.0 entry). Documentation
  index — [`../docs/README.md`](../docs/README.md).

## Development

```bash
make install      # editable install into .venv
make test         # pytest
make build-binary # PyInstaller standalone binary -> dist/sentinel
make smoke        # build + run --help
```

MIT — see [LICENSE](./LICENSE).
