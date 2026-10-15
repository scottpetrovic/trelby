import tests.u as u
import trelby.screenplay as scr
from trelby.line import Line

# tests for auto-completion


# script with the given lines, plus an empty line of type lt at the end,
# with the cursor on it
def makeScript(lines, lt=scr.CHARACTER):
    sp = u.new()
    sp.lines = lines + [Line(scr.LB_LAST, lt, "")]
    sp.line = len(sp.lines) - 1
    sp.column = 0

    return sp


def chars(*names):
    ls = []

    for name in names:
        ls.append(Line(scr.LB_LAST, scr.CHARACTER, name))
        ls.append(Line(scr.LB_LAST, scr.DIALOGUE, "Hi."))

    return ls


def testCompletesPrefix():
    sp = makeScript(chars("JOHN", "MARY"))
    sp.cmdChars("j")
    assert sp.acItems == ["J", "JOHN"]
    assert sp.acSel == 1

    sp.cmd("splitElement")
    assert sp.lines[-2].text == "JOHN"


def testTypedPrefixIsOffered():
    sp = makeScript(chars("BOBBY"))
    sp.cmdChars("bob")
    assert sp.acItems == ["BOB", "BOBBY"]

    sp.cmd("moveUp")
    assert sp.acSel == 0

    sp.cmd("splitElement")
    assert sp.lines[-2].text == "BOB"


def testExactMatchComesFirst():
    # BOBBY is the nearest match above, but BOB was typed exactly
    sp = makeScript(chars("BOB", "BOBBY"))
    sp.cmdChars("bob")
    assert sp.acItems == ["BOB", "BOBBY"]
    assert sp.acSel == 0

    sp.cmd("splitElement")
    assert sp.lines[-2].text == "BOB"


def testOtherSpeakerFirst():
    # JOHN spoke last, so JANE is the likelier next speaker
    sp = makeScript(chars("JANE", "JOHN"))
    sp.cmdChars("j")
    assert sp.acItems == ["J", "JANE", "JOHN"]
    assert sp.acSel == 1


def testRecentThenMostUsed():
    # nothing above the cursor: most used first, then alphabetical
    sp = u.new()
    sp.lines = [Line(scr.LB_LAST, scr.CHARACTER, "")] + chars("CY", "BO", "AL", "BO")
    sp.line = sp.column = 0
    sp.fillAutoComp()
    assert sp.acItems == ["BO", "AL", "CY"]


def testLocationsMostRecentFirst():
    ls = scenes("INT. A - DAY", "INT. B - DAY", "INT. A - DAY")
    sp = makeScript(ls, scr.SCENE)
    sp.lines += scenes("INT. C - DAY")
    sp.cmdChars("int. ")
    assert sp.acItems == ["INT. A - ", "INT. B - ", "INT. C - "]


# script of the given speeches, with the cursor at the end of the last one
def atEndOfDialogue(*names):
    sp = u.new()
    sp.lines = chars(*names)
    sp.line = len(sp.lines) - 1
    sp.column = len(sp.lines[-1].text)

    return sp


def testListOnNewCharacter():
    sp = atEndOfDialogue("JOHN", "MARY")
    sp.cmd("splitElement")
    assert sp.lines[sp.line].lt == scr.CHARACTER
    assert sp.acItems == ["JOHN", "MARY"]
    assert sp.acSel == 0

    # Enter picks the other speaker and moves on to their dialogue
    sp.cmd("splitElement")
    assert sp.lines[sp.line - 1].text == "JOHN"
    assert sp.lines[sp.line].lt == scr.DIALOGUE
    assert not sp.acItems

    sp.cmdChars("Hello.")
    sp.cmd("splitElement")
    assert sp.acItems == ["MARY", "JOHN"]


def testListOnTabToCharacter():
    sp = atEndOfDialogue("JOHN")
    sp.lines.append(Line(scr.LB_LAST, scr.ACTION, ""))
    sp.line += 1
    sp.column = 0

    sp.cmd("tab")
    assert sp.lines[sp.line].lt == scr.CHARACTER
    assert sp.acItems == ["JOHN"]

    # Tab again still cycles the type
    sp.cmd("tab")
    assert sp.lines[sp.line].lt != scr.CHARACTER
    assert not sp.acItems


def testEscapeClosesList():
    sp = atEndOfDialogue("JOHN")
    sp.cmd("splitElement")
    assert sp.acItems

    sp.cmd("abort")
    assert not sp.acItems


def testNoListMovingOntoEmptyCharacter():
    sp = makeScript(chars("JOHN"))
    sp.line = 0
    sp.cmd("moveDown", count=2)
    assert sp.line == len(sp.lines) - 1
    assert not sp.acItems


def testNoTypedRowWithoutMatches():
    sp = makeScript(chars("MARY"))
    sp.cmdChars("z")
    assert not sp.acItems


def testEmptyElementsNotOffered():
    sp = makeScript(chars("", "MARY"))
    sp.cmdChars("m")
    sp.cmd("deleteBackward")
    assert sp.acItems == ["MARY"]


