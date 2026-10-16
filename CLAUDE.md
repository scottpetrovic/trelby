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

- `trelby/names.txt.gz`, `trelby/dict_en.dat.gz`: gzipped copies of `names.txt` / `dict_en.dat`, produced by `make` (or `gzip -c`). `gutil.loadMaybeCompressedFile` prefers the uncompressed file, so running from source doesn't need them; they exist only for packaging (PyPI `package_data`, Debian, the exe).
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

The operations are in `trelby/mcptools.py`, which needs neither the MCP SDK nor wx (see [Model and GUI modules](#model-and-gui-modules)): `FileDoc` (file on disk) and `LiveDoc` (an `Editor` on a script in memory, with undo; `mcpapp.AppDoc` uses the tab's `ctrl.ed` and adds the GUI refresh). Edits get an `Editor` (`FileDoc` makes a throwaway one). Every write needs the revision (a content hash) from an earlier read. Tests: `tests/test_mcptools.py`, `tests/test_mcpserver.py`.

The `mcp` SDK is an optional extra (`pip install trelby[mcp]`, entry point `trelby-mcp`); without it the app runs normally and the settings page says the server isn't available. The exe always bundles it (about 25 MB of the ~125 MB `dist/Trelby/`): `tools/build-exe.sh` installs it if missing and fails if the lazily imported MCP/uvicorn modules are missing from `PYZ-00.toc`. To test the exe's server without touching your real settings, run it with `--test` from the repo root and add `MCP/Enabled:True` (and `MCP/Port:N` if a source Trelby already holds 7789) to `.trelby/default.conf`.

For a stdio client config, use the venv's python as the command, `["-m", "trelby.mcpserver"]` (plus `"--app"` for the bridge) as args, and `PYTHONPATH` set to the repo root in `env` (Claude Desktop has no `cwd` option, and trelby isn't pip-installed in the venv). For the exe it's just `Trelby.exe` with `["--mcp-bridge", "--port", "N"]`. Claude Desktop rewrites its config file while running, so quit it fully (tray → Quit) before editing `claude_desktop_config.json`.

## The screenplay model

`trelby/screenplay/` is the script model, with a map of its modules in `__init__.py`. It has two classes, both built from per-area mixins that call each other through `self`:

- `Screenplay` (`model.py`, usually `sp`) is the document: lines, title pages, headers, config, character profiles, world building, and the page breaks worked out from them. Its methods read the script or change lines at positions they're given (`structure`, `wrapping`, `pagination`, `locks`...).
- `Editor` (`editor.py`, usually `ed`) is an editing session on one: `ed.sp`, the cursor (`ed.line` / `ed.column`), the selection (`ed.mark`), the scroll position, the auto-completion list, the typing style and the undo history (`ed.undoHistory`). It has the commands (`ed.cmd("moveLeft")`, `commands`, `textinput`) and every undoable edit (`editing`, `selection`, `formatting`, and the `*EditMixin` classes in `centering`, `dualdialogue`, `locks`, `sceneoutline`). Undo objects (`trelby/undo.py`) take the Editor, since they restore the cursor too.

`MyCtrl` has both (`self.sp`, `self.ed`) and makes a new Editor whenever it gets a new script. Code that only works on a script from the outside is plain functions of `sp`: `export/` (`export.generateFDX(sp)` etc.), `render` (pml page layout for PDF and the page views), `compare`, `proofing`, and `fileformat` (behind `sp.save()` / `Screenplay.load()`).

- The rule for where a method goes: if it records undo, or reads or moves the cursor or selection, it's an Editor method; otherwise it's a Screenplay method. New read-only consumers (exports, reports) go in plain functions, not on either class.
- The wrapping functions (`rewrapPara`, `rewrapElem(s)`, `reformatRange`, `reformatAll`...) take an optional `cursor` (anything with `line` / `column`) that they keep on the same text. The Editor has same-named wrappers that pass itself, and default to the cursor's paragraph / element. `ed.reformatAll()` insists on an empty undo history; `sp.reformatAll()` doesn't check.
- The cursor position saved in a file is `sp.cfg.cursorLine` / `cursorColumn`: `load` sets them, a new `Editor(sp)` starts there, and `ed.save()` stores the cursor before saving. `sp.save()` writes whatever they hold, so save through the Editor when there is one.
- Tests that edit use `u.newEditor()` / `u.loadEditor()` / `u.loadStringEditor()` (`tests/u.py`) and reach the document as `ed.sp`; `ed._validate()` checks the cursor and then the script.
- `import trelby.screenplay as screenplay` still gives `Screenplay`, the `LB_*` / element type constants and the `datatypes` classes. The package's `__init__` must import `constants` before anything else, because `config` and `line` import the package while it's still loading.
- Find and replace: `screenplay/search.py` has `FindOptions` (text, `matchCase`, `wholeWord`, `up`, `elementTypes`: a frozenset of line types or None for all) and the read-only `findNext(sp, line, col, opts)`, which returns a `Match(line, col, length)` or None. It doesn't wrap around (`startPos(sp, up)` is where a whole-script search starts), and going up a match must end at or before `col`. Each line is searched on its own, so matches can't span wrapped lines. The Editor side is `ed.replaceRange(line, col, length, text)`, the one replace primitive: one undo step, rewraps the paragraph, and leaves the cursor just past the new text (or at its start) wherever the rewrap put it. On top of it are `ed.replaceAt(match, text, up)` and `ed.replaceAll(opts, text)` (every match in the script, one undo step). Callers paginate. `finddlg.FindDlg` is only the UI: the last match, the "continue at the start?" question, and `FindState`, which is what the dialog was left showing (`MyCtrl.findState`). `spellcheckdlg` uses `replaceRange` and `spellcheck.suggest(word, dicts, n)`, the n closest words. Tests: `tests/test_search.py`, `tests/test_spellcheck.py`, and `tests/test_finddlg.py`, which drives the dialog's handlers on a `FindDlg.__new__` with stand-in controls.
- Export and import formats are listed once, in `formats.py` (`EXPORT_FORMATS` / `IMPORT_FORMATS`: key, file dialog name, menu label, extensions, the export function or the importer module, options, binary flag). The File menu, its file dialogs, `mcptools.export` and the MCP tool's `format` argument all use it, so a new format goes there. Its texts are functions (`lambda: _("...")`), since the lists are made before the translations are loaded.
- Importers: `trelby/importers/` has one module per format (`astx`, `celtx`, `fadein`, `fdx`, `fountain`, `text`), each with `parse(data, options=None)` returning an `ImportResult` (`lines`, and `titlePages` to replace the script's, or None). `data` is the file's contents, bytes if the module's `BINARY` is set (the zip formats), otherwise str. Errors raise `ImportFailed`, whose `message` is for the user. `common.py` has the shared helpers (`addElem`, `parseXML`, `checkNotEmpty`, `checkLines`). Fountain and text have an `Options` class: Fountain's carries the script's title pages, which it puts the titles on a copy of, finding Title / Author / Contact's strings by `TitleString.kind`; the text importer is split into `guessIndents` and `parse` with `Options(lineTypes=...)`, because the user fixes the guesses in `ImportDlg` in between. `myimport.importFile(fileName, fmt, frame, sp)` is the GUI around them: it reads the file, asks for the options (`ASK_OPTIONS`, by format key), shows the errors, and returns the result, which `MyCtrl.importFile` applies to a new script. Tests: `tests/test_importers.py` pins each format's output on the samples in `tests/fixtures/import/`, through `myimport` with the dialogs answered (`tests/importrun.py`) and through `parse` directly.

## Model and GUI modules

The model imports without wxPython, so the MCP server and anything else working on `.trelby` files runs without it: `screenplay` (including `screenplay.search`), `config`, `commands`, `keys`, `formats`, `util`, `textutil`, `misc`, `pml`, `spellcheck`, the reports, `mcptools`, `importers`... `tests/test_imports.py` checks this (`testModelDoesNotImportWx`), and that each listed module can be the first trelby import. Keep it that way: a model module must not import wx or a GUI module; pass it the data instead (e.g. `spellcheck.loadDict(s)` takes the dictionary's text, and the GUI's `spellcheckdlg.loadDict(frame)` reads the file, with message boxes on errors).

Where things live:

- `misc`: the platform, path and version globals (`init`, `isWindows`, `progPath`, `confPath`, `scriptDir`...), `getFullPath` and `mnemonic`.
- `textutil`: text helpers (case mapping, character classes, `wrapText`, escaping, words). `util`: the other wx-free helpers (numbers, `atomicWrite` and other file helpers, finding the PDF viewer, `ALIGN_*`, `getTextWidth`).
- `config`: `Config` / `ConfigGlobal`, no wx. `commands`: `Command`, the default command table (`defaultCommands()`, which must stay in alphabetical order), the key binding helpers (`addShiftKeys`, `removeKey`, `getConflictingKeys`), and what a key press in the editor does: `makeKeyMap` (via `cfgGl.getKeyMap()`, kept in `gd.keyMap`) and `resolveKey`, which returns the character to type or the `Command` to run. `keys`: `Key`, `MyKeyEvent`, and copies of the `wx.WXK_*` codes it uses (`tests/test_keys.py` checks them against wx).
- GUI: `gutil` (text extents, drawing, `finishWindow`, `getBitmap`, themed widgets, and `loadFile` / `writeToFile` / `showPDF`, which show message boxes on errors), `configgui` (`ConfigGui`, the theme), `tabctrl`, `toolbar`, `mrufiles`, and the small dialogs `checkboxdlg`, `textdlg`, `keydlg`, `scriptchooserdlg`. `checkboxitem` is the wx-free item class `CheckBoxDlg` uses.
- Reports (wx-free): `textreport.TextReport` is the base of the scene, location, character and script reports. Each lays itself out once in `format(tf)`, rendered to PDF (`generate`) or HTML (`generateHtml`); its checkbox options are a class-level `options` list of `(name, label function)`, with the current values in `report.opts`. Who speaks where comes from `screenplay.speeches.iterSpeeches(sp)` (a `Speech` per run of dialogue / parenthetical lines: name, character line, start / end, dialogue and parenthetical lines, scene heading); the reports differ on purpose in what they count from it, see their comments. `scenereport.splitScenes` splits the script at scene headings and act breaks. `dialoguechart` has the chart's data (`DialogueChart`), its sort orders (`SORTS`), and its layout (`generateDoc`). Their windows are in `reports.py`, on `reportwindow.ReportFrame` / `TextReportFrame`. `tests/test_reportoutput.py` compares every report's output with `tests/fixtures/reports/`; after an intended change, rewrite those with `.venv/Scripts/python -m tests.reportdump` and check the diff.
- `pml.BOLD` etc. are defined in `fontinfo` and re-exported by `pml`, since `util` imports `fontinfo` and `pml` imports `util`.

## The main window and the editor

The GUI around one script is split up like this:

- `trelbyframe.MyFrame` (`gd.mainFrame`): the main window. It holds the tabs (`tabctrl`), each a `trelbypanel.MyPanel` with the script's `MyCtrl`, its scroll bar and the outline view, and does the app-wide work: opening, importing and closing scripts, the view mode, zoom, fullscreen, the language, and applying the global settings (`applyGlobalCfg`, which updates every tab). `self.panel` is the current tab.
- `menus.py`: one table (`makeTable`) of `Action`s, one per menu item, toolbar button and menu keyboard command: name, id, label, mnemonic, accelerator, what it runs (`OnScript(scriptactions.f, *args)` or `OnFrame("method", *args)`) and `canUse(frame, ctrl)`, which greys it out. `build` makes the menu bar from it, `bind` binds the ids (EVT_MENU and EVT_UPDATE_UI), and `makeRightClickMenu` makes the editor's right-click menu. A menu keyboard command (`Command.isMenu`) runs the Action of the same name (`frame.runAction(name)`), so a new menu command needs a `Command` in `commands.py` and an Action with that name. `elemTypes()` is the list of element types the toolbar and the right-click menu show.
- `scriptactions.py`: the menu commands that work on one script, as functions `f(frame, ctrl, ...)`: the script dialogs, reports, export, find, goto, clipboard, undo... `frame` is the dialogs' parent.
- `trelbyctrl.MyCtrl`: the editor widget for one script: its file (load, save, autosave), mouse and keyboard input, scrolling, and keeping the screen up to date (`updateScreen`, `makeLineVisible`). `OnKeyChar` uses `commands.resolveKey`: a character is typed, a menu command goes to `frame.runAction`, and other commands run `EDITOR_COMMANDS[name]` on the Editor or a `cmd<name>` method (for the few that need the window, like page up / down).
- `scriptpainter.py`: drawing the script (`ScriptPainter.paint`). It gets a `Viewport` (the script, its Editor, the screen fonts, the window size and the scale) instead of the `MyCtrl`; the view modes (`viewmode.py`) accept one in place of a ctrl when laying out the screen.
- `toolbar.MainToolBar` (the toolbar's buttons and its element type / format / centering controls) and `statusbar.MainStatusBar` (the fields and the zoom buttons). Both run Actions by name for their controls, through `frame.runBarAction`. `frame.showScriptState(ctrl)` shows the current script's state in them.
- `recoverydlg.py`: offering to restore autosaved recovery copies at startup.

App-wide state lives in `globaldata.GlobalData` (`gd`): the configs, `keyMap`, Trelby's own `clipboard`, `showFormatting`, the view mode, zoom...

Tests: `tests/test_menus.py` checks that every menu item and keyboard command has a handler (`PrintScript`, CTRL+P, is listed in Help / Commands but has never had one), and that fixed menu commands' keys match their accelerators. `tests/test_keyinput.py` drives `MyCtrl.OnKeyChar` on a `MyCtrl` made without a window (`MyCtrl.__new__`); `tests/test_scriptpainter.py` paints into a bitmap.

## Code conventions worth knowing

- Data files are found relative to the package: `misc.getFullPath("trelby/resources/...")` (uses `misc.progPath`, the parent of the `trelby/` package) or `trelby.__path__[0]`. Use these instead of hard-coded or CWD-relative paths, or the exe build breaks.
- `misc.init()` sets `progPath = "."` in `--test` mode and in tests, so tests must run from the repo root.
- UI strings are wrapped in `_()` for gettext; translations live in `trelby/locales` and `po/` (see `TRANSLATION_NOTES.txt`).
- Version string is duplicated in `pyproject.toml`, `trelby/misc.py`, `doc/version.xml`, and `choco/`; bump all of them together.
- Packaging metadata and dependency bounds live in `pyproject.toml`; `requirements.txt` is the dev install (same bounds plus pytest). Keep them in sync.
- Menu/control IDs: use `wx.NewIdRef()` (not the deprecated `wx.NewId()`). `WindowIDRef` works as a dict key and in `Bind`/`Append`, but doesn't support arithmetic; convert with `int()` when you need it (see `mrufiles.MRUFiles`). Submenus use `AppendSubMenu`.
- Font constants: use `wx.FONTFAMILY_*` / `wx.FONTSTYLE_*` / `wx.FONTWEIGHT_*`, not the old `wx.NORMAL` / `wx.BOLD` / `wx.MODERN`.
- To catch new deprecations, run the app with `.venv/Scripts/python -X dev -W always trelby.py --test`; startup should print no warnings.
