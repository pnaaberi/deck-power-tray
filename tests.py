#!/usr/bin/env python3
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import dbus
from gi.repository import Gio, GLib

from deck_power_tray.app import (
    APP_BUS,
    APP_VERSION,
    BatteryReadError,
    BatteryReader,
    StatusNotifierItem,
    TrayApp,
    autostart_file,
    autostart_enabled,
    desktop_entry,
    desktop_exec_arg,
    disable_autostart,
    enable_autostart,
    find_supplies,
    format_measurement,
    tray_icon_font_size,
    tray_icon_text,
    tray_icon_uses_colored_decimal_dot,
)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class BatteryReaderTests(unittest.TestCase):
    def test_reads_steam_deck_style_battery(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            bat = base / "BAT1"
            ac = base / "ACAD"
            write(bat / "type", "Battery\n")
            write(bat / "status", "Charging\n")
            write(bat / "capacity", "68\n")
            write(bat / "voltage_now", "8676000\n")
            write(bat / "current_now", "3786000\n")
            write(ac / "type", "Mains\n")
            write(ac / "online", "1\n")

            sample = BatteryReader(base).read()

            self.assertEqual(sample.status, "Charging")
            self.assertEqual(sample.capacity, 68)
            self.assertTrue(sample.ac_online)
            self.assertAlmostEqual(sample.volts, 8.676)
            self.assertAlmostEqual(sample.amps, 3.786)
            self.assertAlmostEqual(sample.watts, 32.849, places=2)

    def test_prefers_power_now_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            bat = base / "BAT0"
            write(bat / "type", "Battery\n")
            write(bat / "status", "Discharging\n")
            write(bat / "voltage_now", "8000000\n")
            write(bat / "current_now", "1000000\n")
            write(bat / "power_now", "4200000\n")

            sample = BatteryReader(base).read()

            self.assertAlmostEqual(sample.watts, 4.2)

    def test_accepts_power_now_without_voltage_or_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            bat = base / "BAT0"
            write(bat / "type", "Battery\n")
            write(bat / "status", "Discharging\n")
            write(bat / "power_now", "4200000\n")

            sample = BatteryReader(base).read()

            self.assertAlmostEqual(sample.watts, 4.2)
            self.assertIsNone(sample.volts)
            self.assertIsNone(sample.amps)
            self.assertEqual(format_measurement(sample.volts, "V", 2), "n/a V")

    def test_missing_battery_is_clear_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "No battery"):
                BatteryReader(Path(tmp)).read()

    def test_find_supplies_handles_empty_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(find_supplies(Path(tmp)), (None, None))

    def test_rejects_missing_or_malformed_required_readings(self):
        cases = {
            "missing voltage": {"current_now": "1000000"},
            "missing current": {"voltage_now": "8000000"},
            "malformed current": {"voltage_now": "8000000", "current_now": "bad"},
        }
        for name, readings in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                bat = base / "BAT1"
                write(bat / "type", "Battery\n")
                for field, value in readings.items():
                    write(bat / field, value)

                with self.assertRaises(BatteryReadError):
                    BatteryReader(base).read()

    def test_unknown_ac_state_is_not_reported_as_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            bat = base / "BAT1"
            ac = base / "ACAD"
            write(bat / "type", "Battery\n")
            write(bat / "voltage_now", "8000000\n")
            write(bat / "current_now", "0\n")
            write(ac / "type", "Mains\n")

            self.assertIsNone(BatteryReader(base).read().ac_online)


