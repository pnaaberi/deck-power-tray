# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases use [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.1] - 2026-07-12

### Fixed

- Autostart status detection now handles source paths containing desktop-entry escape characters

## [0.1.0] - 2026-07-12

### Added

- Live tray watt readout and ten-minute watts, volts, and amps graph
- Battery, AC, charge-state, and capacity details
- KDE StatusNotifierItem integration with registration recovery
- Single-instance activation, `--show`, `--quit`, `--help`, and `--version`
- XDG autostart and application launcher installation
- Automated regression tests and GitHub Actions checks

### Fixed

- Desktop entries now work when the source path contains spaces or reserved shell characters
- Incomplete battery reads now display a recoverable error instead of false zero values
- Error icon changes are signaled to the tray and recover correctly
- Duplicate launches reuse the running process
- Installer files are staged, validated, mode-stable, and cleaned after failure
- Removed the predictable temporary PNG write

[Unreleased]: https://github.com/pnaaberi/deck-power-tray/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/pnaaberi/deck-power-tray/releases/tag/v0.1.1
[0.1.0]: https://github.com/pnaaberi/deck-power-tray/releases/tag/v0.1.0
