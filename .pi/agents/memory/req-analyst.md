# req-analyst memory

## 2026-11-04 — tempwatch STORIES.md
- Task brief claimed install.sh installs Vitals v86 + appends enabled-extensions; install.sh has neither → recorded REQ-S11-04/05 as `[pending]` + Conflicts, not `[implemented]`. Briefs lie; code is truth.
- test_tempwatch.py had uncommitted +157-line additions in the working tree (live lane owns it) — never touch, report as #collision#.
- Counting tags in tallies: a line can carry both ✅ and TODO (e.g. arithmetic tested, side-effect untested); grep tallies double-count, verify per-line.
- Evidence: cite file:line via grep -n on key defs before writing; 63 ACs → 11✅/36TODO/16MANUAL.
- Dual registries drift: tempwatch.py (TUI) NAMES/WANT vs tempwatch-app.py SOURCES — flag as drift risk in stories touching both.
