import tests.u as u
import trelby.screenplay as scr
from trelby.line import Line

# tests delete commands


# we had a bug where pasting on an empty line right after a forced
# linebreak would think "oh, I'm in an empty element, I'll just change the
# linetype of this line and be done with it", which is wrong, because the
# linetypes of the lines above were not changed, and now you had an
# element with multiple different linetypes. the right thing to do is not
# change the linetypes at all unless the entire element is empty.
def testPasteAfterForcedLineBreak():
    sp = u.new()

    sp.cmd("addChar", char="E")
    assert sp.lines[0].lt != scr.CHARACTER

    sp.cmd("insertForcedLineBreak")
    sp.paste([Line(text="Tsashkataar", lt=scr.CHARACTER)])

    assert len(sp.lines) == 2
    assert (sp.line == 1) and (sp.column == 11)
    assert sp.lines[0].text == "E"
    assert sp.lines[0].lt == scr.SCENE
    assert sp.lines[0].lb == scr.LB_FORCED
    assert sp.lines[1].text == "Tsashkataar"
    assert sp.lines[1].lt == scr.SCENE
    assert sp.lines[1].lb == scr.LB_LAST

    sp._validate()


# pasting lines whose first one ends in a forced linebreak in the middle
# of a line used to leave the second pasted line in the element pasted
# into, but with its own line type.
def testPasteForcedLineBreakInMiddle():
    sp = u.new()
    sp.lines = [Line(scr.LB_LAST, scr.CHARACTER, "BOBBY")]
    sp.line = 0
    sp.column = 2

    sp.paste(
        [
            Line(scr.LB_FORCED, scr.ACTION, "Xy", fmt="11"),
            Line(scr.LB_LAST, scr.ACTION, "Zw", fmt="02"),
        ]
    )

    sp._validate()

    assert [ln.text for ln in sp.lines] == ["BOXy", "Zw", "BBY"]
    assert [ln.lb for ln in sp.lines] == [scr.LB_FORCED, scr.LB_LAST, scr.LB_LAST]
    assert [ln.lt for ln in sp.lines] == [scr.CHARACTER] * 3
    assert [ln.fmt for ln in sp.lines] == ["0011", "02", None]
    assert (sp.line == 1) and (sp.column == 2)


# pasting several elements at the end of a line ending in a forced
# linebreak used to keep that linebreak, joining the first line's element
# to the pasted lines after it.
def testPasteAtEndOfLineWithForcedLineBreak():
    sp = u.new()
    sp.lines = [
        Line(scr.LB_FORCED, scr.CHARACTER, "BOB"),
        Line(scr.LB_LAST, scr.CHARACTER, "BY"),
    ]
    sp.line = 0
    sp.column = 3

    sp.paste(
        [
            Line(scr.LB_LAST, scr.CHARACTER, "AB"),
            Line(scr.LB_LAST, scr.ACTION, "Cd", fmt="10"),
        ]
    )

    sp._validate()

    assert [ln.text for ln in sp.lines] == ["BOBAB", "Cd", "BY"]
    assert [ln.lb for ln in sp.lines] == [scr.LB_LAST] * 3
    assert [ln.lt for ln in sp.lines] == [scr.CHARACTER, scr.ACTION, scr.CHARACTER]
    assert sp.lines[1].fmt == "10"
    assert (sp.line == 1) and (sp.column == 2)


# pasted lines ending in a forced linebreak, at the end of an element,
# must not join the element after it
def testPasteForcedLineBreakAtEndOfElement():
    sp = u.new()
    sp.lines = [
        Line(scr.LB_LAST, scr.CHARACTER, "BOB"),
        Line(scr.LB_LAST, scr.DIALOGUE, "Hi."),
    ]
    sp.line = 0
    sp.column = 3

    sp.paste(
        [
            Line(scr.LB_LAST, scr.CHARACTER, "BY"),
            Line(scr.LB_FORCED, scr.ACTION, "Cd"),
        ]
    )

    sp._validate()

    assert [ln.text for ln in sp.lines] == ["BOBBY", "Cd", "Hi."]
    assert [ln.lt for ln in sp.lines] == [scr.CHARACTER, scr.ACTION, scr.DIALOGUE]


# copying and pasting multi-line selections around a script must always
# leave every element's lines with the same line type
def testCopyPasteKeepsLineTypes():
    for doDelete in (False, True):
        sp = u.load()

        for i in range(0, len(sp.lines) - 3, 7):
            sp.line = i
            sp.column = len(sp.lines[i].text) // 2
            sp.cmd("setMark")
            sp.cmd("moveDown", count=1 + i % 2)
            cd = sp.getSelectedAsCD(doDelete)
            sp._validate()

            sp.line = (i * 5) % len(sp.lines)
            sp.column = (i * 3) % (len(sp.lines[sp.line].text) + 1)
            sp.paste(cd.lines)
            sp._validate()


# FIXME: lot more tests
