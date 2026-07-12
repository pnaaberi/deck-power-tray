# Deck Power Tray

![Deck Power Tray icon](icons/deck-power-tray.svg)

Deck Power Tray shows live Steam Deck battery watts in the KDE Plasma system tray. Click the tray item to open a ten-minute graph for watts, volts, and amps.

## Features

- Live watt readout in the tray, updated every two seconds
- Voltage, current, battery percentage, charge state, and AC state in the tooltip and graph window
- Ten minutes of in-memory history with discharge periods highlighted
- One running instance, even when the launcher is opened more than once
- Optional desktop-session autostart
- Automatic recovery after temporary battery or KDE tray failures
- No network access, telemetry, or persistent power history

## Requirements

- Steam Deck in Desktop Mode, or a compatible Linux system with battery data under `/sys/class/power_supply`
- KDE Plasma with StatusNotifierItem support
- Python 3.10 or newer
- Python GTK 3, Cairo, and D-Bus bindings

SteamOS normally includes the required Python bindings. On Arch-based systems the packages are commonly named `python-gobject`, `python-cairo`, and `python-dbus`. Package names differ on other distributions.

## Quick Start

```sh
git clone https://github.com/pnaaberi/deck-power-tray.git
cd deck-power-tray
./deck-power-tray --show
```

Close the graph window to hide it. The tray process keeps running.

## Install

Run the installer from the checked-out source directory:

```sh
./install.sh
```

The application continues to run from that source directory. Do not move or delete the checkout after installation. If it is moved, run `./install.sh` again from the new location.

The installer writes these files:

```text
${XDG_CONFIG_HOME:-$HOME/.config}/autostart/deck-power-tray.desktop
${XDG_DATA_HOME:-$HOME/.local/share}/applications/deck-power-tray.desktop
```

XDG paths are used only when they are absolute. Empty or relative XDG values fall back to the matching directory under `$HOME`.

The application launcher opens the graph. The autostart entry starts it hidden in the tray. Both files are replaced atomically and use mode `0644`.

The **Start with system** checkbox only controls the autostart entry. It does not remove the application launcher.

## Usage

| Action | Result |
| --- | --- |
| Click or right-click the tray item | Toggle or show the graph window |
| Close the graph window | Hide the window and keep the tray process running |
| Enable **Start with system** | Create the autostart entry |
| Disable **Start with system** | Remove the autostart entry |

Tray status colors:

- Green: AC power is connected
- Orange: running from battery
- Blue: the kernel reports the battery as full
- Red `ERR`: required battery data is temporarily unavailable or invalid

## Command Line

```text
deck-power-tray [--show | --quit | --version]
```

- No option: start hidden, or exit successfully if an instance is already running.
- `--show`: start and show the graph, or show the existing instance.
- `--quit`: stop the existing instance.
- `--version`: print the application version.
- `--help`: print command usage.

## Uninstall

Run:

```sh
./uninstall.sh
```

The uninstaller stops the running app and removes both desktop entries. It does not delete the source directory or any unrelated files.

## Troubleshooting

Check the user service and recent log messages:

```sh
systemctl --user status 'app-deck\x2dpower\x2dtray@autostart.service'
journalctl --user -u 'app-deck\x2dpower\x2dtray@autostart.service' -n 50 --no-pager
```

Restart it after updating the source:

```sh
systemctl --user restart 'app-deck\x2dpower\x2dtray@autostart.service'
```

If the tray displays `ERR`, hover over it for the specific missing or invalid battery field. The app keeps polling and recovers without a restart when valid data returns.

If the tray item is absent but the process is running, restart KDE's tray service or log out and back in. Deck Power Tray retries StatusNotifierItem registration every five seconds.

Paths containing spaces and common shell metacharacters are supported. `%` and `=` are not supported in the source path because they conflict with desktop-entry command parsing.

## Privacy And State

Deck Power Tray reads local kernel power-supply files. It makes no network requests and has no telemetry. The graph keeps at most ten minutes of samples in memory and writes no power history to disk.

Persistent state is limited to the two desktop entries listed under [Install](#install). KDE and systemd may keep their normal service logs and generated user units.

## Development

Run the test and syntax checks:

```sh
python3 tests.py -v
python3 -m py_compile deck_power_tray/app.py tests.py
sh -n deck-power-tray install.sh uninstall.sh
git diff --check
```

The test suite uses temporary power-supply trees and temporary XDG directories. Do not point tests at writable copies of real system battery data.

Repository layout:

```text
deck_power_tray/app.py  Application, battery reader, graph, tray, and autostart logic
deck-power-tray         Portable launcher
install.sh              Dependency check and desktop-entry installer
uninstall.sh            Process stop and desktop-entry removal
tests.py                 Unit and regression tests
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for changes and [RELEASING.md](RELEASING.md) for the release checklist.

## Known Limits

- Only the first detected battery and AC-style power source are used.
- The graph uses a fixed 0-50 scale for watts, volts, and amps.
- The tray integration targets KDE Plasma. Other desktop environments are not tested.
- Samples exist only for the lifetime of the process.

## License

Deck Power Tray is available under the [MIT License](LICENSE).
