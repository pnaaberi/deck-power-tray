#!/usr/bin/env python3
import math
import os
import sys
import tempfile
import time
import warnings
from dataclasses import dataclass
from pathlib import Path

import cairo
import dbus
import dbus.mainloop.glib
import dbus.service
import gi

warnings.filterwarnings("ignore", category=DeprecationWarning, module=__name__)

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk


POWER_SUPPLY = Path(os.environ.get("DECK_POWER_TRAY_POWER_SUPPLY", "/sys/class/power_supply"))
APP_ROOT = Path(__file__).resolve().parents[1]
APP_ICON = APP_ROOT / "icons" / "deck-power-tray.svg"
APP_COMMAND = APP_ROOT / "deck-power-tray"
SAMPLE_SECONDS = 2
HISTORY_SECONDS = 10 * 60
MAX_SAMPLES = HISTORY_SECONDS // SAMPLE_SECONDS
GRAPH_MAX_VALUE = 50.0
TRAY_ICON_SCALE = 2
TRAY_ICON_WIDTH = 96 * TRAY_ICON_SCALE
TRAY_ICON_HEIGHT = 32 * TRAY_ICON_SCALE
TRAY_TEXT_WIDTH = 78 * TRAY_ICON_SCALE
SNI_IFACE = "org.kde.StatusNotifierItem"
PROPS_IFACE = "org.freedesktop.DBus.Properties"
WATCHER_BUS = "org.kde.StatusNotifierWatcher"
WATCHER_PATH = "/StatusNotifierWatcher"


@dataclass
class Sample:
    ts: float
    watts: float
    volts: float
    amps: float
    capacity: int | None
    status: str
    ac_online: bool | None


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _read_int(path: Path) -> int | None:
    raw = _read(path)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def find_supplies(base: Path) -> tuple[Path | None, Path | None]:
    battery = None
    ac = None
    for item in sorted(base.glob("*")):
        kind = (_read(item / "type") or "").lower()
        if kind == "battery" and battery is None:
            battery = item
        elif kind in {"mains", "usb", "usb_c", "usb_pd"} and ac is None:
            ac = item
    return battery, ac


class BatteryReader:
    def __init__(self, base: Path = POWER_SUPPLY):
        self.base = base

    def read(self) -> Sample:
        battery, ac = find_supplies(self.base)
        if battery is None:
            raise RuntimeError(f"No battery found under {self.base}")

        voltage_uv = _read_int(battery / "voltage_now")
        current_ua = _read_int(battery / "current_now")
        power_uw = _read_int(battery / "power_now")
        capacity = _read_int(battery / "capacity")
        status = _read(battery / "status") or "Unknown"

        if power_uw is None and voltage_uv is not None and current_ua is not None:
            power_uw = (voltage_uv * current_ua) // 1_000_000

        volts = (voltage_uv or 0) / 1_000_000
        amps = (current_ua or 0) / 1_000_000
        watts = (power_uw or 0) / 1_000_000

        ac_online = None
        if ac is not None:
            ac_online = (_read_int(ac / "online") or 0) == 1

        return Sample(time.time(), watts, volts, amps, capacity, status, ac_online)


