import tests.u as u
import trelby.screenplay as scr
from trelby.line import Line

# tests for auto-completion


# script with the given lines, plus an empty line of type lt at the end,
# with the cursor on it
def makeScript(lines, lt=scr.CHARACTER):
    ed = u.newEditor()
    ed.sp.lines = lines + [Line(scr.LB_LAST, lt, "")]
    ed.line = len(ed.sp.lines) - 1
    ed.column = 0

    return ed


def chars(*names):
    ls = []

    for name in names:
        ls.append(Line(scr.LB_LAST, scr.CHARACTER, name))
        ls.append(Line(scr.LB_LAST, scr.DIALOGUE, "Hi."))

    return ls


def testCompletesPrefix():
    ed = makeScript(chars("JOHN", "MARY"))
    ed.cmdChars("j")
    assert ed.acItems == ["J", "JOHN"]
    assert ed.acSel == 1

    ed.cmd("splitElement")
    assert ed.sp.lines[-2].text == "JOHN"


def testTypedPrefixIsOffered():
    ed = makeScript(chars("BOBBY"))
    ed.cmdChars("bob")
    assert ed.acItems == ["BOB", "BOBBY"]

    ed.cmd("moveUp")
    assert ed.acSel == 0

    ed.cmd("splitElement")
    assert ed.sp.lines[-2].text == "BOB"


def testExactMatchComesFirst():
    # BOBBY is the nearest match above, but BOB was typed exactly
    ed = makeScript(chars("BOB", "BOBBY"))
    ed.cmdChars("bob")
    assert ed.acItems == ["BOB", "BOBBY"]
    assert ed.acSel == 0

    ed.cmd("splitElement")
    assert ed.sp.lines[-2].text == "BOB"


def testOtherSpeakerFirst():
    # JOHN spoke last, so JANE is the likelier next speaker
    ed = makeScript(chars("JANE", "JOHN"))
    ed.cmdChars("j")
    assert ed.acItems == ["J", "JANE", "JOHN"]
    assert ed.acSel == 1


def testRecentThenMostUsed():
    # nothing above the cursor: most used first, then alphabetical
    ed = u.newEditor()
    ed.sp.lines = [Line(scr.LB_LAST, scr.CHARACTER, "")] + chars("CY", "BO", "AL", "BO")
    ed.line = ed.column = 0
    ed.fillAutoComp()
    assert ed.acItems == ["BO", "AL", "CY"]


def testLocationsMostRecentFirst():
    ls = scenes("INT. A - DAY", "INT. B - DAY", "INT. A - DAY")
    ed = makeScript(ls, scr.SCENE)
    ed.sp.lines += scenes("INT. C - DAY")
    ed.cmdChars("int. ")
    assert ed.acItems == ["INT. A - ", "INT. B - ", "INT. C - "]


# script of the given speeches, with the cursor at the end of the last one
def atEndOfDialogue(*names):
    ed = u.newEditor()
    ed.sp.lines = chars(*names)
    ed.line = len(ed.sp.lines) - 1
    ed.column = len(ed.sp.lines[-1].text)

    return ed


def testListOnNewCharacter():
    ed = atEndOfDialogue("JOHN", "MARY")
    ed.cmd("splitElement")
    assert ed.sp.lines[ed.line].lt == scr.CHARACTER
    assert ed.acItems == ["JOHN", "MARY"]
    assert ed.acSel == 0

    # Enter picks the other speaker and moves on to their dialogue
    ed.cmd("splitElement")
    assert ed.sp.lines[ed.line - 1].text == "JOHN"
    assert ed.sp.lines[ed.line].lt == scr.DIALOGUE
    assert not ed.acItems

    ed.cmdChars("Hello.")
    ed.cmd("splitElement")
    assert ed.acItems == ["MARY", "JOHN"]


def testListOnTabToCharacter():
    ed = atEndOfDialogue("JOHN")
    ed.sp.lines.append(Line(scr.LB_LAST, scr.ACTION, ""))
    ed.line += 1
    ed.column = 0

    ed.cmd("tab")
    assert ed.sp.lines[ed.line].lt == scr.CHARACTER
    assert ed.acItems == ["JOHN"]

    # Tab again still cycles the type
    ed.cmd("tab")
    assert ed.sp.lines[ed.line].lt != scr.CHARACTER
    assert not ed.acItems


def testEscapeClosesList():
    ed = atEndOfDialogue("JOHN")
    ed.cmd("splitElement")
    assert ed.acItems

    ed.cmd("abort")
    assert not ed.acItems


def testNoListMovingOntoEmptyCharacter():
    ed = makeScript(chars("JOHN"))
    ed.line = 0
    ed.cmd("moveDown", count=2)
    assert ed.line == len(ed.sp.lines) - 1
    assert not ed.acItems


def testNoTypedRowWithoutMatches():
    ed = makeScript(chars("MARY"))
    ed.cmdChars("z")
    assert not ed.acItems


def testEmptyElementsNotOffered():
    ed = makeScript(chars("", "MARY"))
    ed.cmdChars("m")
    ed.cmd("deleteBackward")
    assert ed.acItems == ["MARY"]


