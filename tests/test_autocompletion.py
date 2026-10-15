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


def testNearestAboveFirst():
    sp = makeScript(chars("JANE", "JOHN"))
    sp.cmdChars("j")
    assert sp.acItems == ["J", "JOHN", "JANE"]


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
