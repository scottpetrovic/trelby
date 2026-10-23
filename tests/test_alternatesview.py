import pytest
import wx

import tests.u as u
import trelby.commands as commands
import trelby.config as config
import trelby.keys as keys
import trelby.screenplay as screenplay
import trelby.translations as translations

_ = translations.trelby_translations_load()

import trelby.dialogs.alternatesdlg as alternatesdlg  # noqa: E402
import trelby.ui.configgui as configgui  # noqa: E402
import trelby.ui.menus as menus  # noqa: E402
import trelby.ui.scriptactions as scriptactions  # noqa: E402
import trelby.ui.scriptpainter as scriptpainter  # noqa: E402
import trelby.ui.trelbyctrl as trelbyctrl  # noqa: E402
import trelby.ui.viewmode as viewmode  # noqa: E402
from trelby.screenplay.alternates import Take  # noqa: E402

# the alternates' GUI: the right-click menu's Alternates submenu (on a
# MyCtrl without a window), the badge drawn beside elements that have
# alternates, the keyboard commands and the alternates dialog

SCRIPT = [
    "#Version 3",
    "#Start-Script ",
    ".\\INT. KITCHEN - DAY",
    "..Mary cooks.",
    "._MARY",
    "#Alternate |Dinner.",
    "#Alternate |Food's on the table & getting cold!",
    ".:Dinner's ready!",
    "._JOHN",
    ".:Coming.",
]


def load():
    sp = u.loadString("\n".join(SCRIPT))
    sp.paginate()

    return screenplay.Editor(sp)


# a MyCtrl for ed, without a window, with what the alternates need
def makeCtrl(ed):
    ctrl = trelbyctrl.MyCtrl.__new__(trelbyctrl.MyCtrl)
    ctrl.sp = ed.sp
    ctrl.ed = ed
    ctrl.altIds = [wx.NewIdRef() for i in range(trelbyctrl.ALT_ITEMS)]
    ctrl.altLine = None
    ctrl.altMarkers = []
    ctrl.clearAutoComp = lambda: None
    ctrl.updateScreen = lambda *args: None
    ctrl.makeLineVisible = lambda *args: None

    return ctrl


def menuEvent(id):
    return wx.CommandEvent(wx.wxEVT_MENU, int(id))


def texts(takes):
    return [t.text for t in takes]


def testMenuSwitchesTakes(app):
    ed = load()
    ctrl = makeCtrl(ed)

    shown, items = ctrl.alternatesMenu(3)

    assert shown == "Dinner's ready!"

    # "&" would be a mnemonic
    assert [label for id, label in items] == [
        "Dinner.",
        "Food's on the table && getting cold!",
    ]
    assert ctrl.altLine == 3

    ctrl.OnAlternateMenu(menuEvent(ctrl.altIds[1]))

    assert ed.sp.lines[3].text.startswith("Food's")
    assert texts(ed.sp.getAlternates(3)) == ["Dinner's ready!", "Dinner."]

    ed.cmd("undo")
    assert ed.sp.lines[3].text == "Dinner's ready!"


def testMenuWithoutAlternatesOrWithSelection(app):
    ed = load()
    ctrl = makeCtrl(ed)

    # an element without takes still gets the submenu, to add one
    assert ctrl.alternatesMenu(5) == ("Coming.", [])

    ed.setMark(1, 0)
    assert ctrl.alternatesMenu(3) is None
    assert ctrl.alternatesMenu(None) is None


def testAddAndCycleThroughCtrl(app):
    ed = load()
    ctrl = makeCtrl(ed)

    assert ctrl.addAlternate(5)
    assert not ctrl.addAlternate(5)
    assert texts(ed.sp.getAlternates(5)) == ["Coming."]

    assert ctrl.cycleAlternate(3, 1)
    assert ed.sp.lines[3].text == "Dinner."
    assert not ctrl.cycleAlternate(1, 1)


