#!/usr/bin/env bash
# Build a portable AppImage of Desktop Planner.
# Requires: appimagetool in $PATH, plus the system GTK4 / Libadwaita / PyGObject.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build/appimage"
APPDIR="$BUILD/Planner.AppDir"

rm -rf "$BUILD"
mkdir -p "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/scalable/apps" \
         "$APPDIR/usr/lib/desktop-planner"

cp -r "$ROOT/src/desktop_planner" "$APPDIR/usr/lib/desktop-planner/"
cp "$ROOT/packaging/org.example.DesktopPlanner.desktop" \
   "$APPDIR/usr/share/applications/"
cp "$ROOT/packaging/org.example.DesktopPlanner.desktop" \
   "$APPDIR/org.example.DesktopPlanner.desktop"
cp "$ROOT/packaging/org.example.DesktopPlanner.svg" \
   "$APPDIR/usr/share/icons/hicolor/scalable/apps/"
cp "$ROOT/packaging/org.example.DesktopPlanner.svg" \
   "$APPDIR/org.example.DesktopPlanner.svg"

cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "$0")")"
export PYTHONPATH="$HERE/usr/lib/desktop-planner:${PYTHONPATH:-}"
exec python3 -m desktop_planner "$@"
EOF
chmod +x "$APPDIR/AppRun"

if command -v appimagetool >/dev/null 2>&1; then
    appimagetool "$APPDIR" "$ROOT/build/Planner-x86_64.AppImage"
    echo "Built: $ROOT/build/Planner-x86_64.AppImage"
else
    echo "AppDir prepared at $APPDIR"
    echo "Install appimagetool to produce a single-file AppImage."
fi
