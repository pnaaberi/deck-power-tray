# Security Policy

## Supported Versions

Security fixes are made on the latest released version. Older versions are not maintained separately.

## Reporting A Vulnerability

Use the repository's **Security** tab to report a vulnerability privately. If private reporting is not yet enabled, contact the maintainer through the [pnaaberi GitHub profile](https://github.com/pnaaberi) before sharing sensitive details. Do not put secrets, private paths, or working exploit details in a public issue.

Include the affected version, trigger, impact, and a minimal reproduction. Reports about installer path handling, local file writes, DBus trust boundaries, or data exposure are in scope.

## Data And Network Scope

Deck Power Tray reads local Linux power-supply data and communicates with the user's KDE session over DBus. It does not require elevated privileges, make network requests, collect telemetry, or persist battery samples.
