import os
from typing import Union
from unittest import mock

import wx

import tests.u as u
import trelby.myimport as myimport
import trelby.screenplay as screenplay
import trelby.screenplay.export as export
import trelby.translations as translations
from trelby.line import Line

_ = translations.trelby_translations_load()


def testImportCeltx() -> None:
    u.init()
    location = os.path.dirname(__file__)
    pathToTestScriptCeltx = os.path.join(location, "fixtures/test.celtx")

    importedLines = myimport.importCeltx(pathToTestScriptCeltx, mock.Mock())

    assert importedLines is not None

    # in order to compare the screenplays, we need to reformat it with the same configuration as the loaded one
    importedScreenplay = u.new()
    importedScreenplay.lines = importedLines
    importedScreenplay.reformatAll()

    expectedScreenplay = u.load()

    for line, expectedLine in zip(importedScreenplay.lines, expectedScreenplay.lines):
        assert line == expectedLine


def testImportTextFile() -> None:
    u.init()
    location = os.path.dirname(__file__)
    pathToTestScriptTxt = os.path.join(location, "fixtures/test.txt")

    # accept the "Adjust styles" dialog as it comes up
    dlg = mock.Mock()
    dlg.ShowModal.return_value = wx.ID_OK

    with mock.patch.object(myimport, "ImportDlg", return_value=dlg):
        lines = myimport.importTextFile(pathToTestScriptTxt, mock.Mock())

    expectedScreenplay = u.load()
    for line, expectedLine in zip(lines, expectedScreenplay.lines):
        assert TextImportMatcher(line) == TextImportMatcher(expectedLine)


# return the dual dialogue blocks in imported lines, as lists of the
# character names in them
def importedDuals(lines):
    sp = u.new()
    sp.lines = lines
    sp.reformatAll()

    blocks = {
        sp.getDualBlock(i)
        for i, ln in enumerate(sp.lines)
        if ln.lt == screenplay.CHARACTER and sp.getDualBlock(i)
    }

    return sorted(
        [sp.lines[first].text, sp.lines[right].text] for first, right, last in blocks
    )


def dualScript():
    import tests.test_dualdialogue as dd

    return dd.makeScript()


def testImportFDXDualDialogue(tmp_path) -> None:
    path = tmp_path / "dual.fdx"
    path.write_bytes(export.generateFDX(dualScript().sp))

    lines = myimport.importFDX(str(path), mock.Mock())

    assert importedDuals(lines) == [["BRICK", "STEEL"]]


def testImportFountainDualDialogue(tmp_path) -> None:
    path = tmp_path / "dual.fountain"
    path.write_text(export.generateFountain(dualScript().sp), encoding="UTF-8")

    dlg = mock.Mock()
    dlg.ShowModal.return_value = myimport.wx.ID_OK

    with mock.patch.object(myimport.checkboxdlg, "CheckBoxDlg", return_value=dlg):
        lines, titlePages = myimport.importFountain(str(path), mock.Mock(), [])

    assert importedDuals(lines) == [["BRICK", "STEEL"]]
    assert "^" not in "".join(ln.text for ln in lines)


class TextImportMatcher:
    line: Line

    def __init__(self, line: Line):
        self.line = line

    def __eq__(self, other):
        """
        The text import has some known limitations:
            - depending on the export config, some lines are all caps, so it can't reliably preserve case
            - it can't reliably detect linebreak types
            - sometimes, it can't distinguish ACTION from SCENE types
        That's why this implementation is not so hard on it, and only compares the text case-insensitively, doesn't
        compare linebreak types at all and only compares the line type if it's not ACTION or SCENE
        """
        if not isinstance(other, TextImportMatcher):
            return NotImplemented
        if self.line.text.lower() != other.line.text.lower():
            return False
        if (
            self.line.lt != screenplay.ACTION
            and self.line.lt != screenplay.SCENE
            and self.line.lt != other.line.lt
        ):
            return False
        return True

    def __repr__(self) -> str:
        return self.line.__str__()
