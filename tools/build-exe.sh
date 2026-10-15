#!/bin/sh
# Build the Windows exe into dist/Trelby/ (Trelby.exe + _internal/). Run
# from Git Bash; works from any directory. Needs the .venv from CLAUDE.md.

set -e

cd "$(dirname "$0")/.."

PY=.venv/Scripts/python

if tasklist //FI "IMAGENAME eq Trelby.exe" 2>/dev/null | grep -qi "Trelby.exe"; then
    echo "Trelby.exe is running; close it first so dist/Trelby/ can be replaced." >&2
    exit 1
fi

$PY -m PyInstaller --version >/dev/null 2>&1 || $PY -m pip install pyinstaller

# the MCP SDK, for the MCP server in the settings and Trelby.exe
# --mcp-bridge. optional when running from source, but always bundled in
# the exe (about 25 MB). PyInstaller finds it through mcpapp.py's imports,
# and pyinstaller-hooks-contrib covers uvicorn's dynamic ones.
$PY -c "import mcp.server.mcpserver, uvicorn" 2>/dev/null || $PY -m pip install "mcp>=2.3,<3"

# packaged copies of the data files (see CLAUDE.md; don't commit these)
gzip -c trelby/names.txt > trelby/names.txt.gz
gzip -c trelby/dict_en.dat > trelby/dict_en.dat.gz

$PY -m PyInstaller --noconfirm --windowed --name Trelby \
    --icon trelby/resources/icon256.ico \
    --add-data "trelby/resources;trelby/resources" \
    --add-data "trelby/locales;trelby/locales" \
    --add-data "trelby/names.txt.gz;trelby" \
    --add-data "trelby/dict_en.dat.gz;trelby" \
    --add-data "trelby/sample.trelby;trelby" \
    --add-data "trelby/fileformat.txt;trelby" \
    --add-binary ".venv/Lib/site-packages/wx/WebView2Loader.dll;wx" \
    trelby.py

# modules the MCP server needs that are only imported lazily or by name
for m in mcp.server.mcpserver mcp.server.stdio uvicorn.loops.asyncio \
    uvicorn.protocols.http.h11_impl uvicorn.lifespan.on; do
    if ! grep -q "'$m'" build/Trelby/PYZ-00.toc; then
        echo "$m is missing from the build; the MCP server won't work." >&2
        exit 1
    fi
done

echo "Built $(pwd)/dist/Trelby/Trelby.exe"
