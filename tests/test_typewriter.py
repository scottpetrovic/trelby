from types import SimpleNamespace

import pytest
import wx

import tests.u as u
import trelby.config as config
import trelby.screenplay as screenplay
import trelby.ui.configgui as configgui
import trelby.ui.gutil as gutil
import trelby.ui.scriptpainter as scriptpainter
import trelby.ui.trelbyctrl as trelbyctrl
import trelby.ui.viewmode as viewmode

# typewriter scrolling (ViewMode.scrollLineTo, MyCtrl's use of it) and
# focus mode's fading of the text around the cursor (ScriptPainter)

SIZE = (900, 1000)


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


def viewport(ed, vm):
    cfgGui = configgui.ConfigGui(ed.sp.cfgGl, 100)

    return scriptpainter.Viewport.make(
        ed.sp, ed, cfgGui, vm, wx.Size(*SIZE), lambda n: n
    )


def lineY(vp, vm, line):
    for t in vm.getScreen(vp, True, True)[0]:
        if t.line == line:
            return t.y

    return None


MODES = [viewmode.ViewModeDraft, viewmode.ViewModeLayout]


# every line, wherever it is in the script, ends up exactly at the target,
# the first one too, which needs blank space above it
@pytest.mark.parametrize("mode", MODES)
def testLineGoesToTarget(app, mode):
    ed = loadSample()
    vm = mode()
    vp = viewport(ed, vm)
    target = 400
    n = len(ed.sp.lines)

    for line in [0, 1, 2, 5, 30, n // 3, n // 2, n - 40, n - 2, n - 1]:
        vm.scrollLineTo(vp, line, target)

        assert lineY(vp, vm, line) == target, line

    vm.scrollLineTo(vp, 0, target)
    assert ed.topOffset > 0
    assert ed.getTopLine() == 0


# typing down the script, the cursor's line doesn't move
@pytest.mark.parametrize("mode", MODES)
def testEveryLineOfAStretch(app, mode):
    ed = loadSample()
    vm = mode()
    vp = viewport(ed, vm)

    for line in range(100, 220):
        vm.scrollLineTo(vp, line, 450)

        assert lineY(vp, vm, line) == 450, line


# lines moved above the screen aren't in it, unless partials are asked
# for and some of the line shows
def testDraftSkipsLinesAboveScreen(app):
    ed = loadSample()
    vm = viewmode.ViewModeDraft()
    vp = viewport(ed, vm)

    ed.setTopLine(50)
    ed.topOffset = -100

    texts = vm.getScreen(vp, False)[0]

    assert texts[0].line > 50
    assert all(t.y >= 0 for t in texts)

    partial = vm.getScreen(vp, False, True)[0]
    assert all(t.y + vp.cfgGui.fontYdelta > 0 for t in partial)


# a MyCtrl without a window, for the scrolling and focus methods
def makeCtrl(ed, vm, focusMode=False, typewriter=False):
    ctrl = trelbyctrl.MyCtrl.__new__(trelbyctrl.MyCtrl)
    ctrl.sp = ed.sp
    ctrl.ed = ed
    ed.sp.cfgGl.typewriterScrolling = typewriter
    ctrl.gd = SimpleNamespace(
        cfgGl=ed.sp.cfgGl,
        keyMap=ed.sp.cfgGl.getKeyMap(),
        vm=vm,
        focusMode=focusMode,
    )

    return ctrl


def testIsTypewriter():
    ed = u.newEditor()

    assert not makeCtrl(ed, viewmode.ViewModeDraft()).isTypewriter()
    assert makeCtrl(ed, viewmode.ViewModeDraft(), typewriter=True).isTypewriter()
    assert makeCtrl(ed, viewmode.ViewModeLayout(), typewriter=True).isTypewriter()

    # focus mode only fades the text
    assert not makeCtrl(ed, viewmode.ViewModeDraft(), focusMode=True).isTypewriter()

    # whole pages from the top: not in side by side
    assert not makeCtrl(
        ed, viewmode.ViewModeSideBySide(), typewriter=True
    ).isTypewriter()


class FixedHeight(viewmode.ViewModeDraft):
    def getLineHeight(self, ctrl):
        return 10


# the wheel first scrolls away the blank space above the start of the
# script, and scrolls back to its start when that's above the screen
def testScrollByUsesOffsetFirst():
    ed = loadSample()
    ctrl = makeCtrl(ed, FixedHeight(), typewriter=True)

    ed.setTopLine(0)
    ed.topOffset = 35

    ctrl.scrollBy(2)
    assert (ed.getTopLine(), ed.topOffset) == (0, 15)

    ctrl.scrollBy(2)
    assert (ed.getTopLine(), ed.topOffset) == (0, 0)

    ctrl.scrollBy(2)
    assert (ed.getTopLine(), ed.topOffset) == (2, 0)

    ed.setTopLine(0)
    ed.topOffset = -25

    ctrl.scrollBy(-2)
    assert (ed.getTopLine(), ed.topOffset) == (0, -5)

    ctrl.scrollBy(-2)
    assert (ed.getTopLine(), ed.topOffset) == (0, 0)

    # elsewhere, lines, keeping the offset
    ed.setTopLine(40)
    ed.topOffset = -7

    ctrl.scrollBy(-4)
    assert (ed.getTopLine(), ed.topOffset) == (36, -7)


def testFocusLines():
    ed = loadSample()
    sp = ed.sp
    ctrl = makeCtrl(ed, viewmode.ViewModeDraft())

    ed.line = next(i for i, l in enumerate(sp.lines) if l.lt == screenplay.DIALOGUE)

    assert ctrl.focusLines() is None

    ctrl.gd.focusMode = True

    sp.cfgGl.focusDim = config.FOCUS_DIM_ELEMENT
    assert ctrl.focusLines() == sp.getElemIndexesFromLine(ed.line)

    sp.cfgGl.focusDim = config.FOCUS_DIM_SCENE
    assert ctrl.focusLines() == sp.getSceneIndexesFromLine(ed.line)

    sp.cfgGl.focusDim = config.FOCUS_DIM_NONE
    assert ctrl.focusLines() is None


def paint(ed, vm, focusLines=None):
    vp = viewport(ed, vm)
    bmp = wx.Bitmap(*SIZE)
    dc = wx.MemoryDC(bmp)
    painter = scriptpainter.ScriptPainter(
        vp, vm, ed.sp.cfgGl, False, None, None, None, focusLines
    )
    painter.paint(dc)
    dc.SelectObject(wx.NullBitmap)

    return vp, painter, bmp


# the darkest pixel in the rows of the line drawn at y
def darkest(bmp, y, h):
    img = bmp.ConvertToImage()

    return min(
        sum((img.GetRed(x, yy), img.GetGreen(x, yy), img.GetBlue(x, yy)))
        for yy in range(y, y + h)
        for x in range(0, img.GetWidth(), 1)
    )


# the lines outside focusLines are faded into the page, the ones in it
# aren't
@pytest.mark.parametrize("mode", MODES)
def testFocusFadesOtherLines(app, mode):
    ed = loadSample()
    vm = mode()
    line = next(i for i in range(20, 60) if ed.sp.lines[i].text.strip())
    ed.line = line
    ed.setTopLine(10)

    vp, painter, plain = paint(ed, vm)
    vp, painter, focused = paint(ed, vm, (line, line))

    texts = [t for t in vm.getScreen(vp, False)[0] if t.text.strip()]
    h = vp.cfgGui.fontYdelta // 2

    inside = next(t for t in texts if t.line == line)
    outside = next(t for t in texts if t.line not in (-1, line))

    assert darkest(focused, inside.y, h) == darkest(plain, inside.y, h)
    assert darkest(focused, outside.y, h) > darkest(plain, outside.y, h)

    assert painter.isFaded(line - 1)
    assert painter.isFaded(-1)
    assert not painter.isFaded(line)
