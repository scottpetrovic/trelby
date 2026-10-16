import tests.u as u
import trelby.screenplay as scr

# tests delete commands


def testBackStart():
    ed = u.loadEditor()
    ed.cmd("deleteBackward")
    assert (ed.line == 0) and (ed.column == 0)
    assert ed.sp.lines[0].text == "ext. stonehenge - night"


def testBack():
    ed = u.loadEditor()
    ed.cmd("moveRight")
    ed.cmd("deleteBackward")
    assert (ed.line == 0) and (ed.column == 0)
    assert ed.sp.lines[0].text == "xt. stonehenge - night"


def testBackJoinElements():
    ed = u.loadEditor()
    ed.cmd("moveDown")
    ed.cmd("deleteBackward")
    assert (ed.line == 0) and (ed.column == 23)
    assert (
        ed.sp.lines[0].text == "ext. stonehenge - nightA blizzard rages."
        " Snow is everywhere"
    )


def testBackLbSpace():
    ed = u.loadEditor()
    ed.gotoPos(16, 60)
    ed.cmd("addChar", char=" ")
    assert ed.sp.lines[16].lb == scr.LB_SPACE
    ed.cmd("moveDown")
    ed.cmd("moveLineStart")
    ed.cmd("deleteBackward")
    assert (ed.line == 17) and (ed.column == 0)
    assert ed.sp.lines[16].lb == scr.LB_SPACE
    assert (
        ed.sp.lines[16].text == "A calm night, with the ocean almost still."
        " Two fishermen are"
    )
    assert ed.sp.lines[17].text == "smoking at the rear deck."


def testBackLbNone():
    ed = u.loadEditor()

    ed.gotoPos(20, 0)
    assert ed.sp.lines[19].lb == scr.LB_NONE
    ed.cmd("deleteBackward")
    assert (ed.line == 19) and (ed.column == 34)
    assert ed.sp.lines[19].text == "Aye,it'snightslikethisthatmakemeree"
    assert ed.sp.lines[20].text == "mber why I love being a fisherman."
    assert ed.sp.lines[19].lb == scr.LB_NONE
    ed.cmd("moveRight", count=3)
    ed.cmd("addChar", char=" ")
    ed.cmd("moveLeft", count=2)
    ed.cmd("deleteBackward")
    assert (ed.line == 19) and (ed.column == 34)
    assert ed.sp.lines[19].text == "Aye,it'snightslikethisthatmakemerem"
    assert ed.sp.lines[20].text == "ber why I love being a fisherman."
    assert ed.sp.lines[19].lb == scr.LB_SPACE


def testBackLbForced():
    ed = u.loadEditor()

    ed.gotoPos(34, 0)
    assert ed.sp.lines[33].lb == scr.LB_FORCED
    ed.cmd("deleteBackward")
    assert (ed.line == 33) and (ed.column == 6)
    assert ed.sp.lines[33].text == "brightyellow package at their feet."
    assert ed.sp.lines[33].lb == scr.LB_LAST


# test that when joining two elements of different type, the latter of
# which contains forced linebreaks, that the whole of the latter element
# is rewrapped correctly.
def testBackLbForcedTypeConvert():
    ed = u.loadEditor()

    ed.cmd("toTransition")
    ed.cmd("moveDown", count=3)
    ed.cmd("insertForcedLineBreak")
    ed.cmd("moveUp")
    ed.cmd("deleteBackward")

    ed._validate()


# FIXME: more tests for forward deletion


# test that when joining two elements of different type, the latter of
# which contains forced linebreaks, that the whole of the latter element
# is rewrapped correctly.
def testForwardLbForcedTypeConvert():
    ed = u.loadEditor()

    ed.cmd("toTransition")
    ed.cmd("moveDown", count=3)
    ed.cmd("insertForcedLineBreak")
    ed.cmd("moveUp", count=2)
    ed.cmd("moveLineEnd")
    ed.cmd("deleteForward")

    ed._validate()
