#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Builds dist/Twigpad-<version>-x86_64.AppImage (and its .zsync update file).
#
# The AppImage carries its own Python (python-build-standalone), the PyQt5 and
# PyCryptodome wheels from PyPI, the Hunspell library with a US English
# dictionary, and the xcb libraries Qt's X11 plugin needs. Every download is
# pinned by version and checked against a SHA-256 sum, so the same commit gives
# the same AppImage. Build on the oldest distribution you want to support (the
# Hunspell and xcb libraries come from its packages; Ubuntu 22.04 is used for
# releases).
#
#   packaging/appimage/build-appimage.sh [OUTPUT_DIR]
#
# Needs: curl, sha256sum, tar, apt-get and dpkg-deb (Debian or Ubuntu), file.
# Downloads are cached in build/appimage/cache.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HERE="$ROOT/packaging/appimage"
OUT="${1:-$ROOT/dist}"
WORK="$ROOT/build/appimage"
CACHE="$WORK/cache"
APPDIR="$WORK/AppDir"
APP_ID="com.warlordsoftwares.twigpad"
ARCH="x86_64"
TRIPLET="x86_64-linux-gnu"

# --- pinned downloads -------------------------------------------------------
PY_VERSION="3.12.16"
PY_RELEASE="20261026"
PY_FILE="cpython-${PY_VERSION}+${PY_RELEASE}-${ARCH}-unknown-linux-gnu-install_only.tar.gz"
PY_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PY_RELEASE}/${PY_FILE/+/%2B}"
PY_SHA256="6a79e922e50006b601f29e688407659da1c2b86ebcd4e9c7254cf234be8b89de"

TOOL_VERSION="1.9.1"
TOOL_URL="https://github.com/AppImage/appimagetool/releases/download/${TOOL_VERSION}/appimagetool-${ARCH}.AppImage"
TOOL_SHA256="ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0"

# The static runtime: the AppImage starts without libfuse2 on the user's system.
RUNTIME_VERSION="20251108"
RUNTIME_URL="https://github.com/AppImage/type2-runtime/releases/download/${RUNTIME_VERSION}/runtime-${ARCH}"
RUNTIME_SHA256="2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d"

# Debian/Ubuntu packages unpacked into the AppImage.
HUNSPELL_DEBS=(libhunspell-1.7-0 hunspell-en-us)
XCB_DEBS=(libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0
          libxcb-shape0 libxcb-util1 libxcb-xinerama0 libxcb-xkb1 libxkbcommon-x11-0)

# Qt modules Twigpad does not use (it needs Core, Gui, Widgets, PrintSupport,
# Svg, DBus and the X11/Wayland platform support).
UNUSED_QT=(Bluetooth Designer Help Location Multimedia MultimediaGstTools MultimediaQuick
           MultimediaWidgets Nfc Positioning PositioningQuick Qml QmlModels QmlWorkerScript
           Quick Quick3D Quick3DAssetImport Quick3DRender Quick3DRuntimeRender Quick3DUtils
           QuickControls2 QuickParticles QuickShapes QuickTemplates2 QuickTest QuickWidgets
           RemoteObjects Sensors SerialPort Sql Test TextToSpeech WebChannel WebSockets
           WebView XmlPatterns)
UNUSED_QT_PLUGINS=(assetimporters audio geometryloaders geoservices mediaservice playlistformats
                   position renderers renderplugins sceneparsers sensorgestures sensors
                   sqldrivers texttospeech webview)

# --- helpers ----------------------------------------------------------------
die() { echo "build-appimage: $*" >&2; exit 1; }
step() { echo "==> $*"; }

need() {   # need COMMAND PACKAGE
    command -v "$1" >/dev/null 2>&1 || die "'$1' is missing. Install it with: sudo apt install $2"
}

fetch() {   # fetch URL SHA256 DEST
    local url="$1" sha="$2" dest="$3"
    if [ -f "$dest" ] && echo "$sha  $dest" | sha256sum --quiet -c - 2>/dev/null; then
        return
    fi
    step "Downloading $(basename "$dest")"
    curl -fsSL --retry 3 --proto '=https' -o "$dest.part" "$url"
    echo "$sha  $dest.part" | sha256sum --quiet -c - || die "checksum mismatch for $url"
    mv "$dest.part" "$dest"
}

[ "$(uname -m)" = "$ARCH" ] || die "only $ARCH AppImages can be built (this machine is $(uname -m))"
need curl curl
need sha256sum coreutils
need tar tar
need file file
need apt-get apt
need dpkg-deb dpkg

VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$ROOT/src/twigpad/__init__.py")"
[ -n "$VERSION" ] || die "could not read __version__ from src/twigpad/__init__.py"
NAME="Twigpad-${VERSION}-${ARCH}.AppImage"
# Fixed timestamps (the last commit's) so rebuilding the same commit gives the same files.
SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(git -C "$ROOT" log -1 --format=%ct 2>/dev/null || date +%s)}"
export SOURCE_DATE_EPOCH

mkdir -p "$CACHE/debs" "$OUT"
rm -rf "$APPDIR" "$CACHE/debroot"
mkdir -p "$APPDIR/usr" "$CACHE/debroot"

# --- Python and the Python packages -----------------------------------------
fetch "$PY_URL" "$PY_SHA256" "$CACHE/$PY_FILE"
fetch "$TOOL_URL" "$TOOL_SHA256" "$CACHE/appimagetool-$TOOL_VERSION.AppImage"
fetch "$RUNTIME_URL" "$RUNTIME_SHA256" "$CACHE/runtime-$RUNTIME_VERSION-$ARCH"
chmod +x "$CACHE/appimagetool-$TOOL_VERSION.AppImage"

step "Unpacking Python $PY_VERSION"
tar -xzf "$CACHE/$PY_FILE" -C "$APPDIR/usr"        # gives usr/python
PY="$APPDIR/usr/python/bin/python3"
PYVER="$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
SITE="$APPDIR/usr/python/lib/python$PYVER/site-packages"

step "Installing PyQt5 and PyCryptodome (pinned, hash-checked wheels)"
PIP_DISABLE_PIP_VERSION_CHECK=1 "$PY" -s -m pip install --quiet --no-cache-dir --no-compile \
    --no-warn-script-location --only-binary=:all: --require-hashes -r "$HERE/requirements.txt"

step "Copying Twigpad $VERSION"
# The package itself is copied rather than pip-installed: no build backend to fetch.
cp -r "$ROOT/src/twigpad" "$SITE/twigpad"
find "$SITE/twigpad" -name '__pycache__' -prune -exec rm -rf {} +

