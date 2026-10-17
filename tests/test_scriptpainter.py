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

        vp, rect, bmp = paint(ed, vm(), scDict=spellcheck.Dict())
        assert countColor(bmp, red) > 0


# the note markers go 20 pixels right of the page, or as far inside it
# where the next page leaves no room (side by side)
@pytest.mark.parametrize(
    "vm, inside",
    [
        (viewmode.ViewModeDraft, False),
        (viewmode.ViewModeLayout, False),
        (viewmode.ViewModeSideBySide, True),
    ],
)
def testPaintNoteMarkers(app, vm, inside):
    ed = loadSample()
    ed.sp.lines[1].notes = (Note("Hi"),)
    vm = vm()
    size = wx.Size(1600, 600)
    cfgGui = configgui.ConfigGui(ed.sp.cfgGl, 100)
    vp = scriptpainter.Viewport.make(ed.sp, ed, cfgGui, vm, size, lambda n: n)

    painter = scriptpainter.ScriptPainter(vp, vm, ed.sp.cfgGl, False)
    dc = wx.MemoryDC(wx.Bitmap(size))
    painter.paint(dc)
    dc.SelectObject(wx.NullBitmap)

    strings, dpages = vm.getScreen(vp, True, True)
    t = next(t for t in strings if t.line == 1)

    if dpages:
        right = next(dp.x2 for dp in dpages if dp.x1 <= t.x <= dp.x2)
    else:
        right = (size.width - vp.pageW) // 2 + vp.pageW

    assert len(painter.noteMarkers) == 1
    rect, line = painter.noteMarkers[0]
    assert line == 1
    assert rect.y == t.y

    if inside:
        assert rect.x + rect.width == right - 20
    else:
        assert rect.x == right + 20
