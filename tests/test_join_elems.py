import tests.u as u
import trelby.screenplay as scr

# tests element joining


# we used to have a bug where if the latter element contained a forced
# linebreak the result was invalid. this one tests the case where the
# forced linebreak is on the first line of the element, the second one
# where it is on the third line.
def testForcedLb():
    ed = u.newEditor()

    ed.cmd("addChar", char="a")
    ed.cmd("splitElement")
    ed.cmd("toDialogue")
    ed.cmd("addChar", char="b")
    ed.cmd("insertForcedLineBreak")
    ed.cmd("addChar", char="c")
    ed.cmd("moveLeft")
    ed.cmd("moveUp")
    ed.cmd("deleteBackward")

    assert len(ed.sp.lines) == 2
    assert (ed.line == 0) and (ed.column == 1)
    assert ed.sp.lines[0].text == "AB"
    assert ed.sp.lines[0].lt == scr.SCENE
    assert ed.sp.lines[0].lb == scr.LB_FORCED
    assert ed.sp.lines[1].text == "c"
    assert ed.sp.lines[1].lt == scr.SCENE
    assert ed.sp.lines[1].lb == scr.LB_LAST


def testForcedLb2():
    ed = u.newEditor()

    ed.cmd("addChar", char="a")
    ed.cmd("splitElement")
    ed.cmd("toTransition")
    ed.cmdChars("line 1///////////// ")
    ed.cmdChars("line 2///////////// ")
    ed.cmdChars("line 3")
    ed.cmd("insertForcedLineBreak")
    ed.cmdChars("line 4")
    ed.gotoPos(1, 0)
    ed.cmd("deleteBackward")

    assert len(ed.sp.lines) == 2
    assert (ed.line == 0) and (ed.column == 1)
    assert ed.sp.lines[0].text == "ALine 1///////////// line 2///////////// line 3"
    assert ed.sp.lines[0].lt == scr.SCENE
    assert ed.sp.lines[0].lb == scr.LB_FORCED
    assert ed.sp.lines[1].text == "line 4"
    assert ed.sp.lines[1].lt == scr.SCENE
    assert ed.sp.lines[1].lb == scr.LB_LAST
