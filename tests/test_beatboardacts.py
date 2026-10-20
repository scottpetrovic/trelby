import pytest
import wx

import tests.u as u
import trelby.config as config
import trelby.screenplay.beatboard as beatboard
import trelby.translations as translations
import trelby.ui.configgui as configgui
import trelby.ui.gutil as gutil
from tests.test_beatboardview import Panel, drag, ed, editKey, mouse, paint

_ = translations.trelby_translations_load()

import trelby.ui.beatboardview as beatboardview  # noqa: E402

# acts on the beat board: beatboard.Act (saving, loading, laying out its
# cards) and the view's frames, dragging cards in and out of them, moving,
# resizing and folding them

W, H = beatboard.CARD_WIDTH, beatboard.CARD_HEIGHT
PAD, GAP, TITLE = beatboard.ACT_PAD, beatboard.ACT_GAP, beatboard.ACT_TITLE_HEIGHT
TOP = beatboard.ACT_TOP


def size(beat):
    return (beat.width or W, beat.height or H)


def makeBoard():
    board = beatboard.BeatBoard()

    for i in range(5):
        board.beats.append(beatboard.Beat("Card %d" % i, 0, 0))

    act = beatboard.Act("Act one", 100, 50)
    act.beats = board.beats[:3]
    board.acts.append(act)

    return board


def test_saveLoad():
    board = makeBoard()
    act = board.acts[0]
    act.color = "b8d4ff"
    act.folded = True
    act.width = 700
    act.extra["Future"] = "x"
    board.acts.append(beatboard.Act("Act two:\nthe middle", 0, 900))
    board.acts[1].beats = [board.beats[4]]

    s = board.save()
    loaded = beatboard.BeatBoard()
    loaded.load(s)

    assert loaded.save() == s
    assert len(loaded.acts) == 2

    one, two = loaded.acts
    assert (one.title, one.x, one.y, one.width) == ("Act one", 100, 50, 700)
    assert (one.color, one.folded, one.extra) == ("b8d4ff", True, {"Future": "x"})
    assert one.beats == loaded.beats[:3]
    assert two.title == "Act two:\nthe middle"
    assert two.beats == [loaded.beats[4]]
    assert loaded.actOf(loaded.beats[1]) is one
    assert loaded.actOf(loaded.beats[3]) is None


# a board without acts saves as it did before there were any
def test_noActsSavesAsBefore():
    board = makeBoard()
    board.acts = []

    assert "Act" not in board.save()

    board = beatboard.BeatBoard()
    board.acts.append(beatboard.Act("Empty"))
    assert board.hasInfo()


def test_loadBadCards():
    board = beatboard.BeatBoard()
    board.load(
        "Beats:2\nBeat/1/X:0\nBeat/1/Y:0\nBeat/2/X:0\nBeat/2/Y:0\n"
        "Acts:2\nAct/1/Cards:2,9,x,2,0\nAct/1/Width:5\n"
        "Act/2/Cards:2,1\n"
    )

    # unknown and repeated cards are left out, and a card is in one act
    assert board.acts[0].beats == [board.beats[1]]
    assert board.acts[1].beats == [board.beats[0]]
    assert board.acts[0].width == beatboard.MIN_ACT_WIDTH


def test_layout():
    board = makeBoard()
    act = board.acts[0]
    act.width = 2 * W + GAP + 2 * PAD

    act.layout(size)

    # two to a row
    assert [(b.x, b.y) for b in act.beats] == [
        (100 + PAD, 50 + TOP),
        (100 + PAD + W + GAP, 50 + TOP),
        (100 + PAD, 50 + TOP + H + GAP),
    ]
    assert act.height == TOP + 2 * H + GAP + PAD

    # a taller card makes its row taller
    act.beats[1].setSize(W, H + 50)
    act.layout(size)
    assert act.beats[2].y == 50 + TOP + H + 50 + GAP

    act.folded = True
    act.layout(size)
    assert act.height == TITLE

    # an empty act has room for a card
    empty = beatboard.Act("Empty")
    empty.layout(size)
    assert empty.height == TOP + H + PAD


def test_insertIndex():
    board = makeBoard()
    act = board.acts[0]
    act.width = 2 * W + GAP + 2 * PAD
    act.layout(size)
    a, b, c = act.beats

    assert act.insertIndex(a.x + 10, a.y + 10, size) == 0
    assert act.insertIndex(a.x + W - 10, a.y + 10, size) == 1
    assert act.insertIndex(b.x + W - 10, b.y + 10, size) == 2
    assert act.insertIndex(c.x + 10, c.y + 10, size) == 2
    assert act.insertIndex(c.x + W, c.y + 10, size) == 3

    # leaving out the card being dragged
    assert act.insertIndex(b.x + W - 10, b.y + 10, size, [a]) == 1


