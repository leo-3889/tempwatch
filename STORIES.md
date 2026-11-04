# ⚡ TempWatch — Product Backlog (User Stories)

Source of truth: `tempwatch-app.py` (GTK app, 513 lines), `tempwatch.py` (TUI, 215 lines),
`test_tempwatch.py` (14 tests, all passing: 13 test functions + module load of
`tempwatch-app.py` via importlib asserted at import), `install.sh`,
`uninstall.sh`, `packaging/build_deb.sh`, `.github/workflows/release.yml`, `README.md`.

AC evidence tags:
- ✅ `<test-name>` — proven by an automated test in `test_tempwatch.py`
- TODO: `test <name>` — behavior present in code, needs an automated test
- MANUAL — verifiable only by hand on a GNOME 50 session (Wayland/Xwayland)

Status tags: `[implemented@file:line]` per story; no citation = `[guess]`.

---

## S1 — Sensor table: friendly names, sparklines, min/max, limit

As a **Ryzen/ASUS desktop user** I want a table of every temperature sensor with a plain-language name, live color-coded value, session min/max, firmware limit, and a 3-minute sparkline so that I can spot a overheating component without reading raw `temp1_input` labels.

Implemented: `discover()` tempwatch-app.py:103-147, `color_for()` :155-159, `SparkRenderer` :163-189, columns :427-437, `tick()` :482-509.