def testRightClickMenuItems(app):
    actions = {a.name: a for a in menus.allActions(*menus.makeTable())}
    ed = load()
    takeId = wx.NewIdRef()

    m = menus.makeRightClickMenu(
        actions,
        ed.sp.cfg,
        screenplay.DIALOGUE,
        False,
        alternates=("Dinner's ready!", [(takeId, "Dinner.")]),
    )
    items = m.GetMenuItems()
    labels = [it.GetItemLabelText() for it in items]
    alt = labels.index("Alternates")

    assert labels[alt - 1].startswith("Add note")

    sub = items[alt].GetSubMenu()
    subItems = sub.GetMenuItems()

    assert [it.GetItemLabelText() for it in subItems if not it.IsSeparator()] == [
        "Dinner's ready!",
        "Dinner.",
        "Add as alternate",
        "Manage alternates...",
    ]
    assert subItems[0].IsChecked()
    assert not subItems[1].IsChecked()
    assert subItems[1].GetId() == int(takeId)
    m.Destroy()

    # no submenu without alternates
    m = menus.makeRightClickMenu(actions, ed.sp.cfg, screenplay.DIALOGUE, False)
    assert "Alternates" not in [it.GetItemLabelText() for it in m.GetMenuItems()]
    m.Destroy()


def testActions(app):
    ed = load()
    ctrl = makeCtrl(ed)

    ed.line = 3
    assert scriptactions.hasAlternates(None, ctrl)
    assert scriptactions.canAddAlternate(None, ctrl)

    ed.line = 5
    assert not scriptactions.hasAlternates(None, ctrl)

    scriptactions.addAlternate(None, ctrl)
    assert scriptactions.hasAlternates(None, ctrl)

    ed.line = 3
    scriptactions.cycleAlternate(None, ctrl, -1)
    assert ed.sp.lines[3].text.startswith("Food's")


@pytest.mark.parametrize(
    "key, name",
    [(keys.WXK_RIGHT, "NextAlternate"), (keys.WXK_LEFT, "PrevAlternate")],
)
def testAltArrowKeys(key, name):
    keyMap = commands.makeKeyMap(commands.defaultCommands())

    text, cmd = commands.resolveKey(keyMap, keys.WXK_NONE, key, alt=True)
    assert cmd.name == name

    # without Alt they still move the cursor
    text, cmd = commands.resolveKey(keyMap, keys.WXK_NONE, key)
    assert cmd.name in ("MoveLeft", "MoveRight")


# paint ed's script into a bitmap and return the ScriptPainter
def paint(ed, vm):
    cfgGl = ed.sp.cfgGl
    cfgGui = configgui.ConfigGui(cfgGl, 100)
    size = wx.Size(900, 1200)
    vp = scriptpainter.Viewport.make(ed.sp, ed, cfgGui, vm, size, lambda n: n)

    bmp = wx.Bitmap(size)
    dc = wx.MemoryDC(bmp)
    painter = scriptpainter.ScriptPainter(vp, vm, cfgGl, False)
    painter.paint(dc)
    dc.SelectObject(wx.NullBitmap)

    return painter, vp


@pytest.mark.parametrize(
    "vm",
    [viewmode.ViewModeDraft, viewmode.ViewModeLayout, viewmode.ViewModeSideBySide],
)
def testPaintMarkers(app, vm):
    ed = load()
    painter, vp = paint(ed, vm())

    # one badge, left of the dialogue it's for
    assert [line for rect, line in painter.altMarkers] == [3]

    rect = painter.altMarkers[0][0]
    strings, dpages = vm().getScreen(vp, True, True)
    t = next(t for t in strings if t.line == 3)

    assert rect.right < t.x
    assert rect.y == t.y

    ed.keepAlternate(3)
    painter, vp = paint(ed, vm())
    assert painter.altMarkers == []


