import tests.u as u
import trelby.config as config
import trelby.screenplay as scr
from trelby.screenplay.line import Line

# tests isModified updating


def testInitial():
    ed = u.loadEditor()
    assert not ed.sp.isModified()


def testAddChar():
    ed = u.loadEditor()
    ed.cmd("addChar", char="a")
    assert ed.sp.isModified()


def testDeleteBackwardsStart():
    ed = u.loadEditor()
    ed.cmd("deleteBackward")
    assert not ed.sp.isModified()


def testDeleteBackwards():
    ed = u.loadEditor()
    ed.cmd("moveRight")
    ed.cmd("deleteBackward")
    assert ed.sp.isModified()


def testDelete():
    ed = u.loadEditor()
    ed.cmd("deleteForward")
    assert ed.sp.isModified()


def testDeleteEnd():
    ed = u.loadEditor()
    ed.cmd("moveEnd")
    ed.cmd("deleteForward")
    assert not ed.sp.isModified()


# waste of time to test all move commands, test just one
def testMoveRight():
    ed = u.loadEditor()
    ed.cmd("moveRight")
    assert not ed.sp.isModified()


def testForcedLineBreak():
    ed = u.loadEditor()
    ed.cmd("insertForcedLineBreak")
    assert ed.sp.isModified()


def testSplitElement():
    ed = u.loadEditor()
    ed.cmd("splitElement")
    assert ed.sp.isModified()


def testTab():
    ed = u.loadEditor()
    ed.cmd("tab")
    assert ed.sp.isModified()


def testToPrevTypeTab():
    ed = u.loadEditor()
    ed.cmd("toPrevTypeTab")
    assert ed.sp.isModified()


def testConvert():
    ed = u.loadEditor()
    ed.cmd("toShot")
    assert ed.sp.isModified()


def testPaste():
    ed = u.loadEditor()
    ed.paste([Line(text="yo")])
    assert ed.sp.isModified()


def testRemoveElementTypes():
    ed = u.loadEditor()
    ed.removeElementTypes({scr.ACTION: 0}, False)
    assert ed.sp.isModified()


def testApplyCfg():
    ed = u.loadEditor()
    ed.applyCfg(config.Config())
    assert ed.sp.isModified()


def testCut():
    ed = u.loadEditor()
    ed.cmd("setMark")
    ed.cmd("moveRight")
    ed.getSelectedAsCD(True)
    assert ed.sp.isModified()