Acceptance Criteria:
1. REQ-S1-01. The window (760×500 default, title "TempWatch", role `tempwatch-main`) contains a TreeView with exactly the columns Sensor, Now, Min, Max, Limit, and "Temperature over time (last 3 min)" (expanded, min 140px). — TODO: test `test_table_columns_built` (ast/structural assert on the `("Sensor",…),("Now",…),…` tuple + spark column title in `do_activate`)
2. REQ-S1-02. `k10temp Tctl` displays as "CPU Package (Tctl)", `Tccd1` as "CPU CCD 1 (Tccd1)", `spd5118` instance 1 as "Memory Stick 1", `nct6799 AUXTIN3` as "TSENSOR1 Custom Probe", `nvme Composite` as "NVMe SSD 1". — ✅ test_discover
3. REQ-S1-03. The Now cell is markup-colored `#2ec27e`/`#e5a50a`/`#c01c28` per `color_for(v, hi, crit)`: red when `v >= crit-5`, red when `v >= hi` and `v >= crit-15`, yellow when `v >= hi`, green otherwise. — ✅ test_color_for
4. REQ-S1-04. Min/Max columns show per-sensor session extremes accumulated from first tick (keyed by `driver|hwmon|tempN`, survives sensor reordering). — TODO: test `test_tick_updates_session_stats`
5. REQ-S1-05. Limit column shows `tempN_max` rounded (`NN°`), falling back to `tempN_crit`, else literal `—`. — ✅ test_discovery_robustness (drives `app.tick()` on a fake hwmon with `_crit` set and `_max` absent → Limit cell renders `95°`; the `—` branch is exercised in the same run's store row for sensors with no thresholds).
6. REQ-S1-06. Each row's sparkline renders its last 180 one-second samples (`deque(maxlen=HISTORY)`, HISTORY=180), auto-scaled to the series min/max with a 4.0°C minimum range, colored by the row's threshold color; rows with <2 samples draw nothing. — TODO: test `test_spark_series_window_and_scale`
7. REQ-S1-07. Header shows `⚡ TempWatch — <hostname>` and an `updated HH:MM:SS` stamp refreshed each second; footer reads "min/max are session values · limits from firmware · chart auto-scales per sensor". — MANUAL
8. REQ-S1-08. Rows disappearing from hwmon (module unload, USB probe unplug) vanish from the store and their history is freed within 1 s. — TODO: test `test_tick_prunes_stale_rows`

Tests: `test_discover` (AC2), `test_color_for` (AC3), `test_discovery_robustness` (AC5, calls `app.tick()`), `test_activate_builds_ui` (guards `do_activate` has no nested defs and ends with `show_all` — partial AC1).

---

## S2 — Tray/top-bar icon present from startup (Ayatana AppIndicator)

As a **GNOME user with a background monitor** I want the tray icon to exist the moment the app starts (before/without any window) so that I always have an entry point and a live readout in the top bar.

Implemented: `do_startup` tempwatch-app.py:346-351 (creates indicator, Solaar-style), `_make_indicator` :316-336, `_update_indicator` :377-387, `do_shutdown` :362-365.

Acceptance Criteria:
1. REQ-S2-01. `do_startup` calls `_make_indicator()` (AyatanaAppIndicator3 0.1, id `dev.leo.tempwatch`, ACTIVE) before/independent of `do_activate`; icon visible in the top bar immediately after launch, before first window interaction. — MANUAL
2. REQ-S2-02. On a tray-less desktop (no Ayatana schema) indicator creation fails inside `contextlib.suppress(Exception)` and the app still starts window-only with exit-clean. — TODO: test `test_indicator_failure_degrades_to_window_only`
3. REQ-S2-03. Indicator label = `<hottest>°` (rounded) with tooltip `<name> · <cur>°` and title `TempWatch — hottest <name> <cur>°`; the pinned sensor (S4) outranks the true hottest; `set_label` is called only when `(round(temp), name)` changes. — TODO: test `test_update_indicator_selects_pinned_then_hottest`
4. REQ-S2-04. On app quit the indicator is set to `IndicatorStatus.NEVER` (2) so the icon disappears from the top bar. — MANUAL

Tests: none covering the indicator — AC1/4 manual, AC2/3 need new tests.

---

## S3 — Right-click sensor row → single-slot top-bar pin (GNOME Vitals)

As a **Vitals user** I want to right-click any sensor row and pick "Show value in taskbar" so that exactly one sensor I choose appears in the GNOME top bar via Vitals' `hot-sensors`, with zero Vitals configuration on my side.

Implemented: `_on_row_click` tempwatch-app.py:299-314, `_pin_vitals` :275-297, `_vitals_key` :231-250, `_vitals_key_base` :252-262, `_open_vitals` :213-229.

Acceptance Criteria:
1. REQ-S3-01. Right-click (button 3) on a row pops a menu with the single item "Show value in taskbar"; left-click and clicks on empty rows do nothing; the menu only appears when the Vitals schema was found. — MANUAL
2. REQ-S3-02. The pin key equals Vitals v86's display key `<chipname> <label>` with `Package id`→`CPU` (e.g. `k10temp Tctl`, `nct6799 AUXTIN3`); labelless sensors use the sysfs key (`spd5118 temp1`); NVMe uses `<chip> <model> <key>`. — ✅ test_vitals_keys (k10temp/nct6799/spd5118 keys), ✅ test_vitals_keys_nvme_and_dedup (NVMe `nvme WDS100T2B0A-00SM50 temp1`, both call `app._vitals_key`)
3. REQ-S3-03. Duplicate base keys get Vitals-style dedup suffixes in enumeration order: first `spd5118 temp1`, second `spd5118 temp1 2`, third `spd5118 temp1 3`. — ✅ test_vitals_keys, ✅ test_vitals_keys_nvme_and_dedup (three-DIMM ` 2`/` 3` chain via `app._vitals_key`)
4. REQ-S3-04. After pinning, `gsettings get org.gnome.shell.extensions.vitals hot-sensors` contains exactly one app-produced key — every key in the app's key-set is removed first, the chosen key appended; foreign keys (e.g. `_memory_usage_`, user-curated keys for drivers TempWatch doesn't know) are preserved verbatim. — TODO: test `test_pin_vitals_sweeps_app_keys` (drive `app._pin_vitals` with a mock-free stub settings object recording `get_strv`/`set_strv`/`get_int`/`set_int`/`get_boolean`/`set_boolean`, fake `self.vitals`; assert appended key + preserved foreign keys). `test_single_slot` does NOT count: it hand-replicates the sweep list arithmetic inside the test and never calls `_pin_vitals`.
5. REQ-S3-05. On pin, `position-in-panel` is set to `2` (right, next to the tray) only if it currently differs; a user-set value of 2 is not rewritten. — TODO: test `test_pin_sets_panel_position_once`
6. REQ-S3-06. After writing `hot-sensors`, the app toggles `show-temperature` off and back on (v86 has no `changed::hot-sensors` handler) so the panel repaints without a shell reload, leaving `show-temperature` at its original value. — TODO: test `test_show_temperature_nudge_restores_value`
7. REQ-S3-07. Vitals schema is resolved from the extension dir (`~/.local/share` then `/usr/share`, `Vitals@CoreCoding.com/schemas/gschemas.compiled`) so pinning works from a normal (non-extension) process; absent schema → right-click is inert, app runs. — MANUAL
8. REQ-S3-08. On a GNOME 50 session the pinned value is visible in the top bar within 1 s of the click, no shell reload needed. — MANUAL

