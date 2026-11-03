# release-packer memory

## 2026-11-03 — tempwatch v1.1.0 deb review
- `cat >` into the deb tree inherits the builder umask: /usr/bin shims shipped mode 644/664 (no +x) in the released v1.1.0 .deb. Always `install -m 0755` (or explicit chmod) for every file that must be executable, and verify modes with `dpkg-deb -c`, not just build exit code.
- CI smoke trap: bash `command -v <name>` returns the path for NON-executable PATH files (verified exit 0 on a 644 file). It does not gate +x. Use `test -x` in release smoke tests.
- `python3 - <<'EOF'` inside a YAML block scalar: base indentation is set by the block's first line, so the heredoc body/EOF dedent cleanly; `bash -n` the extracted run script via `yaml.safe_load` to prove it.
- TUI `max()` on an empty sensor list crashes on Intel/NVIDIA boxes — every "hottest sensor" shortcut needs an empty guard; test with `HWMON=/tmp/empty-hwmon`.
- desktop-file-validate passes for both the deb and the user-level desktop files; Icon as absolute path is valid.
