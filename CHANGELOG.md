# Changelog

All notable changes to the Sentinel CLI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Pre-1.0 policy:** Minor versions (0.x) may include breaking changes.

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
