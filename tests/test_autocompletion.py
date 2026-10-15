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


def testScenesMostRecentFirst():
    ls = [
        Line(scr.LB_LAST, scr.SCENE, "INT. A - DAY"),
        Line(scr.LB_LAST, scr.SCENE, "INT. B - DAY"),
        Line(scr.LB_LAST, scr.SCENE, "INT. A - DAY"),
        Line(scr.LB_LAST, scr.SCENE, "INT. C - DAY"),
    ]
    sp = makeScript(ls[:3], scr.SCENE)
    sp.lines.append(ls[3])
    sp.cmdChars("i")
    assert sp.acItems == ["I", "INT. A - DAY", "INT. B - DAY", "INT. C - DAY"]


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
    sp.cmdChars("i")
    assert sp.acItems == ["I", "INT. KITCHEN - DAY"]


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