Tests: `test_vitals_keys` + `test_vitals_keys_nvme_and_dedup` (AC2, AC3). AC4-6 have no valid automated coverage — `test_single_slot` replicates the arithmetic in-test without calling app code.

---

## S4 — Pin persistence and single-slot sweep

As a **returning user** I want my pinned sensor to survive app restarts, and app-owned keys to be swept on unpin, so that the top bar never accumulates stale TempWatch sensors and never shows more than one.

Implemented: load tempwatch-app.py:206-209, `_save_pin` :340-347, sweep in `_pin_vitals` :286-288.

Acceptance Criteria:
1. REQ-S4-01. Pinning writes `{"row": "<driver>|<hwmon>|<tempN>"}` to `~/.config/tempwatch-pin.json` (mkdir -p `~/.config`); a missing/unreadable/corrupt file is suppressed and leaves `pinned=None` (app must not crash on a garbage file). — TODO: test `test_pin_file_roundtrip_and_corruption`
2. REQ-S4-02. On startup the pinned row is restored from that file and drives the indicator label priority (REQ-S2-03). — TODO: test `test_startup_restores_pinned_row`
3. REQ-S4-03. [removed@f9f90bd] — the "Show hottest sensor" unpin affordance and `_unpin` were deleted; only the pin-write and app-key sweep survive in `_pin_vitals` :286-288.
4. REQ-S4-04. At any moment `hot-sensors` contains ≤1 key from the app's key-set (single slot — a second pin replaces the first; sweep-before-append guarantees it even if a stale key from a previous session lingers). — TODO: test `test_pin_vitals_sweeps_app_keys` (shared with REQ-S3-04: pin A then pin B via `app._pin_vitals`, assert stub `set_strv` payload has ≤1 app key)

Tests: none valid — `test_single_slot` computes its own `hot = [k for k in hot if k not in app_keys] + [new]` list in-test and never invokes `_pin_vitals`; it proves the *idea*, not the code.

---

## S5 — Minimize (−) hides the window, app keeps running

As a **user who wants the monitor out of the way** I want the minimize button to hide the window completely (no minimized-window ghost, no taskbar entry) while the app keeps sampling in the tray, so that the top-bar readout stays live.

Implemented: `_on_state` tempwatch-app.py:462-468, custom titlebar with − button wired `clicked → win.hide()` :392-400 (`set_titlebar` :413), `set_skip_taskbar_hint`/`set_skip_pager_hint` :420-421, per-second `tick` continues on hidden window :495.

Acceptance Criteria:
1. REQ-S5-01. On the `window-state-event` ICONIFIED transition the handler calls `win.hide()` and returns `False` (no minimized state lingers); FOCUSED/other states leave visibility untouched. — ✅ test_on_state_minimize
2. REQ-S5-02. After minimize the process stays alive (`pgrep -f tempwatch-app.py` = 1), the tick keeps updating the indicator, and no window exists in the GNOME overview / `wmctrl -l` (Wayland: window count via Looking Glass). — MANUAL
3. REQ-S5-03. Tray "Show TempWatch" restores: `deiconify` + `show` + `present` (:338-343), window regains focus. — MANUAL
4. REQ-S5-04. The window's custom titlebar ships its own − button (decoration layout drops the default minimize, `"icon:maximize,close"`) wired `clicked → win.hide()`, so minimize works on Wayland where the SSD minimize is a no-op. — ✅ test_minimize_button_wired (ast: `set_titlebar` in `do_activate` + a `"clicked"` connection whose body contains `win.hide()`)

