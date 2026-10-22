from unittest import mock

import pytest
import wx

import tests.u as u
import trelby.screenplay.proofing as proofing
import trelby.translations as translations

_ = translations.trelby_translations_load()

import trelby.dialogs.formattingerrorsdlg as formattingerrorsdlg  # noqa: E402

# the Formatting Errors dialog (dialogs/formattingerrorsdlg.py) on
# fixtures/formatting-errors.trelby: its rows, and the cursor moving to the
# selected error


# a stand-in for the MyCtrl, with a real Editor on the script
class Ctrl:
    def __init__(self, ed):
        self.ed = ed
        self.sp = ed.sp
        self.fileNameDisplay = "formatting-errors.trelby"
        self.visible = None

    def makeLineVisible(self, line):
        self.visible = line

    def updateScreen(self):
        pass


@pytest.fixture
def dlg(app):
    ed = u.loadEditor("formatting-errors.trelby")
    ed.line, ed.column = 3, 5

    d = formattingerrorsdlg.FormattingErrorsDlg(
        None, Ctrl(ed), proofing.findErrors(ed.sp)
    )
    d.EndModal = mock.Mock()
    yield d
    d.Destroy()


def rows(d):
    return [
        [d.list.GetItemText(i, c) for c in range(d.list.GetColumnCount())]
        for i in range(d.list.GetItemCount())
    ]


def testRows(dlg):
    assert rows(dlg) == [
        ["1", "Action", "Empty line.", "(empty)"],
        [
            "1",
            "Character",
            "Element type 'Action' can not follow type 'Character'.",
            "DETECTIVE HALE",
        ],
        [
            "1",
            "Dialogue",
            "Element type 'Dialogue' can not follow type 'Action'.",
            "Coffee. Black.",
        ],
        ["1", "Parenthetical", "Empty parenthetical.", "()"],
        [
            "2",
            "Parenthetical",
            "Element type 'Parenthetical' can not follow type 'Action'.",
            "(to himself)",
        ],
        ["2", "Action", "Empty line (contains only spaces).", "(3 spaces)"],
        [
            "2",
            "Dialogue",
            "Element type 'Dialogue' can not follow type 'Scene'.",
            "Nobody home.",
        ],
    ]


def testLongTextIsCutShort(dlg):
    s = dlg.shownText("x" * 100)

    assert len(s) == dlg.MAX_TEXT
    assert s.endswith("...")


def testGoToMovesCursorToSelectedError(dlg):
    ed = dlg.ctrl.ed
    dlg.list.Select(4)
    dlg.OnGoTo(None)

    assert (ed.line, ed.column) == (dlg.errors[4].line, 0)
    assert dlg.ctrl.visible == dlg.errors[4].line
    dlg.EndModal.assert_called_once_with(wx.ID_OK)


def testCloseRestoresCursor(dlg):
    ed = dlg.ctrl.ed
    dlg.showLine(dlg.errors[2].line)
    dlg.OnClose(None)

    assert (ed.line, ed.column) == (3, 5)
    dlg.EndModal.assert_called_once_with(wx.ID_CANCEL)
