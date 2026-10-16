import os
import subprocess
import sys

import pytest

# these modules used to fail with a "partially initialized module" error
# when imported before anything else in trelby, because of circular
# imports (util -> config -> pml -> util, and misc -> gutil -> config ->
# pml / screenplay -> misc). each is imported in a fresh interpreter, since
# in this one they're all loaded already.
#
# some modules still can't be imported first (line, undo...).


@pytest.mark.parametrize(
    "module",
    [
        "util",
        "textutil",
        "misc",
        "config",
        "configgui",
        "commands",
        "keys",
        "gutil",
        "fontinfo",
        "pml",
        "titles",
        "truetype",
        "textedit",
        "menubar",
        "commandsdlg",
        "tabctrl",
        "toolbar",
        "checkboxitem",
        "checkboxdlg",
        "scriptchooserdlg",
        "textdlg",
        "keydlg",
        "mrufiles",
        "screenplay",
        "screenplay.export",
        "screenplay.render",
        "screenplay.plaintext",
        "formats",
        "mcptools",
        "importers",
        "importers.fountain",
        "importers.text",
        "myimport",
    ],
)
def testImportFirst(module):
    res = _run("import trelby." + module)

    assert res.returncode == 0, res.stderr


# the model doesn't need wxPython: the MCP server and scripts that work on
# .trelby files run without it. wx belongs in the GUI modules (gutil,
# configgui, the dialogs...).
@pytest.mark.parametrize(
    "module",
    [
        "screenplay",
        "mcptools",
        "config",
        "commands",
        "util",
        "textutil",
        "misc",
        "scriptreport",
        "formats",
        "screenplay.plaintext",
        "importers",
        "importers.astx",
        "importers.celtx",
        "importers.fadein",
        "importers.fdx",
        "importers.fountain",
        "importers.text",
    ],
)
def testModelDoesNotImportWx(module):
    res = _run("import sys, trelby.%s; print('wx' in sys.modules)" % module)

    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == "False"


# run code in a fresh interpreter, from the repo root
def _run(code):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=root,
        capture_output=True,
        text=True,
    )
