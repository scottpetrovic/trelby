# Trelby

Screenplay writing app. Python 3 + wxPython (GUI), lxml, reportlab (PDF export). Package code is in `trelby/`, tests in `tests/`, DocBook manual sources in `doc/`.

## Dev setup (Windows)

```bash
py -3 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```

`make` and `xsltproc` are not needed for day-to-day work.

## Run / test

```bash
.venv/Scripts/python trelby.py --test trelby/sample.trelby   # --test: no splash, config goes in ./.trelby/
.venv/Scripts/python -m pytest
```

Without `--test`, config is written to `%USERPROFILE%\Trelby\conf` (Windows) or `~/.config/trelby` (Unix).

## Generated files: do not commit

- `trelby/names.txt.gz`, `trelby/dict_en.dat.gz`: gzipped copies of `names.txt` / `dict_en.dat`, produced by `make` (or `gzip -c`). `util.loadMaybeCompressedFile` prefers the uncompressed file, so running from source doesn't need them; they exist only for packaging (PyPI `package_data`, Debian, the exe).
- `trelby/manual.html`, `trelby/trelby.1.gz`: built from `doc/` by `make`, which needs `xsltproc` plus DocBook XSL stylesheets at Linux paths (use WSL). Without them, Help → Manual is the only thing that breaks.
- `.venv/`, `build/`, `dist/`, `*.spec`, `.trelby/`.

## Building a Windows exe (PyInstaller)

Install with `.venv/Scripts/python -m pip install pyinstaller`, then generate the `.gz` files and run:

```bash
.venv/Scripts/pyinstaller --noconfirm --windowed --name Trelby --icon trelby/resources/icon256.ico --add-data "trelby/resources;trelby/resources" --add-data "trelby/locales;trelby/locales" --add-data "trelby/names.txt.gz;trelby" --add-data "trelby/dict_en.dat.gz;trelby" --add-data "trelby/sample.trelby;trelby" --add-data "trelby/fileformat.txt;trelby" trelby.py
```

Output is `dist/Trelby/` (`Trelby.exe` + `_internal/`, which must stay together). If you add a new data file, add an `--add-data` for it.

## Code conventions worth knowing

- Data files are found relative to the package: `misc.getFullPath("trelby/resources/...")` (uses `misc.progPath`, the parent of the `trelby/` package) or `trelby.__path__[0]`. Use these instead of hard-coded or CWD-relative paths, or the exe build breaks.
- `misc.init()` sets `progPath = "."` in `--test` mode and in tests, so tests must run from the repo root.
- UI strings are wrapped in `_()` for gettext; translations live in `trelby/locales` and `po/` (see `TRANSLATION_NOTES.txt`).
- Version string is duplicated in `pyproject.toml`, `trelby/misc.py`, `doc/version.xml`, and `choco/`; bump all of them together.
- Packaging metadata and dependency bounds live in `pyproject.toml`; `requirements.txt` is the dev install (same bounds plus pytest). Keep them in sync.
- Menu/control IDs: use `wx.NewIdRef()` (not the deprecated `wx.NewId()`). `WindowIDRef` works as a dict key and in `Bind`/`Append`, but doesn't support arithmetic; convert with `int()` when you need it (see `misc.MRUFiles`). Submenus use `AppendSubMenu`.
- Font constants: use `wx.FONTFAMILY_*` / `wx.FONTSTYLE_*` / `wx.FONTWEIGHT_*`, not the old `wx.NORMAL` / `wx.BOLD` / `wx.MODERN`.
- To catch new deprecations, run the app with `.venv/Scripts/python -X dev -W always trelby.py --test`; startup should print no warnings.
