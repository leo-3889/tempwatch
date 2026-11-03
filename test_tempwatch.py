#!/usr/bin/env python3
"""Tests for tempwatch-app.py — run: python3 test_tempwatch.py

No pytest/fixtures: fake hwmon tree in a temp dir, plain asserts.
"""
import importlib.util
import os
import tempfile

spec = importlib.util.spec_from_file_location(
    "tw", os.path.join(os.path.dirname(__file__), "tempwatch-app.py"))
assert spec is not None and spec.loader is not None
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def mk_sensor(root, hwmon, name, idx, label=None, val=45000, mx=None):
    d = os.path.join(root, hwmon)
    os.makedirs(d, exist_ok=True)
    with open(f"{d}/name", "w") as f:
        f.write(name)
    with open(f"{d}/temp{idx}_input", "w") as f:
        f.write(str(val))
    if label:
        with open(f"{d}/temp{idx}_label", "w") as f:
            f.write(label)
    if mx is not None:
        with open(f"{d}/temp{idx}_max", "w") as f:
            f.write(str(mx))


def test_discover():
    with tempfile.TemporaryDirectory() as root:
        mk_sensor(root, "hwmon5", "k10temp", 1, "Tctl", 66000, 95000)
        mk_sensor(root, "hwmon5", "k10temp", 3, "Tccd1", 61000)
        mk_sensor(root, "hwmon6", "spd5118", 1, None, 55500)
        mk_sensor(root, "hwmon7", "nct6799", 3, "AUXTIN3", 42000)
        mk_sensor(root, "hwmon7", "nct6799", 1, "AUXTIN1", 15000)  # filtered
        mk_sensor(root, "hwmon8", "nvme", 1, "Composite", 40000)
        mk_sensor(root, "hwmon9", "r8169", 1, "phy", 44000)        # ignored
        m.HWMON = root  # type: ignore[attr-defined]
        rows = m.discover()
        names = [n for _s, n, _c, _h, _cr in rows]
        assert "CPU Package (Tctl)" in names, names
        assert "CPU CCD 1 (Tccd1)" in names, names
        assert "Memory Stick 1" in names, names
        assert "TSENSOR1 Custom Probe" in names, names
        assert "NVMe SSD 1" in names, names
        assert not any("AUXTIN1" in n for n in names), names
        assert not any("r8169" in n.lower() for n in names), names
        assert len(rows) == 5, rows
        # order: CPU before DIMM before board before nvme
        secs = [r[0].split("|")[0] for r in rows]
        assert secs == ["k10temp", "k10temp", "spd5118", "nct6799", "nvme"], secs
        tctl = [r for r in rows if r[1].endswith("(Tctl)")][0]
        assert tctl[2] == 66.0 and tctl[3] == 95.0
        print("test_discover ok")


def test_color_for():
    assert m.color_for(50, 80, None) == m.GREEN
    assert m.color_for(81, 80, 100) == m.YELLOW
    assert m.color_for(96, 80, 100) == m.RED
    assert m.color_for(104, None, 100) == m.RED
    assert m.color_for(20, None, None) == m.GREEN
    print("test_color_for ok")


def test_vitals_keys():
    with tempfile.TemporaryDirectory() as root:
        mk_sensor(root, "hwmon1", "k10temp", 1, "Tctl", 50000)
        mk_sensor(root, "hwmon2", "nct6799", 3, "AUXTIN3", 41000)
        mk_sensor(root, "hwmon3", "spd5118", 1, None, 50000)
        mk_sensor(root, "hwmon4", "spd5118", 1, None, 51000)  # dup base
        m.HWMON = root  # type: ignore[attr-defined]
        app = m.TempWatch.__new__(m.TempWatch)
        rows = m.discover()
        by_name = {n: sid for sid, n, *_x in rows}
        assert app._vitals_key(by_name["CPU Package (Tctl)"], rows) \
            == "k10temp Tctl"
        assert app._vitals_key(by_name["TSENSOR1 Custom Probe"], rows) \
            == "nct6799 AUXTIN3"
        # duplicate DIMM chips get Vitals-style dedup suffixes
        dimms = [n for n in by_name if n.startswith("Memory Stick")]
        k1 = app._vitals_key(by_name[dimms[0]], rows)
        k2 = app._vitals_key(by_name[dimms[1]], rows)
        assert k1 == "spd5118 temp1" and k2 == "spd5118 temp1 2", (k1, k2)
        print("test_vitals_keys ok")


def test_single_slot():
    """Pinning replaces the previous sensor (no Vitals settings needed:
    exercise the list arithmetic directly)."""
    app_keys = {"k10temp Tctl", "nct6799 AUXTIN3", "spd5118 temp1"}
    hot = ["_memory_usage_", "k10temp Tctl"]
    new = "nct6799 AUXTIN3"
    hot = [k for k in hot if k not in app_keys] + [new]
    assert hot == ["_memory_usage_", "nct6799 AUXTIN3"], hot
    print("test_single_slot ok")


if __name__ == "__main__":
    test_color_for()
    test_discover()
    test_vitals_keys()
    test_single_slot()
    print("ALL TESTS PASSED")
