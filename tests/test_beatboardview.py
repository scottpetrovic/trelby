import copy
import io

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

    b = beatboard.Beat("Catalyst", 300, 20)
    b.color = "ffd1a3"
    board.beats.append(b)

    board.beats.append(beatboard.Beat("Midpoint", 580, 20))
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
    assert beat.color == beatboard.DEFAULT_COLOR

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


# a picture file's contents: w x h, all one color, as 'kind' (a
# wx.BITMAP_TYPE_*)
def pictureFile(w, h, color=(200, 30, 60), kind=wx.BITMAP_TYPE_PNG):
    img = wx.Image(w, h)
    img.SetRGB(wx.Rect(0, 0, w, h), *color)
    stream = io.BytesIO()
    assert img.SaveFile(stream, kind)

    return stream.getvalue()


# a wx.Image of w x h, all one color
def pictureImage(w, h):
    img = wx.Image(w, h)
    img.SetRGB(wx.Rect(0, 0, w, h), 200, 30, 60)

    return img


def pictureSize(data):
    img = beatboardview.decodePicture(data)

    return (img.GetWidth(), img.GetHeight())


def test_imageData(app):
    # a small PNG or JPEG is kept as it is
    png = pictureFile(40, 30)
    assert beatboardview.imageData(png) == png

    jpeg = pictureFile(40, 30, kind=wx.BITMAP_TYPE_JPEG)
    assert beatboardview.imageData(jpeg) == jpeg

    # other kinds are converted, to JPEG without transparency
    bmp = pictureFile(40, 30, kind=wx.BITMAP_TYPE_BMP)
    data = beatboardview.imageData(bmp)
    assert beatboardview.isPngOrJpeg(data) and data.startswith(b"\xff\xd8")
    assert pictureSize(data) == (40, 30)

    # and big ones made smaller, keeping their shape
    side = beatboard.MAX_IMAGE_SIDE
    data = beatboardview.imageData(pictureFile(side * 2, side))
    assert pictureSize(data) == (side, side // 2)

    # with transparency, it stays a PNG
    img = wx.Image(side + 10, 10)
    img.InitAlpha()
    data = beatboardview.encodePicture(img)
    assert data.startswith(b"\x89PNG")

    assert beatboardview.imageData(b"not a picture") is None
    assert beatboardview.imageData(b"") is None


def test_pictureFiles(view, tmp_path, monkeypatch):
    wide = tmp_path / "wide.png"
    wide.write_bytes(pictureFile(480, 120))
    tall = tmp_path / "tall.jpg"
    tall.write_bytes(pictureFile(60, 400, kind=wx.BITMAP_TYPE_JPEG))
    text = tmp_path / "notes.txt"
    text.write_text("hello")

    messages = []
    monkeypatch.setattr(
        beatboardview.gutil, "messageBox", lambda msg, *a, **k: messages.append(msg)
    )

    n = len(view.board.beats)
    pos = view.FromDIP(wx.Point(400, 400))
    beats = view.addPictureFiles([str(wide), str(text), str(tall)], pos)

    # a card for each picture, the first centered where they were dropped
    # and the next one further down and right, the last one selected
    assert len(beats) == 2
    assert view.board.beats[n:] == beats
    assert view.selected is beats[1]

    def middle(beat):
        w, h = view.cardSize(beat)

        return (beat.x + w // 2, beat.y + h // 2)

    assert middle(beats[0]) == (400, 400)
    assert middle(beats[1]) == (400 + beatboardview.CASCADE,) * 2

    # the pictures are fitted in the card's picture area, keeping their
    # shape
    assert view.pictureSize(beats[0]) == (beatboardview.PICTURE_WIDTH, 60)
    assert view.pictureSize(beats[1]) == (27, beatboardview.PICTURE_HEIGHT)

    # the narrow one's card isn't narrower than the minimum
    assert view.cardSize(beats[1])[0] == beatboardview.PICTURE_CARD_MIN_WIDTH

    # the file that isn't a picture is mentioned
    assert len(messages) == 1 and "notes.txt" in messages[0]

    # all in the script, as one undo step
    sp = ed(view).sp
    assert [b.image for b in sp.beatBoard.beats[n:]] == [b.image for b in beats]
    ed(view).cmd("undo")
    assert len(sp.beatBoard.beats) == n
    assert not ed(view).undoHistory.canUndo()


def test_pictureCard(view):
    beat = view.addBitmap(wx.Bitmap(pictureImage(100, 50)))[0]
    assert beat.image.startswith(b"\xff\xd8")
    assert view.board.beats[-1] is beat

    r = view.cardRect(beat)
    pad = view.FromDIP(beatboardview.CARD_PAD)

    # a picture card without text has no caption
    assert r.height == view.FromDIP(50 + 2 * beatboardview.CARD_PAD)

    view.scrollTo(r.x - 10, r.y - 10)
    img = paint(view)
    x, y = view.CalcScrolledPosition(r.x + r.width // 2, r.y + pad + 20)
    color = pixel(img, x, y)
    assert all(abs(a - b) < 8 for a, b in zip(color, (200, 30, 60)))

    # text gives it a caption under the picture
    view.startEdit(beat)
    view.editing[1].SetValue("The villain\nnot shown")
    view.finishEdit(True)
    assert view.cardRect(beat).height == r.height + view.FromDIP(
        beatboardview.CAPTION_HEIGHT
    )
    paint(view)

    # emptying it doesn't remove the card, even though it's new
    view.startEdit(beat, True)
    view.editing[1].SetValue("")
    view.finishEdit(True)
    assert view.board.beats[-1] is beat

    # taking the picture away makes it a text card again
    view.setPicture(beat, None)
    assert ed(view).sp.beatBoard.beats[-1].image is None
    assert view.cardSize(beat) == (beatboard.CARD_WIDTH, beatboard.CARD_HEIGHT)


def test_unreadablePicture(view):
    # a card whose picture can't be read is shown as a text card
    beat = view.board.beats[0]
    beat.image = b"broken"
    assert view.cardSize(beat) == (beatboard.CARD_WIDTH, beatboard.CARD_HEIGHT)
    paint(view)


def test_reloadForgetsPictures(view):
    beat = view.addBitmap(wx.Bitmap(pictureImage(30, 30)))[0]
    paint(view)
    assert beat.image in view.pictures
    assert view.bitmaps

    ed(view).cmd("undo")
    view.reload()
    assert not view.pictures and not view.bitmaps


def test_paste(view, monkeypatch):
    # what's on the clipboard, without touching the real one
    got = [("bitmap", wx.Bitmap(pictureImage(20, 10)))]
    monkeypatch.setattr(view, "getClipboardPictures", lambda: got[0])

    n = len(view.board.beats)
    beats = view.paste(wx.Point(100, 100))
    assert len(beats) == 1 and len(view.board.beats) == n + 1
    assert view.pictureSize(beats[0]) == (20, 10)

    got[0] = None
    assert view.paste(wx.Point(100, 100)) == []
    assert len(view.board.beats) == n + 1


# drag beat's resizing corner by (dx, dy) unscaled pixels
def resizeCard(view, beat, dx, dy, shift=False):
    r = view.gripRect(beat)
    x, y = view.CalcScrolledPosition(r.x + r.width // 2, r.y + r.height // 2)
    assert view.gripHitTest(wx.Point(x, y)) is beat

    view.OnLeftDown(mouse(wx.wxEVT_LEFT_DOWN, x, y))
    e = drag(x + view.FromDIP(dx), y + view.FromDIP(dy))
    e.SetShiftDown(shift)
    view.OnMotion(e)
    view.OnLeftUp(mouse(wx.wxEVT_LEFT_UP, x, y))


def test_resizeCard(view):
    beat = view.board.beats[0]

    # a click on the corner leaves it the default size
    r = view.gripRect(beat)
    x, y = view.CalcScrolledPosition(r.x + 2, r.y + 2)
    view.OnLeftDown(mouse(wx.wxEVT_LEFT_DOWN, x, y))
    assert view.resize and not view.drag
    view.OnLeftUp(mouse(wx.wxEVT_LEFT_UP, x, y))
    assert beat.width is None
    assert not ed(view).undoHistory.canUndo()

    # the grip is drawn on the selected card
    paint(view)

    resizeCard(view, beat, 100, 40)
    assert (beat.width, beat.height) == (
        beatboard.CARD_WIDTH + 100,
        beatboard.CARD_HEIGHT + 40,
    )
    assert (beat.x, beat.y) == (20, 20)
    assert view.board.beats[-1] is beat
    assert ed(view).sp.beatBoard.beats[-1].width == beatboard.CARD_WIDTH + 100

    # not smaller than the minimum
    resizeCard(view, beat, -1000, -1000)
    assert (beat.width, beat.height) == (
        beatboard.MIN_CARD_WIDTH,
        beatboard.MIN_CARD_HEIGHT,
    )

    # with shift, it keeps its shape
    resizeCard(view, beat, 80, 0, True)
    assert (beat.width, beat.height) == (2 * 80, 2 * 50)

    # each resize is an undo step
    ed(view).cmd("undo")
    view.reload()
    assert view.board.beats[-1].width == beatboard.MIN_CARD_WIDTH

    # and the size can be reset
    beat = view.board.beats[-1]
    view.setSize(beat, None)
    assert view.cardSize(beat) == (beatboard.CARD_WIDTH, beatboard.CARD_HEIGHT)
    assert ed(view).sp.beatBoard.beats[-1].width is None


def test_resizePicture(view):
    beat = view.addBitmap(wx.Bitmap(pictureImage(100, 50)))[0]
    view.scrollTo(0, 0)
    pad = beatboardview.CARD_PAD
    assert view.cardSize(beat) == (100 + 2 * pad, 50 + 2 * pad)

    # the picture grows with the card, keeping its shape
    resizeCard(view, beat, 200, 100)
    assert view.cardSize(beat) == (300 + 2 * pad, 150 + 2 * pad)
    assert view.pictureSize(beat) == (300, 150)

    # and fits a card of another shape, centered in it
    view.setSize(beat, 300 + 2 * pad, 50 + 2 * pad)
    assert view.pictureSize(beat) == (100, 50)

    r = view.cardRect(beat)
    view.scrollTo(r.x - 10, r.y - 10)
    img = paint(view)
    middle = view.CalcScrolledPosition(r.x + r.width // 2, r.y + r.height // 2)
    color = pixel(img, *middle)
    assert all(abs(a - b) < 8 for a, b in zip(color, (200, 30, 60)))
    left = view.CalcScrolledPosition(r.x + view.FromDIP(pad + 20), 0)[0]
    assert pixel(img, left, middle[1]) != color

    # and shrinks with it, leaving room for the caption
    beat.text = "Caption"
    view.setSize(beat, 80, 60)
    area = view.pictureArea(beat)
    assert area == (80 - 2 * pad, 60 - 2 * pad - beatboardview.CAPTION_HEIGHT)
    assert view.pictureSize(beat) == (area[1] * 2, area[1])

    # only the bitmaps of the sizes shown are kept
    paint(view)
    resizeCard(view, beat, 40, 40)
    shown = tuple(view.FromDIP(n) for n in view.pictureSize(beat))
    assert all(k[1:] == shown for k in view.bitmaps)


# the board's own zoom scales the cards, keeping the point zoomed around
# where it is, and the cards' text is in Courier Prime at the zoom level
def test_zoom(view):
    beat = view.board.beats[0]
    r100 = view.cardRect(beat)
    font100 = view.cardFont()
    assert font100.GetFaceName() == gutil.courierFace()

    pos = wx.Point(*view.CalcScrolledPosition(r100.x, r100.y))
    view.setZoom(200, pos)
    r200 = view.cardRect(beat)
    assert abs(r200.width - r100.width * 2) <= 2
    assert abs(r200.height - r100.height * 2) <= 2
    assert view.cardFont().GetFractionalPointSize() == pytest.approx(
        font100.GetFractionalPointSize() * 2
    )

    # the card's corner stays under the mouse, and board coordinates
    # still map back
    corner = view.CalcScrolledPosition(r200.x, r200.y)
    assert abs(corner[0] - pos.x) <= 1 and abs(corner[1] - pos.y) <= 1
    x, y = view.toBoard(wx.Point(*corner))
    assert abs(x - beat.x) <= 1 and abs(y - beat.y) <= 1
    assert view.hitTest(wx.Point(corner[0] + 5, corner[1] + 5)) is beat

    view.setZoom(50)
    r50 = view.cardRect(beat)
    assert abs(r50.width - r100.width / 2) <= 1

    paint(view)
    view.setZoom(100)
    assert view.cardRect(beat) == r100
    assert not view.bitmaps


# zooming ends a card's editing, since the text control would be out of
# place
def test_zoomEndsEdit(view):
    beat = view.board.beats[0]
    view.startEdit(beat)
    view.editing[1].SetValue("Changed")
    view.setZoom(150)
    assert view.editing is None
    assert beat.text == "Changed"


# both right-click menus get to the other view through the View menu's
# Beat board item
def test_scriptItem(view):
    import trelby.ui.ids as ids

    menu = wx.Menu()
    view.addScriptItem(menu)
    item = menu.FindItemById(ids.ID_VIEW_BEAT_BOARD)
    assert item and item.GetItemLabelText() == _("Go to script")
    menu.Destroy()


def test_deleteButton(view):
    n = len(view.board.beats)
    opening = view.board.beats[0]
    r = view.closeRect(opening)
    x, y = view.CalcScrolledPosition(r.x + r.width // 2, r.y + r.height // 2)

    # in the card's top right corner
    card = view.cardRect(opening)
    assert card.Contains(r)
    assert r.GetRight() > card.x + card.width * 3 // 4
    assert r.y < card.y + card.height // 4

    # hovering over it highlights it
    before = paint(view)
    view.OnMotion(mouse(wx.wxEVT_MOTION, x, y))
    assert view.hover is opening
    assert pixel(paint(view), x - 4, y) != pixel(before, x - 4, y)

    view.OnLeftDown(mouse(wx.wxEVT_LEFT_DOWN, x, y))
    assert opening not in view.board.beats
    assert len(ed(view).sp.beatBoard.beats) == n - 1
    assert view.hover is None

    # the double-click a second click makes adds nothing where it was
    view.OnLeftDClick(mouse(wx.wxEVT_LEFT_DCLICK, x, y))
    assert not view.editing
    assert len(view.board.beats) == n - 1

    ed(view).cmd("undo")
    view.reload()
    assert len(view.board.beats) == n

    # elsewhere on a card, a click selects it
    view.OnLeftDown(mouse(wx.wxEVT_LEFT_DOWN, x - 40, y + 30))
    view.OnLeftUp(mouse(wx.wxEVT_LEFT_UP, x - 40, y + 30))
    assert view.selected is view.board.beats[0]
    assert len(view.board.beats) == n