Tests: `test_on_state_minimize` (AC1, calls `app._on_state`), `test_minimize_button_wired` (AC4, ast guard on `do_activate`).

---

## S6 — Close (X) quits the app

As a **user finishing a session** I want the window's close button to fully quit the app so that no invisible poller and no tray icon remain.

Implemented: `delete-event` tempwatch-app.py:412 — `lambda *_a: (self.quit(), False)[1]`; `do_shutdown` indicator NEVER :362-365.

Acceptance Criteria:
1. REQ-S6-01. Clicking the (X) (delete-event) invokes `self.quit()` and the handler returns `False` (GTK proceeds with destruction); app `do_shutdown` runs, indicator set NEVER. — TODO: test `test_delete_event_quits` (invoke the connected lambda on a stub with `quit()`, assert called and return `False`)
2. REQ-S6-02. After close: `pgrep -f tempwatch-app.py` = 0 and the tray icon is gone from the top bar. — MANUAL

Tests: `test_window_structure` ast-guards that `do_activate` connects `delete-event` and the wiring references `self.quit` (structural half of AC1); the runtime contract (handler returns `False`, process exits) needs `test_delete_event_quits`.

---

## S7 — Relaunch while running = present, single instance

As an **apps-grid clicker** I want launching TempWatch again to surface the existing window instead of opening a second app, so that exactly one sampler, one tray icon, and one window exist.

Implemented: `super().__init__(application_id=APP_ID)` tempwatch-app.py:197 — default flags (0), NON_UNIQUE not passed; `do_activate` reuse path :389-394.

Acceptance Criteria:
1. REQ-S7-01. The `Gtk.Application` is constructed with no `flags=` argument (default `FLAGS_NONE`/0), so GApplication D-Bus single-instance applies; `Gio.ApplicationFlag.NON_UNIQUE` appears nowhere in the source. — TODO: test `test_no_non_unique_flag` (ast: `TempWatch.__init__` super() call has no `flags` keyword)
2. REQ-S7-02. A second activation with `self.win` set calls `deiconify` + `show` + `present` and returns without constructing a new window (window count stays 1, exactly one `tick` timer running — `do_activate` returns before `GLib.timeout_add_seconds`). — TODO: test `test_activate_reuses_existing_window`
3. REQ-S7-03. Launching from the app grid (or a second terminal run) while running surfaces the existing window focused within ~1 s; `pgrep -cf tempwatch-app.py` counts a single persistent process (second process exits after forwarding activation). — MANUAL

Tests: none — both new tests listed.

---

## S8 — Tray menu: Show TempWatch / Quit

As a **tray user** I want a three-item menu on the indicator so that I can reach the window, clear the pin, or exit without any other UI.

Implemented: `_make_indicator` menu tempwatch-app.py:323-336.

Acceptance Criteria:
1. REQ-S8-01. Indicator menu is exactly: "Show TempWatch" → `_show_window`, separator, "Quit" → `self.quit()` (`tempwatch-app.py:325-331`). — TODO: test `test_indicator_menu_labels` (construct menu against a stubbed indicator, assert item labels == ["Show TempWatch", "Quit"] + handlers)
2. REQ-S8-02. [removed@f9f90bd] — unpin menu entry deleted with `_unpin`.
3. REQ-S8-03. "Quit" terminates the process (`pgrep` → 0) and removes the indicator. — MANUAL

Tests: none — AC1/2 need new tests.

---

## S9 — Platform sensor registry (SOURCES): one entry per hwmon driver