# --- Hunspell and the xcb libraries -----------------------------------------
step "Fetching ${HUNSPELL_DEBS[*]} ${XCB_DEBS[*]} from this system's package sources"
( cd "$CACHE/debs" && rm -f ./*.deb && apt-get download "${HUNSPELL_DEBS[@]}" "${XCB_DEBS[@]}" ) \
    || die "apt-get download failed (run 'sudo apt update' and try again)"
for deb in "$CACHE"/debs/*.deb; do
    dpkg-deb -x "$deb" "$CACHE/debroot"
done
DEBLIB="$CACHE/debroot/usr/lib/$TRIPLET"
install -d "$APPDIR/usr/lib/$TRIPLET" "$APPDIR/usr/share/hunspell"
cp -L "$DEBLIB"/libhunspell-1.7.so.0 "$APPDIR/usr/lib/$TRIPLET/"
cp -L "$CACHE"/debroot/usr/share/hunspell/en_US.{aff,dic} "$APPDIR/usr/share/hunspell/"
QTLIB="$SITE/PyQt5/Qt5/lib"            # the Qt plugins' RUNPATH points here
for lib in "$DEBLIB"/libxcb-*.so.* "$DEBLIB"/libxkbcommon-x11.so.*; do
    [ -L "$lib" ] && [ -e "$QTLIB/$(basename "$lib")" ] && continue
    cp -L "$lib" "$QTLIB/"
done
install -d "$APPDIR/usr/share/doc"
cp -r "$CACHE"/debroot/usr/share/doc/* "$APPDIR/usr/share/doc/"

# --- trimming ---------------------------------------------------------------
step "Removing what Twigpad does not use"
STDLIB="$APPDIR/usr/python/lib/python$PYVER"
rm -rf "$STDLIB"/{test,idlelib,tkinter,turtledemo,ensurepip,lib2to3} "$STDLIB"/config-* \
       "$APPDIR"/usr/python/lib/{tcl,tk,itcl,thread}* "$APPDIR"/usr/python/lib/lib{tcl,tk}* \
       "$APPDIR"/usr/python/include "$APPDIR"/usr/python/share \
       "$STDLIB"/lib-dynload/_tkinter* "$SITE"/pip "$SITE"/pip-*.dist-info \
       "$SITE/PyQt5/Qt5/qml" "$SITE/PyQt5/bindings" "$SITE/PyQt5/uic"
# Also PyQt5's developer tools: Twigpad does not use them, and pip writes the
# build folder into their first line.
rm -f "$APPDIR"/usr/python/bin/{idle3*,pip*,pydoc3*,2to3*,pyuic5,pylupdate5,pyrcc5}
for mod in "${UNUSED_QT[@]}"; do
    rm -f "$QTLIB/libQt5$mod.so"* "$SITE/PyQt5/Qt$mod".*.so "$SITE/PyQt5/Qt$mod".pyi
done
for dir in "${UNUSED_QT_PLUGINS[@]}"; do
    rm -rf "$SITE/PyQt5/Qt5/plugins/$dir"
done
# The PDF image plugin needs QtPdf, which the wheel lacks; WebGL streaming needs WebSockets.
rm -f "$SITE/PyQt5/Qt5/plugins/imageformats/libqpdf.so" "$SITE/PyQt5/Qt5/plugins/platforms/libqwebgl.so"

step "Checking that every bundled library finds what it links against"
missing=0
while IFS= read -r so; do
    if out="$(LD_LIBRARY_PATH="$APPDIR/usr/lib/$TRIPLET" ldd "$so" 2>/dev/null | grep 'not found')"; then
        echo "  ${so#"$APPDIR"/}:"; echo "$out"; missing=1
    fi
done < <(find "$SITE/PyQt5" "$APPDIR/usr/lib" -name '*.so*' -type f)
[ "$missing" = 0 ] || die "some libraries are missing (see above)"

step "Byte-compiling"
# -s/-p: record /usr/python/... as the source path, not this machine's build folder.
"$PY" -s -m compileall -q -j 0 --invalidation-mode unchecked-hash -s "$APPDIR" -p / "$STDLIB" >/dev/null || true
if grep -rlaF "$ROOT" "$APPDIR" >/dev/null 2>&1; then
    grep -rlaF "$ROOT" "$APPDIR" | sed "s|$APPDIR/|  |" | head >&2
    die "the files above contain this machine's build path ($ROOT)"
fi

# --- desktop integration ----------------------------------------------------
step "Adding the menu entry, icon, file types and AppStream metadata"
install -m755 "$HERE/AppRun" "$APPDIR/AppRun"
install -Dm644 "$ROOT/data/$APP_ID.desktop" "$APPDIR/usr/share/applications/$APP_ID.desktop"
install -Dm644 "$ROOT/data/$APP_ID.metainfo.xml" "$APPDIR/usr/share/metainfo/$APP_ID.appdata.xml"
install -Dm644 "$ROOT/data/twigpad-mime.xml" "$APPDIR/usr/share/mime/packages/$APP_ID.xml"
install -Dm644 "$ROOT/src/twigpad/resources/twigpad.svg" \
    "$APPDIR/usr/share/icons/hicolor/scalable/apps/$APP_ID.svg"
install -Dm644 "$ROOT/LICENSE" "$APPDIR/usr/share/doc/twigpad/copyright"
cp "$APPDIR/usr/share/applications/$APP_ID.desktop" "$APPDIR/$APP_ID.desktop"
cp "$ROOT/src/twigpad/resources/twigpad.svg" "$APPDIR/$APP_ID.svg"
ln -sf "$APP_ID.svg" "$APPDIR/.DirIcon"
find "$APPDIR" -exec touch -h -d "@$SOURCE_DATE_EPOCH" {} +

# --- the AppImage -----------------------------------------------------------
step "Packing $NAME"
rm -f "$OUT/$NAME" "$OUT/$NAME.zsync"
(
    cd "$OUT"
    # Extract-and-run: building does not need FUSE on this machine either.
    APPIMAGE_EXTRACT_AND_RUN=1 ARCH="$ARCH" VERSION="$VERSION" \
        "$CACHE/appimagetool-$TOOL_VERSION.AppImage" --no-appstream \
        --runtime-file "$CACHE/runtime-$RUNTIME_VERSION-$ARCH" \
        --updateinformation "gh-releases-zsync|rishabh3354|twigpad|latest|Twigpad-*-$ARCH.AppImage.zsync" \
        "$APPDIR" "$OUT/$NAME"
)
[ -f "$OUT/$NAME" ] || die "appimagetool did not write $OUT/$NAME"
echo "Built $OUT/$NAME"
