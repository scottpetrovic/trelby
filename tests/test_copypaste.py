import tests.u as u
import trelby.screenplay as scr
from trelby.screenplay.line import Line

# tests delete commands


# we had a bug where pasting on an empty line right after a forced
# linebreak would think "oh, I'm in an empty element, I'll just change the
# linetype of this line and be done with it", which is wrong, because the
# linetypes of the lines above were not changed, and now you had an
# element with multiple different linetypes. the right thing to do is not
# change the linetypes at all unless the entire element is empty.
def testPasteAfterForcedLineBreak():
    ed = u.newEditor()

    ed.cmd("addChar", char="E")
    assert ed.sp.lines[0].lt != scr.CHARACTER

    ed.cmd("insertForcedLineBreak")
    ed.paste([Line(text="Tsashkataar", lt=scr.CHARACTER)])

    assert len(ed.sp.lines) == 2
    assert (ed.line == 1) and (ed.column == 11)
    assert ed.sp.lines[0].text == "E"
    assert ed.sp.lines[0].lt == scr.SCENE
    assert ed.sp.lines[0].lb == scr.LB_FORCED
    assert ed.sp.lines[1].text == "Tsashkataar"
    assert ed.sp.lines[1].lt == scr.SCENE
    assert ed.sp.lines[1].lb == scr.LB_LAST

    ed._validate()


# pasting lines whose first one ends in a forced linebreak in the middle
# of a line used to leave the second pasted line in the element pasted
# into, but with its own line type.
def testPasteForcedLineBreakInMiddle():
    ed = u.newEditor()
    ed.sp.lines = [Line(scr.LB_LAST, scr.CHARACTER, "BOBBY")]
    ed.line = 0
    ed.column = 2

    ed.paste(
        [
            Line(scr.LB_FORCED, scr.ACTION, "Xy", fmt="11"),
            Line(scr.LB_LAST, scr.ACTION, "Zw", fmt="02"),
        ]
    )

    ed._validate()

    assert [ln.text for ln in ed.sp.lines] == ["BOXy", "Zw", "BBY"]
    assert [ln.lb for ln in ed.sp.lines] == [scr.LB_FORCED, scr.LB_LAST, scr.LB_LAST]
    assert [ln.lt for ln in ed.sp.lines] == [scr.CHARACTER] * 3
    assert [ln.fmt for ln in ed.sp.lines] == ["0011", "02", None]
    assert (ed.line == 1) and (ed.column == 2)


# pasting several elements at the end of a line ending in a forced
# linebreak used to keep that linebreak, joining the first line's element
# to the pasted lines after it.
def testPasteAtEndOfLineWithForcedLineBreak():
    ed = u.newEditor()
    ed.sp.lines = [
        Line(scr.LB_FORCED, scr.CHARACTER, "BOB"),
        Line(scr.LB_LAST, scr.CHARACTER, "BY"),
    ]
    ed.line = 0
    ed.column = 3

    ed.paste(
        [
            Line(scr.LB_LAST, scr.CHARACTER, "AB"),
            Line(scr.LB_LAST, scr.ACTION, "Cd", fmt="10"),
        ]
    )

    ed._validate()

    assert [ln.text for ln in ed.sp.lines] == ["BOBAB", "Cd", "BY"]
    assert [ln.lb for ln in ed.sp.lines] == [scr.LB_LAST] * 3
    assert [ln.lt for ln in ed.sp.lines] == [scr.CHARACTER, scr.ACTION, scr.CHARACTER]
    assert ed.sp.lines[1].fmt == "10"
    assert (ed.line == 1) and (ed.column == 2)


# pasted lines ending in a forced linebreak, at the end of an element,
# must not join the element after it
def testPasteForcedLineBreakAtEndOfElement():
    ed = u.newEditor()
    ed.sp.lines = [
        Line(scr.LB_LAST, scr.CHARACTER, "BOB"),
        Line(scr.LB_LAST, scr.DIALOGUE, "Hi."),
    ]
    ed.line = 0
    ed.column = 3

    ed.paste(
        [
            Line(scr.LB_LAST, scr.CHARACTER, "BY"),
            Line(scr.LB_FORCED, scr.ACTION, "Cd"),
        ]
    )

    ed._validate()

    assert [ln.text for ln in ed.sp.lines] == ["BOBBY", "Cd", "Hi."]
    assert [ln.lt for ln in ed.sp.lines] == [scr.CHARACTER, scr.ACTION, scr.DIALOGUE]


# copying and pasting multi-line selections around a script must always
# leave every element's lines with the same line type
def testCopyPasteKeepsLineTypes():
    for doDelete in (False, True):
        ed = u.loadEditor()

        for i in range(0, len(ed.sp.lines) - 3, 7):
            ed.line = i
            ed.column = len(ed.sp.lines[i].text) // 2
            ed.cmd("setMark")
            ed.cmd("moveDown", count=1 + i % 2)
            cd = ed.getSelectedAsCD(doDelete)
            ed._validate()

            ed.line = (i * 5) % len(ed.sp.lines)
            ed.column = (i * 3) % (len(ed.sp.lines[ed.line].text) + 1)
            ed.paste(cd.lines)
            ed._validate()


# FIXME: lot more tests
