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
# some modules still can't be imported first (pml, titles, line, undo...).


@pytest.mark.parametrize(
    "module",
    ["util", "fontinfo", "truetype", "textedit", "menubar", "commandsdlg"],
)
def testImportFirst(module):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    res = subprocess.run(
        [sys.executable, "-c", "import trelby." + module],
        cwd=root,
        capture_output=True,
        text=True,
    )

    assert res.returncode == 0, res.stderr
