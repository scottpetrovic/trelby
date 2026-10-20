import os

import tests.u as u
import trelby.screenplay as scr
import trelby.textutil as textutil

# tests for the outline view's model: Screenplay.getOutline and
# Editor.moveScene


def loadSmall():
    return u.loadStringEditor(
        "\n".join(
            [
                "#Version 3",
                # the trailing space is required by the file format
                "#Start-Script ",
                "./Fade in:",
                ".\\int. kitchen - day",
                "..Mary cooks.",
                ".%Ingredients matter here.",
                ".\\ext. garden - night",
                "..John waits.",
                ".@Act two",
                ".\\int. car - day",
                "._MARY",
                ".:Hello.",
            ]
        )
    )


def headings(ed):
    return [it.heading for it in ed.sp.getOutline()]


def testGetOutline():
    ed = loadSmall()
    items = ed.sp.getOutline()

    assert [it.lt for it in items] == [scr.SCENE, scr.SCENE, scr.ACTBREAK, scr.SCENE]
    assert [it.sceneNr for it in items] == ["1", "2", "", "3"]
    assert headings(ed) == [
        "INT. KITCHEN - DAY",
        "EXT. GARDEN - NIGHT",
        "ACT TWO",
        "INT. CAR - DAY",
    ]

    # the summary is the action, not the notes
    assert items[0].summary == "Mary cooks."
    assert items[1].summary == "John waits."
    assert items[3].summary == ""

    # items cover the whole script after the preamble, without gaps
    assert items[0].startLine == 1
    for prev, cur in zip(items, items[1:]):
        assert cur.startLine == prev.endLine + 1
    assert items[-1].endLine == len(ed.sp.lines) - 1


def testGetOutlineMatchesSceneLocations():
    ed = u.loadEditor()

    scenes = [(it.sceneNr, it.startLine) for it in ed.sp.getOutline() if it.sceneNr]

    assert scenes == ed.sp.getSceneLocations()


def testGetOutlineMultiLineHeading():
    ed = u.newEditor()
    ed.cmdChars("int. " + "very long place name " * 6 + "- day")

    assert len(ed.sp.lines) > 1
    assert ed.sp.getOutline()[0].heading == textutil.upper(
        "int. " + "very long place name " * 6 + "- day"
    )


def testMoveSceneDown():
    ed = loadSmall()
    lineCnt = len(ed.sp.lines)

    assert ed.moveScene(1, 1)

    assert headings(ed) == [
        "EXT. GARDEN - NIGHT",
        "INT. KITCHEN - DAY",
        "ACT TWO",
        "INT. CAR - DAY",
    ]
    assert len(ed.sp.lines) == lineCnt
    assert ed.sp.lines[0].text == "Fade in:"
    assert ed.line == ed.sp.getOutline()[1].startLine
    assert ed.column == 0
    assert ed.sp.isModified()


def testMoveSceneUpFromMiddleOfScene():
    ed = loadSmall()

    # a line inside the last scene
    assert ed.moveScene(len(ed.sp.lines) - 1, -1)

    assert headings(ed) == [
        "INT. KITCHEN - DAY",
        "EXT. GARDEN - NIGHT",
        "INT. CAR - DAY",
        "ACT TWO",
    ]
    assert ed.line == ed.sp.getOutline()[2].startLine


def testMoveSceneLimits():
    ed = loadSmall()
    before = [str(ln) for ln in ed.sp.lines]

    # first scene can't go above the preamble, last scene can't go down,
    # and the preamble itself can't be moved
    assert not ed.moveScene(1, -1)
    assert not ed.moveScene(len(ed.sp.lines) - 1, 1)
    assert not ed.moveScene(0, 1)

    assert [str(ln) for ln in ed.sp.lines] == before
    assert not ed.undoHistory.canUndo()


def testMoveSceneUndoRedo():
    ed = loadSmall()
    before = [str(ln) for ln in ed.sp.lines]

    ed.line = 1
    ed.moveScene(ed.line, 1)
    after = [str(ln) for ln in ed.sp.lines]

    ed.cmd("undo")
    assert [str(ln) for ln in ed.sp.lines] == before
    assert ed.line == 1

    ed.cmd("redo")
    assert [str(ln) for ln in ed.sp.lines] == after


def testMoveSceneKeepsScriptValid():
    ed = u.loadEditor()

    for i in range(len(ed.sp.getOutline())):
        ed.moveScene(ed.sp.getOutline()[0].startLine, 1)
        ed._validate()


