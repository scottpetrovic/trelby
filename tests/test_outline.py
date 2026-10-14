import os

import tests.u as u
import trelby.screenplay as scr
import trelby.util as util

# tests for the outline view's model: Screenplay.getOutline and
# Screenplay.moveScene


def loadSmall():
    return u.loadString(
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


def headings(sp):
    return [it.heading for it in sp.getOutline()]


def testGetOutline():
    sp = loadSmall()
    items = sp.getOutline()

    assert [it.lt for it in items] == [scr.SCENE, scr.SCENE, scr.ACTBREAK, scr.SCENE]
    assert [it.sceneNr for it in items] == ["1", "2", "", "3"]
    assert headings(sp) == [
        "INT. KITCHEN - DAY",
        "EXT. GARDEN - NIGHT",
        "ACT TWO",
        "INT. CAR - DAY",
    ]

    # notes win over action for the summary
    assert items[0].summary == "Ingredients matter here."
    assert items[1].summary == "John waits."
    assert items[3].summary == ""

    # items cover the whole script after the preamble, without gaps
    assert items[0].startLine == 1
    for prev, cur in zip(items, items[1:]):
        assert cur.startLine == prev.endLine + 1
    assert items[-1].endLine == len(sp.lines) - 1


def testGetOutlineMatchesSceneLocations():
    sp = u.load()

    scenes = [(it.sceneNr, it.startLine) for it in sp.getOutline() if it.sceneNr]

    assert scenes == sp.getSceneLocations()


def testGetOutlineMultiLineHeading():
    sp = u.new()
    sp.cmdChars("int. " + "very long place name " * 6 + "- day")

    assert len(sp.lines) > 1
    assert sp.getOutline()[0].heading == util.upper(
        "int. " + "very long place name " * 6 + "- day"
    )


def testMoveSceneDown():
    sp = loadSmall()
    lineCnt = len(sp.lines)

    assert sp.moveScene(1, 1)

    assert headings(sp) == [
        "EXT. GARDEN - NIGHT",
        "INT. KITCHEN - DAY",
        "ACT TWO",
        "INT. CAR - DAY",
    ]
    assert len(sp.lines) == lineCnt
    assert sp.lines[0].text == "Fade in:"
    assert sp.line == sp.getOutline()[1].startLine
    assert sp.column == 0
    assert sp.isModified()


def testMoveSceneUpFromMiddleOfScene():
    sp = loadSmall()

    # a line inside the last scene
    assert sp.moveScene(len(sp.lines) - 1, -1)

    assert headings(sp) == [
        "INT. KITCHEN - DAY",
        "EXT. GARDEN - NIGHT",
        "INT. CAR - DAY",
        "ACT TWO",
    ]
    assert sp.line == sp.getOutline()[2].startLine


def testMoveSceneLimits():
    sp = loadSmall()
    before = [str(ln) for ln in sp.lines]

    # first scene can't go above the preamble, last scene can't go down,
    # and the preamble itself can't be moved
    assert not sp.moveScene(1, -1)
    assert not sp.moveScene(len(sp.lines) - 1, 1)
    assert not sp.moveScene(0, 1)

    assert [str(ln) for ln in sp.lines] == before
    assert not sp.canUndo()


def testMoveSceneUndoRedo():
    sp = loadSmall()
    before = [str(ln) for ln in sp.lines]

    sp.line = 1
    sp.moveScene(sp.line, 1)
    after = [str(ln) for ln in sp.lines]

    sp.cmd("undo")
    assert [str(ln) for ln in sp.lines] == before
    assert sp.line == 1

    sp.cmd("redo")
    assert [str(ln) for ln in sp.lines] == after


def testMoveSceneKeepsScriptValid():
    sp = u.load()

    for i in range(len(sp.getOutline())):
        sp.moveScene(sp.getOutline()[0].startLine, 1)
        sp._validate()


def testMoveSceneToLaterPosition():
    sp = loadSmall()

    assert sp.moveSceneTo(1, 2)

    assert headings(sp) == [
        "EXT. GARDEN - NIGHT",
        "ACT TWO",
        "INT. KITCHEN - DAY",
        "INT. CAR - DAY",
    ]
    assert sp.lines[0].text == "Fade in:"
    assert sp.line == sp.getOutline()[2].startLine


def testMoveSceneToFirstPosition():
    sp = loadSmall()
    last = sp.getOutline()[-1]

    assert sp.moveSceneTo(last.startLine, 0)

    assert headings(sp) == [
        "INT. CAR - DAY",
        "INT. KITCHEN - DAY",
        "EXT. GARDEN - NIGHT",
        "ACT TWO",
    ]
    # the moved scene goes after the preamble, not before it
    assert sp.lines[0].text == "Fade in:"
    assert sp.line == 1


def testMoveSceneToKeepsContents():
    sp = u.load()
    before = sorted(str(ln) for ln in sp.lines)
    items = sp.getOutline()

    assert sp.moveSceneTo(items[3].startLine, len(items) - 1)

    assert sorted(str(ln) for ln in sp.lines) == before
    assert sp.getOutline()[-1].heading == items[3].heading
    sp._validate()


def testMoveSceneToInvalid():
    sp = loadSmall()
    n = len(sp.getOutline())

    assert not sp.moveSceneTo(1, 0)
    assert not sp.moveSceneTo(1, -1)
    assert not sp.moveSceneTo(1, n)
    assert not sp.moveSceneTo(0, 2)
    assert not sp.canUndo()


def testMoveSceneToUndo():
    sp = loadSmall()
    before = [str(ln) for ln in sp.lines]

    sp.moveSceneTo(1, 3)
    sp.cmd("undo")

    assert [str(ln) for ln in sp.lines] == before


# outline-sample.trelby (in the repo root) is a hand-testing script for the
# outline view; make sure it stays loadable and keeps covering what it's
# meant to.
def testOutlineSample():
    path = os.path.join(os.path.dirname(__file__), "..", "outline-sample.trelby")

    with open(path, "r", encoding="utf-8") as f:
        sp = u.loadString(f.read())

    sp._validate()

    assert {ln.lt for ln in sp.lines} == {
        scr.SCENE,
        scr.ACTION,
        scr.CHARACTER,
        scr.DIALOGUE,
        scr.PAREN,
        scr.TRANSITION,
        scr.SHOT,
        scr.ACTBREAK,
        scr.NOTE,
    }

    items = sp.getOutline()

    assert len([it for it in items if it.lt == scr.ACTBREAK]) == 3
    assert len([it for it in items if it.lt == scr.SCENE]) == 11
    assert items[0].startLine > 0
