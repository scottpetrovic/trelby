import pytest
import wx

import trelby.config as config
import trelby.screenplay.beatboard as beatboard
import trelby.translations as translations
import trelby.ui.configgui as configgui
import trelby.ui.gutil as gutil

_ = translations.trelby_translations_load()

import trelby.dialogs.beatboarddlg as beatboarddlg  # noqa: E402

# the beat board dialog (dialogs/beatboarddlg.py): drawing the board into a
# bitmap, and panning it with simulated mouse and key events


@pytest.fixture(scope="module")
def app():
    a = wx.App(False)
    gutil.init()
    yield a
    a.Destroy()


@pytest.fixture
def dlg(app):
    board = beatboard.BeatBoard()
    board.beats.append(beatboard.Beat("Opening image\nThe city at dawn.", 20, 20))

    b = beatboard.Beat("Catalyst", 240, 20)
    b.color = "ffd1a3"
    board.beats.append(b)

    board.beats.append(beatboard.Beat("Midpoint", 460, 20))
    board.beats.append(beatboard.Beat("", 700, 180))

    d = beatboarddlg.BeatBoardDlg(None, board)
    d.canvas.SetClientSize(d.canvas.FromDIP(wx.Size(960, 560)))

    yield d

    d.Destroy()


def paint(canvas):
    bmp = wx.Bitmap(*canvas.GetClientSize())
    dc = wx.MemoryDC(bmp)
    canvas.DoPrepareDC(dc)
    canvas.paint(dc)
    dc.SelectObject(wx.NullBitmap)

    return bmp.ConvertToImage()


def pixel(img, x, y):
    return (img.GetRed(x, y), img.GetGreen(x, y), img.GetBlue(x, y))


def test_copy(dlg):
    # the dialog edits its own copy of the board
    board = beatboard.BeatBoard()
    board.beats.append(beatboard.Beat("x"))

    d = beatboarddlg.BeatBoardDlg(None, board)
    d.board.beats[0].text = "changed"
    assert board.beats[0].text == "x"
    d.Destroy()


