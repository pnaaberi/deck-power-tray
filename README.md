# Deck Power Tray

Small Steam Deck tray app that shows current battery charge power as watts in the KDE system tray.

Click the tray item to open a live graph for watts, volts, and amps. Right click for the menu.

## Run

```sh
./deck-power-tray
```

## Install autostart

```sh
./install.sh
```

The installer writes one desktop file to:

```text
${XDG_CONFIG_HOME:-$HOME/.config}/autostart/deck-power-tray.desktop
```

## Uninstall

```sh
./uninstall.sh
```

## Notes

The app reads Linux battery data from `/sys/class/power_supply`. It uses `power_now` when available, otherwise it calculates watts from `voltage_now * current_now`.