def test_removeAndShown():
    board = makeBoard()
    act = board.acts[0]
    a, b = board.beats[:2]

    board.remove([b])
    assert b not in board.beats
    assert act.beats == [a, board.beats[1]]

    board.takeOut([a])
    assert a in board.beats
    assert a not in act.beats

    act.folded = True
    assert board.shownBeats() == [a] + board.beats[2:]


def test_undo():
    e = u.newEditor()
    board = makeBoard()

    assert e.setBeatBoard(board)

    board = beatboard.BeatBoard()
    board.load(e.sp.beatBoard.save())
    board.acts[0].folded = True
    assert e.setBeatBoard(board)

    e.cmd("undo")
    assert not e.sp.beatBoard.acts[0].folded
    assert e.sp.beatBoard.acts[0].beats == e.sp.beatBoard.beats[:3]


@pytest.fixture(scope="module")
def app():
    a = wx.App(False)
    gutil.init()
    yield a
    a.Destroy()


# a board with an act of three cards at the top, and two free cards below
# it
@pytest.fixture
def view(app):
    board = makeBoard()
    board.beats[3].x, board.beats[3].y = 100, 600
    board.beats[4].x, board.beats[4].y = 500, 600

    e = u.newEditor()
    e.sp.beatBoard = board

    frame = wx.Frame(None)
    v = beatboardview.BeatBoardView(frame, Panel(e))
    v.SetClientSize(v.FromDIP(wx.Size(1400, 900)))
    v.reload()

    yield v

    frame.Destroy()


# the window position of (x, y) on the board
def at(view, x, y):
    return (view.px(x), view.px(y))


def dragFromTo(view, start, end):
    view.OnLeftDown(mouse(wx.wxEVT_LEFT_DOWN, *at(view, *start)))
    view.OnMotion(drag(*at(view, *end)))
    view.OnLeftUp(mouse(wx.wxEVT_LEFT_UP, *at(view, *end)))


def test_laidOutOnLoad(view):
    act = view.board.acts[0]

    assert [(b.x, b.y) for b in act.beats] == [
        (100 + PAD + i * (W + GAP), 50 + TOP) for i in range(3)
    ]


def test_dragIntoAct(view):
    act = view.board.acts[0]
    a, b, c, free = view.board.beats[:4]

    # dropped on the left half of the second card, it goes before it
    dragFromTo(view, (free.x + 10, free.y + 10), (b.x + 20, b.y + 20))

    assert act.beats == [a, free, b, c]
    assert (free.x, free.y) == (100 + PAD + W + GAP, 50 + TOP)
    assert view.board.save() == ed(view).sp.beatBoard.save()
    assert view.dropTarget is None

    ed(view).cmd("undo")
    view.reload()
    assert len(view.board.acts[0].beats) == 3


def test_reorderInAct(view):
    act = view.board.acts[0]
    a, b, c = act.beats

    # the first card, dropped past the last one
    dragFromTo(view, (a.x + 10, a.y + 10), (c.x + W - 10, c.y + 10))

    assert act.beats == [b, c, a]
    assert a.x == 100 + PAD + 2 * (W + GAP)


def test_dragOutOfAct(view):
    act = view.board.acts[0]
    a = act.beats[0]

    dragFromTo(view, (a.x + 10, a.y + 10), (900, 400))

    assert a not in act.beats
    assert (a.x, a.y) == (900 - 10, 400 - 10)
    assert act.beats[0].x == 100 + PAD