def test_hint(dlg, monkeypatch):
    c = dlg.canvas
    w, h = c.GetClientSize()
    withHint = paint(c)

    monkeypatch.setattr(c, "drawHint", lambda *args: None)
    without = paint(c)

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
def test_paint(dlg, theme):
    c = dlg.canvas

    if theme:
        cfgGl = config.ConfigGlobal()
        cfgGl.theme = theme
        c.applyTheme(configgui.ConfigGui(cfgGl, 100))

    # selecting brings the card to the front, the end of the list
    catalyst = dlg.board.beats[1]
    c.select(catalyst)
    assert dlg.board.beats[-1] is catalyst

    img = paint(c)
    step = c.FromDIP(beatboarddlg.GRID)

    # on a grid line, away from the cards, and in the middle of a square
    x = 20 * step + step // 2
    y = 12 * step
    assert pixel(img, x, y) != pixel(img, x, y + step // 2)

    # a card covers the grid
    r = c.cardRect(catalyst)
    assert pixel(img, r.x + r.width // 2, r.GetBottom() - 4) == (255, 209, 163)

    # and scrolled
    c.scrollTo(37, 53)
    paint(c)


def mouse(t, x, y):
    e = wx.MouseEvent(t)
    e.SetPosition(wx.Point(x, y))

    return e


def key(t, code):
    e = wx.KeyEvent(t)
    e.SetKeyCode(code)

    return e


def test_middlePan(dlg):
    c = dlg.canvas

    c.OnMiddleDown(mouse(wx.wxEVT_MIDDLE_DOWN, 300, 300))
    c.OnMotion(mouse(wx.wxEVT_MOTION, 200, 250))
    assert c.GetViewStart() == (100, 50)

    # not above or left of the board's corner
    c.OnMotion(mouse(wx.wxEVT_MOTION, 500, 500))
    assert c.GetViewStart() == (0, 0)

    c.OnMiddleUp(mouse(wx.wxEVT_MIDDLE_UP, 500, 500))
    assert not c.pan
    assert not c.HasCapture()


def test_spacePan(dlg):
    c = dlg.canvas
    beat = dlg.board.beats[0]
    r = c.cardRect(beat)
    x, y = r.x + 10, r.y + 10

    c.OnKeyDown(key(wx.wxEVT_KEY_DOWN, wx.WXK_SPACE))
    assert c.spaceDown

    # pressing on a card pans instead of grabbing it
    c.OnLeftDown(mouse(wx.wxEVT_LEFT_DOWN, x, y))
    c.OnMotion(mouse(wx.wxEVT_MOTION, x - 30, y - 40))
    assert c.GetViewStart() == (30, 40)
    assert (beat.x, beat.y) == (20, 20)
    assert not c.drag

    c.OnLeftUp(mouse(wx.wxEVT_LEFT_UP, x - 30, y - 40))
    c.OnKeyUp(key(wx.wxEVT_KEY_UP, wx.WXK_SPACE))
    assert not (c.pan or c.spaceDown or c.HasCapture())

    # without space, the card is dragged
    c.scrollTo(0, 0)
    c.OnLeftDown(mouse(wx.wxEVT_LEFT_DOWN, x, y))
    c.OnMotion(_drag(x + c.FromDIP(50), y + c.FromDIP(30)))
    c.OnLeftUp(mouse(wx.wxEVT_LEFT_UP, x, y))
    assert (beat.x, beat.y) == (70, 50)
    assert c.GetViewStart() == (0, 0)


# a motion event with the left button down
def _drag(x, y):
    e = mouse(wx.wxEVT_MOTION, x, y)
    e.SetLeftDown(True)

    return e


def editKey(code, ctrl=False):
    e = key(wx.wxEVT_CHAR_HOOK, code)
    e.SetControlDown(ctrl)

    return e


def test_editInline(dlg):
    c = dlg.canvas
    beat = dlg.board.beats[0]
    old = beat.text

    c.startEdit(beat)
    _beat, ctrl, isNew = c.editing
    assert not isNew
    assert ctrl.GetValue() == old

    # it covers the card's text
    r = c.textRect(beat)
    assert ctrl.GetRect() == wx.Rect(c.CalcScrolledPosition(r.GetTopLeft()), r.GetSize())
    assert c.cardRect(beat).Contains(r)

    # Esc cancels
    ctrl.SetValue("changed")
    c.OnEditKey(editKey(wx.WXK_ESCAPE))
    assert not c.editing
    assert beat.text == old

    # Ctrl+Enter keeps the text
    c.startEdit(beat)
    c.editing[1].SetValue("New title\nmore")
    c.OnEditKey(editKey(wx.WXK_RETURN, True))
    assert beat.text == "New title\nmore"

    # and so does clicking the board
    c.startEdit(beat)
    c.editing[1].SetValue("Clicked away")
    c.OnLeftDown(mouse(wx.wxEVT_LEFT_DOWN, 900, 500))
    c.OnLeftUp(mouse(wx.wxEVT_LEFT_UP, 900, 500))
    assert beat.text == "Clicked away"
    assert not c.editing


def test_newCard(dlg):
    c = dlg.canvas
    n = len(dlg.board.beats)

    # left empty, a new card goes away again
    beat = dlg.addCard(700, 300)
    assert c.editing[0] is beat
    assert c.editing[2]
    c.finishEdit(True)
    assert len(dlg.board.beats) == n

    beat = dlg.addCard(700, 300)
    c.editing[1].SetValue("Dark night of the soul")
    c.finishEdit(True)
    assert dlg.board.beats[-1] is beat
    assert beat.text == "Dark night of the soul"

    # cancelling a new card removes it too
    dlg.addCard(700, 500)
    c.editing[1].SetValue("x")
    c.finishEdit(False)
    assert len(dlg.board.beats) == n + 1

    # editing an existing card that's emptied keeps it
    c.startEdit(beat)
    c.editing[1].SetValue("")
    c.finishEdit(True)
    assert dlg.board.beats[-1] is beat


def test_okKeepsEdit(dlg):
    c = dlg.canvas
    beat = dlg.board.beats[0]

    c.startEdit(beat)
    c.editing[1].SetValue("Typed, then OK")

    dlg.EndModal = lambda code: None
    dlg.OnOK(None)
    assert beat.text == "Typed, then OK"