def testWrappedElementNotOffered():
    # a scene heading wrapped onto two lines: neither line is a complete
    # heading, so neither is offered
    ls = [
        Line(scr.LB_SPACE, scr.SCENE, "INT. A VERY LONG LOCATION NAME"),
        Line(scr.LB_LAST, scr.SCENE, "NIGHT"),
        Line(scr.LB_LAST, scr.SCENE, "INT. KITCHEN - DAY"),
    ]
    ed = makeScript(ls, scr.SCENE)

    ed.cmdChars("n")
    assert not ed.acItems

    ed.cmd("deleteBackward")
    ed.cmdChars("int. ")
    assert ed.acItems == ["INT. KITCHEN - "]


def testNoCompletionOnWrappedLine():
    ed = makeScript(chars("JOHN"))
    ed.sp.lines[-1:] = [
        Line(scr.LB_SPACE, scr.CHARACTER, "SOMEONE WITH A VERY"),
        Line(scr.LB_LAST, scr.CHARACTER, ""),
    ]
    ed.line = len(ed.sp.lines) - 1
    ed.column = 0

    ed.cmdChars("j")
    assert not ed.acItems


def scenes(*names):
    return [Line(scr.LB_LAST, scr.SCENE, s) for s in names]


def testScenePrefixes():
    ed = makeScript(scenes("EXT. PARK - DAY", "EXT. PARK - NIGHT"), scr.SCENE)
    ed.cmdChars("e")
    assert ed.acItems == ["E", "EXT. ", "EST. "]

    ed.cmd("deleteBackward")
    ed.cmdChars("i")
    assert ed.acItems == ["I", "INT. ", "INT./EXT. ", "I/E. "]


def testSceneInParts():
    ed = makeScript(
        scenes("INT. KITCHEN - NIGHT", "EXT. KEEP - DAY", "INT. HALL - DAY"),
        scr.SCENE,
    )

    # prefix: Enter fills it in and keeps going
    ed.cmdChars("in")
    assert ed.acItems[ed.acSel] == "INT. "
    ed.cmd("splitElement")
    assert ed.sp.lines[ed.line].text == "INT. "
    assert ed.sp.lines[ed.line].lt == scr.SCENE

    # locations, from any prefix, most recent first
    assert ed.acItems == ["INT. HALL - ", "INT. KEEP - ", "INT. KITCHEN - "]
    ed.cmdChars("k")
    assert ed.acItems == ["INT. K", "INT. KEEP - ", "INT. KITCHEN - "]
    ed.cmd("moveDown")
    ed.cmd("tab")
    assert ed.sp.lines[ed.line].text == "INT. KITCHEN - "

    # times: used ones first, then the defaults
    assert ed.acItems[:4] == [
        "INT. KITCHEN - DAY",
        "INT. KITCHEN - NIGHT",
        "INT. KITCHEN - CONTINUOUS",
        "INT. KITCHEN - LATER",
    ]
    ed.cmdChars("n")
    assert ed.acItems == ["INT. KITCHEN - N", "INT. KITCHEN - NIGHT"]

    # a whole heading ends the element as usual
    ed.cmd("splitElement")
    assert ed.sp.lines[ed.line - 1].text == "INT. KITCHEN - NIGHT"
    assert ed.sp.lines[ed.line].lt == scr.ACTION

    # and the steps undo one at a time
    ed.cmd("undo")
    assert ed.sp.lines[ed.line].text.upper() == "INT. KITCHEN - N"
    ed.cmd("undo", count=2)
    assert ed.sp.lines[ed.line].text.upper() == "INT. K"


def testSceneEndAcceptsPart():
    ed = makeScript(scenes("INT. KITCHEN - NIGHT"), scr.SCENE)
    ed.cmdChars("int. k")
    ed.cmd("moveLineEnd")
    assert ed.sp.lines[ed.line].text == "INT. KITCHEN - "
    assert ed.acItems[0] == "INT. KITCHEN - NIGHT"


def testNewLocationHasNoList():
    ed = makeScript(scenes("INT. KITCHEN - NIGHT"), scr.SCENE)
    ed.cmdChars("int. z")
    assert not ed.acItems


def testOtherHeadingsCompleteWhole():
    ed = makeScript(scenes("INSERT - LETTER", "INT. HALL - DAY"), scr.SCENE)
    ed.cmdChars("in")
    assert ed.acItems == ["IN", "INT. ", "INT./EXT. ", "INSERT - LETTER"]

    ed.cmdChars("s")
    assert ed.acItems == ["INS", "INSERT - LETTER"]
    ed.cmd("splitElement")
    assert ed.sp.lines[ed.line - 1].text == "INSERT - LETTER"


def testCharacterExtensions():
    ed = makeScript(chars("JOHN", "MARY (O.S.)"))
    ed.cmdChars("john (")
    assert ed.acItems == [
        "JOHN (",
        "JOHN (O.S.)",
        "JOHN (V.O.)",
        "JOHN (O.C.)",
        "JOHN (CONT'D)",
    ]

    ed.cmdChars("v")
    assert ed.acItems == ["JOHN (V", "JOHN (V.O.)"]
    ed.cmd("splitElement")
    assert ed.sp.lines[ed.line - 1].text == "JOHN (V.O.)"
    assert ed.sp.lines[ed.line].lt == scr.DIALOGUE
