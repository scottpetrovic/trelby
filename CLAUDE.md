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

AI assistants can read and edit scripts over MCP, with one set of tools (`makeServer` in `trelby/mcpserver.py`) served three ways:

- **Files on disk:** `.venv/Scripts/python -m trelby.mcpserver` (stdio). Every write saves the file with a `.bak` backup, and doesn't reach a copy of the script open in the app.
- **In the app:** Settings → MCP Server turns on an HTTP server at `http://127.0.0.1:7789/mcp` (`trelby/mcpapp.py`, off by default, `mcpEnabled` / `mcpPort` in the global config). It edits the open scripts live: the `path` argument picks a script, defaulting to the active tab. Calls run in the GUI thread via `wx.CallAfter`; edits are undoable and refused while a modal dialog is open.
- **Bridge:** `python -m trelby.mcpserver --app [--port N]` is a stdio server that forwards to the app, for Claude Desktop, which can only start servers. The exe runs it as `Trelby.exe --mcp-bridge [--port N]` (checked in `trelby.trelby.main` before any wx startup; stdio works even though the exe is windowed). The settings page has a button that copies its config entry, in whichever form is running.

The operations are in `trelby/mcptools.py`, which needs neither the MCP SDK nor wx: `FileDoc` (file on disk) and `LiveDoc` (script in memory, with undo; `mcpapp.AppDoc` adds the GUI refresh). Every write needs the revision (a content hash) from an earlier read. Tests: `tests/test_mcptools.py`, `tests/test_mcpserver.py`.

The `mcp` SDK is an optional extra (`pip install trelby[mcp]`, entry point `trelby-mcp`); without it the app runs normally and the settings page says the server isn't available. The exe always bundles it (about 25 MB of the ~125 MB `dist/Trelby/`): `tools/build-exe.sh` installs it if missing and fails if the lazily imported MCP/uvicorn modules are missing from `PYZ-00.toc`. To test the exe's server without touching your real settings, run it with `--test` from the repo root and add `MCP/Enabled:True` (and `MCP/Port:N` if a source Trelby already holds 7789) to `.trelby/default.conf`.

For a stdio client config, use the venv's python as the command, `["-m", "trelby.mcpserver"]` (plus `"--app"` for the bridge) as args, and `PYTHONPATH` set to the repo root in `env` (Claude Desktop has no `cwd` option, and trelby isn't pip-installed in the venv). For the exe it's just `Trelby.exe` with `["--mcp-bridge", "--port", "N"]`. Claude Desktop rewrites its config file while running, so quit it fully (tray → Quit) before editing `claude_desktop_config.json`.

## The screenplay model

`trelby/screenplay/` is the document model, with a map of its modules in `__init__.py`. `Screenplay` (`model.py`) holds a script's state and gets most of its methods from per-area mixins (`structure`, `wrapping`, `pagination`, `locks`, `selection`, `commands`, `textinput`...), which call each other through `self`. Code that only works on a script from the outside is plain functions of `sp`: `export/` (`export.generateFDX(sp)` etc.), `render` (pml page layout for PDF and the page views), `compare`, `proofing`, and `fileformat` (behind `sp.save()` / `Screenplay.load()`). The undo history is `sp.undoHistory` (`undohistory.py`).

- New editing behavior goes in the mixin for its area, and new read-only consumers (exports, reports) go in plain functions, not on the class.
- `import trelby.screenplay as screenplay` still gives `Screenplay`, the `LB_*` / element type constants and the `datatypes` classes. The package's `__init__` must import `constants` before anything else, because `config` and `line` import the package while it's still loading.
- `mcptools.py` has its own `export` function, so it imports the export package as `exporters`.

## Code conventions worth knowing

- Data files are found relative to the package: `misc.getFullPath("trelby/resources/...")` (uses `misc.progPath`, the parent of the `trelby/` package) or `trelby.__path__[0]`. Use these instead of hard-coded or CWD-relative paths, or the exe build breaks.
- `misc.init()` sets `progPath = "."` in `--test` mode and in tests, so tests must run from the repo root.
- UI strings are wrapped in `_()` for gettext; translations live in `trelby/locales` and `po/` (see `TRANSLATION_NOTES.txt`).
- Version string is duplicated in `pyproject.toml`, `trelby/misc.py`, `doc/version.xml`, and `choco/`; bump all of them together.
- Packaging metadata and dependency bounds live in `pyproject.toml`; `requirements.txt` is the dev install (same bounds plus pytest). Keep them in sync.
- Menu/control IDs: use `wx.NewIdRef()` (not the deprecated `wx.NewId()`). `WindowIDRef` works as a dict key and in `Bind`/`Append`, but doesn't support arithmetic; convert with `int()` when you need it (see `misc.MRUFiles`). Submenus use `AppendSubMenu`.
- Font constants: use `wx.FONTFAMILY_*` / `wx.FONTSTYLE_*` / `wx.FONTWEIGHT_*`, not the old `wx.NORMAL` / `wx.BOLD` / `wx.MODERN`.
- To catch new deprecations, run the app with `.venv/Scripts/python -X dev -W always trelby.py --test`; startup should print no warnings.
