import copy

import pytest
import wx

import tests.u as u
import trelby.config as config
import trelby.screenplay.beatboard as beatboard
import trelby.translations as translations
import trelby.ui.configgui as configgui
import trelby.ui.gutil as gutil

_ = translations.trelby_translations_load()

import trelby.ui.beatboardview as beatboardview  # noqa: E402

# the beat board view (ui/beatboardview.py): drawing the board into a
# bitmap, driving it with made-up mouse and key events, and its changes
# going into the script as undo steps


@pytest.fixture(scope="module")
def app():
    a = wx.App(False)
    gutil.init()
    yield a
    a.Destroy()


# stand-ins for the MyPanel the view is in and its MyCtrl, with a real
# Editor on a script
class Ctrl:
    def __init__(self, ed):
        self.ed = ed
        self.sp = ed.sp
        self.updates = 0

    def updateScreen(self, redraw=True):
        self.updates += 1


class Panel:
    def __init__(self, ed):
        self.ctrl = Ctrl(ed)


@pytest.fixture
def view(app):
    board = beatboard.BeatBoard()
    board.beats.append(beatboard.Beat("Opening image\nThe city at dawn.", 20, 20))

    b = beatboard.Beat("Catalyst", 240, 20)
    b.color = "ffd1a3"
    board.beats.append(b)

    board.beats.append(beatboard.Beat("Midpoint", 460, 20))
    board.beats.append(beatboard.Beat("", 700, 180))

    ed = u.newEditor()
    ed.sp.beatBoard = board

    frame = wx.Frame(None)
    v = beatboardview.BeatBoardView(frame, Panel(ed))
    v.SetClientSize(v.FromDIP(wx.Size(960, 560)))
    v.reload()

    yield v

    frame.Destroy()


def ed(view):
    return view.panel.ctrl.ed


def paint(view):
    bmp = wx.Bitmap(*view.GetClientSize())
    dc = wx.MemoryDC(bmp)
    view.DoPrepareDC(dc)
    view.paint(dc)
    dc.SelectObject(wx.NullBitmap)

    return bmp.ConvertToImage()


def pixel(img, x, y):
    return (img.GetRed(x, y), img.GetGreen(x, y), img.GetBlue(x, y))


def mouse(t, x, y):
    e = wx.MouseEvent(t)
    e.SetPosition(wx.Point(x, y))

    return e


# a motion event with the left button down
def drag(x, y):
    e = mouse(wx.wxEVT_MOTION, x, y)
    e.SetLeftDown(True)

    return e


def key(t, code):
    e = wx.KeyEvent(t)
    e.SetKeyCode(code)

    return e


def editKey(code, ctrl=False):
    e = key(wx.wxEVT_CHAR_HOOK, code)
    e.SetControlDown(ctrl)

    return e


def test_copy(view):
    # the view shows a copy of the script's board
    assert view.board is not ed(view).sp.beatBoard
    assert view.board.save() == ed(view).sp.beatBoard.save()


