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

"$APP_DIR/deck-power-tray" --quit >/dev/null 2>&1 || true
if command -v systemctl >/dev/null 2>&1; then
  systemctl --user stop 'app-deck\x2dpower\x2dtray@autostart.service' >/dev/null 2>&1 || true
fi

if [ -f "$DESKTOP_FILE" ] || [ -L "$DESKTOP_FILE" ]; then
  rm -- "$DESKTOP_FILE"
  echo "Removed $DESKTOP_FILE"
else
  echo "No autostart entry found at $DESKTOP_FILE"
fi

if [ -f "$APP_DESKTOP_FILE" ] || [ -L "$APP_DESKTOP_FILE" ]; then
  rm -- "$APP_DESKTOP_FILE"
  echo "Removed $APP_DESKTOP_FILE"
else
  echo "No application entry found at $APP_DESKTOP_FILE"
fi

if command -v systemctl >/dev/null 2>&1; then
  systemctl --user daemon-reload >/dev/null 2>&1 || true
fi
