#!/usr/bin/env sh
set -eu

AUTOSTART_DIR="${XDG_CONFIG_HOME:-"$HOME/.config"}/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/deck-power-tray.desktop"
APPLICATIONS_DIR="${XDG_DATA_HOME:-"$HOME/.local/share"}/applications"
APP_DESKTOP_FILE="$APPLICATIONS_DIR/deck-power-tray.desktop"

if [ -f "$DESKTOP_FILE" ]; then
  rm "$DESKTOP_FILE"
  echo "Removed $DESKTOP_FILE"
else
  echo "No autostart entry found at $DESKTOP_FILE"
fi

if [ -f "$APP_DESKTOP_FILE" ]; then
  rm "$APP_DESKTOP_FILE"
  echo "Removed $APP_DESKTOP_FILE"
else
  echo "No application entry found at $APP_DESKTOP_FILE"
fi
