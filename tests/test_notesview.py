import time
from types import SimpleNamespace

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

import trelby.ui.noteeditor as noteeditor  # noqa: E402
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
    ctrl.noteChecks = []

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


# editing a note on its card beside the page (ui/noteeditor.py), on a
# stand-in for the MyCtrl that's a real window, so the text field has a
# parent
class EditCtrl(wx.Panel):
    def __init__(self, parent, ed):
        wx.Panel.__init__(self, parent)
        self.ed = ed
        self.sp = ed.sp
        self.noteEditor = None
        self.newNoteLine = None

    def getCfgGui(self):
        return SimpleNamespace(textBgColor=wx.WHITE, textColor=wx.BLACK)

    def addNote(self, line, text):
        self.ed.addNote(line, text)

    def setNote(self, line, index, note):
        self.ed.setNote(line, index, note)

    def deleteNote(self, line, index):
        self.ed.deleteNote(line, index)


@pytest.fixture
def editCtrl(app):
    ed = u.newEditor()
    ed.sp.lines[0].text = "Hello"
    ed.addNote(0, "One")
    ed.addNote(0, "Two")

    frame = wx.Frame(None, size=wx.Size(600, 400))
    ctrl = EditCtrl(frame, ed)

    yield ctrl

    frame.Destroy()


def startEdit(ctrl, index, rect=wx.Rect(10, 20, 200, 30)):
    ctrl.noteEditor = noteeditor.NoteEditor(ctrl, 0, index, rect)

    return ctrl.noteEditor


def testInlineEditKeeps(editCtrl):
    e = startEdit(editCtrl, 1)
    assert e.text.GetValue() == "Two"

    # at least EDIT_LINES high, over the card
    r = e.text.GetRect()
    assert (r.x, r.y, r.width) == (10, 20, 200)
    assert r.height >= e.text.GetCharHeight() * noteeditor.EDIT_LINES

    e.text.SetValue("Two\nlines ")
    e.finish(True)

    assert editCtrl.noteEditor is None
    assert editCtrl.sp.getParaNotes(0) == (Note("One"), Note("Two\nlines"))

    # it's done once
    e.text.SetValue("Again")
    e.finish(True)
    assert editCtrl.sp.getParaNotes(0) == (Note("One"), Note("Two\nlines"))


def testInlineEditCancels(editCtrl):
    e = startEdit(editCtrl, 0)
    e.text.SetValue("Changed")
    e.finish(False)

    assert editCtrl.sp.getParaNotes(0) == (Note("One"), Note("Two"))


def testInlineEditEmptiedDeletes(editCtrl):
    e = startEdit(editCtrl, 0)
    e.text.SetValue("  ")
    e.finish(True)

    assert editCtrl.sp.getParaNotes(0) == (Note("Two"),)


# a note that moved among its paragraph's notes while it was edited is
# still the one changed, and one that's gone isn't brought back
def testInlineEditFindsMovedNote(editCtrl):
    e = startEdit(editCtrl, 1)
    editCtrl.ed.deleteNote(0, 0)
    e.text.SetValue("Moved")
    e.finish(True)

    assert editCtrl.sp.getParaNotes(0) == (Note("Moved"),)

    e = startEdit(editCtrl, 0)
    editCtrl.ed.deleteNote(0, 0)
    e.text.SetValue("Gone")
    e.finish(True)

    assert editCtrl.sp.getParaNotes(0) == ()


# the text field follows its card when the script is drawn again, and
# the editing ends when the card is gone
def testInlineEditFollowsCard(editCtrl):
    e = startEdit(editCtrl, 1)
    e.text.SetValue("New")

    e.update([(wx.Rect(0, 0, 100, 10), 0, 0), (wx.Rect(30, 70, 150, 30), 0, 1)])
    assert e.text.GetRect().GetPosition() == wx.Point(30, 70)
    assert editCtrl.noteEditor is e

    e.update([(wx.Rect(0, 0, 100, 10), 0, 0)])
    wx.Yield()

    assert editCtrl.noteEditor is None
    assert editCtrl.sp.getParaNotes(0) == (Note("One"), Note("New"))


