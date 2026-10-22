# Agent instructions — Deck Power Tray

- Read README.md, CONTRIBUTING.md and SECURITY.md before changes; follow
  RELEASING.md only for an explicitly authorized release.
- Keep changes small and focused on the Steam Deck/KDE battery tray application.
- Battery access is read-only. Do not add elevated permissions, network calls,
  telemetry or persistent battery history.
- Preserve the application identity, session-bus singleton, hidden startup,
  explicit show/quit behavior and ordinary tray activation semantics.
- Reuse existing GTK/native styles; do not introduce visual frameworks or
  unrelated design changes.
- Test with disposable power-supply and HOME/XDG fixtures. GUI and singleton
  checks must use a private D-Bus session and virtual display, never a live
  desktop singleton or autostart configuration.
- Run focused regressions, `python3 tests.py -v`, Python syntax checks,
  `sh -n deck-power-tray install.sh uninstall.sh`, and `git diff --check`.
- Update README.md and CHANGELOG.md when behavior changes. Keep generated QA,
  personal data, private logs and credentials outside versioned source.
- Do not install, change live autostart, publish, push or release without explicit
  authorization. Label source-only checks separately from Steam Deck acceptance.
