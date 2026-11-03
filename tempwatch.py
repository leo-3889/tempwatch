#!/usr/bin/env python3
"""tempwatch — live HWiNFO-style sensor dashboard, stdlib only.

Reads /sys/class/hwmon and renders the main temperature sensors with
live values, min/max since start, thresholds and colored bars.

Usage: tempwatch.py [--interval 1.0] [--once] [--all]
"""
import argparse
import os
import socket
import sys
import time
from collections import deque

HWMON = "/sys/class/hwmon"

# pretty section names per hwmon driver (display groups: CPU / DRAM / TSENSOR1 / GPU)
NAMES = {
    "k10temp": "CPU",
    "coretemp": "CPU",
    "spd5118": "DRAM",
    "amdgpu": "GPU",
    "nvidia": "GPU",
    "nct6799": "Board",
    "asus": "Board (ASUS WMI)",
    "nvme": "NVMe",
}
# order sections
ORDER = ["k10temp", "coretemp", "spd5118", "tsensor", "nct6799", "asus",
         "amdgpu", "nvidia", "nvme"]
WANT = {"k10temp", "coretemp", "spd5118", "amdgpu", "nvidia", "nct6799",
        "asus", "nvme"}
# amdgpu exposes junk labels; keep the meaningful temps only
GPU_LABELS = {"edge", "junction", "mem"}
# NCT6799 board thermistors (TSENSOR header shows as one of the AUXTINs)
BOARD_LABELS = {"SYSTIN", "CPUTIN", "AUXTIN0", "AUXTIN1", "AUXTIN2",
                "AUXTIN3", "AUXTIN4", "AUXTIN5"}

RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
FG = {"g": "\033[32m", "y": "\033[33m", "r": "\033[31m", "w": "\033[37m", "c": "\033[36m"}


