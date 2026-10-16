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
# line and undo couldn't be, before line moved into the screenplay
# package.


@pytest.mark.parametrize(
    "module",
    [
        "util",
        "textutil",
        "misc",
        "config",
        "ui.configgui",
        "commands",
        "keys",
        "ui.gutil",
        "ui.fileio",
        "ui.icons",
        "ui.theming",
        "ui.widgets",
        "ui.scrollbar",
        "pdf.fontinfo",
        "pdf.pml",
        "pdf.truetype",
        "ui.textedit",
        "ui.menubar",
        "dialogs.commandsdlg",
        "ui.tabctrl",
        "ui.toolbar",
        "checkboxitem",
        "dialogs.checkboxdlg",
        "dialogs.scriptchooserdlg",
        "dialogs.textdlg",
        "dialogs.keydlg",
        "ui.mrufiles",
        "screenplay",
        "screenplay.export",
        "screenplay.render",
        "screenplay.plaintext",
        "screenplay.speeches",
        "screenplay.search",
        "screenplay.line",
        "screenplay.titles",
        "screenplay.headers",
        "screenplay.characterprofiles",
        "screenplay.locations",
        "screenplay.worldbuilding",
        "screenplay.pagelock",
        "screenplay.autocompletion",
        "screenplay.autocompletiontype",
        "undo",
        "spellcheck",
        "thesaurus",
        "formats",
        "mcpserver.tools",
        "importers",
        "importers.fountain",
        "importers.pdf",
        "importers.text",
        "ui.myimport",
        "reports.scenereport",
        "reports.characterreport",
        "reports.dialoguechart",
        "reports.reportframes",
        "dialogs.finddlg",
        "dialogs.spellcheckdlg",
    ],
)
def testImportFirst(module):
    res = _run("import trelby." + module)

    assert res.returncode == 0, res.stderr


# the model doesn't need wxPython: the MCP server and scripts that work on
# .trelby files run without it. wx belongs in the GUI modules (ui/,
# dialogs/).
@pytest.mark.parametrize(
    "module",
    [
        "screenplay",
        "mcpserver.tools",
        "config",
        "commands",
        "util",
        "textutil",
        "misc",
        "reports.textreport",
        "reports.scenereport",
        "reports.locationreport",
        "reports.characterreport",
        "reports.scriptreport",
        "reports.dialoguechart",
        "ui.pagelist",
        "screenplay.speeches",
        "formats",
        "screenplay.plaintext",
        "screenplay.search",
        "screenplay.line",
        "screenplay.titles",
        "screenplay.headers",
        "screenplay.characterprofiles",
        "screenplay.locations",
        "screenplay.worldbuilding",
        "screenplay.pagelock",
        "screenplay.autocompletion",
        "screenplay.autocompletiontype",
        "undo",
        "spellcheck",
        "thesaurus",
        "importers",
        "importers.astx",
        "importers.celtx",
        "importers.fadein",
        "importers.fdx",
        "importers.fountain",
        "importers.pdf",
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
