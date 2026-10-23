from types import SimpleNamespace

import pytest
import wx

import tests.u as u
import trelby.screenplay as screenplay
import trelby.translations as translations

_ = translations.trelby_translations_load()

import trelby.ui.breakdownview as breakdownview  # noqa: E402
import trelby.ui.menus as menus  # noqa: E402
import trelby.ui.trelbyctrl as trelbyctrl  # noqa: E402
from trelby.screenplay.breakdown import Tag  # noqa: E402

# the breakdown's GUI: tagging from the script's right-click menu (on a
# MyCtrl without a window), and the side panel's Breakdown tab
# (ui/breakdownview.py) on a stand-in for the MyPanel and MyCtrl, with a
# real Editor on a script

SCRIPT = [
    "#Version 3",
    "#Start-Script ",
    ".\\INT. GARAGE - NIGHT",
    "#Tag props|Revolver|his gun",
    "..Mary watches John clean his gun.",
    "._JOHN",
    ".:Get in the car.",
    ".\\EXT. HIGHWAY - DAY",
    "..The car speeds past.",
]


def load():
    sp = u.loadString("\n".join(SCRIPT))
    sp.paginate()

    return screenplay.Editor(sp)


# a MyCtrl for ed, without a window, with what tagging needs
def makeCtrl(ed):
    ctrl = trelbyctrl.MyCtrl.__new__(trelbyctrl.MyCtrl)
    ctrl.sp = ed.sp
    ctrl.ed = ed
    ctrl.tagIds = [wx.NewIdRef() for i in range(len(trelbyctrl.breakdown.CATEGORIES))]
    ctrl.untagIds = [wx.NewIdRef() for i in range(trelbyctrl.UNTAG_ITEMS)]
    ctrl.clearAutoComp = lambda: None
    ctrl.updateScreen = lambda *args: None

    return ctrl


def menuEvent(id):
    return wx.CommandEvent(wx.wxEVT_MENU, int(id))


def testTagWordFromMenu(app):
    ed = load()
    ctrl = makeCtrl(ed)

    # "Mary" in the action
    tagItems, removeItems = ctrl.tagMenu(1, 1)

    assert [label for id, label in tagItems][:3] == ["Cast", "Extras", "Stunts"]
    assert removeItems == []
    assert ctrl.tagTarget == (1, "Mary")

    ctrl.OnTagMenu(menuEvent(ctrl.tagIds[0]))

    assert ed.sp.lines[1].tags[-1] == Tag("cast", "Mary", "Mary")

    # on "gun", the revolver's tag can be removed
    col = ed.sp.lines[1].text.index("gun")
    tagItems, removeItems = ctrl.tagMenu(1, col)

    assert [label for id, label in removeItems] == ["Remove tag: Revolver (Props)"]

    ctrl.OnTagMenu(menuEvent(ctrl.untagIds[0]))
    assert [t.name for t in ed.sp.lines[1].tags] == ["Mary"]

    ed.cmd("undo")
    assert [t.name for t in ed.sp.lines[1].tags] == ["Revolver", "Mary"]


def testTagSelectionFromMenu(app):
    ed = load()
    ctrl = makeCtrl(ed)
    text = ed.sp.lines[1].text
    a = text.index("clean")

    ed.setMark(1, a)
    ed.line, ed.column = 1, a + len("clean his gun") - 1

    tagItems, removeItems = ctrl.tagMenu(1, 0)
    assert ctrl.tagTarget == (1, "clean his gun")

    ctrl.OnTagMenu(menuEvent(ctrl.tagIds[2]))
    assert ed.sp.lines[1].tags[-1] == Tag("stunts", "clean his gun", "clean his gun")

    # a selection running into another paragraph can't be tagged
    ed.line = 3
    assert ctrl.tagMenu(1, 0) == (None, [])


def testRightClickMenuItems(app):
    actions = {a.name: a for a in menus.allActions(*menus.makeTable())}
    ed = load()
    tagging = ([(wx.NewIdRef(), "Props")], [(wx.NewIdRef(), "Remove tag: X")])

    m = menus.makeRightClickMenu(
        actions, ed.sp.cfg, screenplay.ACTION, False, tagging=tagging
    )
    labels = [it.GetItemLabelText() for it in m.GetMenuItems()]
    m.Destroy()

    tagAs = labels.index("Tag as")

    assert labels[tagAs - 1].startswith("Add note")
    assert labels[tagAs + 1] == "Remove tag: X"


