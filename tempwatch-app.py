#!/usr/bin/env python3
"""TempWatch — HWiNFO-style live sensor monitor for Linux (GTK3, stdlib only).

Clear per-sensor names, session min/max, firmware limits, and a per-sensor
temperature-over-time sparkline (last 3 minutes at 1s sampling).

Sensors: CPU (k10temp), DRAM sticks (spd5118), Board incl. TSENSOR1 (nct6799),
GPUs (amdgpu). No dependencies beyond python3-gi (Ubuntu desktop default).
"""
import contextlib
import glob
import json
import os
import subprocess
import time
from collections import deque
from typing import Any

import gi  # type: ignore[import-not-found]  # isort:skip

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gio, Gtk  # type: ignore[import-not-found]  # isort:skip  # noqa: E402

HWMON = "/sys/class/hwmon"
APP_ID = "dev.leo.tempwatch"
ICON = os.path.join(os.path.dirname(os.path.realpath(__file__)), "tempwatch-icon.svg")
HISTORY = 180  # seconds of trend shown per sensor

NAMES = {"k10temp": "CPU", "coretemp": "CPU", "spd5118": "DRAM", "amdgpu": "GPU",
         "nvidia": "GPU", "nct6799": "Board", "nvme": "NVMe", "asus": "ASUS WMI"}
ORDER = ["k10temp", "coretemp", "spd5118", "nct6799", "asus", "amdgpu", "nvidia", "nvme"]
WANT = set(NAMES)

# plain-language names per raw label
CPU_NAMES = {"Tctl": "CPU Package (Tctl)", "Tccd1": "CPU CCD 1 (Tccd1)",
             "Tccd2": "CPU CCD 2 (Tccd2)"}
CORETEMP_NAMES = {"Package id 0": "CPU Package", "Package": "CPU Package"}
BOARD_NAMES = {"SYSTIN": "Motherboard (SYSTIN)", "CPUTIN": "CPU Socket (CPUTIN)",
               "AUXTIN0": "Board Sensor (AUXTIN0)",
               "AUXTIN3": "TSENSOR1 Custom Probe",   # TSENSOR1 maps to AUXTIN3 on NCT6799
               "AUXTIN4": "Board Sensor (AUXTIN4)"}
GPU_KEEP = {"edge": "Core", "junction": "Hotspot", "mem": "Memory (GDDR)"}
NVIDIA_KEEP = {"GPU Core Temp": "Core", "GPU Memory Temp": "Memory",
               "GPU Hot Spot Temp": "Hotspot"}


def gpu_title(idx: int, hwmon_dir: str) -> str:
    for p in glob.glob(f"{hwmon_dir}/device/drm/card*/device/product_name"):
        name = read_str(p)
        if name and name.lower() not in ("amd rocm", "unknown"):
            return name
    return f"Graphics Adapter {idx}"


# Sensor source registry: one entry per hwmon driver = one platform support
# unit.  title(idx, dir) -> section name; labels maps raw label -> friendly
# name (None = keep all sensors as-is); mapped_only drops unmapped labels.
# Adding a platform = adding one entry + one ORDER item. See README.
SOURCES: dict[str, dict] = {
    "k10temp":  {"title": lambda i, d: "CPU", "labels": CPU_NAMES,
                 "mapped_only": True},
    "coretemp": {"title": lambda i, d: "CPU", "labels": CORETEMP_NAMES,
                 "mapped_only": False},
    "spd5118":  {"title": lambda i, d: f"Memory Stick {i}", "labels": None,
                 "mapped_only": False},
    "nct6799":  {"title": lambda i, d: "Motherboard", "labels": BOARD_NAMES,
                 "mapped_only": True},
    "asus":     {"title": lambda i, d: "Motherboard (ASUS WMI)",
                 "labels": None, "mapped_only": False},
    "amdgpu":   {"title": gpu_title, "labels": GPU_KEEP, "mapped_only": True,
                 "prefix": True},
    "nvidia":   {"title": gpu_title, "labels": NVIDIA_KEEP, "mapped_only": True,
                 "prefix": True},
    "nvme":     {"title": lambda i, d: f"NVMe SSD {i}",
                 "labels": None, "mapped_only": False,
                 "keep": {"Composite"}},   # drive's composite temp only
}

