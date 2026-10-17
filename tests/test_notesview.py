import pytest
import wx

import tests.u as u
import trelby.config as config
import trelby.screenplay as screenplay
import trelby.translations as translations
import trelby.ui.gutil as gutil

_ = translations.trelby_translations_load()

import trelby.ui.notesview as notesview  # noqa: E402

# the notes sidebar (ui/notesview.py): the × on each card that deletes its
# note, driven with made-up mouse events on a stand-in for the MyPanel and
# MyCtrl, with a real Editor on a script


@pytest.fixture(scope="module")
def app():
    a = wx.App(False)
    gutil.init()
    yield a
    a.Destroy()


class Ctrl:
    def __init__(self, ed):
        self.ed = ed
        self.sp = ed.sp

    def showLine(self, line):
        self.ed.gotoPos(line, 0)

    def addNote(self, line, text):
        return (line, self.ed.addNote(line, text))

    def setNote(self, line, index, note):
        self.ed.setNote(line, index, note)

    def deleteNote(self, line, index):
        self.ed.deleteNote(line, index)

    def Refresh(self, eraseBackground=True):
        pass


class Panel:
    def __init__(self, ed):
        self.ctrl = Ctrl(ed)


@pytest.fixture
def panel(app):
    u.init()

    with open("trelby/sample.trelby", encoding="utf-8") as f:
        sp = screenplay.Screenplay.load(f.read(), config.ConfigGlobal())[0]

    sp.paginate()
    ed = screenplay.Editor(sp)
    ed.addNote(1, "First")
    ed.addNote(1, "Second")
    ed.addNote(8, "Third")

    frame = wx.Frame(None, size=wx.Size(400, 700))
    p = notesview.NotesPanel(frame, Panel(ed))
    frame.Layout()
    p.refresh()

    yield p

    frame.Destroy()


def texts(panel):
    return [n.text for _line, _index, n in panel.getCtrl().sp.getAllNotes()]


def mouse(t, pos):
    e = wx.MouseEvent(t)
    e.SetPosition(pos)

    return e


def centre(rect):
    return wx.Point(rect.x + rect.width // 2, rect.y + rect.height // 2)


# the middle of row n's ×
def closePos(panel, n):
    lc = panel.list

    return centre(lc.getCloseRect(lc.GetItemRect(n)))


def testCloseHitTest(panel):
    lc = panel.list
    assert len(panel.items) == 3

    for n in range(3):
        assert lc.closeHitTest(closePos(panel, n)) == n

    # the card's text, and left of the ×
    rect = lc.GetItemRect(1)
    assert lc.closeHitTest(centre(rect)) is None
    pos = closePos(panel, 1)
    assert lc.closeHitTest(wx.Point(pos.x - lc.smallHeight, pos.y)) is None


def testClickingCloseDeletes(panel):
    ed = panel.getCtrl().ed

    panel.OnListLeftDown(mouse(wx.wxEVT_LEFT_DOWN, closePos(panel, 1)))
    assert texts(panel) == ["First", "Third"]
    assert [it.note.text for it in panel.items] == ["First", "Third"]

    # one undo step
    ed.cmd("undo")
    assert texts(panel) == ["First", "Second", "Third"]

    # the second click of a double-click deletes nothing more
    panel.refresh()
    panel.OnListLeftDClick(mouse(wx.wxEVT_LEFT_DCLICK, closePos(panel, 1)))
    assert texts(panel) == ["First", "Second", "Third"]


def testCloseWhileEditing(panel):
    panel.startEdit(0)

    # the card being edited has no ×
    assert panel.list.closeHitTest(closePos(panel, 0)) is None

    panel.editing[1].SetValue("First, changed")
    pos = closePos(panel, 2)
    panel.OnListLeftDown(mouse(wx.wxEVT_LEFT_DOWN, pos))

    # the edit is kept, and the note clicked on deleted
    assert panel.editing is None
    assert texts(panel) == ["First, changed", "Second"]


def testCloseWhileEditingEmptiedNote(panel):
    panel.startEdit(0)
    panel.editing[1].SetValue("")
    panel.OnListLeftDown(mouse(wx.wxEVT_LEFT_DOWN, closePos(panel, 1)))

    # the emptied note is deleted when the edit ends, and the one clicked
    # on is still found though its index changed
    assert texts(panel) == ["Third"]
