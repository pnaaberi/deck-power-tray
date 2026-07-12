#!/usr/bin/env sh
set -eu

APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

case "${XDG_CONFIG_HOME:-}" in
  /*) CONFIG_HOME=$XDG_CONFIG_HOME ;;
  *)
    : "${HOME:?HOME must be set when XDG_CONFIG_HOME is unset or relative}"
    CONFIG_HOME="$HOME/.config"
    ;;
esac

case "${XDG_DATA_HOME:-}" in
  /*) DATA_HOME=$XDG_DATA_HOME ;;
  *)
    : "${HOME:?HOME must be set when XDG_DATA_HOME is unset or relative}"
    DATA_HOME="$HOME/.local/share"
    ;;
esac

AUTOSTART_DIR="$CONFIG_HOME/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/deck-power-tray.desktop"
APPLICATIONS_DIR="$DATA_HOME/applications"
APP_DESKTOP_FILE="$APPLICATIONS_DIR/deck-power-tray.desktop"

if ! python3 - <<'PY'
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
import cairo
import dbus
PY
then
  echo "Missing dependency: python GTK/cairo/dbus bindings." >&2
  echo "On SteamOS these usually come from python-gobject, python-cairo, and python-dbus." >&2
  exit 1
fi

chmod +x "$APP_DIR/deck-power-tray"
mkdir -p "$AUTOSTART_DIR" "$APPLICATIONS_DIR"

autostart_tmp=""
application_tmp=""
cleanup() {
  if [ -n "$autostart_tmp" ]; then
    rm -f -- "$autostart_tmp"
  fi
  if [ -n "$application_tmp" ]; then
    rm -f -- "$application_tmp"
  fi
}
trap cleanup 0
trap 'exit 1' HUP INT TERM

autostart_tmp=$(mktemp "${AUTOSTART_DIR}/.deck-power-tray.tmp.XXXXXX.desktop")
application_tmp=$(mktemp "${APPLICATIONS_DIR}/.deck-power-tray.tmp.XXXXXX.desktop")

(
  cd "$APP_DIR"
  python3 - autostart <<'PY'
import sys

from deck_power_tray.app import desktop_entry

print(desktop_entry(show_on_start=sys.argv[1] == "application"), end="")
PY
) > "$autostart_tmp"

(
  cd "$APP_DIR"
  python3 - application <<'PY'
import sys

from deck_power_tray.app import desktop_entry

print(desktop_entry(show_on_start=sys.argv[1] == "application"), end="")
PY
) > "$application_tmp"

chmod 0644 "$autostart_tmp" "$application_tmp"
if command -v desktop-file-validate >/dev/null 2>&1; then
  desktop-file-validate "$autostart_tmp" "$application_tmp"
fi
mv -f -- "$application_tmp" "$APP_DESKTOP_FILE"
application_tmp=""
mv -f -- "$autostart_tmp" "$DESKTOP_FILE"
autostart_tmp=""
trap - HUP INT TERM
trap - 0

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
fi
if command -v systemctl >/dev/null 2>&1; then
  systemctl --user daemon-reload >/dev/null 2>&1 || true
fi

echo "Installed autostart entry: $DESKTOP_FILE"
echo "Installed application entry: $APP_DESKTOP_FILE"
echo "Run now with: $APP_DIR/deck-power-tray"
