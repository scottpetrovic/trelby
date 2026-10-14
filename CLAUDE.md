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
.venv/Scripts/python trelby.py --test trelby/sample.trelby   # --test: config goes in ./.trelby/
.venv/Scripts/python -m pytest
```

Without `--test`, config is written to `%USERPROFILE%\Trelby\conf` (Windows) or `~/.config/trelby` (Unix).

## Generated files: do not commit

- `trelby/names.txt.gz`, `trelby/dict_en.dat.gz`: gzipped copies of `names.txt` / `dict_en.dat`, produced by `make` (or `gzip -c`). `util.loadMaybeCompressedFile` prefers the uncompressed file, so running from source doesn't need them; they exist only for packaging (PyPI `package_data`, Debian, the exe).
- `trelby/manual.html`, `trelby/trelby.1.gz`: built from `doc/` by `make`, which needs `xsltproc` plus DocBook XSL stylesheets at Linux paths (use WSL). Without them, Help → Manual is the only thing that breaks.
- `.venv/`, `build/`, `dist/`, `*.spec`, `.trelby/`.

## Building a Windows exe (PyInstaller)

```bash
sh tools/build-exe.sh
```

It installs PyInstaller if needed, regenerates the `.gz` files, and builds `dist/Trelby/` (`Trelby.exe` + `_internal/`, which must stay together). Takes about 30s. It refuses to run while `Trelby.exe` is open, since that locks `dist/Trelby/`. If you add a new data file, add an `--add-data` for it in the script.

When the user asks for a "build", "Windows build" or "exe" to test changes, run the full test suite, then the script, then confirm the result. Check that `build/Trelby/PYZ-00.toc` lists any new `trelby.*` modules, and that the exe starts: launch it, then check that `tasklist //V //FI "IMAGENAME eq Trelby.exe" //FO LIST` shows a `Trelby - ...` window title rather than an error dialog. Leave it running for them, and give the path to `dist/Trelby/Trelby.exe`.

## MCP server

`trelby/mcpserver.py` is a stdio MCP server that reads and edits `.trelby` files without the GUI; the operations themselves are in `trelby/mcptools.py` (no MCP SDK dependency, tested in `tests/test_mcptools.py`). The `mcp` SDK is an optional extra (`pip install trelby[mcp]`, entry point `trelby-mcp`) and is not bundled in the exe. Run it from source with `.venv/Scripts/python -m trelby.mcpserver`; for a client config, use the venv's python as the command, `["-m", "trelby.mcpserver"]` as args and the repo root as cwd.

Edits are made to the file on disk, so they don't reach a copy of the script open in the app. Every write needs the revision (content hash) from a previous read, and saves with a `.bak` backup.

## Code conventions worth knowing

- Data files are found relative to the package: `misc.getFullPath("trelby/resources/...")` (uses `misc.progPath`, the parent of the `trelby/` package) or `trelby.__path__[0]`. Use these instead of hard-coded or CWD-relative paths, or the exe build breaks.
- `misc.init()` sets `progPath = "."` in `--test` mode and in tests, so tests must run from the repo root.
- UI strings are wrapped in `_()` for gettext; translations live in `trelby/locales` and `po/` (see `TRANSLATION_NOTES.txt`).
- Version string is duplicated in `pyproject.toml`, `trelby/misc.py`, `doc/version.xml`, and `choco/`; bump all of them together.
- Packaging metadata and dependency bounds live in `pyproject.toml`; `requirements.txt` is the dev install (same bounds plus pytest). Keep them in sync.
- Menu/control IDs: use `wx.NewIdRef()` (not the deprecated `wx.NewId()`). `WindowIDRef` works as a dict key and in `Bind`/`Append`, but doesn't support arithmetic; convert with `int()` when you need it (see `misc.MRUFiles`). Submenus use `AppendSubMenu`.
- Font constants: use `wx.FONTFAMILY_*` / `wx.FONTSTYLE_*` / `wx.FONTWEIGHT_*`, not the old `wx.NORMAL` / `wx.BOLD` / `wx.MODERN`.
- To catch new deprecations, run the app with `.venv/Scripts/python -X dev -W always trelby.py --test`; startup should print no warnings.
