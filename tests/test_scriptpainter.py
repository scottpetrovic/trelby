import pytest
import wx

import tests.u as u
import trelby.config as config
import trelby.configgui as configgui
import trelby.gutil as gutil
import trelby.screenplay as screenplay
import trelby.scriptpainter as scriptpainter
import trelby.translations as translations
import trelby.viewmode as viewmode

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


def paint(ed, vm, showFormatting=False, size=(900, 1200)):
    cfgGl = ed.sp.cfgGl
    cfgGui = configgui.ConfigGui(cfgGl, 100)
    vp = scriptpainter.Viewport.make(
        ed.sp, ed, cfgGui, vm, wx.Size(*size), lambda n: n
    )

    bmp = wx.Bitmap(*size)
    dc = wx.MemoryDC(bmp)
    rect = scriptpainter.ScriptPainter(vp, vm, cfgGl, showFormatting).paint(dc)
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
