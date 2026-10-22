from unittest import mock

import pytest
import wx

import tests.u as u
import trelby.config as config
import trelby.ui.configgui as configgui
import trelby.ui.gutil as gutil
import trelby.screenplay as screenplay
import trelby.spellcheck as spellcheck
import trelby.ui.scriptpainter as scriptpainter
import trelby.translations as translations
import trelby.ui.viewmode as viewmode
from trelby.screenplay.notes import Note

_ = translations.trelby_translations_load()

# drawing a script (scriptpainter.py) into a bitmap, in each view mode,
# with the things that are only sometimes drawn: a selection, the
# auto-completion list, locks and formatting marks


@pytest.fixture(scope="module")
def app():
    a = wx.App(False)
    gutil.init()
    yield a
    a.Destroy()


def loadSample():
    u.init()

    with open("trelby/sample.trelby", encoding="utf-8") as f:
        sp = screenplay.Screenplay.load(f.read(), config.ConfigGlobal())[0]

    sp.paginate()

    return screenplay.Editor(sp)


def paint(ed, vm, showFormatting=False, size=(900, 1200), scDict=None):
    cfgGl = ed.sp.cfgGl
    cfgGui = configgui.ConfigGui(cfgGl, 100)
    vp = scriptpainter.Viewport.make(
        ed.sp, ed, cfgGui, vm, wx.Size(*size), lambda n: n
    )

    bmp = wx.Bitmap(*size)
    dc = wx.MemoryDC(bmp)
    rect = scriptpainter.ScriptPainter(
        vp, vm, cfgGl, showFormatting, scDict
    ).paint(dc)
    dc.SelectObject(wx.NullBitmap)

    return vp, rect, bmp


@pytest.mark.parametrize(
    "vm",
    [viewmode.ViewModeDraft, viewmode.ViewModeLayout, viewmode.ViewModeSideBySide],
)
def testPaint(app, vm):
    ed = loadSample()
    vp, rect, bmp = paint(ed, vm())

    assert vp.pageW > 0 and vp.pageH > vp.pageW
    assert vp.mm2p == pytest.approx(vp.pageW / ed.sp.cfg.paperWidth, rel=0.01)

    # the title page button is drawn above the first page, which there's
    # only in the page modes
    if vm is viewmode.ViewModeDraft:
        assert rect is None
    else:
        assert rect and (rect.width > 0)


def testPaintEverything(app):
    ed = loadSample()

    ed.line = 5
    ed.setMark(2, 0)
    ed.sp.lines[0].pageLock = "1"
    ed.sp.lines[0].sceneLock = "1"
    ed.acItems = ["ONE", "TWO", "THREE"]
    ed.acSel = 1
    ed.acMax = 2

    for vm in (viewmode.ViewModeDraft(), viewmode.ViewModeLayout()):
        paint(ed, vm, showFormatting=True)

    # too small for the title page button
    vp, rect, bmp = paint(ed, viewmode.ViewModeLayout(), size=(300, 40))
    assert rect is None


# how many pixels of bmp are the given (r, g, b) color
def countColor(bmp, rgb):
    data = bmp.ConvertToImage().GetData()

    return sum(
        1 for i in range(0, len(data), 3) if tuple(data[i : i + 3]) == rgb
    )


# how many pixels of bmp are tinted towards rgb: its strongest channel
# standing out by over 'margin', which counts antialiased lines (GTK)
# that are never exactly rgb
def countTint(bmp, rgb, margin=60):
    data = bmp.ConvertToImage().GetData()
    main = rgb.index(max(rgb))
    n = 0

    for i in range(0, len(data), 3):
        px = data[i : i + 3]

        if px[main] - max(px[j] for j in range(3) if j != main) > margin:
            n += 1

    return n


@pytest.mark.parametrize("vm", [viewmode.ViewModeDraft, viewmode.ViewModeLayout])
def testPaintSpellingErrors(app, vm):
    ed = loadSample()
    ed.sp.lines[1].text = "Wrogn wurds"
    ed.sp.paginate()
    ed.line = 0
    red = configgui.getTheme(ed.sp.cfgGl.theme).spellErrorColor()

    # the main dictionary isn't loaded, so nothing is checked
    with mock.patch.object(spellcheck, "gdict", set()):
        vp, rect, bmp = paint(ed, vm(), scDict=spellcheck.Dict())
        assert countColor(bmp, red) == 0

    with mock.patch.object(spellcheck, "gdict", {"x"}):
        vp, rect, bmp = paint(ed, vm())
        assert countColor(bmp, red) == 0
        unchecked = countTint(bmp, red)

        # more red than the same page without underlines, since the
        # page has other reddish pixels
        vp, rect, bmp = paint(ed, vm(), scDict=spellcheck.Dict())
        assert countTint(bmp, red) > unchecked


