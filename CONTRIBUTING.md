# Contributing

Contributions should stay small and match the app's Steam Deck and KDE focus.

## Setup

Use Python 3.10 or newer with GTK 3, Cairo, and D-Bus bindings. SteamOS normally provides these dependencies.

Run the app from the repository:

```sh
./deck-power-tray --show
```

## Checks

Run all checks before opening a pull request:

```sh
python3 tests.py -v
python3 -m py_compile deck_power_tray/app.py tests.py
sh -n deck-power-tray install.sh uninstall.sh
git diff --check
```

Behavior changes need focused regression tests. Installer and autostart changes also need temporary-directory checks for:

- A source path containing spaces, UTF-8 characters, and supported desktop-entry escape characters
- Absolute custom `XDG_CONFIG_HOME` and `XDG_DATA_HOME`
- An unset `HOME` when both XDG paths are set
- Reinstall over existing entries
- Missing dependencies and generation failure
- Cleanup without partial desktop entries or stale temporary files

Runtime changes should cover initial failure, recovery, duplicate launches, and KDE watcher loss when relevant.

## Pull Requests

- Explain the user-visible problem and the failure path.
- Keep unrelated refactors out of the change.
- Update README and CHANGELOG when behavior or installation changes.
- Include the checks that were run and any path that could not be tested.
- Do not include personal battery history, logs with private paths, or full-desktop screenshots.
