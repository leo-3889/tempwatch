#!/usr/bin/env bash
# Build a system-wide .deb from the repo files. Run from repo root.
# Output: dist/tempwatch_<ver>_all.deb
set -euo pipefail
cd "$(dirname "$0")/.."

VER="${1:-$(git describe --tags --abbrev=0 2>/dev/null | sed 's/^v//' || echo 0.0.0)}"
NAME="tempwatch_${VER}_all"
ROOT="dist/$NAME"
rm -rf "$ROOT"
mkdir -p "$ROOT/DEBIAN" "$ROOT/usr/bin" "$ROOT/usr/share/tempwatch" \
         "$ROOT/usr/share/applications" "$ROOT/usr/share/icons/hicolor/scalable/apps"

install -m 0755 tempwatch-app.py "$ROOT/usr/share/tempwatch/tempwatch-app.py"
install -m 0755 tempwatch.py     "$ROOT/usr/share/tempwatch/tempwatch.py"
install -m 0644 tempwatch-icon.svg "$ROOT/usr/share/icons/hicolor/scalable/apps/dev.leo.tempwatch.svg"
cp tempwatch-icon.svg "$ROOT/usr/share/tempwatch/tempwatch-icon.svg"

install -m 0755 /dev/stdin "$ROOT/usr/bin/tempwatch" <<'EOF'
#!/bin/sh
exec python3 /usr/share/tempwatch/tempwatch-app.py "$@"
EOF
install -m 0755 /dev/stdin "$ROOT/usr/bin/tempwatch-tui" <<'EOF'
#!/bin/sh
exec python3 /usr/share/tempwatch/tempwatch.py "$@"
EOF

cat > "$ROOT/usr/share/applications/dev.leo.tempwatch.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=TempWatch
Comment=Live hardware temperature monitor
Exec=/usr/bin/tempwatch
Icon=dev.leo.tempwatch
Terminal=false
Categories=System;Monitor;
StartupWMClass=dev.leo.tempwatch
EOF

cat > "$ROOT/DEBIAN/control" <<EOF
Package: tempwatch
Version: $VER
Section: utils
Priority: optional
Architecture: all
Depends: python3, python3-gi, gir1.2-gtk-3.0
Maintainer: leo-3889
Homepage: https://github.com/leo-3889/tempwatch
Description: HWiNFO-style live hardware temperature monitor
 GTK3 sensor dashboard reading /sys/class/hwmon: CPU (k10temp/coretemp),
 DDR5 DIMMs (spd5118), motherboard + TSENSOR headers (nct6775), AMD and
 NVIDIA GPUs, NVMe drives; per-sensor temperature-over-time graphs.
EOF

cat > "$ROOT/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
for m in spd5118 nct6775; do
    echo "$m" > "/etc/modules-load.d/$m.conf"
    modprobe "$m" 2>/dev/null || true
done
gtk-update-icon-cache -q /usr/share/icons/hicolor 2>/dev/null || true
update-desktop-database /usr/share/applications 2>/dev/null || true
EOF
cat > "$ROOT/DEBIAN/prerm" <<'EOF'
#!/bin/sh
set -e
rm -f /etc/modules-load.d/spd5118.conf /etc/modules-load.d/nct6775.conf || true
EOF
chmod 0755 "$ROOT/DEBIAN/postinst" "$ROOT/DEBIAN/prerm"

mkdir -p dist
dpkg-deb --build --root-owner-group "$ROOT" "dist/$NAME.deb"
rm -rf "$ROOT"
echo "built: dist/$NAME.deb"
