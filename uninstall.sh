#!/usr/bin/env bash
# Remove the user-level TempWatch install (files in ~/.local).
# Leaves /etc/modules-load.d/{spd5118,nct6775}.conf in place; remove those
# with sudo rm if you also want to disable the sensor modules at boot.
set -euo pipefail
rm -rf "$HOME/.local/share/tempwatch"
rm -f  "$HOME/.local/bin/tempwatch"
rm -f  "$HOME/.local/share/applications/dev.leo.tempwatch.desktop"
rm -f  "$HOME/.local/share/icons/hicolor/scalable/apps/dev.leo.tempwatch.svg"
gtk-update-icon-cache -q "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
echo "TempWatch (user install) removed."