def test_hint(view, monkeypatch):
    w, h = view.GetClientSize()
    withHint = paint(view)

    monkeypatch.setattr(view, "drawHint", lambda *args: None)
    without = paint(view)

    def differs(x0, x1, y0, y1):
        return any(
            pixel(withHint, x, y) != pixel(without, x, y)
            for x in range(x0, x1)
            for y in range(y0, y1)
        )

    # it's in the middle
    assert differs(w // 2 - 40, w // 2 + 40, h // 2 - 10, h // 2 + 10)
    assert not differs(0, w, 0, h // 4)


@pytest.mark.parametrize("theme", [None, "Light", "Dark"])
def test_paint(view, theme):
    if theme:
        cfgGl = config.ConfigGlobal()
        cfgGl.theme = theme
        view.applyTheme(configgui.ConfigGui(cfgGl, 100))

    catalyst = view.board.beats[1]
    view.select(catalyst)

    img = paint(view)
    step = view.FromDIP(beatboardview.GRID)

    # on a grid line, away from the cards, and in the middle of a square
    x = 20 * step + step // 2
    y = 12 * step
    assert pixel(img, x, y) != pixel(img, x, y + step // 2)

    # a card covers the grid
    r = view.cardRect(catalyst)
    assert pixel(img, r.x + r.width // 2, r.GetBottom() - 4) == (255, 209, 163)

    # and scrolled
    view.scrollTo(37, 53)
    paint(view)


def test_middlePan(view):
    view.OnMiddleDown(mouse(wx.wxEVT_MIDDLE_DOWN, 300, 300))
    view.OnMotion(mouse(wx.wxEVT_MOTION, 200, 250))
    assert view.GetViewStart() == (100, 50)

    # not above or left of the board's corner
    view.OnMotion(mouse(wx.wxEVT_MOTION, 500, 500))
    assert view.GetViewStart() == (0, 0)

    view.OnMiddleUp(mouse(wx.wxEVT_MIDDLE_UP, 500, 500))
    assert not view.pan
    assert not view.HasCapture()
    assert not ed(view).undoHistory.canUndo()


def test_spacePan(view):
    beat = view.board.beats[0]
    r = view.cardRect(beat)
    x, y = r.x + 10, r.y + 10

    # space goes to the board when it has the focus, and keeps being held
    # down while it has
    view.SetFocus()
    wx.SafeYield()
    view.OnKeyDown(key(wx.wxEVT_KEY_DOWN, wx.WXK_SPACE))
    assert view.spaceDown

    # pressing on a card pans instead of grabbing it
    view.OnLeftDown(mouse(wx.wxEVT_LEFT_DOWN, x, y))
    view.OnMotion(mouse(wx.wxEVT_MOTION, x - 30, y - 40))
    assert view.GetViewStart() == (30, 40)
    assert (beat.x, beat.y) == (20, 20)
    assert not view.drag

    view.OnLeftUp(mouse(wx.wxEVT_LEFT_UP, x - 30, y - 40))
    view.OnKeyUp(key(wx.wxEVT_KEY_UP, wx.WXK_SPACE))
    assert not (view.pan or view.spaceDown or view.HasCapture())


def test_dragCard(view):
    beat = view.board.beats[0]
    r = view.cardRect(beat)
    x, y = r.x + 10, r.y + 10

    # a click without moving changes nothing
    view.OnLeftDown(mouse(wx.wxEVT_LEFT_DOWN, x, y))
    view.OnLeftUp(mouse(wx.wxEVT_LEFT_UP, x, y))
    assert view.selected is beat
    assert not ed(view).undoHistory.canUndo()

    view.OnLeftDown(mouse(wx.wxEVT_LEFT_DOWN, x, y))
    view.OnMotion(drag(x + view.FromDIP(50), y + view.FromDIP(30)))
    view.OnLeftUp(mouse(wx.wxEVT_LEFT_UP, x, y))
    assert (beat.x, beat.y) == (70, 50)

    # the moved card comes to the front, and that's in the script
    assert view.board.beats[-1] is beat
    sp = ed(view).sp
    assert (sp.beatBoard.beats[-1].x, sp.beatBoard.beats[-1].y) == (70, 50)
    assert view.panel.ctrl.updates == 1


def test_undo(view):
    beat = view.board.beats[1]
    old = view.board.save()

    view.setColor(beat, "b8d4ff")
    assert ed(view).sp.beatBoard.beats[1].color == "b8d4ff"

    view.deleteCard(view.board.beats[0])
    assert len(ed(view).sp.beatBoard.beats) == 3

    # two undo steps, and the view shows the board as the undo left it
    ed(view).cmd("undo")
    view.reload()
    assert len(view.board.beats) == 4
    assert view.board.beats[1].color == "b8d4ff"

    ed(view).cmd("undo")
    view.reload()
    assert view.board.save() == old
    assert not ed(view).undoHistory.canUndo()


def test_reloadDropsEdit(view):
    beat = view.board.beats[0]

    view.startEdit(beat)
    view.editing[1].SetValue("not kept")
    view.reload()

    assert not view.editing
    assert view.board.beats[0].text == "Opening image\nThe city at dawn."
    assert not ed(view).undoHistory.canUndo()


def test_editInline(view):
    beat = view.board.beats[0]
    old = beat.text

    view.startEdit(beat)
    _beat, ctrl, isNew = view.editing
    assert not isNew
    assert ctrl.GetValue() == old

    # it covers the card's text
    r = view.textRect(beat)
    assert ctrl.GetRect() == wx.Rect(
        view.CalcScrolledPosition(r.GetTopLeft()), r.GetSize()
    )
    assert view.cardRect(beat).Contains(r)

    # Esc cancels
    ctrl.SetValue("changed")
    view.OnEditKey(editKey(wx.WXK_ESCAPE))
    assert not view.editing
    assert beat.text == old
    assert not ed(view).undoHistory.canUndo()

    # Ctrl+Enter keeps the text, in the script too
    view.startEdit(beat)
    view.editing[1].SetValue("New title\nmore")
    view.OnEditKey(editKey(wx.WXK_RETURN, True))
    assert beat.text == "New title\nmore"
    assert ed(view).sp.beatBoard.beats[0].text == "New title\nmore"

    # and so does clicking the board
    view.startEdit(beat)
    view.editing[1].SetValue("Clicked away")
    view.OnLeftDown(mouse(wx.wxEVT_LEFT_DOWN, 900, 500))
    view.OnLeftUp(mouse(wx.wxEVT_LEFT_UP, 900, 500))
    assert beat.text == "Clicked away"
    assert not view.editing
    assert ed(view).sp.beatBoard.beats[0].text == "Clicked away"


def test_newCard(view):
    n = len(view.board.beats)
    saved = copy.deepcopy(ed(view).sp.beatBoard)

    # left empty, a new card goes away again, and nothing changes
    beat = view.addCard(700, 300)
    assert view.editing[0] is beat
    assert view.editing[2]
    view.finishEdit(True)
    assert len(view.board.beats) == n
    assert ed(view).sp.beatBoard.save() == saved.save()
    assert not ed(view).undoHistory.canUndo()

    beat = view.addCard(700, 300)
    view.editing[1].SetValue("Dark night of the soul")
    view.finishEdit(True)
    assert view.board.beats[-1] is beat
    assert ed(view).sp.beatBoard.beats[-1].text == "Dark night of the soul"

    # cancelling a new card removes it too
    view.addCard(700, 500)
    view.editing[1].SetValue("x")
    view.finishEdit(False)
    assert len(view.board.beats) == n + 1

    # editing an existing card that's emptied keeps it
    view.startEdit(beat)
    view.editing[1].SetValue("")
    view.finishEdit(True)
    assert view.board.beats[-1] is beat