class AutostartTests(unittest.TestCase):

    def test_autostart_toggle_writes_and_removes_desktop_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_home = Path(tmp) / "config"

            self.assertFalse(autostart_enabled(config_home))
            desktop_file = enable_autostart(config_home)

            self.assertTrue(desktop_file.exists())
            self.assertTrue(autostart_enabled(config_home))
            entry = desktop_file.read_text(encoding="utf-8")
            self.assertIn("Name=Deck Power Tray", entry)
            self.assertIn("Exec=", entry)
            self.assertIn("Icon=", entry)
            self.assertIn("StartupWMClass=deck-power-tray", entry)
            self.assertNotIn("--show", entry)
            self.assertEqual(desktop_file.stat().st_mode & 0o777, 0o644)
            self.assertEqual(list(desktop_file.parent.glob(".deck-power-tray.desktop.tmp.*")), [])

            self.assertTrue(disable_autostart(config_home))
            self.assertFalse(autostart_enabled(config_home))

    def test_disable_autostart_is_safe_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(disable_autostart(Path(tmp) / "config"))

    def test_autostart_parser_respects_disabled_and_invalid_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_home = Path(tmp) / "config"
            path = enable_autostart(config_home)
            path.write_text(desktop_entry() + "Hidden=true\n", encoding="utf-8")
            self.assertFalse(autostart_enabled(config_home))

            path.write_text(desktop_entry(show_on_start=True), encoding="utf-8")
            self.assertFalse(autostart_enabled(config_home))

            path.write_text("not a desktop entry\n", encoding="utf-8")
            self.assertFalse(autostart_enabled(config_home))

    def test_desktop_exec_quotes_reserved_characters(self):
        self.assertEqual(desktop_exec_arg("/tmp/Power Tray/app"), '"/tmp/Power Tray/app"')
        self.assertEqual(
            desktop_exec_arg('/tmp/quote"dir/app'),
            '"/tmp/quote' + "\\" * 2 + '"dir/app"',
        )
        self.assertEqual(
            desktop_exec_arg("/tmp/dollar$dir/app"),
            '"/tmp/dollar' + "\\" * 2 + '$dir/app"',
        )
        self.assertEqual(
            desktop_exec_arg("/tmp/slash\\dir/app"),
            '"/tmp/slash' + "\\" * 4 + 'dir/app"',
        )

    def test_glib_launches_executable_path_containing_backslash(self):
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / "slash\\dir" / "app"
            executable.parent.mkdir()
            executable.symlink_to("/bin/true")
            data = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=Test\n"
                f"Exec={desktop_exec_arg(executable)}\n"
            )
            entry = GLib.KeyFile()
            entry.load_from_data(data, len(data), GLib.KeyFileFlags.NONE)
            app_info = Gio.DesktopAppInfo.new_from_keyfile(entry)

            self.assertIsNotNone(app_info)
            self.assertTrue(app_info.launch([], None))

    def test_desktop_exec_rejects_unrepresentable_paths(self):
        for value in ("/tmp/percent%dir/app", "/tmp/equal=dir/app", "/tmp/new\nline/app"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                desktop_exec_arg(value)

    def test_autostart_enabled_handles_desktop_exec_escapes(self):
        escaped_directories = ('dollar$dir', 'quote"dir', "tick`dir", "slash\\dir")
        with tempfile.TemporaryDirectory() as tmp:
            config_home = Path(tmp) / "config"
            for directory in escaped_directories:
                with self.subTest(directory=directory), patch(
                    "deck_power_tray.app.APP_COMMAND",
                    Path(tmp) / directory / "deck-power-tray",
                ):
                    enable_autostart(config_home)
                    self.assertTrue(autostart_enabled(config_home))

    def test_autostart_enabled_accepts_equivalent_keyfile_escaping(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_home = Path(tmp) / "config"
            command = Path(tmp) / "Power Tray" / "deck-power-tray"
            with patch("deck_power_tray.app.APP_COMMAND", command):
                path = enable_autostart(config_home)
                encoded = desktop_exec_arg(command)
                equivalent = encoded.replace("Power Tray", r"Power\sTray")
                entry = path.read_text(encoding="utf-8").replace(
                    f"Exec={encoded}",
                    f"Exec={equivalent}",
                )
                path.write_text(entry, encoding="utf-8")

                self.assertTrue(autostart_enabled(config_home))

    def test_autostart_enabled_handles_utf8_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_home = Path(tmp) / "config"
            directory = "unicode-" + "\u00e9" * 8 + "-dir"
            command = Path(tmp) / directory / "deck-power-tray"
            with patch("deck_power_tray.app.APP_COMMAND", command):
                enable_autostart(config_home)
                self.assertTrue(autostart_enabled(config_home))

    def test_application_entry_shows_window_but_autostart_entry_does_not(self):
        self.assertNotIn(" --show", desktop_entry(show_on_start=False))
        self.assertIn(" --show", desktop_entry(show_on_start=True))

    def test_relative_xdg_config_home_falls_back_to_home(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "relative/path"}):
            self.assertEqual(autostart_file(), Path.home() / ".config/autostart/deck-power-tray.desktop")


class TrayRuntimeTests(unittest.TestCase):
    def test_public_version_is_semantic(self):
        major, minor, patch_version = APP_VERSION.split(".")
        self.assertTrue(all(part.isdigit() for part in (major, minor, patch_version)))

    def test_read_error_updates_icon_once_and_keeps_polling(self):
        class Reader:
            def read(self):
                raise BatteryReadError("battery unavailable")

        class Tray:
            def __init__(self):
                self.icon_calls = 0
                self.tooltip_calls = 0

            def NewIcon(self):
                self.icon_calls += 1

            def NewToolTip(self):
                self.tooltip_calls += 1

        class App:
            reader = Reader()
            tray = Tray()
            last_icon = None
            last_error = None
            drawn = []

            def draw_icon(self, text, color):
                self.drawn.append((text, color))

            update_error = TrayApp.update_error

        app = App()
        with patch("sys.stderr"):
            self.assertTrue(TrayApp.poll(app))
            self.assertTrue(TrayApp.poll(app))
        self.assertEqual(app.drawn, [("ERR", "#a33")])
        self.assertEqual(app.tray.icon_calls, 1)
        self.assertEqual(app.tray.tooltip_calls, 2)

    def test_watcher_registration_failure_is_recoverable(self):
        class Bus:
            def name_has_owner(self, _bus_name):
                return False

            def get_object(self, _bus_name, _path):
                raise AssertionError("must not activate a missing watcher")

        item = StatusNotifierItem.__new__(StatusNotifierItem)
        item.bus = Bus()
        item.service_name = APP_BUS
        item.registered = True

        self.assertFalse(item.register_with_watcher())
        self.assertFalse(item.registered)

    def test_watcher_registration_schedules_and_completes_retry(self):
        item = StatusNotifierItem.__new__(StatusNotifierItem)
        item.registration_retry_id = None

        with (
            patch.object(item, "register_with_watcher", return_value=False),
            patch("deck_power_tray.app.GLib.timeout_add_seconds", return_value=73) as timeout,
        ):
            item.ensure_registered()

        self.assertEqual(item.registration_retry_id, 73)
        timeout.assert_called_once()

        with patch.object(item, "register_with_watcher", return_value=True):
            self.assertFalse(item._retry_registration())
        self.assertIsNone(item.registration_retry_id)


class TrayIconTests(unittest.TestCase):

    def test_error_icon_renders_with_short_hex_color(self):
        class App:
            pass

        app = App()
        TrayApp.draw_icon(app, "ERR", "#a33")
        self.assertEqual(len(app.icon_pixmap), 1)

    def test_tray_icon_uses_compact_square_readout(self):
        self.assertEqual(tray_icon_text(4.86), "4.9")
        self.assertEqual(tray_icon_text(12.3), "12")
        self.assertEqual(tray_icon_font_size("4.9"), 40)
        self.assertEqual(tray_icon_font_size("12"), 44)
        self.assertEqual(tray_icon_font_size("100"), 36)
        self.assertTrue(tray_icon_uses_colored_decimal_dot("4.9"))
        self.assertFalse(tray_icon_uses_colored_decimal_dot("12"))


if __name__ == "__main__":
    unittest.main()
