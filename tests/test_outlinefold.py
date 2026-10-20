from types import SimpleNamespace

import pytest
import wx

import tests.u as u
import trelby.screenplay as screenplay
import trelby.translations as translations
import trelby.ui.gutil as gutil

_ = translations.trelby_translations_load()

import trelby.ui.outline as outline  # noqa: E402

# folding acts in the outline panel (ui/outline.py), on a stand-in for the
# MyCtrl with a real Editor


def item(lt, heading):
    return screenplay.OutlineItem(lt, "", 0, 0, heading, "", "")


def testMakeRows():
    S, A = screenplay.SCENE, screenplay.ACTBREAK
    items = [
        item(S, "PROLOGUE"),
        item(A, "ACT ONE"),
        item(S, "ONE"),
        item(S, "TWO"),
        item(A, "ACT TWO"),
        item(S, "THREE"),
        item(A, "ACT ONE"),
    ]
    keys = outline.actKeys(items)

    assert keys == [
        None,
        ("ACT ONE", 0),
        None,
        None,
        ("ACT TWO", 0),
        None,
        ("ACT ONE", 1),
    ]
    assert outline.actEnd(items, 1) == 3
    assert outline.actEnd(items, 6) == 6

    assert outline.makeRows(items, set()) == [(i, i) for i in range(7)]
    assert outline.makeRows(items, {("ACT ONE", 0), ("ACT ONE", 1)}) == [
        (0, 0),
        (1, 3),
        (4, 4),
        (5, 5),
        (6, 6),
    ]
    assert outline.makeRows(items, {("ACT TWO", 0)}) == [
        (0, 0),
        (1, 1),
        (2, 2),
        (3, 3),
        (4, 5),
        (6, 6),
    ]


@pytest.fixture(scope="module")
def app():
    a = wx.App(False)
    gutil.init()
    yield a
    a.Destroy()


SCRIPT = "\n".join(
    [
        "#Version 3",
        "#Start-Script ",
        "./Fade in:",
        ".\\int. kitchen - day",
        "..Mary cooks.",
        ".@Act one",
        ".\\ext. garden - night",
        "..John waits.",
        ".\\int. car - day",
        "..They drive.",
        ".@Act two",
        ".\\int. roof - dawn",
        "..The end.",
    ]
)


class FakeCtrl:
    def __init__(self, ed):
        self.ed = ed

    @property
    def sp(self):
        return self.ed.sp

    def gotoLine(self, line):
        self.ed.gotoPos(line, 0)

    def moveSceneTo(self, line, newIndex, count=1):
        self.ed.moveSceneTo(line, newIndex, count)

    def insertScenes(self, line, lines=None):
        if lines is None:
            self.ed.addScene(line)
        else:
            self.ed.insertScenes(line, lines)

    def SetFocus(self):
        pass


@pytest.fixture
def panel(app):
    ed = u.loadStringEditor(SCRIPT)
    frame = wx.Frame(None, size=wx.Size(300, 700))
    p = outline.OutlinePanel(frame, SimpleNamespace(ctrl=FakeCtrl(ed)))
    frame.Show()
    p.refresh()

    yield p

    frame.Destroy()


def shownHeadings(p):
    return [it.heading for it in p.list.items]


def testFoldAndUnfold(panel):
    assert shownHeadings(panel) == [
        "INT. KITCHEN - DAY",
        "ACT ONE",
        "EXT. GARDEN - NIGHT",
        "INT. CAR - DAY",
        "ACT TWO",
        "INT. ROOF - DAWN",
    ]
    assert panel.list.folds[1] == (False, 2)

    panel.toggleFold(1)

    assert shownHeadings(panel) == [
        "INT. KITCHEN - DAY",
        "ACT ONE",
        "ACT TWO",
        "INT. ROOF - DAWN",
    ]
    assert panel.list.folds == [None, (True, 2), (False, 1), None]
    assert panel.list.foldedText(1) == "2 scenes"

    # only act breaks fold
    panel.toggleFold(0)
    assert len(panel.list.items) == 4

    panel.toggleFold(1)
    assert len(panel.list.items) == 6


def testFoldAll(panel):
    panel.foldAll(True)
    assert shownHeadings(panel) == ["INT. KITCHEN - DAY", "ACT ONE", "ACT TWO"]

    panel.foldAll(False)
    assert len(panel.list.items) == 6


# the cursor inside a folded act selects its row
def testSelectionInFoldedAct(panel):
    ctrl = panel.getCtrl()
    car = ctrl.sp.getOutline()[3].startLine
    ctrl.ed.gotoPos(car + 1, 0)

    panel.toggleFold(1)
    panel.selectCurrent()

    assert panel.list.GetSelection() == 1


# a folded act moves with its scenes
def testMoveFoldedAct(panel):
    sp = panel.getCtrl().sp

    panel.foldAll(True)
    panel.moveItem(1, 2)

    assert [it.heading for it in sp.getOutline()] == [
        "INT. KITCHEN - DAY",
        "ACT TWO",
        "INT. ROOF - DAWN",
        "ACT ONE",
        "EXT. GARDEN - NIGHT",
        "INT. CAR - DAY",
    ]
    assert shownHeadings(panel) == ["INT. KITCHEN - DAY", "ACT TWO", "ACT ONE"]
    assert panel.list.GetSelection() == 2

    # and back up, as a whole
    panel.moveItem(2, 1)

    assert [it.heading for it in sp.getOutline()] == [
        "INT. KITCHEN - DAY",
        "ACT ONE",
        "EXT. GARDEN - NIGHT",
        "INT. CAR - DAY",
        "ACT TWO",
        "INT. ROOF - DAWN",
    ]
    assert len(panel.list.items) == 3
    assert panel.list.GetSelection() == 1


# a scene moved below a folded act goes at the end of it, unfolding it
def testMoveIntoFoldedAct(panel):
    sp = panel.getCtrl().sp

    panel.toggleFold(1)
    panel.moveItem(0, 1)

    assert [it.heading for it in sp.getOutline()][:4] == [
        "ACT ONE",
        "EXT. GARDEN - NIGHT",
        "INT. CAR - DAY",
        "INT. KITCHEN - DAY",
    ]
    assert len(panel.list.items) == 6
    assert panel.list.GetSelection() == 3


def testFoldKeys(panel):
    # Left on a scene in an act folds the act and selects it
    panel.list.SetSelection(3)
    panel.foldKey(3, True)

    assert len(panel.list.items) == 4
    assert panel.list.GetSelection() == 1

    panel.foldKey(1, False)
    assert len(panel.list.items) == 6


def testFoldToggleHitTest(panel):
    lc = panel.list

    assert lc.isFoldToggle(1, 0)
    assert not lc.isFoldToggle(1, lc.getTextX())
    assert not lc.isFoldToggle(0, 0)
    assert not lc.isFoldToggle(wx.NOT_FOUND, 0)


# another script in the tab starts with nothing folded
def testNewScriptUnfolds(panel):
    panel.toggleFold(1)
    ctrl = panel.getCtrl()
    ctrl.ed = u.loadStringEditor(SCRIPT)
    panel.refresh()

    assert not panel.folded
    assert len(panel.list.items) == 6


def testPaints(panel):
    panel.toggleFold(1)
    panel.list.Refresh()
    panel.list.Update()
