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


def test_activate_builds_ui():
    """Structural guard: a method def inside do_activate silently truncates
    it (real bug once: UI-building code became dead code)."""
    import ast as _ast
    with open(os.path.join(os.path.dirname(__file__), "tempwatch-app.py")) as f:
        src = f.read()
    tree = _ast.parse(src)
    cls = next(n for n in tree.body
               if isinstance(n, _ast.ClassDef) and n.name == "TempWatch")
    act = next(n for n in cls.body
               if isinstance(n, _ast.FunctionDef) and n.name == "do_activate")
    inner = [n for n in _ast.walk(act)
             if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef))
             and n is not act]
    assert not inner, f"nested defs inside do_activate: {[f.name for f in inner]}"
    # and do_activate must end with showing the window
    last = act.body[-1]
    assert "show_all" in _ast.unparse(last), _ast.unparse(last)
    print("test_activate_builds_ui ok")


def test_minimize_button_wired():
    """do_activate must give the window a custom titlebar whose − button
    hides the window (GNOME SSD minimize is a Wayland no-op)."""
    import ast as _ast
    src_path = os.path.join(os.path.dirname(__file__), "tempwatch-app.py")
    with open(src_path) as f:
        src = f.read()
    tree = _ast.parse(src)
    cls = next(n for n in tree.body
               if isinstance(n, _ast.ClassDef) and n.name == "TempWatch")
    act = next(n for n in cls.body
               if isinstance(n, _ast.FunctionDef) and n.name == "do_activate")
    code = _ast.unparse(act)
    assert "set_titlebar" in code, "custom titlebar (CSD) required"
    hits = [n for n in _ast.walk(act)
            if isinstance(n, _ast.Call)
            and _ast.unparse(n.func).endswith("connect")
            and len(n.args) >= 2
            and isinstance(n.args[0], _ast.Constant)
            and n.args[0].value == "clicked"
            and "win.hide()" in _ast.unparse(n)]
    assert hits, "minimize button must connect clicked -> win.hide()"
    print("test_minimize_button_wired ok")


def test_on_state_minimize():
    """Minimize hides the window; other states don't touch visibility."""
    class Ev:
        def __init__(self, st): self.new_window_state = st
    class Win:
        def __init__(self): self.hidden = False
        def hide(self): self.hidden = True
    app = m.TempWatch.__new__(m.TempWatch)
    w = Win()
    app._on_state(w, Ev(m.Gdk.WindowState.ICONIFIED))
    assert w.hidden, "minimize must hide the window"
    w2 = Win()
    app._on_state(w2, Ev(m.Gdk.WindowState.FOCUSED))
    assert not w2.hidden, "focus must not hide"
    print("test_on_state_minimize ok")


def test_discovery_robustness():
    """Non-numeric input skipped, dir without name ignored, hwmon with zero
    readable temps yields no rows, _max missing falls back to _crit."""
    with tempfile.TemporaryDirectory() as root:
        # non-numeric temp file -> skipped
        mk_sensor(root, "hwmon1", "spd5118", 1, None, mx=70000)
        with open(os.path.join(root, "hwmon1", "temp1_input"), "w") as f:
            f.write("not-a-number")
        # dir without 'name' -> ignored entirely
        d = os.path.join(root, "hwmon2")
        os.makedirs(d)
        with open(f"{d}/temp1_input", "w") as f:
            f.write("45000")
        # label but no input -> zero rows for this hwmon
        d = os.path.join(root, "hwmon3")
        os.makedirs(d)
        with open(f"{d}/name", "w") as f:
            f.write("k10temp")
        with open(f"{d}/temp1_label", "w") as f:
            f.write("Tctl")
        # _crit present, _max absent -> row carries crit, max None
        d = os.path.join(root, "hwmon4")
        os.makedirs(d)
        with open(f"{d}/name", "w") as f:
            f.write("k10temp")
        with open(f"{d}/temp1_input", "w") as f:
            f.write("66500")
        with open(f"{d}/temp1_label", "w") as f:
            f.write("Tctl")
        with open(f"{d}/temp1_crit", "w") as f:
            f.write("95000")
        m.HWMON = root  # type: ignore[attr-defined]
        rows = m.discover()
        assert len(rows) == 1, rows
        sid, name, cur, hi, crit = rows[0]
        assert name == "CPU Package (Tctl)", name
        assert cur == 66.5 and hi is None and crit == 95.0, (cur, hi, crit)
        # tick() renders the crit as the Limit cell when _max is missing
        app = m.TempWatch.__new__(m.TempWatch)
        app.win = object()
        app.stats, app.hist, app.store = {}, {}, []
        app.stamp = type("L", (), {"set_text": lambda self, t: None})()
        app._update_indicator = lambda _r: None  # type: ignore[method-assign]
        assert app.tick() is True
        assert app.store[0][2] == "66.5°", app.store[0]   # 66500 -> 66.5
        assert app.store[0][5] == "95°", app.store[0]     # limit falls back to crit
        print("test_discovery_robustness ok")


def test_nvme_naming():
    """nvme: 'NVMe SSD N' display, Composite-only keep, phantom Sensor N
    labels filtered, Composite never a display name."""
    with tempfile.TemporaryDirectory() as root:
        mk_sensor(root, "hwmon1", "nvme", 1, "Composite", 40000)
        mk_sensor(root, "hwmon2", "nvme", 1, "Composite", 41000)
        mk_sensor(root, "hwmon3", "nvme", 1, "Sensor 1", 42000)  # phantom
        mk_sensor(root, "hwmon4", "nvme", 1, "Sensor 2", 43000)  # phantom
        m.HWMON = root  # type: ignore[attr-defined]
        names = [n for _s, n, *_x in m.discover()]
        assert names == ["NVMe SSD 1", "NVMe SSD 2"], names
        assert not any("Composite" in n for n in names), names
        assert not any("Sensor" in n for n in names), names
        print("test_nvme_naming ok")


