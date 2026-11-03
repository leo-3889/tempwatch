# review-gate memory

## 2026-11-02 — tempwatch pre-commit (STORIES.md + test_tempwatch.py 6→12)
Defect classes seen:
- Self-arithmetic tests: a ✅ AC cited to a test that recomputes the rule inside the test body (test_single_slot) — implementation break leaves it green. Counterfactual-test every ✅ citation, not just existence.
- Doc generated mid-slice: STORIES.md written against the 6/7-test suite; builder added 6 tests covering listed TODOs → stale "needs test" tags + broken tallies. Always diff doc claims against the CURRENT suite, run the counts with grep -c, don't trust the doc's own arithmetic (claimed 16 MANUAL, actual 18).
- Silent-degradation features: feature degrades gracefully (Vitals absent → right-click inert) so tests stay green, but the Must-story outcome is unreachable on a fresh machine and README has zero mentions. Graceful ≠ shippable for the feature claim.