def testMoveSceneToLaterPosition():
    ed = loadSmall()

    assert ed.moveSceneTo(1, 2)

    assert headings(ed) == [
        "EXT. GARDEN - NIGHT",
        "ACT TWO",
        "INT. KITCHEN - DAY",
        "INT. CAR - DAY",
    ]
    assert ed.sp.lines[0].text == "Fade in:"
    assert ed.line == ed.sp.getOutline()[2].startLine


def testMoveSceneToFirstPosition():
    ed = loadSmall()
    last = ed.sp.getOutline()[-1]

    assert ed.moveSceneTo(last.startLine, 0)

    assert headings(ed) == [
        "INT. CAR - DAY",
        "INT. KITCHEN - DAY",
        "EXT. GARDEN - NIGHT",
        "ACT TWO",
    ]
    # the moved scene goes after the preamble, not before it
    assert ed.sp.lines[0].text == "Fade in:"
    assert ed.line == 1


def testMoveSceneToKeepsContents():
    ed = u.loadEditor()
    before = sorted(str(ln) for ln in ed.sp.lines)
    items = ed.sp.getOutline()

    assert ed.moveSceneTo(items[3].startLine, len(items) - 1)

    assert sorted(str(ln) for ln in ed.sp.lines) == before
    assert ed.sp.getOutline()[-1].heading == items[3].heading
    ed._validate()


def testMoveSceneToInvalid():
    ed = loadSmall()
    n = len(ed.sp.getOutline())

    assert not ed.moveSceneTo(1, 0)
    assert not ed.moveSceneTo(1, -1)
    assert not ed.moveSceneTo(1, n)
    assert not ed.moveSceneTo(0, 2)
    assert not ed.undoHistory.canUndo()


def testMoveSceneToUndo():
    ed = loadSmall()
    before = [str(ln) for ln in ed.sp.lines]

    ed.moveSceneTo(1, 3)
    ed.cmd("undo")

    assert [str(ln) for ln in ed.sp.lines] == before


# outline-sample.trelby (in the repo root) is a hand-testing script for the
# outline view; make sure it stays loadable and keeps covering what it's
# meant to.
def testOutlineSample():
    path = os.path.join(os.path.dirname(__file__), "..", "outline-sample.trelby")

    with open(path, "r", encoding="utf-8") as f:
        ed = u.loadStringEditor(f.read())

    ed._validate()

    assert {ln.lt for ln in ed.sp.lines} == {
        scr.SCENE,
        scr.ACTION,
        scr.CHARACTER,
        scr.DIALOGUE,
        scr.PAREN,
        scr.TRANSITION,
        scr.SHOT,
        scr.ACTBREAK,
    }

    # its note elements are notes now
    assert ed.sp.hasNotes()

    items = ed.sp.getOutline()

    assert len([it for it in items if it.lt == scr.ACTBREAK]) == 3
    assert len([it for it in items if it.lt == scr.SCENE]) == 11
    assert items[0].startLine > 0


def testSummaryJoinsActionParagraphs():
    ed = u.loadStringEditor(
        "\n".join(
            [
                "#Version 3",
                "#Start-Script ",
                ".\\int. kitchen - day",
                "..Later.",
                "._MARY",
                ".:Hello.",
                "..Mary cooks.",
                ".\\ext. garden - night",
                "..A" + " very long sentence" * 20,
                "..Not reached.",
            ]
        )
    )
    items = ed.sp.getOutline()

    # action only, dialogue left out
    assert items[0].summary == "Later. Mary cooks."

    # stops once it has enough
    assert items[1].summary.startswith("A very long sentence")
    assert "Not reached" not in items[1].summary


def testMoveSceneToSeveral():
    ed = loadSmall()
    items = ed.sp.getOutline()

    # the act break and its scene, up to the top
    assert ed.moveSceneTo(items[2].startLine, 0, 2)

    assert headings(ed) == [
        "ACT TWO",
        "INT. CAR - DAY",
        "INT. KITCHEN - DAY",
        "EXT. GARDEN - NIGHT",
    ]
    assert ed.sp.lines[0].text == "Fade in:"
    assert ed.line == 1
    ed._validate()

    # and back down to the end
    assert ed.moveSceneTo(1, 2, 2)

    assert headings(ed) == [
        "INT. KITCHEN - DAY",
        "EXT. GARDEN - NIGHT",
        "ACT TWO",
        "INT. CAR - DAY",
    ]
    assert ed.line == ed.sp.getOutline()[2].startLine


def testMoveSceneToSeveralInvalid():
    ed = loadSmall()

    # past the end, or more items than there are after it
    assert not ed.moveSceneTo(1, 3, 2)
    assert not ed.moveSceneTo(ed.sp.getOutline()[2].startLine, 0, 3)
    assert not ed.moveSceneTo(1, 1, 0)
    assert not ed.undoHistory.canUndo()