def test_cpu_naming():
    """Exact strings from CPU_NAMES / CORETEMP_NAMES in the code."""
    with tempfile.TemporaryDirectory() as root:
        mk_sensor(root, "hwmon1", "k10temp", 1, "Tctl", 60000)
        mk_sensor(root, "hwmon2", "coretemp", 1, "Package id 0", 55000)
        mk_sensor(root, "hwmon2", "coretemp", 2, "Core 0", 57000)
        m.HWMON = root  # type: ignore[attr-defined]
        names = [n for _s, n, *_x in m.discover()]
        assert "CPU Package (Tctl)" in names, names
        assert "CPU Package" in names, names          # 'Package id 0' mapped
        assert "CPU · Core 0" in names, names         # unmapped core: section · label
        print("test_cpu_naming ok")


def test_vitals_keys_nvme_and_dedup():
    """nvme vitals key includes device/model; dup base keys get ' 2',' 3';
    TSENSOR1 row key is 'nct6799 AUXTIN3'."""
    with tempfile.TemporaryDirectory() as root:
        mk_sensor(root, "hwmon1", "nvme", 1, "Composite", 40000)
        os.makedirs(os.path.join(root, "hwmon1", "device"))
        with open(os.path.join(root, "hwmon1", "device", "model"), "w") as f:
            f.write("WDS100T2B0A-00SM50 \n")
        mk_sensor(root, "hwmon2", "nct6799", 3, "AUXTIN3", 41000)
        for i, h in enumerate(("hwmon3", "hwmon4", "hwmon5")):
            mk_sensor(root, h, "spd5118", 1, None, 50000 + i)
        m.HWMON = root  # type: ignore[attr-defined]
        app = m.TempWatch.__new__(m.TempWatch)
        rows = m.discover()
        by_name = {n: sid for sid, n, *_x in rows}
        k = app._vitals_key(by_name["NVMe SSD 1"], rows)
        assert k == "nvme WDS100T2B0A-00SM50 temp1", k
        assert app._vitals_key(by_name["TSENSOR1 Custom Probe"], rows) \
            == "nct6799 AUXTIN3"
        dimms = sorted(n for n in by_name if n.startswith("Memory Stick"))
        keys = [app._vitals_key(by_name[n], rows) for n in dimms]
        assert keys == ["spd5118 temp1", "spd5118 temp1 2",
                        "spd5118 temp1 3"], keys
        print("test_vitals_keys_nvme_and_dedup ok")


def test_window_structure():
    """AST guards: exactly one _show_window def; do_activate has no nested
    defs, ends with show_all, and its delete-event wiring calls self.quit."""
    import ast as _ast
    with open(os.path.join(os.path.dirname(__file__), "tempwatch-app.py")) as f:
        tree = _ast.parse(f.read())
    cls = next(n for n in tree.body
               if isinstance(n, _ast.ClassDef) and n.name == "TempWatch")
    shows = [n for n in cls.body if isinstance(n, _ast.FunctionDef)
             and n.name == "_show_window"]
    assert len(shows) == 1, f"expected 1 _show_window def, got {len(shows)}"
    act = next(n for n in cls.body
               if isinstance(n, _ast.FunctionDef) and n.name == "do_activate")
    inner = [n for n in _ast.walk(act)
             if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef))
             and n is not act]
    assert not inner, f"nested defs inside do_activate: {[f.name for f in inner]}"
    assert "show_all" in _ast.unparse(act.body[-1]), _ast.unparse(act.body[-1])
    dels = [n for n in _ast.walk(act)
            if isinstance(n, _ast.Call) and _ast.unparse(n.func).endswith("connect")
            and n.args and _ast.unparse(n.args[0]) == "'delete-event'"]
    assert dels, "no delete-event connection in do_activate"
    assert any("self.quit" in _ast.unparse(n) for n in dels), \
        "delete-event wiring must reference self.quit"
    print("test_window_structure ok")


def test_sources_invariants():
    """Every SOURCES entry has title/labels/mapped_only; mapped_only=True
    drivers drop unmapped raw labels (AUXTIN1/PCI/SN -> nothing, only
    mapped AUXTIN3 emits a row)."""
    for drv, src in m.SOURCES.items():
        assert "title" in src and "labels" in src and "mapped_only" in src, drv
        assert callable(src["title"]), drv
        assert isinstance(src["mapped_only"], bool), drv
        assert src["labels"] is None or isinstance(src["labels"], dict), drv
    with tempfile.TemporaryDirectory() as root:
        for idx, lbl in ((1, "AUXTIN1"), (2, "PCI"), (7, "SN"), (3, "AUXTIN3")):
            mk_sensor(root, "hwmon1", "nct6799", idx, lbl, 40000 + idx)
        m.HWMON = root  # type: ignore[attr-defined]
        rows = m.discover()
        names = [n for _s, n, *_x in rows]
        assert names == ["TSENSOR1 Custom Probe"], names
        print("test_sources_invariants ok")


if __name__ == "__main__":
    test_color_for()
    test_discover()
    test_vitals_keys()
    test_single_slot()
    test_activate_builds_ui()
    test_on_state_minimize()
    test_minimize_button_wired()
    test_discovery_robustness()
    test_nvme_naming()
    test_cpu_naming()
    test_vitals_keys_nvme_and_dedup()
    test_window_structure()
    test_sources_invariants()
    print("ALL TESTS PASSED")