def test_dropMark(view):
    act = view.board.acts[0]
    free = view.board.beats[3]
    b = act.beats[1]

    view.OnLeftDown(mouse(wx.wxEVT_LEFT_DOWN, *at(view, free.x + 10, free.y + 10)))
    view.OnMotion(drag(*at(view, b.x + 20, b.y + 20)))

    assert view.dropTarget == (act, 1)

    img = paint(view)
    x, y = at(view, b.x - GAP // 2, b.y + H // 2)
    accent = view.getColors()[5]
    assert (img.GetRed(x, y), img.GetGreen(x, y), img.GetBlue(x, y)) == (
        accent.Red(),
        accent.Green(),
        accent.Blue(),
    )

    view.OnLeftUp(mouse(wx.wxEVT_LEFT_UP, *at(view, b.x + 20, b.y + 20)))


def test_fold(view):
    act = view.board.acts[0]
    a = act.beats[0]
    fold = view.actFoldRect(act)

    view.OnLeftDown(mouse(wx.wxEVT_LEFT_DOWN, fold.x + 5, fold.y + 5))
    view.OnLeftUp(mouse(wx.wxEVT_LEFT_UP, fold.x + 5, fold.y + 5))

    assert act.folded
    assert act.height == TITLE
    assert view.hitTest(wx.Point(*at(view, a.x + 10, a.y + 10))) is None
    assert a not in view.board.shownBeats()
    assert ed(view).sp.beatBoard.acts[0].folded
    paint(view)

    # cards dropped on a folded act go at its end
    free = view.board.beats[3]
    dragFromTo(view, (free.x + 10, free.y + 10), (act.x + 200, act.y + 10))
    assert act.beats[-1] is free
    assert free not in view.board.shownBeats()

    view.foldAll(False)
    assert not act.folded


def test_moveAct(view):
    act = view.board.acts[0]
    a = act.beats[0]

    dragFromTo(view, (act.x + 100, act.y + 10), (act.x + 150, act.y + 400))

    assert (act.x, act.y) == (150, 440)
    assert (a.x, a.y) == (150 + PAD, 440 + TOP)
    assert ed(view).sp.beatBoard.acts[0].y == 440


def test_resizeAct(view):
    act = view.board.acts[0]
    grip = view.actGripRect(act)
    x, y = grip.x + grip.width // 2, grip.y + grip.height // 2
    narrower = 2 * W + GAP + 2 * PAD - act.width

    view.OnLeftDown(mouse(wx.wxEVT_LEFT_DOWN, x, y))
    view.OnMotion(drag(x + view.px(narrower), y))
    view.OnLeftUp(mouse(wx.wxEVT_LEFT_UP, x + view.px(narrower), y))

    # the third card wraps
    assert act.width == 2 * W + GAP + 2 * PAD
    assert act.beats[2].y == 50 + TOP + H + GAP
    assert ed(view).sp.beatBoard.acts[0].width == act.width


def test_deleteAct(view):
    act = view.board.acts[0]
    cards = list(act.beats)
    close = view.actCloseRect(act)

    view.OnLeftDown(mouse(wx.wxEVT_LEFT_DOWN, close.x + 2, close.y + 2))

    assert not view.board.acts
    assert all(b in view.board.beats for b in cards)
    assert not ed(view).sp.beatBoard.acts


def test_deleteActWithCards(view):
    view.deleteAct(view.board.acts[0], True)

    assert len(view.board.beats) == 2


def test_addCardInAct(view):
    act = view.board.acts[0]
    b = act.beats[1]

    view.OnLeftDClick(mouse(wx.wxEVT_LEFT_DCLICK, *at(view, b.x + 20, b.y + H + 5)))
    new, ctrl = view.editing[:2]

    assert act.beats[1] is new
    ctrl.SetValue("New beat")
    view.OnEditKey(editKey(wx.WXK_RETURN, True))

    assert ed(view).sp.beatBoard.acts[0].beats[1].text == "New beat"

    # left empty, it's gone from the act too
    view.OnLeftDClick(mouse(wx.wxEVT_LEFT_DCLICK, *at(view, b.x + 20, b.y + H + 5)))
    view.OnEditKey(editKey(wx.WXK_ESCAPE))
    assert len(act.beats) == 4


def test_renameAct(view):
    act = view.board.acts[0]

    view.OnLeftDClick(mouse(wx.wxEVT_LEFT_DCLICK, *at(view, act.x + 100, act.y + 10)))
    obj, ctrl = view.editing[:2]

    assert obj is act
    ctrl.SetValue("The setup")
    view.OnEditKey(editKey(wx.WXK_RETURN))

    assert view.editing is None
    assert ed(view).sp.beatBoard.acts[0].title == "The setup"


def test_addActAround(view):
    free = view.board.beats[3:]
    view.addActAround(free)
    act = view.board.acts[-1]
    view.finishEdit(True)

    assert act.beats == free
    assert (act.x, act.y) == (100 - PAD, 600 - TOP)
    assert act.title == "Act 2"
    assert ed(view).sp.beatBoard.acts[1].beats == ed(view).sp.beatBoard.beats[3:]


@pytest.mark.parametrize("theme", [None, "Light", "Dark"])
def test_paint(view, theme):
    if theme:
        cfgGl = config.ConfigGlobal()
        cfgGl.theme = theme
        view.applyTheme(configgui.ConfigGui(cfgGl, 100))

    view.board.acts[0].color = "b8d4ff"
    view.board.acts.append(beatboard.Act("Empty", 100, 800))
    view.layout()

    img = paint(view)

    # the act's frame is drawn under its cards, between them
    act = view.board.acts[0]
    x, y = at(view, act.x + PAD + W + GAP // 2, act.y + TOP + H // 2)
    fill = view.getActColors(act)[0]
    assert (img.GetRed(x, y), img.GetGreen(x, y), img.GetBlue(x, y)) == (
        fill.Red(),
        fill.Green(),
        fill.Blue(),
    )

    view.board.acts[0].folded = True
    view.layout()
    paint(view)
