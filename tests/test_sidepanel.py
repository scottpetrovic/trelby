from types import SimpleNamespace

import pytest
import wx

import tests.u as u
import trelby.config as config
import trelby.screenplay as screenplay
import trelby.translations as translations
import trelby.ui.gutil as gutil

_ = translations.trelby_translations_load()

import trelby.ui.sidepanel as sidepanel  # noqa: E402
from trelby.ui.globaldata import GlobalData  # noqa: E402

# the side panel (ui/sidepanel.py) with the outline, the notes and the
# read aloud controls as tabs, on a stand-in for the MyPanel and the main
# frame, with a real Editor on a script


@pytest.fixture(scope="module")
def app():
    a = wx.App(False)
    gutil.init()
    yield a
    a.Destroy()


@pytest.fixture
def side(app):
    u.init()

    with open("trelby/sample.trelby", encoding="utf-8") as f:
        sp = screenplay.Screenplay.load(f.read(), config.ConfigGlobal())[0]

    sp.paginate()
    ed = screenplay.Editor(sp)
    ed.addNote(1, "First")

    calls = []
    frame = wx.Frame(None, size=wx.Size(300, 700))
    scriptPanel = SimpleNamespace(
        ctrl=SimpleNamespace(ed=ed, sp=sp),
        gd=SimpleNamespace(
            mainFrame=SimpleNamespace(
                showSideTab=lambda tab: calls.append(("tab", tab)),
                setShowSidePanel=lambda show: calls.append(("show", show)),
                reader=None,
            )
        ),
    )

    p = sidepanel.SidePanel(frame, scriptPanel)
    p.calls = calls
    frame.Layout()

    yield p

    frame.Destroy()


def shown(p):
    return [
        (page.IsShown(), page.tools.IsShown())
        for page in (p.outline, p.notes, p.readAloud)
    ]


def testStartsAtOutline(side):
    assert side.tab == GlobalData.SIDE_OUTLINE
    assert side.tabs.selected == GlobalData.SIDE_OUTLINE
    assert shown(side) == [(True, True), (False, False), (False, False)]


# switching tabs shows only that page and its buttons, up to date
def testSetTab(side):
    side.setTab(GlobalData.SIDE_NOTES)

    assert side.tabs.selected == GlobalData.SIDE_NOTES
    assert shown(side) == [(False, False), (True, True), (False, False)]
    assert [it.note.text for it in side.notes.items] == ["First"]

    side.setTab(GlobalData.SIDE_OUTLINE)

    assert shown(side) == [(True, True), (False, False), (False, False)]
    assert side.outline.items


# a click on a tab, and the close button, go through the main frame, which
# does it in every script's tab
def testClicks(side):
    tabs = side.tabs
    rects = tabs.getRects(wx.ClientDC(tabs))
    assert len(rects) == 3

    for i, r in enumerate(rects):
        e = wx.MouseEvent(wx.wxEVT_LEFT_DOWN)
        e.SetPosition(r.GetPosition() + wx.Point(2, 2))
        tabs.OnLeftDown(e)

    side.OnClose(None)

    assert side.calls == [
        ("tab", GlobalData.SIDE_OUTLINE),
        ("tab", GlobalData.SIDE_NOTES),
        ("tab", GlobalData.SIDE_READ_ALOUD),
        ("show", False),
    ]


# leaving the notes tab finishes editing a note, keeping it
def testLeavingNotesFinishesEdit(side):
    side.setTab(GlobalData.SIDE_NOTES)
    finished = []
    side.notes.finishEdit = lambda keep, refocus=False: finished.append(keep)

    side.setTab(GlobalData.SIDE_OUTLINE)

    assert finished == [True]
