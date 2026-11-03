# req-analyst memory

## 2026-11-04 — tempwatch STORIES.md
- Task brief claimed install.sh installs Vitals v86 + appends enabled-extensions; install.sh has neither → recorded REQ-S11-04/05 as `[pending]` + Conflicts, not `[implemented]`. Briefs lie; code is truth.
- test_tempwatch.py had uncommitted +157-line additions in the working tree (live lane owns it) — never touch, report as #collision#.
- Counting tags in tallies: a line can carry both ✅ and TODO (e.g. arithmetic tested, side-effect untested); grep tallies double-count, verify per-line.
- Evidence: cite file:line via grep -n on key defs before writing; 63 ACs → 11✅/36TODO/16MANUAL.
- Dual registries drift: tempwatch.py (TUI) NAMES/WANT vs tempwatch-app.py SOURCES — flag as drift risk in stories touching both.

## 2026-11-04 — review-gate BLOCK fixes (STORIES.md v2)
- Gate rule: a ✅ counts only if the named test CALLS app code; tests that hand-replicate the app's arithmetic in-test (test_single_slot) do NOT count → demoted S3-04/S4-03/S4-04.
- Suite grew 7→14 tests mid-slice (new: discovery_robustness, nvme_naming, cpu_naming, vitals_keys_nvme_and_dedup, minimize_button_wired, window_structure, sources_invariants) — retagged S1-05/S9-03/S9-06 ✅, added REQ-S5-04. Final: 13 stories/64 AC/12✅/34TODO/18MANUAL.
- Gate's quoted counts can be stale by design ("recount after fixes") — recount by grep, never copy the gate's numbers.
- Citation drift is constant on a live repo: app grew 509→526 lines (custom titlebar); re-grep line anchors before every handoff.
