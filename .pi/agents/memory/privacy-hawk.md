# privacy-hawk memory

## 2026-11-03 — tempwatch public-repo audit (GO)
- Clean tree pattern worth reusing: secrets grep + /home//Users + email + IP + git log --all -p + `git rev-list --all --objects | cat-file --batch-check` blob inventory catches history-deleted leaks; tempwatch had zero (only intentional leo-3889 / dev.leo.tempwatch ids, noreply commit emails).
- Recurring class: hardware-model fingerprints (exact motherboard + AUXTIN3=TSENSOR mapping) in README/code = author device fingerprint, not PII; NIT-level.
- Check README asset links vs git ls-files (docs/screenshot.png referenced, absent) — broken-publish defect class, not privacy.
- gitignored dist/__pycache__/.ruff_cache not in public repo, but artifacts uploaded manually to Releases need same scan as tracked files.
