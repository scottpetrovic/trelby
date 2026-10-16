import tests.u as u
import trelby.screenplay as screenplay
import trelby.translations as translations

translations.trelby_translations_load()

# regression tests: moveNextWord used to raise IndexError when the cursor
# was after the last character of a line (column == len(text))


def testMoveNextWordFromLineEnd():
    ed = u.loadEditor()
    ed.cmd("moveLineEnd")
    assert (ed.line == 0) and (ed.column == len(ed.sp.lines[0].text))
    ed.cmd("moveNextWord")
    assert (ed.line == 1) and (ed.column == 0)


def testMoveNextWordFromScriptEnd():
    ed = u.loadEditor()
    ed.cmd("moveEnd")
    line, column = ed.line, ed.column
    assert column == len(ed.sp.lines[line].text)
    ed.cmd("moveNextWord")
    assert (ed.line == line) and (ed.column == column)


def testMoveNextWordOnEmptyLastLine():
    ed = u.loadEditor()
    ed.cmd("moveEnd")
    ed.sp.lines[-1].text = ""
    ed.column = 0
    ed.cmd("moveNextWord")
    assert ed.line == len(ed.sp.lines) - 1


# run a movement command the way Shift+key does
def _shiftCmd(ed, name):
    cs = screenplay.CommandState()
    cs.mark = True
    getattr(ed, name + "Cmd")(cs)
    ed.cmdPost(cs)


# Shift+Ctrl+Right / Left used to move without starting a selection
def testShiftMoveNextWordSelects():
    ed = u.loadEditor()
    assert ed.mark is None
    _shiftCmd(ed, "moveNextWord")
    assert ed.mark == screenplay.Mark(0, 0)
    assert (ed.line, ed.column) != (0, 0)

    # extending the selection keeps the mark where it was
    _shiftCmd(ed, "moveNextWord")
    assert ed.mark == screenplay.Mark(0, 0)


def testShiftMovePrevWordSelects():
    ed = u.loadEditor()
    ed.gotoPos(1, 0)
    ed.cmd("moveLineEnd")
    end = len(ed.sp.lines[1].text)
    _shiftCmd(ed, "movePrevWord")
    assert ed.mark == screenplay.Mark(1, end)
    assert (ed.line == 1) and (ed.column < end)


def testMoveWordWithoutShiftDoesntSelect():
    ed = u.loadEditor()
    ed.cmd("moveNextWord")
    ed.cmd("movePrevWord")
    assert ed.mark is None
