#!/bin/sh
# Build Trelby with PyInstaller: on Windows dist/Trelby/ (Trelby.exe +
# _internal/), on macOS dist/Trelby.app, on Linux dist/Trelby/ (Trelby +
# _internal/). Run from Git Bash on Windows; works from any directory.
# Uses the .venv from CLAUDE.md, or the python in $PY (as the GitHub
# Actions build does).

set -e

cd "$(dirname "$0")/.."

case "$(uname -s)" in
    MINGW* | MSYS* | CYGWIN*) OS=windows ;;
    Darwin) OS=mac ;;
    *) OS=linux ;;
esac

if [ -z "$PY" ]; then
    if [ "$OS" = windows ]; then
        PY=.venv/Scripts/python
    else
        PY=.venv/bin/python
    fi
fi

# PyInstaller's --add-data separator
if [ "$OS" = windows ]; then
    SEP=";"
else
    SEP=":"
fi

if [ "$OS" = windows ] &&
    tasklist //FI "IMAGENAME eq Trelby.exe" 2>/dev/null | grep -qi "Trelby.exe"; then
    echo "Trelby.exe is running; close it first so dist/Trelby/ can be replaced." >&2
    exit 1
fi

$PY -m PyInstaller --version >/dev/null 2>&1 || $PY -m pip install pyinstaller

# the MCP SDK, for the MCP server in the settings and Trelby.exe
# --mcp-bridge. optional when running from source, but always bundled in
# the exe (about 25 MB). PyInstaller finds it through mcpserver/app.py's imports,
# and pyinstaller-hooks-contrib covers uvicorn's dynamic ones.
$PY -c "import mcp.server.mcpserver, uvicorn" 2>/dev/null || $PY -m pip install "mcp>=2.3,<3"

# pypdf, for importing PDF files (trelby/importers/pdf.py). optional when
# running from source, but always bundled in the exe.
$PY -c "import pypdf" 2>/dev/null || $PY -m pip install "pypdf>=5,<7"

PLATFORM_ARGS=
if [ "$OS" = windows ]; then
    # pyttsx3, for reading scripts aloud with the SAPI voices
    # (trelby/speech.py). optional when running from source, but always
    # bundled in the exe. it imports its driver by name, and that makes
    # comtypes generate SAPI's wrapper (comtypes.gen.SpeechLib), which the
    # build includes once it exists. macOS and Linux read aloud with the
    # say / espeak commands instead.
    $PY -c "import pyttsx3" 2>/dev/null || $PY -m pip install "pyttsx3>=2.90,<3"
    $PY -c "import pyttsx3; pyttsx3.Engine()"

    WXDIR=$($PY -c "import os, wx; print(os.path.dirname(wx.__file__))")
    PLATFORM_ARGS="--icon trelby/resources/icon256.ico
        --add-binary $WXDIR/WebView2Loader.dll${SEP}wx
        --hidden-import pyttsx3.drivers.sapi5
        --collect-submodules comtypes.gen"
elif [ "$OS" = mac ]; then
    PLATFORM_ARGS="--icon resources_mac/icon.icns
        --osx-bundle-identifier org.trelby.Trelby"
fi

# packaged copies of the data files (see CLAUDE.md; don't commit these)
gzip -c trelby/names.txt > trelby/names.txt.gz
gzip -c trelby/dict_en.dat > trelby/dict_en.dat.gz
gzip -c trelby/thesaurus_en.dat > trelby/thesaurus_en.dat.gz

# wxWidgets' own translations (stock button labels, see
# gutil.loadWxTranslations), only for the languages Trelby has, e.g.
# wx/locale/zh_CN for trelby/locales/zh_CN, or wx/locale/it for it_IT
WXLOCALE=$($PY -c "import os, wx; print(os.path.join(os.path.dirname(wx.__file__), 'locale'))")
WXDATA=
for d in trelby/locales/*/; do
    lang=$(basename "$d")
    for wxlang in "$lang" "${lang%%_*}"; do
        if [ -d "$WXLOCALE/$wxlang" ]; then
            WXDATA="$WXDATA --add-data $WXLOCALE/$wxlang${SEP}wx/locale/$wxlang"
            break
        fi
    done
done

# $WXDATA and $PLATFORM_ARGS are split into arguments on purpose
# shellcheck disable=SC2086
$PY -m PyInstaller --noconfirm --windowed --name Trelby $WXDATA $PLATFORM_ARGS \
    --add-data "trelby/resources${SEP}trelby/resources" \
    --add-data "trelby/locales${SEP}trelby/locales" \
    --add-data "trelby/names.txt.gz${SEP}trelby" \
    --add-data "trelby/dict_en.dat.gz${SEP}trelby" \
    --add-data "trelby/thesaurus_en.dat.gz${SEP}trelby" \
    --add-data "trelby/sample.trelby${SEP}trelby" \
    --add-data "trelby/fileformat.txt${SEP}trelby" \
    trelby.py

# modules the MCP server needs that are only imported lazily or by name
for m in mcp.server.mcpserver mcp.server.stdio uvicorn.loops.asyncio \
    uvicorn.protocols.http.h11_impl uvicorn.lifespan.on; do
    if ! grep -q "'$m'" build/Trelby/PYZ-00.toc; then
        echo "$m is missing from the build; the MCP server won't work." >&2
        exit 1
    fi
done

if ! grep -q "'pypdf'" build/Trelby/PYZ-00.toc; then
    echo "pypdf is missing from the build; importing PDF files won't work." >&2
    exit 1
fi

if [ "$OS" = windows ]; then
    for m in pyttsx3.drivers.sapi5 comtypes.gen.SpeechLib; do
        if ! grep -q "'$m'" build/Trelby/PYZ-00.toc; then
            echo "$m is missing from the build; reading aloud won't work." >&2
            exit 1
        fi
    done
    echo "Built $(pwd)/dist/Trelby/Trelby.exe"
elif [ "$OS" = mac ]; then
    echo "Built $(pwd)/dist/Trelby.app"
else
    echo "Built $(pwd)/dist/Trelby/Trelby"
fi
