#!/usr/bin/env sh
set -eu

APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
AUTOSTART_DIR="${XDG_CONFIG_HOME:-"$HOME/.config"}/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/deck-power-tray.desktop"
APPLICATIONS_DIR="${XDG_DATA_HOME:-"$HOME/.local/share"}/applications"
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
tmp=$(mktemp "${APP_DESKTOP_FILE}.tmp.XXXXXX")
cat > "$tmp" <<EOF
[Desktop Entry]
Type=Application
Name=Deck Power Tray
Comment=Show Steam Deck battery watts in the system tray
Exec=$APP_DIR/deck-power-tray
Icon=$APP_DIR/icons/deck-power-tray.svg
Terminal=false
StartupWMClass=deck-power-tray
X-GNOME-Autostart-enabled=true
EOF
cp "$tmp" "$DESKTOP_FILE"
mv "$tmp" "$APP_DESKTOP_FILE"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
fi

echo "Installed autostart entry: $DESKTOP_FILE"
echo "Installed application entry: $APP_DESKTOP_FILE"
echo "Run now with: $APP_DIR/deck-power-tray"
