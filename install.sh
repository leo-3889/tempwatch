#!/usr/bin/env bash
# TempWatch all-in-one installer (Ubuntu desktop, X11/GNOME).
# - ensures sensor kernel modules load at boot (spd5118, nct6775)
# - installs the GTK app to ~/.local/share/tempwatch
# - registers app icon + launcher (taskbar icon when minimized)
# - CLI TUI variant installed as `tempwatch` in ~/.local/bin
set -euo pipefail
cd "$(dirname "$0")"

SRC="$HOME/.local/share/tempwatch"
BIN="$HOME/.local/bin"
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor/scalable/apps"

echo "==> Checking dependencies"
command -v python3 >/dev/null || { echo "python3 missing"; exit 1; }
if ! python3 -c "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk" 2>/dev/null; then
    echo "    installing gir1.2-gtk-3.0 (needs sudo)"
    sudo apt-get update -qq && sudo apt-get install -y -qq gir1.2-gtk-3.0
fi

echo "==> Ensuring sensor modules load at boot"
for m in spd5118 nct6775; do
    echo "$m" | sudo tee "/etc/modules-load.d/$m.conf" >/dev/null
    sudo modprobe "$m" 2>/dev/null || echo "    note: $m not loadable now (ok if hardware absent)"
done
SENSORS_OUT="$(sensors 2>/dev/null || true)"
echo "$SENSORS_OUT" | grep -qi "nct6799\|spd5118" \
    || echo "    warning: no board/dram sensors visible yet — check 'sensors'"

echo "==> Installing app files"
mkdir -p "$SRC" "$BIN" "$APPS" "$ICONS"
install -m 0755 tempwatch-app.py "$SRC/tempwatch-app.py"
install -m 0644 tempwatch-icon.svg "$SRC/tempwatch-icon.svg"
[ -f tempwatch.py ] && install -m 0755 tempwatch.py "$BIN/tempwatch"
cp -f "$SRC/tempwatch-icon.svg" "$ICONS/dev.leo.tempwatch.svg"

cat > "$APPS/dev.leo.tempwatch.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=TempWatch
Comment=Live hardware temperature monitor
Exec=$SRC/tempwatch-app.py
Icon=$SRC/tempwatch-icon.svg
Terminal=false
Categories=System;Monitor;
StartupWMClass=dev.leo.tempwatch
EOF
chmod +x "$SRC/tempwatch-app.py"

gtk-update-icon-cache -q "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
update-desktop-database "$APPS" 2>/dev/null || true

echo
echo "==> Done."
echo "    GUI : search 'TempWatch' in the apps grid, or run: $SRC/tempwatch-app.py"
echo "    TUI : tempwatch   (terminal dashboard)"
echo "    Tip : launch it, right-click the dock icon -> 'Pin to Dock'"
