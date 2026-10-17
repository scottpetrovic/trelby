import pytest
import wx

import tests.u as u
import trelby.config as config
import trelby.screenplay as screenplay
import trelby.translations as translations
import trelby.ui.gutil as gutil
from tests.test_keyinput import makeCtrl
from trelby.screenplay.notes import Note

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

    # the whole column is the button, but not the card's text left of it
    rect = lc.GetItemRect(1)
    cr = lc.getCloseRect(rect)
    assert lc.closeHitTest(wx.Point(cr.x + 1, rect.y + 1)) == 1
    assert lc.closeHitTest(wx.Point(cr.GetRight(), rect.y + rect.height - 2)) == 1
    assert lc.closeHitTest(centre(rect)) is None
    assert lc.closeHitTest(wx.Point(cr.x - 1, cr.y + 1)) is None


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


# the scroll bar is only there when the list can scroll, so it doesn't
# take room from the cards
def testScrollBarOnlyWhenNeeded(panel):
    panel.layoutList()
    assert not panel.scrollBar.IsShown()

    ed = panel.getCtrl().ed

    for i in range(30):
        ed.addNote(8, "Note %d" % i)

    panel.refresh()
    panel.layoutList()
    assert panel.scrollBar.IsShown()


# a new note left empty, on a script with no other notes, goes away when
# the editing ends, and the panel says there are no notes
@pytest.mark.parametrize("keep", [True, False])
def testEmptyNewNoteOnScriptWithoutNotes(app, keep):
    ed = u.newEditor()

    frame = wx.Frame(None, size=wx.Size(400, 700))
    p = notesview.NotesPanel(frame, Panel(ed))
    frame.Layout()

    try:
        p.refresh()
        assert p.emptyText.IsShown()

        p.addNote()
        assert p.editing
        assert p.list.GetItemCount() == 1

        p.finishEdit(keep)

        assert p.items == []
        assert p.list.GetItemCount() == 0
        assert p.emptyText.IsShown()
        assert texts(p) == []

        # a note added after that can be edited
        p.addNote()
        p.editing[1].SetValue("Hello")
        p.finishEdit(True)
        assert texts(p) == ["Hello"]
        assert p.list.GetItemCount() == 1

        p.startEdit(0)
        assert p.editing
        p.finishEdit(False)
    finally:
        frame.Destroy()


# the right-click menu of a note beside the page in the script, with the
# menu answered by its item's label
def answerMenu(ctrl, label):
    def popup(menu, pos):
        ctrl.menuLabels = [it.GetItemLabelText() for it in menu.GetMenuItems()]

        return menu.FindItem(label) if label else wx.ID_NONE

    ctrl.GetPopupMenuSelectionFromUser = popup


def noteCtrl():
    sp = u.new()
    sp.lines[0].text = "Hello"
    ctrl = makeCtrl(sp)
    ctrl.clearAutoComp = lambda: None
    ctrl.ed.addNote(0, "One")
    ctrl.ed.addNote(0, "Two")

    return ctrl


def testNoteMenuResolveAndDelete(app):
    ctrl = noteCtrl()
    sp = ctrl.sp

    answerMenu(ctrl, _("Mark as resolved"))
    ctrl.noteMenu(0, 1, wx.Point(0, 0))
    assert ctrl.menuLabels == [_("Edit"), _("Mark as resolved"), _("Delete")]
    assert sp.getParaNotes(0) == (Note("One"), Note("Two", resolved=True))

    answerMenu(ctrl, _("Mark as not resolved"))
    ctrl.noteMenu(0, 1, wx.Point(0, 0))
    assert sp.getParaNotes(0) == (Note("One"), Note("Two"))

    answerMenu(ctrl, _("Delete"))
    ctrl.noteMenu(0, 0, wx.Point(0, 0))
    assert sp.getParaNotes(0) == (Note("Two"),)

    # cancelled
    answerMenu(ctrl, None)
    ctrl.noteMenu(0, 0, wx.Point(0, 0))
    assert sp.getParaNotes(0) == (Note("Two"),)

    # an icon for a paragraph's only note acts on it
    answerMenu(ctrl, _("Delete"))
    ctrl.noteMenu(0, None, wx.Point(0, 0))
    assert sp.getParaNotes(0) == ()
