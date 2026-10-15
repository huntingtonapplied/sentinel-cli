# Changelog

All notable changes to the Sentinel CLI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Pre-1.0 policy:** Minor versions (0.x) may include breaking changes.

## [Unreleased]

## [0.1.6] - 2026-10-14

### Fixed
- The update check no longer queries PyPI. `sentinel-cli` is not published there and the PyPI name may belong to an unrelated project, so the old check could report a stranger's version and suggest installing it. It now reads the latest GitHub release of huntingtonapplied/sentinel-cli and suggests `pip install --upgrade git+https://github.com/huntingtonapplied/sentinel-cli`, only when that release is newer.

## [0.1.5] - 2026-10-14

### Changed
- `scan` against the hosted API now refuses with "Hosted scans of local code aren't supported yet. Use the desktop app or a local backend" (exit 4) instead of submitting a path the hosted service cannot read. README and `scan --help` say the same. (SENTINEL-HOSTED-SCAN)
- `scan` no longer sends the client's absolute local path to a remote API; the hosted API receives only the directory name. A local backend (`localhost`) still gets the absolute path. (R-sentinel-cli-scan-upload-1)

## [0.1.4] - 2026-10-13

### Changed
- README: version badge and release-history reference match the shipped release.

## [0.1.3] - 2026-10-13

### Changed
- README: describes the hosted API only and states plainly that `sentinel scan` does not upload local files yet.

## [0.1.2] - 2026-10-13

### Changed
- README: version badge and default API URL now match the shipped release; removed links to files that are not part of this repository.

## [0.1.0] - 2026-07-18

### Added
- Initial public release — a thin client for the hosted Sentinel API.
- Commands: `login`, `status`, `doctor`, `metrics`, `completion`, `scan`,
  `scans`, `findings`, `reports`.
- `install.sh` for binary download + install.