As a **maintainer adding hardware** I want every platform's naming/filtering rules in one `SOURCES` table so that supporting a new hwmon driver is a single dict entry plus an `ORDER` position, not a code change.

Implemented: `SOURCES` tempwatch-app.py:61-79, `ORDER` :33, `discover()` :103-147, `gpu_title` :49-53; README "Extending to new platforms".

Acceptance Criteria:
1. REQ-S9-01. `SOURCES` covers exactly `k10temp, coretemp, spd5118, nct6799, asus, amdgpu, nvidia, nvme`, displayed in `ORDER` sequence (k10temp → coretemp → spd5118 → nct6799 → asus → amdgpu → nvidia → nvme). — ✅ test_discover (ordering assert `["k10temp","k10temp","spd5118","nct6799","nvme"]`)
2. REQ-S9-02. `nct6799` is `mapped_only`: `SYSTIN/CPUTIN/AUXTIN0/AUXTIN3/AUXTIN4` map to friendly names with `AUXTIN3` = "TSENSOR1 Custom Probe" (TSENSOR1 header on ASUS ProArt B850-CREATOR WIFI NEO); unmapped AUXTINs (e.g. AUXTIN1) are dropped. — ✅ test_discover
3. REQ-S9-03. `nvme` keeps `{"Composite"}` only — per-SSD non-composite sensors (e.g. a second temp labeled for a flash chip) never appear; composite name is the section title "NVMe SSD N". — ✅ test_nvme_naming (two Composite drives → exactly `["NVMe SSD 1", "NVMe SSD 2"]`; phantom `Sensor 1`/`Sensor 2` labels filtered; `Composite` never in names — calls `m.discover()`)
4. REQ-S9-04. GPU sources (`amdgpu`, `nvidia`) are `mapped_only` + `prefix`: section title from `product_name` sysfs (fallback `Graphics Adapter <idx>`), names `GPU · Core` / `GPU · Hotspot` / `GPU · Memory (GDDR)` (amdgpu edge/junction/mem) and Core/Memory/Hotspot (nvidia). — TODO: test `test_gpu_prefix_and_title_fallback`
5. REQ-S9-05. Drivers not in `SOURCES` (r8169, iwl_5000_series, battery…) produce zero rows. — ✅ test_discover (r8169 ignored)
6. REQ-S9-06. `k10temp` is `mapped_only` (Tctl/Tccd1/Tccd2 only; TDDOTCRITICAL-class entries dropped); `coretemp` maps "Package id 0"→"CPU Package" and keeps unmapped cores as `CPU · Core N`; `spd5118` keeps all labels as "Memory Stick <idx>". — ✅ test_cpu_naming (`Package id 0`→`CPU Package`, unmapped core → `CPU · Core 0`, via `m.discover()`), ✅ test_sources_invariants (every `SOURCES` entry has title/labels/mapped_only; `mapped_only` driver nct6799 drops unmapped AUXTIN1/PCI/SN — calls `m.discover()`)
7. REQ-S9-07. On real hardware (ProArt B850-CREATOR WIFI NEO): the TSENSOR1 header reading appears as "TSENSOR1 Custom Probe"; `coretemp` path validated on Intel; `asus` (WMI) section "Motherboard (ASUS WMI)" appears only where asus_wmi exposes hwmon. — MANUAL
8. REQ-S9-08. A new platform works by adding one `SOURCES` entry + one `ORDER` item with zero changes to `discover()`; a sensor with an unreadable `_input` value is skipped, a missing `_label` defaults to "Temp" (name collapses to section title). — TODO: test `test_new_driver_entry_only`

Tests: `test_discover` (AC1, AC2, AC5), `test_nvme_naming` (AC3), `test_cpu_naming` + `test_sources_invariants` (AC6), `test_discovery_robustness` (AC8 non-numeric `_input` skipped).

---

## S10 — .deb release pipeline (tag → tests → deb → smoke → GitHub Release + SHA256SUMS)

As a **maintainer** I want pushing tag `v*` to run tests, build a `.deb`, smoke-test it in CI, and publish a GitHub Release with checksums so that users get installable, verifiable artifacts without manual steps.