class GraphWindow(Gtk.Window):
    def __init__(self, app: "TrayApp"):
        super().__init__(title="Deck Power")
        self.app = app
        self.hover_x: float | None = None
        self.hover_y: float | None = None
        self.set_default_size(760, 430)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_border_width(0)
        if APP_ICON.exists():
            self.set_icon_from_file(str(APP_ICON))

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(root)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header.get_style_context().add_class("header")
        root.pack_start(header, False, False, 0)

        self.summary = Gtk.Label(xalign=0)
        self.summary.get_style_context().add_class("summary")
        header.pack_start(self.summary, True, True, 0)

        self.autostart_button = Gtk.CheckButton(label="Start with system")
        self.autostart_button.set_active(autostart_enabled())
        self.autostart_handler = self.autostart_button.connect("toggled", self._autostart_toggled)
        header.pack_start(self.autostart_button, False, False, 0)

        self.area = Gtk.DrawingArea()
        self.area.add_events(Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.area.connect("draw", self.draw_graph)
        self.area.connect("motion-notify-event", self._mouse_moved)
        self.area.connect("leave-notify-event", self._mouse_left)
        root.pack_start(self.area, True, True, 0)

        self.connect("delete-event", self._hide_instead)
        self.apply_css()

    def apply_css(self) -> None:
        css = b"""
        window { background: #11151c; color: #ecf2f8; }
        .header { padding: 12px 16px; background: #18202b; }
        .summary { font: 16px Sans; }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _hide_instead(self, *_args):
        self.hide()
        return True

    def refresh(self) -> None:
        self.autostart_button.handler_block(self.autostart_handler)
        self.autostart_button.set_active(autostart_enabled())
        self.autostart_button.handler_unblock(self.autostart_handler)

        current = self.app.history[-1] if self.app.history else None
        if current is None:
            text = "Waiting for battery data..."
        else:
            charge = f"{current.capacity}%" if current.capacity is not None else "n/a"
            ac = "AC on" if current.ac_online else "AC off" if current.ac_online is False else "AC n/a"
            text = (
                f"{current.watts:.1f} W   {current.volts:.2f} V   {current.amps:.2f} A"
                f"   {charge}   {current.status}   {ac}"
            )
        self.summary.set_text(text)
        self.area.queue_draw()

    def _mouse_moved(self, _widget, event) -> bool:
        self.hover_x = event.x
        self.hover_y = event.y
        self.area.queue_draw()
        return True

    def _mouse_left(self, *_args) -> bool:
        self.hover_x = None
        self.hover_y = None
        self.area.queue_draw()
        return True

    def _autostart_toggled(self, button: Gtk.CheckButton) -> None:
        try:
            if button.get_active():
                enable_autostart()
            else:
                disable_autostart()
        except OSError as exc:
            button.handler_block(self.autostart_handler)
            button.set_active(autostart_enabled())
            button.handler_unblock(self.autostart_handler)
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Could not update startup setting",
            )
            dialog.format_secondary_text(str(exc))
            dialog.run()
            dialog.destroy()

    def draw_graph(self, _widget, ctx: cairo.Context) -> bool:
        width = self.area.get_allocated_width()
        height = self.area.get_allocated_height()
        pad_l, pad_r, pad_t, pad_b = 58, 22, 26, 44
        plot_w = max(1, width - pad_l - pad_r)
        plot_h = max(1, height - pad_t - pad_b)

        ctx.set_source_rgb(0.07, 0.09, 0.12)
        ctx.paint()

        samples = self.app.history[-MAX_SAMPLES:]
        now = time.time()
        start = now - HISTORY_SECONDS

        self._draw_discharge_regions(ctx, samples, start, plot_w, plot_h, pad_l, pad_t)

        ctx.set_line_width(1)
        ctx.set_source_rgba(1, 1, 1, 0.09)
        for i in range(6):
            y = pad_t + plot_h * i / 5
            ctx.move_to(pad_l, y)
            ctx.line_to(width - pad_r, y)
            ctx.stroke()
        for i in range(5):
            x = pad_l + plot_w * i / 4
            ctx.move_to(x, pad_t)
            ctx.line_to(x, height - pad_b)
            ctx.stroke()

        if len(samples) < 2:
            self._label(ctx, width / 2 - 80, height / 2, "Collecting samples...")
            return False

        series = [
            ("Watts", "#f2c94c", lambda s: s.watts, GRAPH_MAX_VALUE, "W"),
            ("Volts", "#56ccf2", lambda s: s.volts, GRAPH_MAX_VALUE, "V"),
            ("Amps", "#6fcf97", lambda s: s.amps, GRAPH_MAX_VALUE, "A"),
        ]

        for name, color, getter, scale, unit in series:
            self._line(ctx, samples, start, plot_w, plot_h, pad_l, pad_t, color, getter, scale)

        self._draw_hover(ctx, samples, start, plot_w, plot_h, pad_l, pad_t, width, height)

        self._label(ctx, 16, 22, f"{GRAPH_MAX_VALUE:.0f}")
        self._label(ctx, 16, height - pad_b + 4, "0")
        self._label(ctx, pad_l, height - 18, "10 min ago")
        self._label(ctx, width - pad_r - 34, height - 18, "now")

        x = pad_l
        for name, color, getter, _scale, unit in series:
            value = getter(samples[-1])
            self._swatch(ctx, x, 12, color)
            self._label(ctx, x + 18, 22, f"{name} {value:.2f} {unit}")
            x += 142
        return False

    def _draw_hover(self, ctx, samples, start, plot_w, plot_h, pad_l, pad_t, width, height):
        if self.hover_x is None or not samples:
            return
        plot_left = pad_l
        plot_right = width - 22
        x = max(plot_left, min(plot_right, self.hover_x))
        ratio = (x - plot_left) / plot_w
        target_ts = start + ratio * HISTORY_SECONDS
        sample = min(samples, key=lambda item: abs(item.ts - target_ts))
        x = pad_l + ((sample.ts - start) / HISTORY_SECONDS) * plot_w

        ctx.set_source_rgba(0.93, 0.95, 0.98, 0.55)
        ctx.set_line_width(1.4)
        ctx.move_to(x, pad_t)
        ctx.line_to(x, pad_t + plot_h)
        ctx.stroke()

        values = [
            ("#f2c94c", f"{sample.watts:.1f} W"),
            ("#56ccf2", f"{sample.volts:.2f} V"),
            ("#6fcf97", f"{sample.amps:.2f} A"),
        ]
        box_w = 72
        box_h = 62
        gap = box_w
        box_x = x + gap
        if box_x + box_w > width - 10:
            box_x = x - gap - box_w
        box_x = max(10, min(width - box_w - 10, box_x))
        cursor_y = self.hover_y if self.hover_y is not None else pad_t + plot_h * 0.5
        box_y = cursor_y - box_h * 0.5
        box_y = max(pad_t + 8, min(pad_t + plot_h - box_h - 8, box_y))
        ctx.set_source_rgba(0.05, 0.07, 0.09, 0.82)
        round_rect(ctx, box_x, box_y, box_w, box_h, 6)
        ctx.fill()
        ctx.set_source_rgba(1, 1, 1, 0.16)
        round_rect(ctx, box_x, box_y, box_w, box_h, 6)
        ctx.stroke()

        y = box_y + 19
        for color, text in values:
            ctx.set_source_rgb(*hex_to_rgb(color))
            ctx.arc(box_x + 10, y - 4, 3, 0, math.tau)
            ctx.fill()
            self._label(ctx, box_x + 18, y, text)
            y += 18

    def _draw_discharge_regions(self, ctx, samples, start, plot_w, plot_h, pad_l, pad_t):
        if len(samples) < 2:
            return
        region_start = None
        for index, sample in enumerate(samples):
            discharging = sample.status.lower() == "discharging"
            if discharging and region_start is None:
                region_start = sample.ts
            is_last = index == len(samples) - 1
            if region_start is not None and (not discharging or is_last):
                end_ts = sample.ts if is_last and discharging else samples[index - 1].ts
                x1 = pad_l + ((max(region_start, start) - start) / HISTORY_SECONDS) * plot_w
                x2 = pad_l + ((min(end_ts, time.time()) - start) / HISTORY_SECONDS) * plot_w
                if x2 > x1:
                    ctx.set_source_rgba(1.0, 0.48, 0.12, 0.16)
                    ctx.rectangle(x1, pad_t, x2 - x1, plot_h)
                    ctx.fill()
                region_start = None

    def _line(self, ctx, samples, start, plot_w, plot_h, pad_l, pad_t, color, getter, scale):
        ctx.set_source_rgb(*hex_to_rgb(color))
        ctx.set_line_width(2.4)
        first = True
        for sample in samples:
            x = pad_l + ((sample.ts - start) / HISTORY_SECONDS) * plot_w
            y = pad_t + plot_h - (getter(sample) / scale) * plot_h
            y = max(pad_t, min(pad_t + plot_h, y))
            if first:
                ctx.move_to(x, y)
                first = False
            else:
                ctx.line_to(x, y)
        ctx.stroke()

    def _label(self, ctx, x, y, text):
        ctx.set_source_rgba(0.92, 0.95, 0.98, 0.86)
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        ctx.set_font_size(12)
        ctx.move_to(x, y)
        ctx.show_text(text)

    def _swatch(self, ctx, x, y, color):
        ctx.set_source_rgb(*hex_to_rgb(color))
        ctx.rectangle(x, y, 11, 11)
        ctx.fill()


class StatusNotifierItem(dbus.service.Object):
    def __init__(self, app: "TrayApp"):
        self.app = app
        self.bus = dbus.SessionBus()
        self.service_name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
        self.bus_name = dbus.service.BusName(self.service_name, bus=self.bus, allow_replacement=True)
        super().__init__(self.bus_name, "/StatusNotifierItem")

        watcher = self.bus.get_object(WATCHER_BUS, WATCHER_PATH)
        watcher.RegisterStatusNotifierItem(
            self.service_name,
            dbus_interface=WATCHER_BUS,
        )

    def properties(self) -> dict[str, object]:
        return {
            "Category": dbus.String("Hardware"),
            "Id": dbus.String("deck-power-tray"),
            "Title": dbus.String(self.app.title),
            "Status": dbus.String("Active"),
            "WindowId": dbus.UInt32(0),
            "IconName": dbus.String(""),
            "IconPixmap": self.app.icon_pixmap,
            "OverlayIconName": dbus.String(""),
            "OverlayIconPixmap": dbus.Array([], signature="(iiay)"),
            "AttentionIconName": dbus.String(""),
            "AttentionIconPixmap": dbus.Array([], signature="(iiay)"),
            "AttentionMovieName": dbus.String(""),
            "ToolTip": self.app.tooltip,
            "ItemIsMenu": dbus.Boolean(False),
            "Menu": dbus.ObjectPath("/NO_DBUSMENU"),
        }

    @dbus.service.method(PROPS_IFACE, in_signature="ss", out_signature="v")
    def Get(self, interface_name, property_name):
        if interface_name != SNI_IFACE:
            raise dbus.exceptions.DBusException("Unknown interface")
        try:
            return self.properties()[property_name]
        except KeyError:
            raise dbus.exceptions.DBusException("Unknown property")

    @dbus.service.method(PROPS_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface_name):
        if interface_name != SNI_IFACE:
            return dbus.Dictionary({}, signature="sv")
        return dbus.Dictionary(self.properties(), signature="sv")

    @dbus.service.method(PROPS_IFACE, in_signature="ssv", out_signature="")
    def Set(self, _interface_name, _property_name, _value):
        raise dbus.exceptions.DBusException("Properties are read-only")

    @dbus.service.method(SNI_IFACE, in_signature="ii", out_signature="")
    def Activate(self, _x, _y):
        GLib.idle_add(self.app.toggle_window)

    @dbus.service.method(SNI_IFACE, in_signature="ii", out_signature="")
    def SecondaryActivate(self, _x, _y):
        GLib.idle_add(self.app.show_window)

    @dbus.service.method(SNI_IFACE, in_signature="ii", out_signature="")
    def ContextMenu(self, _x, _y):
        GLib.idle_add(self.app.show_window)

    @dbus.service.method(SNI_IFACE, in_signature="ii", out_signature="")
    def Scroll(self, _delta, _orientation):
        return

    @dbus.service.signal(SNI_IFACE, signature="")
    def NewIcon(self):
        return

    @dbus.service.signal(SNI_IFACE, signature="")
    def NewToolTip(self):
        return

    @dbus.service.signal(SNI_IFACE, signature="s")
    def NewStatus(self, _status):
        return


class TrayApp:
    def __init__(self, show_on_start: bool = False):
        self.reader = BatteryReader()
        self.history: list[Sample] = []
        self.last_icon: tuple[str, str] | None = None
        self.title = "Deck Power"
        self.tooltip = sni_tooltip("Deck Power", "Waiting for battery data")
        self.icon_pixmap = dbus.Array([], signature="(iiay)")
        self.icon_path = Path(tempfile.gettempdir()) / f"deck-power-tray-{os.getuid()}.png"
        self.window = GraphWindow(self)
        self.tray = StatusNotifierItem(self)

        self.poll()
        if show_on_start:
            self.show_window()
        GLib.timeout_add_seconds(SAMPLE_SECONDS, self.poll)

    def poll(self):
        try:
            sample = self.reader.read()
            self.history.append(sample)
            self.history = self.history[-MAX_SAMPLES:]
            self.update_tray(sample)
            self.window.refresh()
        except Exception as exc:
            self.tooltip = sni_tooltip("Deck Power", str(exc))
            self.draw_icon("ERR", "#a33")
            self.tray.NewToolTip()
        return True

    def update_tray(self, sample: Sample) -> None:
        suffix = "W"
        text = f"{sample.watts:.0f}{suffix}" if sample.watts >= 10 else f"{sample.watts:.1f}{suffix}"
        color = "#2d9c5b" if sample.ac_online else "#c96d2d"
        if sample.status.lower() == "full":
            color = "#2f80ed"
        if self.last_icon != (text, color):
            self.draw_icon(text, color)
            self.last_icon = (text, color)
            self.tray.NewIcon()
        charge = f"{sample.capacity}%" if sample.capacity is not None else "n/a"
        self.tooltip = sni_tooltip(
            "Deck Power",
            f"{sample.watts:.1f} W  {sample.volts:.2f} V  {sample.amps:.2f} A\n{sample.status}, {charge}",
        )
        self.tray.NewToolTip()

    def draw_icon(self, text: str, dot_color: str) -> None:
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, TRAY_ICON_WIDTH, TRAY_ICON_HEIGHT)
        ctx = cairo.Context(surface)
        ctx.set_source_rgba(0, 0, 0, 0)
        ctx.paint()

        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(tray_icon_font_size(text))
        xb, yb, tw, th, _xa, _ya = ctx.text_extents(text)
        ctx.set_source_rgba(0, 0, 0, 0.58)
        ctx.move_to(
            (TRAY_TEXT_WIDTH - tw) / 2 - xb + 2 * TRAY_ICON_SCALE,
            (TRAY_ICON_HEIGHT - th) / 2 - yb + TRAY_ICON_SCALE,
        )
        ctx.show_text(text)
        ctx.set_source_rgba(0.93, 0.95, 0.98, 0.98)
        ctx.move_to(
            (TRAY_TEXT_WIDTH - tw) / 2 - xb + TRAY_ICON_SCALE,
            (TRAY_ICON_HEIGHT - th) / 2 - yb,
        )
        ctx.show_text(text)

        ctx.set_source_rgb(*hex_to_rgb(dot_color))
        ctx.arc(89 * TRAY_ICON_SCALE, 16 * TRAY_ICON_SCALE, 4.0 * TRAY_ICON_SCALE, 0, math.tau)
        ctx.fill()
        surface.flush()
        surface.write_to_png(str(self.icon_path))
        self.icon_pixmap = cairo_surface_to_sni_pixmap(surface)

    def toggle_window(self, *_args) -> None:
        if self.window.is_visible():
            self.window.hide()
        else:
            self.show_window()

    def show_window(self) -> None:
        self.window.refresh()
        self.window.show_all()
        self.window.present()


def hex_to_rgb(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))


def round_rect(ctx, x, y, w, h, r):
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def tray_icon_font_size(text: str) -> int:
    return (25 if len(text) <= 3 else 22 if len(text) <= 4 else 18) * TRAY_ICON_SCALE


def cairo_surface_to_sni_pixmap(surface: cairo.ImageSurface):
    width = surface.get_width()
    height = surface.get_height()
    stride = surface.get_stride()
    raw = bytes(surface.get_data())
    converted = bytearray()
    for y in range(height):
        row = raw[y * stride : y * stride + width * 4]
        for i in range(0, len(row), 4):
            b, g, r, a = row[i : i + 4]
            converted.extend((a, r, g, b))
    return dbus.Array(
        [
            dbus.Struct(
                (
                    dbus.Int32(width),
                    dbus.Int32(height),
                    dbus.Array(converted, signature="y"),
                ),
                signature=None,
            )
        ],
        signature="(iiay)",
    )


def sni_tooltip(title: str, body: str):
    return dbus.Struct(
        (
            dbus.String(""),
            dbus.Array([], signature="(iiay)"),
            dbus.String(title),
            dbus.String(body),
        ),
        signature=None,
    )


def autostart_file(config_home: Path | None = None) -> Path:
    if config_home is None:
        config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_home / "autostart" / "deck-power-tray.desktop"


def desktop_entry() -> str:
    icon = str(APP_ICON) if APP_ICON.exists() else "battery"
    return "\n".join(
        [
            "[Desktop Entry]",
            "Type=Application",
            "Name=Deck Power Tray",
            "Comment=Show Steam Deck battery watts in the system tray",
            f"Exec={APP_COMMAND}",
            f"Icon={icon}",
            "Terminal=false",
            "StartupWMClass=deck-power-tray",
            "X-GNOME-Autostart-enabled=true",
            "",
        ]
    )


def autostart_enabled(config_home: Path | None = None) -> bool:
    path = autostart_file(config_home)
    if not path.exists():
        return False
    return f"Exec={APP_COMMAND}" in (_read(path) or "")


def enable_autostart(config_home: Path | None = None) -> Path:
    path = autostart_file(config_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    tmp.write_text(desktop_entry(), encoding="utf-8")
    tmp.replace(path)
    return path


def disable_autostart(config_home: Path | None = None) -> bool:
    path = autostart_file(config_home)
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


def main() -> int:
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    GLib.set_prgname("deck-power-tray")
    GLib.set_application_name("Deck Power Tray")
    show_on_start = "--show" in sys.argv[1:]
    app = TrayApp(show_on_start=show_on_start)
    if not app.history:
        return 1
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