# the notes are cards 20 pixels right of the page, one per note, each
# below the one before; where the next page leaves no room for them (side
# by side), each paragraph with notes gets an icon as far inside the page
@pytest.mark.parametrize(
    "vm, cards",
    [
        (viewmode.ViewModeDraft, True),
        (viewmode.ViewModeLayout, True),
        (viewmode.ViewModeSideBySide, False),
    ],
)
def testPaintNoteMarkers(app, vm, cards):
    ed = loadSample()
    ed.sp.lines[1].notes = (Note("Hi " * 100), Note("There"))
    ed.sp.lines[5].notes = (Note("Done", resolved=True),)
    vm = vm()
    size = wx.Size(1600, 600)
    cfgGui = configgui.ConfigGui(ed.sp.cfgGl, 100)
    vp = scriptpainter.Viewport.make(ed.sp, ed, cfgGui, vm, size, lambda n: n)

    painter = scriptpainter.ScriptPainter(vp, vm, ed.sp.cfgGl, False)
    dc = wx.MemoryDC(wx.Bitmap(size))
    painter.paint(dc)
    dc.SelectObject(wx.NullBitmap)

    strings, dpages = vm.getScreen(vp, True, True)
    t1 = next(t for t in strings if t.line == 1)
    t5 = next(t for t in strings if t.line == 5)

    if dpages:
        right = next(dp.x2 for dp in dpages if dp.x1 <= t1.x <= dp.x2)
    else:
        right = (size.width - vp.pageW) // 2 + vp.pageW

    markers = painter.noteMarkers

    if not cards:
        assert [(line, index) for rect, line, index in markers] == [
            (1, None),
            (5, None),
        ]
        assert markers[0][0].y == t1.y
        assert markers[0][0].GetRight() + 1 == right - 20

        return

    assert [(line, index) for rect, line, index in markers] == [
        (1, 0),
        (1, 1),
        (5, 0),
    ]
    rects = [m[0] for m in markers]

    for r in rects:
        assert r.x == right + 20
        assert r.width == scriptpainter.NOTE_WIDTH

    # the long note shows NOTE_LINES lines, the others one
    # (with 8 pixels of padding above and below the text)
    assert rects[0].height - 16 == 3 * (rects[1].height - 16)
    assert rects[2].height == rects[1].height

    assert rects[0].y == t1.y
    assert rects[1].y > rects[0].GetBottom()
    assert rects[2].y == max(t5.y, rects[1].GetBottom() + 1 + 4)

    # each card has a checkbox at the right of its first line
    checks = painter.noteChecks
    assert [(l, index) for rect, l, index in checks] == [(1, 0), (1, 1), (5, 0)]

    for (check, l, index), card in zip(checks, rects):
        assert card.Contains(check.GetTopLeft() + wx.Point(4, 4))
        assert check.GetRight() - 4 > card.x + card.width * 3 // 4
        assert check.y - 4 < card.y + card.height // 2


# a paragraph a new note is being written on gets a blank card after its
# notes, with the index the note will have, even if it has none yet
@pytest.mark.parametrize("line, notes", [(1, (Note("Hi"),)), (5, ())])
def testPaintNewNoteCard(app, line, notes):
    ed = loadSample()
    ed.sp.lines[line].notes = notes
    vm = viewmode.ViewModeDraft()
    size = wx.Size(1600, 600)
    cfgGui = configgui.ConfigGui(ed.sp.cfgGl, 100)
    vp = scriptpainter.Viewport.make(ed.sp, ed, cfgGui, vm, size, lambda n: n)

    painter = scriptpainter.ScriptPainter(
        vp, vm, ed.sp.cfgGl, False, newNoteLine=line
    )
    dc = wx.MemoryDC(wx.Bitmap(size))
    painter.paint(dc)
    dc.SelectObject(wx.NullBitmap)

    keys = [(l, index) for rect, l, index in painter.noteMarkers]
    assert keys == [(line, k) for k in range(len(notes) + 1)]

    # the blank card has no checkbox
    keys = [(l, index) for rect, l, index in painter.noteChecks]
    assert keys == [(line, k) for k in range(len(notes))]


# revised text is highlighted in its revision's color, and its line gets
# the revision mark in the right margin
@pytest.mark.parametrize(
    "vm",
    [viewmode.ViewModeDraft, viewmode.ViewModeLayout, viewmode.ViewModeSideBySide],
)
def testPaintRevisions(app, vm):
    ed = loadSample()
    ed.line = 0
    cfgGui = configgui.ConfigGui(ed.sp.cfgGl, 100)
    painter = scriptpainter.ScriptPainter(
        scriptpainter.Viewport.make(
            ed.sp, ed, cfgGui, vm(), wx.Size(900, 1200), lambda n: n
        ),
        vm(),
        ed.sp.cfgGl,
        False,
    )
    blue = painter.revisionColor(1).Get(False)

    vp, rect, bmp = paint(ed, vm())
    assert countColor(bmp, blue) == 0

    ed.sp.lines[1].revs = "1" * len(ed.sp.lines[1].text)
    vp, rect, bmp = paint(ed, vm())
    assert countColor(bmp, blue) > 0

    marks = []

    with mock.patch.object(
        wx.MemoryDC, "DrawText", lambda dc, s, x, y: marks.append(s)
    ):
        paint(ed, vm())

    assert marks.count("*") == 1