Implemented: `.github/workflows/release.yml` (on: push tags `v*`; steps Tests → Build .deb → Source tarball → Smoke test → Checksums → softprops/action-gh-release@v2), `packaging/build_deb.sh`.

Acceptance Criteria:
1. REQ-S10-01. Pushing a `v*` tag runs `python3 test_tempwatch.py` as the first build step, before `packaging/build_deb.sh`; a failing test suite blocks the release (job fails). — TODO: test `test_release_workflow_step_order` (yaml: index of Tests < Build .deb < Smoke < Checksums < Release)
2. REQ-S10-02. `build_deb.sh <ver>` produces `dist/tempwatch_<ver>_all.deb` (Architecture: all; Depends: python3, python3-gi, gir1.2-gtk-3.0) containing `/usr/bin/tempwatch` (GTK app wrapper), `/usr/bin/tempwatch-tui` (TUI wrapper), `/usr/share/tempwatch/{tempwatch-app.py,tempwatch.py,tempwatch-icon.svg}`, the desktop entry (`Exec=/usr/bin/tempwatch`, `StartupWMClass=dev.leo.tempwatch`), and postinst/prerm managing `/etc/modules-load.d/{spd5118,nct6775}.conf`. — TODO: test `test_deb_layout` (dpkg-deb -c/-f assertions)
3. REQ-S10-03. CI smoke step installs the deb (`sudo apt install ./dist/*_all.deb`), ast-parses the installed `/usr/share/tempwatch/tempwatch-app.py`, asserts `command -v tempwatch tempwatch-tui` + both executables, and prints `dpkg -l tempwatch` (package row present). — TODO: test `test_smoke_step_present_in_workflow` (workflow contains `dpkg -l tempwatch` and `test -x /usr/bin/tempwatch-tui`)
4. REQ-S10-04. `dist/SHA256SUMS.txt` covers every artifact (deb + `.orig.tar.gz`) and all of `dist/*` are attached to the GitHub Release with generated release notes; deb version = tag minus leading `v`. — MANUAL (verify on the released release page)
5. REQ-S10-05. After `sudo dpkg -i` on a clean Ubuntu: `dpkg -l tempwatch` shows `ii`, `/etc/modules-load.d/nct6775.conf` exists; after `sudo apt remove tempwatch` (prerm) the confs are gone. — MANUAL

Tests: none — CI has no repo-side assertions yet; AC1-3 are the new proposed tests. The suite itself is gated by the workflow's Tests step (all 14 existing tests).

---

## S11 — install.sh / uninstall.sh (user-level install, module persistence, Vitals setup)

As a **new user** I want one script that installs deps, persists sensor kernel modules, registers the launcher, and wires up Vitals so that `./install.sh` alone gets me a working monitor + top-bar pin on Ubuntu 22.04+.

Implemented: `install.sh` (deps, modules, files, desktop entry), `uninstall.sh`. `[partial]` — Vitals install and `enabled-extensions` append are **not present in install.sh** (see Conflicts).

