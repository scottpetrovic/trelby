import tests.u as u
import trelby.screenplay as scr

# tests adding characters, i.e. normal typing


def testSpaceAtEOL():
    ed = u.loadEditor()
    ed.cmd("moveDown", count=3)
    ed.cmd("moveLineEnd")
    ed.cmd("addChar", char="z")
    ed.cmd("addChar", char=" ")
    assert ed.sp.lines[3].text.endswith("z ")
    ed.cmd("addChar", char="x")
    assert (ed.line == 4) and (ed.column == 1)
    assert ed.sp.lines[3].lb == scr.LB_SPACE
    assert ed.sp.lines[4].lb == scr.LB_LAST
    assert ed.sp.lines[3].text.endswith("wouldz")
    assert ed.sp.lines[4].text.startswith("x be")


def testNbspAtEOL():
    ed = u.loadEditor()
    ed.cmd("moveDown", count=3)
    ed.cmd("moveLineEnd")
    ed.cmd("addChar", char=chr(160))
    ed.cmd("addChar", char="a")
    assert ed.sp.lines[3].text.endswith("mind")
    assert ed.sp.lines[4].text.startswith("would%sa" % chr(160))
    assert (ed.line == 4) and (ed.column == 7)
    assert ed.sp.lines[3].lb == scr.LB_SPACE
    assert ed.sp.lines[4].lb == scr.LB_LAST


# FIXME: lot more tests