def read_str(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def read(path):
    v = read_str(path)
    if v is None:
        return None
    try:
        return int(v) / 1000.0
    except ValueError:
        return None


def discover(show_all=False):
    """Return list of (section_key, section_title, sensor_label, cur, hi, crit).

    Groups: CPU (k10temp), DRAM (spd5118 DIMMs), TSENSOR1 (any hwmon temp
    labeled *TSensor* — appears once an ASUS-EC driver is installed), GPU.
    """
    out = []
    tsensors = []
    inst_count: dict[str, int] = {}
    try:
        hs = sorted(os.listdir(HWMON))
    except OSError:
        return out
    for h in hs:
        d = os.path.join(HWMON, h)
        driver = read_str(os.path.join(d, "name")) or h
        inst_count[driver] = inst_count.get(driver, 0) + 1
        idx = inst_count[driver]
        title = NAMES.get(driver, driver)
        inst = f"{title} #{idx}" if driver in ("spd5118", "amdgpu") else title
        try:
            files = sorted(os.listdir(d))
        except OSError:
            continue
        for f in files:
            if not f.startswith("temp") or not f.endswith("_input"):
                continue
            key = f[:-6]
            cur = read(os.path.join(d, f))
            if cur is None:
                continue
            label = read_str(f"{d}/{key}_label") or "Temp"
            hi = read(f"{d}/{key}_max")
            crit = read(f"{d}/{key}_crit")
            if "tsensor" in label.lower():
                tsensors.append(("tsensor", "TSENSOR", label, cur, hi, crit))
                continue
            if driver not in WANT:
                continue
            if driver == "amdgpu" and label.lower() not in GPU_LABELS:
                continue
            if driver == "nct6799" and label not in BOARD_LABELS:
                continue
            out.append((driver, inst, label, cur, hi, crit))
    out.extend(tsensors)
    out.sort(key=lambda r: ORDER.index(r[0]) if r[0] in ORDER else 99)
    return out


def color_for(v, hi, crit):
    if crit is not None and v >= crit - 5:
        return "r"
    if hi is not None and v >= hi - 3:
        return "r" if v >= hi else "y"
    return "g"


def bar(v, hi, crit, width=24):
    """Bar scaled 0..(crit or hi or 100), marker at high threshold."""
    scale = crit if crit is not None else (hi if hi is not None else 100.0)
    frac = max(0.0, min(1.0, v / scale)) if scale > 0 else 0
    n = int(frac * width)
    col = color_for(v, hi, crit)
    fill = "█" * n
    rest = "░" * (width - n)
    return f"{FG[col]}{fill}{DIM}{rest}{RESET}"


def render(sensors, stats, hist, t0):
    try:
        W = max(os.get_terminal_size().columns, 78)
    except OSError:  # not a tty (pipe/cron)
        W = 78
    lines = []
    up = time.time() - t0
    lines.append(
        f"{BOLD}{FG['c']}⚡ TEMPWATCH{RESET}  {socket.gethostname()}  "
        f"{DIM}up {int(up//60)}m{int(up%60):02d}s · {time.strftime('%H:%M:%S')}{RESET}"
    )
    lines.append(DIM + "─" * min(W, 78) + RESET)
    lines.append(f"{'Sensor':<34}{'Now':>7}{'Min':>7}{'Max':>7}  {'Limit':>6}  Bar")
    lines.append(DIM + "─" * min(W, 78) + RESET)
    last_sec = None
    for sec, label, key, cur, hi, crit in sensors:
        ident = f"{sec}|{label}|{key}"
        st = stats.setdefault(ident, [cur, cur])
        st[0], st[1] = min(st[0], cur), max(st[1], cur)
        if sec != last_sec:
            lines.append(f"{BOLD}{FG['w']}{sec_name(sec)}{RESET}")
            last_sec = sec
        col = color_for(cur, hi, crit)
        lim = f"{hi:.0f}°" if hi is not None else (f"{crit:.0f}°!" if crit is not None else "  -")
        name = f"{label} \u00b7 {key}" if key not in ("Temp", "Composite") else label
        lines.append(
            f"  {name:<32}{FG[col]}{cur:>6.1f}°{RESET}"
            f"{DIM}{st[0]:>6.1f}°{st[1]:>6.1f}°{RESET}{DIM}{lim:>6}{RESET}  {bar(cur, hi, crit)}"
        )
    if not sensors:
        lines.append("  no supported sensors found — see README (hwmon drivers)")
        return "\n".join(lines)
    # sparkline of hottest sensor over time
    hot = max(sensors, key=lambda r: r[3])
    ident = f"{hot[0]}|{hot[1]}|{hot[2]}"
    series = hist.get(ident, ())
    if len(series) > 2:
        lines.append("")
        lines.append(sparkline(series, f"hottest: {hot[1]} {hot[2]}"))
    return "\n".join(lines)


def sec_name(driver):
    return NAMES.get(driver, driver)


def sparkline(series, title, width=60):
    glyphs = "▁▂▃▄▅▆▇█"
    s = list(series)[-width:]
    lo, hi = min(s), max(s)
    rng = (hi - lo) or 1.0
    graph = "".join(glyphs[int((v - lo) / rng * 7)] for v in s)
    col = "r" if hi >= 80 else ("y" if hi >= 65 else "c")
    return f"{FG[col]}{graph}{RESET} {DIM}{title} [{lo:.1f}–{hi:.1f}°]{RESET}"


def main():
    ap = argparse.ArgumentParser(description="HWiNFO-style live sensor dashboard")
    ap.add_argument("--interval", type=float, default=1.0)
    ap.add_argument("--once", action="store_true", help="print one snapshot and exit")
    ap.add_argument("--all", action="store_true", help="include NIC/EC/battery hwmon devices")
    a = ap.parse_args()

    stats, hist, t0 = {}, {}, time.time()
    if a.once:
        sensors = discover(a.all)
        for sec, label, key, cur, *_ in sensors:
            stats[f"{sec}|{label}|{key}"] = [cur, cur]
        print(render(sensors, stats, hist, t0))
        return

    try:
        while True:
            sensors = discover(a.all)
            for sec, label, key, cur, *_ in sensors:
                hist.setdefault(f"{sec}|{label}|{key}", deque(maxlen=180)).append(cur)
            frame = render(sensors, stats, hist, t0)
            sys.stdout.write("\033[2J\033[H" + frame + "\n")
            sys.stdout.flush()
            time.sleep(a.interval)
    except KeyboardInterrupt:
        print(f"\n{DIM}min/max legend: session stats since launch{RESET}")


if __name__ == "__main__":
    main()