Acceptance Criteria:
1. REQ-S11-01. install.sh writes `spd5118` and `nct6775` to `/etc/modules-load.d/<m>.conf` and `modprobe`s each (non-fatal "not loadable" note when hardware absent); with no `sudo` the step is skipped with a printed note and the app still reads existing sensors. — MANUAL (on a test box: `cat /etc/modules-load.d/nct6775.conf`)
2. REQ-S11-02. If `python3 -c "import gi; gi.require_version('Gtk','3.0')"` fails, install.sh apt-installs `gir1.2-gtk-3.0` (with sudo) or aborts with `ERROR: python3-gi missing and no sudo available`, exit 1. — TODO: test `test_install_script_guards_deps` (grep script text for the guard + exit path)
3. REQ-S11-03. Installs to `~/.local/share/tempwatch/{tempwatch-app.py,tempwatch-icon.svg}`, `~/.local/bin/tempwatch` (TUI), icon `dev.leo.tempwatch.svg` in hicolor, desktop entry `dev.leo.tempwatch.desktop` (`StartupWMClass=dev.leo.tempwatch`, `Categories=System;Monitor;`), refreshes icon/desktop caches. — TODO: test `test_install_script_file_layout`
4. REQ-S11-04. `[pending]` install.sh installs GNOME Vitals v86 (e.g. via `v86`/extensions-app/`gnome-extensions install`) so the top-bar pin (S3) works out of the box. Not implemented — today the user must install Vitals manually. — TODO: test `test_install_script_installs_vitals`
5. REQ-S11-05. `[pending]` install.sh appends `Vitals@CoreCoding.com` to `gsettings get org.gnome.shell enabled-extensions` idempotently (no duplicate on re-run, existing entries preserved). Not implemented. — TODO: test `test_install_script_enables_vitals`
6. REQ-S11-06. uninstall.sh removes exactly the four user-level files (app dir, `~/.local/bin/tempwatch`, desktop entry, icon) and leaves `/etc/modules-load.d/{spd5118,nct6799→nct6775}.conf` in place, printing that note. — TODO: test `test_uninstall_script_targets`
7. REQ-S11-07. TempWatch appears in the GNOME apps grid after install; re-running install.sh twice leaves one desktop entry. — MANUAL

Tests: none — installers are untested shell.

---

## S12 — TUI dashboard (`tempwatch` user / `tempwatch-tui` deb)

As a **terminal user / ssh operator** I want `tempwatch` in the shell with the same sensor set, session min/max, threshold-colored bars, and a sparkline of the hottest sensor so that I can monitor without a GUI.

Implemented: `tempwatch.py` — `discover` :56-104, `bar` :118-126, `render` :129-173, `sparkline` :176-183, `main` args :186-191; wrappers `packaging/build_deb.sh` (`/usr/bin/tempwatch-tui`), `install.sh` (`~/.local/bin/tempwatch`).

Acceptance Criteria:
1. REQ-S12-01. `tempwatch --once` prints one frame (header `⚡ TEMPWATCH <host>`, Sensor/Now/Min/Max/Limit/Bar columns, per-sensor colored bar scaled 0→(crit∥hi∥100) with green/yellow/red thresholds) and exits 0 without entering the loop. — TODO: test `test_tui_once_snapshot`
2. REQ-S12-02. `--interval N` live mode clears/redraws every N s; `--all` admits hwmon devices outside `WANT` (NIC/EC/battery); Ctrl-C prints the "min/max legend: session stats since launch" line and exits. — MANUAL
3. REQ-S12-03. Frames include a `▁▂▃…█` sparkline of the hottest sensor (last ≤60 samples, range `[lo–hi]°`, red ≥80 / yellow ≥65 / cyan below) once ≥3 samples exist. — TODO: test `test_tui_sparkline`
4. REQ-S12-04. With no supported sensors the frame prints `no supported sensors found — see README (hwmon drivers)` and exits 0 (non-tty width falls back to 78). — TODO: test `test_tui_no_sensors_message`
5. REQ-S12-05. On the deb install `command -v tempwatch tempwatch-tui` finds both and `tempwatch-tui --once` runs from `/usr/bin` (proven in CI smoke, REQ-S10-03). — MANUAL

Tests: none — proposed tests listed; TUI `discover` has its own filter sets (`GPU_LABELS`, `BOARD_LABELS`, tsensor-by-label) separate from the app's `SOURCES`.

---

## S13 — README recipe for adding a sensor driver

As a **contributor targeting new hardware (Intel laptops, Raspberry Pi, USB hwmon probes)** I want the README to document the `SOURCES` schema so that I can add a platform from the docs alone, without reading `discover()` line by line.

Implemented: README.md "Extending to new platforms" (schema block + "Adding a platform = adding one SOURCES entry + its position in ORDER"); matches tempwatch-app.py:55-79.