class ClickEvent:
    def __init__(self, pos):
        self.pos = pos

    def GetPosition(self):
        return self.pos


# clicking a note card's checkbox marks the note resolved or not, and so
# does each click of a double click on it
def testNoteCheckBox(app):
    ctrl = noteCtrl()
    sp = ctrl.sp
    ctrl.noteChecks = [(wx.Rect(10, 10, 20, 20), 0, 1)]

    assert not ctrl.toggleNoteCheckAt(wx.Point(5, 5))
    assert ctrl.toggleNoteCheckAt(wx.Point(15, 15))
    assert sp.getParaNotes(0) == (Note("One"), Note("Two", resolved=True))

    ctrl.OnLeftDClick(ClickEvent(wx.Point(15, 15)))
    assert sp.getParaNotes(0) == (Note("One"), Note("Two"))

    ctrl.ed.cmd("undo")
    assert sp.getParaNotes(0) == (Note("One"), Note("Two", resolved=True))


# a double click on a note beside the page edits the note the first click
# was on, even if it has moved since; an icon edits a paragraph's only
# note, and there's nothing to edit for one with more
def testNoteDClick(app):
    ctrl = noteCtrl()
    edited = []
    ctrl.editNote = lambda line, index: edited.append((line, index))
    ctrl.lastDClick = None
    ctrl.lastNoteClick = (time.monotonic(), (0, 1))

    ctrl.OnLeftDClick(ClickEvent(wx.Point(0, 0)))
    assert edited == [(0, 1)]
    assert ctrl.lastNoteClick is None

    ctrl.noteDClick(0, None)
    assert edited == [(0, 1)]

    ctrl.ed.deleteNote(0, 0)
    ctrl.noteDClick(0, None)
    assert edited == [(0, 1), (0, 0)]


# a new note, written on the blank card after the paragraph's notes, is
# added when it's finished with some text, and not otherwise
@pytest.mark.parametrize(
    "keep, text, added",
    [(True, " Three ", ("Three",)), (True, " ", ()), (False, "Three", ())],
)
def testInlineNewNote(editCtrl, keep, text, added):
    editCtrl.newNoteLine = 0
    e = startEdit(editCtrl, None)
    assert e.text.GetValue() == ""

    # it follows the blank card, whose index is the new note's
    e.update([(wx.Rect(0, 0, 100, 10), 0, 1), (wx.Rect(30, 70, 150, 30), 0, 2)])
    assert e.text.GetRect().GetPosition() == wx.Point(30, 70)

    e.text.SetValue(text)
    e.finish(keep)

    assert editCtrl.noteEditor is None
    assert editCtrl.newNoteLine is None
    assert [n.text for n in editCtrl.sp.getParaNotes(0)] == ["One", "Two"] + list(
        added
    )


# clicking a note's card beside the page puts the cursor on its paragraph
# and selects the note in the notes sidebar if it's shown, but doesn't
# show the sidebar; a note icon does, since its notes can't be read
# anywhere else
def testNoteClickOpensSidebarOnlyForIcons(app):
    ctrl = noteCtrl()
    shown = []
    selected = []

    def setShowNotes(show):
        shown.append(show)
        ctrl.gd.showNotes = show

    ctrl.gd.showNotes = False
    ctrl.gd.mainFrame = SimpleNamespace(setShowNotes=setShowNotes)
    ctrl.panel = SimpleNamespace(
        notes=SimpleNamespace(showNotesOf=lambda *args: selected.append(args))
    )
    ctrl.showLine = lambda line: None

    ctrl.showNote(0, 1)
    assert (shown, selected) == ([], [])

    ctrl.showNote(0, None, True)
    assert (shown, selected) == ([True], [(0, None)])

    ctrl.showNote(0, 1)
    assert (shown, selected) == ([True], [(0, None), (0, 1)])