class FakeCtrl:
    def __init__(self, ed):
        self.ed = ed
        self.sp = ed.sp
        self.shown = []

    def showLine(self, line):
        self.shown.append(line)
        self.ed.line = line

    def SetFocus(self):
        pass

    def renameElement(self, *args):
        return self.ed.renameElement(*args)

    def removeElement(self, *args):
        return self.ed.removeElement(*args)

    def addSceneElement(self, *args):
        return self.ed.addSceneElement(*args)


@pytest.fixture
def panel(app):
    ed = load()
    frame = wx.Frame(None, size=wx.Size(300, 700))
    scriptPanel = SimpleNamespace(ctrl=FakeCtrl(ed), gd=SimpleNamespace(showTags=True))

    p = breakdownview.BreakdownPanel(frame, scriptPanel)
    frame.Layout()

    yield p

    frame.Destroy()


def rows(p):
    return [(r.kind, r.text, r.detail) for r in p.rows]


def testSceneRows(panel):
    panel.refresh()

    assert rows(panel) == [
        (breakdownview.HEADING, "1  INT. GARAGE - NIGHT", "Page 1 · 1/8 page"),
        (breakdownview.CATEGORY, "Cast", "1"),
        (breakdownview.ELEMENT, "JOHN", "speaks"),
        (breakdownview.CATEGORY, "Props", "1"),
        (breakdownview.ELEMENT, "Revolver", ""),
    ]
    assert not panel.rows[2].tagged

    # the scene at the cursor
    ctrl = panel.getCtrl()
    ctrl.ed.line = 4
    panel.refresh()

    assert rows(panel)[0][1] == "2  EXT. HIGHWAY - DAY"
    assert panel.rows[1].kind == breakdownview.MESSAGE

    # without counting the speakers
    ctrl.ed.line = 0
    panel.castSpeakers = False
    panel.refresh()

    assert [r.text for r in panel.rows] == ["1  INT. GARAGE - NIGHT", "Props", "Revolver"]


def testScriptRowsAndGoTo(panel):
    ed = panel.getCtrl().ed
    ed.addTag(5, "vehicles", "Car", "car")
    ed.addTag(3, "vehicles", "car", "car")

    panel.setScope(breakdownview.SCOPE_SCRIPT)

    assert rows(panel) == [
        (breakdownview.CATEGORY, "Cast", "1"),
        (breakdownview.ELEMENT, "JOHN", "1 scene"),
        (breakdownview.CATEGORY, "Vehicles", "1"),
        (breakdownview.ELEMENT, "car", "2 scenes"),
        (breakdownview.CATEGORY, "Props", "1"),
        (breakdownview.ELEMENT, "Revolver", "1 scene"),
    ]

    # the next scene it's in after the cursor's, then round to the first
    car = panel.rows[3]
    panel.goTo(car)
    assert panel.getCtrl().shown == [5]

    panel.goTo(car)
    assert panel.getCtrl().shown == [5, 3]

    # a speaking character goes to where they speak
    panel.goTo(panel.rows[1])
    assert panel.getCtrl().shown[-1] == 2


def testRemoveAndChangeCategory(panel):
    ed = panel.getCtrl().ed
    panel.refresh()

    revolver = panel.rows[4]
    panel.changeCategory(revolver, "sfx")

    assert ed.sp.lines[1].tags == (Tag("sfx", "Revolver", "his gun"),)
    assert [r.text for r in panel.rows][-2:] == ["Special effects", "Revolver"]

    panel.removeFromScene(panel.rows[-1])
    assert not ed.sp.hasTags()

    # a speaking character who isn't tagged can't be removed
    john = panel.rows[2]
    assert not john.tagged
    panel.removeFromScene(john)
    assert [r.text for r in panel.rows][2] == "JOHN"


def testSelectOnlyElements(panel):
    panel.refresh()

    panel.list.SetSelection(1)
    panel.OnItemSelected(None)
    assert panel.getSelected() is None

    panel.list.SetSelection(4)
    panel.OnItemSelected(None)
    assert panel.getSelected().name == "Revolver"

    # kept selected over a refresh that changes the list
    panel.getCtrl().ed.addTag(1, "cast", "Mary", "Mary")
    panel.refresh()
    assert panel.getSelected().name == "Revolver"


def testPaintList(panel):
    panel.refresh()
    lc = panel.list
    lc.SetSize(wx.Size(260, 400))

    bmp = wx.Bitmap(260, 400)
    dc = wx.MemoryDC(bmp)

    for n in range(len(panel.rows)):
        rect = wx.Rect(0, 0, 260, lc.OnMeasureItem(n))
        lc.OnDrawBackground(dc, rect, n)
        lc.OnDrawItem(dc, rect, n)

    dc.SelectObject(wx.NullBitmap)