FG_RGB = [(0.18, 0.76, 0.49, 1.0), (0.90, 0.65, 0.04, 1.0), (0.75, 0.11, 0.16, 1.0)]
FG_HEX = ("#2ec27e", "#e5a50a", "#c01c28")


def read_str(path: str) -> str | None:
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def read_temp(path: str) -> float | None:
    v = read_str(path)
    if v is None:
        return None
    try:
        return int(v) / 1000.0
    except ValueError:
        return None


def discover() -> list[tuple[str, str, float, float | None, float | None]]:
    """[(id, display_name, cur, high, crit), ...] ordered by section."""
    out: list[tuple[str, str, float, float | None, float | None]] = []
    inst = dict.fromkeys(NAMES, 0)
    try:
        hs = sorted(os.listdir(HWMON))
    except OSError:
        return out
    for h in hs:
        d = os.path.join(HWMON, h)
        driver = read_str(os.path.join(d, "name")) or ""
        src = SOURCES.get(driver)
        if src is None:
            continue
        inst[driver] += 1
        section = src["title"](inst[driver], d)
        try:
            files = sorted(os.listdir(d))
        except OSError:
            continue
        for f in files:
            if not (f.startswith("temp") and f.endswith("_input")):
                continue
            key = f[:-6]
            cur = read_temp(os.path.join(d, f))
            if cur is None:
                continue
            label = read_str(f"{d}/{key}_label") or "Temp"
            keep = src.get("keep")
            if keep is not None and label not in keep:
                continue
            labels = src["labels"]
            mapped = None
            if labels is not None:
                mapped = labels.get(label) or labels.get(label.lower())
                if mapped is None and src["mapped_only"]:
                    continue
            name = mapped or (section if label in ("Temp", "Composite")
                              else f"{section} · {label}")
            if mapped and src.get("prefix"):
                name = f"{section} · {mapped}"
            out.append((f"{driver}|{h}|{key}", name, cur,
                        read_temp(f"{d}/{key}_max"), read_temp(f"{d}/{key}_crit")))
    out.sort(key=lambda r: ORDER.index(r[0].split("|")[0]))
    return out


# TreeView columns: id, name, now, min, max, limit, pct, color(0/1/2)
COLS: tuple[type, ...] = (str, str, str, str, str, str, int, int)
GREEN, YELLOW, RED = 0, 1, 2


def color_for(v: float, hi: float | None, crit: float | None) -> int:
    if crit is not None and v >= crit - 5:
        return RED
    if hi is not None and v >= hi:
        return RED if crit is not None and v >= crit - 15 else YELLOW
    return GREEN


class SparkRenderer(Gtk.CellRenderer):
    """Draws a mini temperature-over-time line chart for one row."""

    __gtype_name__ = "TempWatchSparkRenderer"

    def __init__(self) -> None:
        super().__init__()
        self.series: list[float] = []
        self.color = FG_RGB[0]

    def do_render(self, cr: Any, widget: Any, bg: Any, area: Any, flags: Any) -> None:
        s = self.series
        if len(s) < 2:
            return
        x0, y0 = area.x + 3, area.y + 3
        w, h = area.width - 6, area.height - 6
        if w <= 4 or h <= 4:
            return
        lo, hi = min(s), max(s)
        rng = max(hi - lo, 4.0)
        n = len(s)
        cr.set_line_width(1.6)
        cr.set_source_rgba(*self.color)
        for i, v in enumerate(s):
            x = x0 + w * i / (n - 1)
            y = y0 + h * (1 - (v - lo) / rng)
            cr.line_to(x, y) if i else cr.move_to(x, y)
        cr.stroke()
        cr.arc(x0 + w, y0 + h * (1 - (s[-1] - lo) / rng), 2.2, 0, 6.2832)
        cr.fill()


