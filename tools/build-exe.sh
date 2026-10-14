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
    trelby.py

echo "Built $(pwd)/dist/Trelby/Trelby.exe"