def testWrappedElementNotOffered():
    # a scene heading wrapped onto two lines: neither line is a complete
    # heading, so neither is offered
    ls = [
        Line(scr.LB_SPACE, scr.SCENE, "INT. A VERY LONG LOCATION NAME"),
        Line(scr.LB_LAST, scr.SCENE, "NIGHT"),
        Line(scr.LB_LAST, scr.SCENE, "INT. KITCHEN - DAY"),
    ]
    sp = makeScript(ls, scr.SCENE)

    sp.cmdChars("n")
    assert not sp.acItems

    sp.cmd("deleteBackward")
    sp.cmdChars("int. ")
    assert sp.acItems == ["INT. KITCHEN - "]


def testNoCompletionOnWrappedLine():
    sp = makeScript(chars("JOHN"))
    sp.lines[-1:] = [
        Line(scr.LB_SPACE, scr.CHARACTER, "SOMEONE WITH A VERY"),
        Line(scr.LB_LAST, scr.CHARACTER, ""),
    ]
    sp.line = len(sp.lines) - 1
    sp.column = 0

    sp.cmdChars("j")
    assert not sp.acItems


def scenes(*names):
    return [Line(scr.LB_LAST, scr.SCENE, s) for s in names]


def testScenePrefixes():
    sp = makeScript(scenes("EXT. PARK - DAY", "EXT. PARK - NIGHT"), scr.SCENE)
    sp.cmdChars("e")
    assert sp.acItems == ["E", "EXT. ", "EST. "]

    sp.cmd("deleteBackward")
    sp.cmdChars("i")
    assert sp.acItems == ["I", "INT. ", "INT./EXT. ", "I/E. "]


def testSceneInParts():
    sp = makeScript(
        scenes("INT. KITCHEN - NIGHT", "EXT. KEEP - DAY", "INT. HALL - DAY"),
        scr.SCENE,
    )

    # prefix: Enter fills it in and keeps going
    sp.cmdChars("in")
    assert sp.acItems[sp.acSel] == "INT. "
    sp.cmd("splitElement")
    assert sp.lines[sp.line].text == "INT. "
    assert sp.lines[sp.line].lt == scr.SCENE

    # locations, from any prefix, most recent first
    assert sp.acItems == ["INT. HALL - ", "INT. KEEP - ", "INT. KITCHEN - "]
    sp.cmdChars("k")
    assert sp.acItems == ["INT. K", "INT. KEEP - ", "INT. KITCHEN - "]
    sp.cmd("moveDown")
    sp.cmd("tab")
    assert sp.lines[sp.line].text == "INT. KITCHEN - "

    # times: used ones first, then the defaults
    assert sp.acItems[:4] == [
        "INT. KITCHEN - DAY",
        "INT. KITCHEN - NIGHT",
        "INT. KITCHEN - CONTINUOUS",
        "INT. KITCHEN - LATER",
    ]
    sp.cmdChars("n")
    assert sp.acItems == ["INT. KITCHEN - N", "INT. KITCHEN - NIGHT"]

    # a whole heading ends the element as usual
    sp.cmd("splitElement")
    assert sp.lines[sp.line - 1].text == "INT. KITCHEN - NIGHT"
    assert sp.lines[sp.line].lt == scr.ACTION

    # and the steps undo one at a time
    sp.cmd("undo")
    assert sp.lines[sp.line].text.upper() == "INT. KITCHEN - N"
    sp.cmd("undo", count=2)
    assert sp.lines[sp.line].text.upper() == "INT. K"


def testSceneEndAcceptsPart():
    sp = makeScript(scenes("INT. KITCHEN - NIGHT"), scr.SCENE)
    sp.cmdChars("int. k")
    sp.cmd("moveLineEnd")
    assert sp.lines[sp.line].text == "INT. KITCHEN - "
    assert sp.acItems[0] == "INT. KITCHEN - NIGHT"


def testNewLocationHasNoList():
    sp = makeScript(scenes("INT. KITCHEN - NIGHT"), scr.SCENE)
    sp.cmdChars("int. z")
    assert not sp.acItems


def testOtherHeadingsCompleteWhole():
    sp = makeScript(scenes("INSERT - LETTER", "INT. HALL - DAY"), scr.SCENE)
    sp.cmdChars("in")
    assert sp.acItems == ["IN", "INT. ", "INT./EXT. ", "INSERT - LETTER"]

    sp.cmdChars("s")
    assert sp.acItems == ["INS", "INSERT - LETTER"]
    sp.cmd("splitElement")
    assert sp.lines[sp.line - 1].text == "INSERT - LETTER"


def testCharacterExtensions():
    sp = makeScript(chars("JOHN", "MARY (O.S.)"))
    sp.cmdChars("john (")
    assert sp.acItems == [
        "JOHN (",
        "JOHN (O.S.)",
        "JOHN (V.O.)",
        "JOHN (O.C.)",
        "JOHN (CONT'D)",
    ]

    sp.cmdChars("v")
    assert sp.acItems == ["JOHN (V", "JOHN (V.O.)"]
    sp.cmd("splitElement")
    assert sp.lines[sp.line - 1].text == "JOHN (V.O.)"
    assert sp.lines[sp.line].lt == scr.DIALOGUE
