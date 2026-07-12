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

1. Install from a path containing a space.
2. Reinstall over the existing desktop entries.
3. Start from autostart and from the application launcher.
4. Confirm repeated launches keep one tray process and one tray item.
5. Confirm charging, fully charged, and battery operation update the tray and graph.
6. Confirm `--quit` and `uninstall.sh` stop the process.
7. Confirm a temporary missing battery field displays `ERR` and recovers.

## Publish

1. Commit the release changes with a clean working tree.
2. Create an annotated tag: `git tag -a v0.1.0 -m "Deck Power Tray 0.1.0"`. Use `-s` instead of `-a` when a Git signing key is configured.
3. Push the branch and tag while the repository is still private.
4. Confirm the GitHub Actions workflow passes on the tag.
5. Change repository visibility to public.
6. Enable private vulnerability reporting in **Settings > Security > Code security**.
7. Create a GitHub release from the matching CHANGELOG section.
8. Confirm the repository license is detected as MIT and the public README renders correctly.

Do not make the repository public until the preflight and verification checks are complete.