class TempWatch(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.stats: dict[str, tuple[float, float]] = {}
        self.hist: dict[str, deque] = {}
        self.win: Gtk.ApplicationWindow | None = None
        self.store = Gtk.ListStore(*COLS)
        self.spark = SparkRenderer()
        self.ind = None  # optional tray/top-bar indicator
        self.vitals: Gio.Settings | None = None  # Vitals shell extension
        with contextlib.suppress(Exception):
            self.vitals = Gio.Settings.new("org.gnome.shell.extensions.vitals")

    # --- top-bar (Vitals extension) pinning -------------------------------

    def _vitals_sensors(self) -> list[dict]:
        vs = self.vitals
        if vs is None:
            return []
        try:
            return [dict(x) for x in vs.get_value(
                "config-custom-sensors-array").unpack()]
        except Exception:
            return []

    def _chip_for(self, h: str, key: str) -> str:
        """Map hwmon dir + temp index -> lm-sensors chip key (Vitals
        matches on it): same sensor label and ~same live reading."""
        d = os.path.join(HWMON, h)
        label = read_str(f"{d}/{key}_label")
        raw = read_str(f"{d}/{key}_input")
        try:
            chips = json.loads(subprocess.run(
                ["sensors", "-j"], capture_output=True, text=True,
                timeout=5).stdout)
        except Exception:
            return h
        want = f"{key}_input"
        for ck, body in chips.items():
            for sub, ent in body.items():
                if not isinstance(ent, dict) or want not in ent:
                    continue
                if label is not None and sub != label:
                    continue
                if raw is not None:
                    try:
                        if abs(float(ent[want]) - int(raw) / 1000.0) > 1.0:
                            continue
                    except (TypeError, ValueError):
                        continue
                return ck
        return h

    def _pin_vitals(self, row_id: str, name: str, on: bool) -> None:
        """Add/remove a custom Vitals sensor for one hwmon input so its
        value shows as text in the GNOME top bar."""
        driver, h, key = row_id.split("|")
        vs = self.vitals
        if vs is None:
            return
        arr = self._vitals_sensors()
        arr = [s for s in arr if s.get("name") != name]
        if on:
            chip = self._chip_for(h, key)
            lab = read_str(f"{HWMON}/{h}/{key}_label") or key
            arr.append({"name": name, "sensorType": "temp", "command": chip,
                        "pw1": key, "label": lab, "scale": 1})
        vs.set_value("config-custom-sensors-array",
                     GLib.Variant("aa{sv}", arr))
        groups = [dict(g) for g in vs.get_value(
            "config-extensions-array").unpack()]
        groups = [g for g in groups
                  if not str(g.get("name", "")).startswith("custom")]
        names = [s["name"] for s in arr]
        for i in range(len(names)):
            groups.append({"name": f"custom{i + 1}", "showLabel": True,
                           "showSeparator": True})
        vs.set_value("config-extensions-array", GLib.Variant("aa{sv}", groups))
        vs.set_boolean("show-extensions-position-text", True)

    def _is_pinned(self, name: str) -> bool:
        return any(s.get("name") == name for s in self._vitals_sensors())

    def _on_row_click(self, view: Gtk.TreeView, event: Any) -> bool:
        if event.button != 3 or self.vitals is None:
            return False
        pos = view.get_path_at_pos(int(event.x), int(event.y))
        if not pos:
            return False
        it = self.store.get_iter(pos[0])
        row_id, name = self.store.get(it, 0, 1)
        menu = Gtk.Menu()
        on = self._is_pinned(name)
        item = Gtk.MenuItem(label=("Remove from taskbar" if on
                                   else "Show value in taskbar"))
        item.connect("activate",
                     lambda *_: self._pin_vitals(row_id, name, not on))
        menu.append(item)
        menu.show_all()
        menu.popup_at_pointer(event)
        return True

    def _make_indicator(self) -> None:
        """Top-bar (AppIndicator) readout of the hottest sensor; no-op on
        desktops without a tray."""
        gi.require_version("AyatanaAppIndicator3", "0.1")
        from gi.repository import AyatanaAppIndicator3 as AI  # type: ignore[import-not-found]
        self.ind = AI.Indicator.new(APP_ID, "dev.leo.tempwatch",
                                    AI.IndicatorCategory.APPLICATION_STATUS)
        self.ind.set_status(AI.IndicatorStatus.ACTIVE)
        menu = Gtk.Menu()
        show = Gtk.MenuItem(label="Show TempWatch")
        show.connect("activate", lambda *_: self.win.present() if self.win else self.activate())
        menu.append(show)
        menu.append(Gtk.SeparatorMenuItem())
        quit_i = Gtk.MenuItem(label="Quit")
        quit_i.connect("activate", lambda *_: self.quit())
        menu.append(quit_i)
        menu.show_all()
        self.ind.set_menu(menu)

    def _update_indicator(self, rows) -> None:
        if self.ind is None or not rows:
            return
        hot = max(rows, key=lambda r: r[2])
        self.ind.set_label(f"{hot[2]:.0f}°", f"{hot[1]} · {hot[2]:.1f}°")
        self.ind.set_title(f"TempWatch — hottest {hot[1]} {hot[2]:.1f}°")

    def do_activate(self) -> None:
        win = self.win = Gtk.ApplicationWindow(application=self, title="TempWatch")
        win.set_default_size(760, 500)
        with contextlib.suppress(Exception):
            win.set_icon_from_file(ICON)
        win.set_role("tempwatch-main")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        win.add(box)

        header = Gtk.Box(spacing=8, margin=6)
        header.pack_start(Gtk.Label(label=f"⚡ TempWatch — {os.uname().nodename}"),
                          False, False, 0)
        self.stamp = Gtk.Label(label="")
        self.stamp.set_opacity(0.55)
        header.pack_end(self.stamp, False, False, 0)
        box.pack_start(header, False, False, 0)

        view = Gtk.TreeView(model=self.store)
        view.connect("button-press-event", self._on_row_click)
        for i, (title, width, col_i) in enumerate(
                [("Sensor", 300, 1), ("Now", 70, 2), ("Min", 70, 3),
                 ("Max", 70, 4), ("Limit", 70, 5)]):
            r = Gtk.CellRendererText()
            r.set_property("xalign", 1.0 if i else 0.0)
            col = Gtk.TreeViewColumn(title, r, text=col_i)
            if i == 1:
                col.set_cell_data_func(r, self._color_cell)
            col.set_alignment(1.0 if i else 0.0)
            col.set_fixed_width(width)
            view.append_column(col)
        self.spark.set_property("height", 26)
        scol = Gtk.TreeViewColumn("Temperature over time (last 3 min)", self.spark)
        scol.set_cell_data_func(self.spark, self._feed_spark)
        scol.set_expand(True)
        scol.set_min_width(140)
        view.append_column(scol)
        sw = Gtk.ScrolledWindow()
        sw.add(view)
        box.pack_start(sw, True, True, 0)

        status = Gtk.Label(label="min/max are session values · limits from firmware · "
                                 "chart auto-scales per sensor",
                           xalign=0.0, margin=4)
        status.set_opacity(0.55)
        box.pack_start(status, False, False, 0)

        self.tick()
        GLib.timeout_add_seconds(1, self.tick)
        with contextlib.suppress(Exception):  # tray-less DEs: window only
            self._make_indicator()
            self._update_indicator(discover())
        win.show_all()

    def _color_cell(self, _col: Any, cell: Any, model: Any, it: Any,
                    _data: Any = None) -> None:
        c = model.get_value(it, 7)
        cell.set_property("markup", f'<span foreground="{FG_HEX[c]}"><b>'
                                    f'{model.get_value(it, 2)}</b></span>')

    def _feed_spark(self, _col: Any, cell: SparkRenderer, model: Any, it: Any,
                    _data: Any = None) -> None:
        sid = model.get_value(it, 0)
        cell.series = list(self.hist.get(sid, ()))
        cell.color = FG_RGB[model.get_value(it, 7)]

    def tick(self) -> bool:
        if self.win is None:
            return False
        rows = discover()
        seen = set()
        for i, (sid, name, cur, hi, crit) in enumerate(rows):
            seen.add(sid)
            lo, mx = self.stats.get(sid, (cur, cur))
            lo, mx = min(lo, cur), max(mx, cur)
            self.stats[sid] = (lo, mx)
            hist = self.hist.setdefault(sid, deque(maxlen=HISTORY))
            hist.append(cur)
            vals = [sid, name, f"{cur:.1f}°", f"{lo:.1f}°", f"{mx:.1f}°",
                    f"{hi:.0f}°" if hi is not None
                    else (f"{crit:.0f}°" if crit is not None else "—"),
                    0, color_for(cur, hi, crit)]
            if i < len(self.store):
                self.store[i] = vals
            else:
                self.store.append(vals)
        while len(self.store) > len(rows):
            del self.store[len(self.store) - 1]
        self._update_indicator(rows)
        for sid in list(self.hist):
            if sid not in seen:
                del self.hist[sid]
        self.stamp.set_text(time.strftime("updated %H:%M:%S"))
        return True


if __name__ == "__main__":
    TempWatch().run()
