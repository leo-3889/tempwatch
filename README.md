# ⚡ TempWatch

HWiNFO-style live hardware temperature monitor for Linux — GTK3, Python,
zero dependencies beyond `python3-gi` (standard on Ubuntu/GNOME desktops).


## What it shows

| Section | Source | Sensors |
|---|---|---|
| CPU | `k10temp` | Package (Tctl), CCD temps |
| Memory sticks | `spd5118` | per-DIMM DDR5 temps |
| Motherboard | `nct6799` (NCT6799D) | system, CPU socket, VRM area, custom **TSENSOR** header probes |
| Graphics | `amdgpu` | core / hotspot / GDDR memory, AMD dGPU + iGPU |

Per sensor: live value (color-coded against firmware limits), session
min/max, limit, and a temperature-over-time sparkline (3 min @ 1 s,
auto-scaled per sensor). Runs in the tray-able GNOME dock as a normal app.

## Install (Ubuntu 22.04+, X11/GNOME)

```bash
git clone https://github.com/leo-3889/tempwatch && cd tempwatch
./install.sh
```

The installer is all-in-one: checks deps (`gir1.2-gtk-3.0`, auto-`apt`),
enables the sensor kernel modules at boot (`spd5118`, `nct6775` — needs
`sudo`), installs the app to `~/.local/share/tempwatch`, registers the
launcher + dock icon (`dev.leo.tempwatch.desktop`), and drops the TUI
dashboard as `tempwatch` in `~/.local/bin`.

Then: apps grid → **TempWatch**. Right-click the dock icon → *Pin to Dock*.

## Debian package (system-wide)

```bash
./packaging/build_deb.sh          # → dist/tempwatch_*_all.deb
sudo apt install ./dist/tempwatch_*_all.deb
```

`postinst` enables the sensor modules in `/etc/modules-load.d/`.
Releases with prebuilt `.deb` files are on the
[releases page](../../releases) — the pipeline is
`.github/workflows/release.yml` (tag `v*` → build → GitHub Release).

## Requirements / support

- AMD Ryzen (Zen 2+) — `k10temp`
- DDR5 DIMMs with thermal sensors — `spd5118`
- Board Super I/O NCT677x/679x — `nct6775` (many ASUS boards, incl.
  ProArt B850-Creator WIFI NEO: its `TSENSOR1` header reads as `AUXTIN3`;
  the ASUS "EC" is SMI-only and exposes nothing on Linux)
- AMD GPUs — `amdgpu`

Anything without a hwmon interface (laptop ECs without `asus_wmi`/`dybus`
exposure, proprietary embedded controllers) simply does not appear.

## Extending to new platforms

All platform support lives in one table in `tempwatch-app.py`:

```python
SOURCES = {
  "<hwmon driver name>": {
      "title":  lambda idx, hwmon_dir: "Section Name",   # per-device section
      "labels": {"raw_label": "Friendly Name"} | None,   # renames; None = as-is
      "mapped_only": True | False,                        # drop unmapped labels?
      "prefix": True,          # optional: name as "Section · Label" (GPUs)
      "keep":   {"Composite"}, # optional: whitelist of raw labels
  },
  ...
}
```

Adding a platform = adding one `SOURCES` entry + its position in `ORDER`
(section sort order). Ships with: `k10temp`, `coretemp`, `spd5118`,
`nct6775` (nct6799), ASUS WMI, `amdgpu`, `nvidia`, `nvme`. Anything that
exposes `/sys/class/hwmon` (Raspberry Pi, Intel laptops, NVMe drives,
hwmon-attached USB probes) works by adding the driver name.

## Uninstall

```bash
./uninstall.sh                 # user-level install
sudo apt remove tempwatch      # .deb install
```

## License

MIT
