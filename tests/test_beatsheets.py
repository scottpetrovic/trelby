from types import SimpleNamespace

import pytest
import wx

import tests.u as u
import trelby.screenplay as scr
from trelby.screenplay.notes import Note
import trelby.translations as translations
import trelby.ui.gutil as gutil

_ = translations.trelby_translations_load()

import trelby.screenplay.beatsheets as beatsheets  # noqa: E402
import trelby.ui.outline as outline  # noqa: E402

# tests for the outline's add scene button: Editor.insertScenes /
# addScene, the beat sheets, and the buttons on the outline panel


def loadSmall():
    return u.loadStringEditor(
        "\n".join(
            [
                "#Version 3",
                "#Start-Script ",
                "./Fade in:",
                ".\\int. kitchen - day",
                "..Mary cooks.",
                ".\\ext. garden - night",
                "..John waits.",
            ]
        )
    )


def headings(ed):
    return [it.heading for it in ed.sp.getOutline()]


def testSheets():
    keys = [s.key for s in beatsheets.SHEETS]
    assert keys == ["savethecat", "threeact", "storycircle", "sequence", "minimovie"]
    assert len(set(s.name() for s in beatsheets.SHEETS)) == len(keys)

    assert [len(s.beats()) for s in beatsheets.SHEETS] == [15, 9, 8, 8, 8]

    for s in beatsheets.SHEETS:
        for b in s.beats():
            assert b.name and b.description
            assert scr.isValidColor(b.color)


def testLines():
    lines = beatsheets.get("storycircle").lines()

    # a heading and an action line per beat
    assert [ln.text for ln in lines[::2]] == [
        "YOU",
        "NEED",
        "GO",
        "SEARCH",
        "FIND",
        "TAKE",
        "RETURN",
        "CHANGE",
    ]
    assert all(ln.lt == scr.SCENE for ln in lines[::2])
    assert all(ln.lt == scr.ACTION for ln in lines[1::2])
    assert all(ln.lb == scr.LB_LAST for ln in lines)

    assert lines[0].notes == (Note("You"),)
    assert lines[1].text == "1. A character is in a zone of comfort."
    assert not lines[1].notes
    assert lines[0].color == beatsheets.ORDINARY_WORLD
    assert lines[4].color == beatsheets.UNFAMILIAR_WORLD
    assert lines[1].color is None


def testAddSceneAfterCursorsScene():
    ed = loadSmall()

    # in the kitchen scene's action
    ed.addScene(2)

    assert headings(ed) == ["INT. KITCHEN - DAY", "", "EXT. GARDEN - NIGHT"]
    assert (ed.line, ed.column) == (3, 0)
    assert ed.sp.lines[3].lt == scr.SCENE
    ed._validate()

    ed.cmd("undo")
    assert headings(ed) == ["INT. KITCHEN - DAY", "EXT. GARDEN - NIGHT"]


def testAddSceneAtEnd():
    ed = loadSmall()
    ed.addScene(len(ed.sp.lines) - 1)

    assert headings(ed) == ["INT. KITCHEN - DAY", "EXT. GARDEN - NIGHT", ""]
    assert ed.line == len(ed.sp.lines) - 1
    ed._validate()


def testAddSceneBeforeFirst():
    ed = loadSmall()

    # on FADE IN:, before the first scene
    ed.addScene(0)

    assert headings(ed) == ["", "INT. KITCHEN - DAY", "EXT. GARDEN - NIGHT"]
    assert ed.line == 1
    ed._validate()


def testAddSceneToEmptyScript():
    ed = u.newEditor()
    ed.addScene(0)

    # it already is an empty scene
    assert len(ed.sp.lines) == 1
    assert ed.undoHistory.isEmpty()


def testInsertBeatSheet():
    ed = loadSmall()
    ed.insertScenes(2, beatsheets.get("threeact").lines())

    assert headings(ed) == [
        "INT. KITCHEN - DAY",
        "SETUP",
        "INCITING INCIDENT",
        "PLOT POINT ONE",
        "RISING ACTION",
        "MIDPOINT",
        "COMPLICATIONS",
        "PLOT POINT TWO",
        "CLIMAX",
        "RESOLUTION",
        "EXT. GARDEN - NIGHT",
    ]
    items = ed.sp.getOutline()
    assert items[1].summary.startswith("The protagonist, their world")
    assert ed.sp.lines[items[1].startLine].notes == (Note("Setup"),)
    assert items[1].color == beatsheets.ACT_ONE
    assert items[4].color == beatsheets.ACT_TWO
    assert ed.line == items[1].startLine
    ed._validate()

    # one undo step
    ed.cmd("undo")
    assert headings(ed) == ["INT. KITCHEN - DAY", "EXT. GARDEN - NIGHT"]


def testBeatSheetReplacesEmptyScript():
    ed = u.newEditor()
    ed.insertScenes(0, beatsheets.get("savethecat").lines())

    assert len(headings(ed)) == 15
    assert headings(ed)[0] == "OPENING IMAGE"

    # nothing left of the empty script, and the descriptions wrapped
    assert ed.sp.lines[0].lt == scr.SCENE
    assert ed.sp.lines[-1].text.endswith("happened.")
    assert ed.sp.lines[-2].lb != scr.LB_LAST
    ed._validate()


@pytest.fixture(scope="module")
def app():
    a = wx.App(False)
    gutil.init()
    yield a
    a.Destroy()


# an OutlinePanel on a stand-in MyPanel / MyCtrl with a real Editor
@pytest.fixture
def panel(app):
    ed = loadSmall()
    ed.sp.paginate()

    def insertScenes(line, lines=None):
        if lines is None:
            ed.addScene(line)
        else:
            ed.insertScenes(line, lines)

    ctrl = SimpleNamespace(
        ed=ed, sp=ed.sp, insertScenes=insertScenes, SetFocus=lambda: None
    )
    frame = wx.Frame(None, size=wx.Size(300, 700))
    p = outline.OutlinePanel(frame, SimpleNamespace(ctrl=ctrl))
    frame.Show()
    p.refresh()

    yield p

    frame.Destroy()


def testAddButton(panel):
    ed = panel.getCtrl().ed

    # after the selected scene, the cursor's (the first) if none
    panel.list.SetSelection(1)
    panel.OnAddScene(None)

    assert headings(ed) == ["INT. KITCHEN - DAY", "EXT. GARDEN - NIGHT", ""]
    assert len(panel.items) == 3


def testBeatSheetButton(panel, monkeypatch):
    ed = panel.getCtrl().ed
    shown = []

    # pick the menu's fourth item, the sequence method
    def popup(menu, pos):
        items = menu.GetMenuItems()
        shown.extend(it.GetItemLabelText() for it in items)

        return items[3].GetId()

    monkeypatch.setattr(panel.tools, "GetPopupMenuSelectionFromUser", popup)
    panel.OnBeatSheetBtn(None)

    assert shown == [s.name() for s in beatsheets.SHEETS]

    # no scene is selected and the cursor is on FADE IN:, so they go
    # before the first scene
    assert headings(ed)[0] == "SEQUENCE A: STATUS QUO AND INCITING INCIDENT"
    assert headings(ed)[-2:] == ["INT. KITCHEN - DAY", "EXT. GARDEN - NIGHT"]
    assert len(headings(ed)) == 10
    assert len(panel.items) == 10