Acceptance Criteria:
1. REQ-S13-01. README documents all five schema keys — `title(idx, hwmon_dir)`, `labels` (dict|None), `mapped_only`, `prefix`, `keep` — with their semantics, matching the keys `discover()` actually reads. — TODO: test `test_readme_documents_sources_keys` (README contains each key; every key `discover()` reads is documented)
2. REQ-S13-02. README states the two-step recipe (one `SOURCES` entry + one `ORDER` item) and lists the shipped drivers (`k10temp, coretemp, spd5118, nct6775/nct6799, ASUS WMI, amdgpu, nvidia, nvme`). — TODO: test `test_readme_lists_shipped_drivers`
3. REQ-S13-03. README's hardware-support table matches `SOURCES`/`NAMES` (no driver documented that isn't in the registry, none in the registry undocumented), including the ProArt B850-CREATOR TSENSOR1→AUXTIN3 note. — TODO: test `test_readme_registry_parity`

Tests: none — docs-drift tests proposed.

---

## Priority

| Story | Title | Priority |
|---|---|---|
| S1 | Sensor table: names, sparklines, min/max, limit | **Must** |
| S2 | Tray icon present from startup (Ayatana) | **Must** |
| S3 | Right-click → single-slot Vitals pin | **Must** |
| S4 | Pin persistence + sweep | **Should** |
| S5 | Minimize hides, app keeps running | **Must** |
| S6 | Close (X) quits | **Must** |
| S7 | Relaunch = present, single instance | **Must** |
| S8 | Tray menu (Show / Show hottest / Quit) | **Must** |
| S9 | SOURCES platform registry | **Must** |
| S10 | .deb release pipeline + SHA256SUMS | **Should** |
| S11 | install.sh / uninstall.sh | **Must** (AC4/5 Vitals setup: **Should**) |
| S12 | TUI tempwatch-tui | **Nice** |
| S13 | README extension recipe | **Nice** |

## Out of scope

- **Windows / macOS support** — Linux-only by design (`/sys/class/hwmon` is the sole data source).
- **Kernel patches** — no upstreaming patches to k10temp/nct6775/etc.; app consumes existing hwmon ABI only.
- **asus-ec-sensors upstreaming** — the ProArt's EC is SMI-only on Linux (README); reading it via an out-of-tree EC driver is explicitly excluded. TSENSOR1 is covered through nct6799 AUXTIN3.
- Non-temperature sensors (fans, voltages, power) — temperatures only.
- Non-GNOME DEs beyond the Ayatana-suppression fallback (KDE/plasma-widgets, macOS bar).

## Conflicts (docs/plan vs code)

1. **Task brief vs install.sh** — brief states install.sh performs "v86 install for Vitals, gsettings enabled-extensions append"; `install.sh` (69 lines) contains neither (no `v86`, no `enabled-extensions`, no Vitals reference). Recorded as REQ-S11-04/05 `[pending]`, not `[implemented]`.
2. **README vs install.sh** — README "Install" section describes the installer accurately (no Vitals); README's Debian section links `../../releases` (relative link from repo root, renders broken on GitHub) — cosmetic, out of slice.
3. **`build_deb.sh` vs task brief** — brief says "CI builds deb → install smoke test → GitHub Release + SHA256SUMS"; workflow also builds a source tarball included in SHA256SUMS (superset, no defect).
4. **Two sensor registries** — `tempwatch.py` (TUI) has independent `NAMES`/`WANT`/label sets (tsensor-by-label-match grouping) that do not match the app's `SOURCES`; TUI shows `AUXTIN3` raw under a "TSENSOR" section, app shows "TSENSOR1 Custom Probe". Drift risk, noted in S12.

---

*Tally: 13 stories, 62 live acceptance criteria — 12 ✅ (ACs proven by tests that call app code), 32 TODO (test proposed), 18 MANUAL (GNOME desktop check); 2 removed@f9f90bd (unpin affordance). ✅ list: S1-02, S1-03, S1-05, S3-02, S3-03, S5-01, S5-04, S9-01, S9-02, S9-03, S9-05, S9-06 (S3-02/S3-03 each cite two tests).*
