# Releasing

## Preflight

1. Confirm `APP_VERSION` in `deck_power_tray/app.py` matches the intended tag.
2. Move relevant entries from `Unreleased` into a dated CHANGELOG section.
3. Confirm README install, uninstall, troubleshooting, and privacy details match the current code.
4. Confirm the repository contains no secrets, private logs, generated screenshots, or user-specific state.

## Verify

Run:

```sh
python3 tests.py -v
python3 -m py_compile deck_power_tray/app.py tests.py
sh -n deck-power-tray install.sh uninstall.sh
git diff --check
```

Also verify on a Steam Deck in Desktop Mode:

1. Install from a path containing spaces, dollar signs, double quotes, backticks, and a literal backslash.
2. Reinstall over the existing desktop entries.
3. Start from autostart and from the application launcher.
4. Confirm repeated launches keep one tray process and one tray item.
5. Confirm charging, fully charged, and battery operation update the tray and graph.
6. Confirm `--quit` and `uninstall.sh` stop the process.
7. Confirm a temporary missing battery field displays `ERR` and recovers.

## Publish

1. Commit the release changes with a clean working tree.
2. Create an annotated tag: `git tag -a vX.Y.Z -m "Deck Power Tray X.Y.Z"`. Use `-s` instead of `-a` when a Git signing key is configured.
3. Push the branch and tag.
4. Confirm the GitHub Actions workflow passes on the tag.
5. Create a GitHub release from the matching CHANGELOG section.
6. Download the public tag archive and repeat the automated and installer checks from the extracted source.
7. Confirm the release is marked latest, the repository license is detected as MIT, and the public README renders correctly.

## First Public Release

For the first public release only:

1. Keep the repository private until the preflight and verification checks are complete.
2. Check commit and tag metadata for private names, email addresses, logs, and generated state.
3. Change repository visibility to public only after branch and tag checks pass.
4. Enable private vulnerability reporting in **Settings > Security > Code security**.
