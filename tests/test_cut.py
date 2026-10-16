import tests.u as u
import trelby.screenplay as scr

# tests deleting selected areas of text


def testBasic():
    ed = u.loadEditor()

    ed.cmd("setMark")
    ed.getSelectedAsCD(True)

    assert ed.sp.lines[0].lb == scr.LB_LAST
    assert ed.sp.lines[0].lt == scr.SCENE
    assert ed.sp.lines[0].text == "xt. stonehenge - night"


def testLastDelete():
    ed = u.loadEditor()

    ed.cmd("moveEnd")
    ed.cmd("setMark")
    ed.cmd("moveUp", count=4)
    ed.cmd("moveLineStart")

    # we used to have a bug where if we deleted e.g. the last two lines of
    # the script, and that element was longer, we didn't mark the
    # third-last line as LB_LAST, and then it crashed in rewrapPara.
    ed.getSelectedAsCD(True)


def testEndPrevPara():
    ed = u.loadEditor()

    ed.cmd("moveDown", count=4)
    ed.cmd("moveLineEnd")
    ed.cmd("setMark")
    ed.cmd("moveLineStart")
    ed.cmd("moveUp")

    ed.getSelectedAsCD(True)

    # test that when deleting the last lines of an element we correctly
    # flag the preceding line as the new last line.

    assert ed.sp.lines[2].lb == scr.LB_LAST
    assert ed.sp.lines[3].lt == scr.CHARACTER


# we used to have a bug where joining two elements when the latter one
# contained a forced linebreak didn't convert it properly to the preceding
# element's type.
def testForcedLb():
    ed = u.loadEditor()

    ed.cmd("moveDown", count=2)
    ed.cmd("insertForcedLineBreak")
    ed.cmd("moveUp", count=2)
    ed.cmd("moveLineEnd")
    ed.cmd("setMark")
    ed.cmd("moveRight")
    ed.getSelectedAsCD(True)
    ed._validate()


# we used to have a bug where if we deleted the first line of an element
# plus at least some of the later lines, the rest of the element was
# erroneously joined to the preceding element.
def testFirstDelete():
    ed = u.loadEditor()

    ed.cmd("moveDown")
    ed.cmd("setMark")
    ed.cmd("moveDown")
    ed.getSelectedAsCD(True)

    assert ed.sp.lines[0].lb == scr.LB_LAST
    assert ed.sp.lines[0].lt == scr.SCENE

    assert ed.sp.lines[1].lb == scr.LB_SPACE
    assert ed.sp.lines[1].lt == scr.ACTION
    assert ed.sp.lines[1].lt == scr.ACTION
    assert (
        ed.sp.lines[1].text == "lmost zero. Only at brief moments do we catch sight of the"
    )

    ed._validate()


# test that when joining two elements of different type, the latter of
# which contains forced linebreaks, that the whole of the latter element
# is rewrapped correctly.
def testTypeConvert():
    ed = u.loadEditor()

    ed.cmd("toTransition")
    ed.cmd("moveDown", count=3)
    ed.cmd("insertForcedLineBreak")
    ed.cmd("moveUp")
    ed.cmd("setMark")
    ed.cmd("moveLeft")
    ed.getSelectedAsCD(True)

    ed._validate()