def testMarkerClick(app):
    ed = load()
    ctrl = makeCtrl(ed)
    ctrl.altMarkers = [(wx.Rect(10, 20, 15, 12), 3)]

    assert ctrl.altMarkerAt(wx.Point(12, 25)) == 3
    assert ctrl.altMarkerAt(wx.Point(40, 25)) is None


# the dialog's list of takes


def takeList():
    return alternatesdlg.TakeList(
        Take("A"), [Take("B", "1"), Take("C")]
    )


def testTakeListEdits():
    tl = takeList()

    tl.selected = 2
    tl.show()
    assert texts(tl.takes) == ["C", "A", "B"]
    assert tl.selected == 0

    tl.selected = 2
    tl.move(-1)
    assert texts(tl.takes) == ["C", "B", "A"]
    assert tl.selected == 1

    # moving one to the top shows it
    tl.move(-1)
    assert texts(tl.takes) == ["B", "C", "A"]
    tl.move(-1)
    assert tl.selected == 0

    tl.add()
    assert tl.selected == 3
    tl.setText("  D \n\n")

    shown, others = tl.result()
    assert shown == Take("B", "1")
    assert texts(others) == ["C", "A", "D"]

    tl.delete()
    tl.delete()
    tl.delete()
    tl.delete()
    assert texts(tl.takes) == ["B"]


def testTakeListDropsEmptyTakes():
    tl = takeList()
    tl.setText("")
    tl.add()

    shown, others = tl.result()
    assert shown.text == "B"
    assert texts(others) == ["C"]

    tl = alternatesdlg.TakeList(Take(""), [])
    assert tl.result() == (Take(""), [])


def testTakeListKeepsFormattingUnlessEdited():
    tl = takeList()
    tl.selected = 1

    tl.setText("B")
    assert tl.takes[1].fmt == "1"

    tl.setText("Bee")
    assert tl.takes[1] == Take("Bee")
    assert tl.label(1) == "Bee"
    assert tl.label(0) == "Shown: A"


def testDialog(app):
    dlg = alternatesdlg.AlternatesDlg(None, "Dialogue: MARY", Take("A"), [Take("B")])

    try:
        assert dlg.list.GetStrings() == ["Shown: A", "B"]
        assert dlg.textCtrl.GetValue() == "A"
        assert not dlg.showBtn.IsEnabled()
        assert not dlg.upBtn.IsEnabled()

        dlg.list.SetSelection(1)
        dlg.OnSelect()
        assert dlg.textCtrl.GetValue() == "B"
        assert dlg.showBtn.IsEnabled()

        dlg.textCtrl.SetValue("Bee")
        assert dlg.list.GetString(1) == "Bee"

        dlg.OnShow()
        assert dlg.list.GetStrings() == ["Shown: Bee", "A"]

        dlg.OnNew()
        assert dlg.list.GetStrings() == ["Shown: Bee", "A", "(empty)"]
        assert dlg.textCtrl.GetValue() == ""

        dlg.OnDelete()
        dlg.OnMove(-1)
        assert dlg.list.GetStrings() == ["Shown: A", "Bee"]

        assert dlg.takes.result() == (Take("A"), [Take("Bee")])
    finally:
        dlg.Destroy()


def testManageAlternates(app, monkeypatch):
    ed = load()
    ctrl = makeCtrl(ed)

    class FakeDlg:
        def __init__(self, parent, title, shown, others):
            assert title == "Dialogue: MARY"
            self.takes = alternatesdlg.TakeList(shown, others)
            self.takes.selected = 2
            self.takes.show()

        def ShowModal(self):
            return wx.ID_OK

        def Destroy(self):
            pass

    monkeypatch.setattr(alternatesdlg, "AlternatesDlg", FakeDlg)

    assert alternatesdlg.manageAlternates(None, ctrl, 3)
    assert ed.sp.lines[3].text.startswith("Food's")
    assert texts(ed.sp.getAlternates(3)) == ["Dinner's ready!", "Dinner."]
