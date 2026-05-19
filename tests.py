#!/usr/bin/env python3
import os
import tempfile
import unittest
from pathlib import Path

from deck_power_tray.app import (
    BatteryReader,
    autostart_enabled,
    disable_autostart,
    enable_autostart,
    find_supplies,
    tray_icon_font_size,
    tray_icon_text,
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

    def test_missing_battery_is_clear_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "No battery"):
                BatteryReader(Path(tmp)).read()

    def test_find_supplies_handles_empty_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(find_supplies(Path(tmp)), (None, None))

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

            self.assertTrue(disable_autostart(config_home))
            self.assertFalse(autostart_enabled(config_home))

    def test_disable_autostart_is_safe_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(disable_autostart(Path(tmp) / "config"))

    def test_tray_icon_uses_compact_square_readout(self):
        self.assertEqual(tray_icon_text(4.86), "4.9")
        self.assertEqual(tray_icon_text(12.3), "12")
        self.assertEqual(tray_icon_font_size("4.9"), 40)
        self.assertEqual(tray_icon_font_size("12"), 44)
        self.assertEqual(tray_icon_font_size("100"), 36)


if __name__ == "__main__":
    unittest.main()
