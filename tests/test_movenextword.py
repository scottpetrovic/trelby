import tests.u as u
import trelby.screenplay as screenplay
import trelby.translations as translations

translations.trelby_translations_load()

# regression tests: moveNextWord used to raise IndexError when the cursor
# was after the last character of a line (column == len(text))


def testMoveNextWordFromLineEnd():
    sp = u.load()
    sp.cmd("moveLineEnd")
    assert (sp.line == 0) and (sp.column == len(sp.lines[0].text))
    sp.cmd("moveNextWord")
    assert (sp.line == 1) and (sp.column == 0)


def testMoveNextWordFromScriptEnd():
    sp = u.load()
    sp.cmd("moveEnd")
    line, column = sp.line, sp.column
    assert column == len(sp.lines[line].text)
    sp.cmd("moveNextWord")
    assert (sp.line == line) and (sp.column == column)


def testMoveNextWordOnEmptyLastLine():
    sp = u.load()
    sp.cmd("moveEnd")
    sp.lines[-1].text = ""
    sp.column = 0
    sp.cmd("moveNextWord")
    assert sp.line == len(sp.lines) - 1


# run a movement command the way Shift+key does
def _shiftCmd(sp, name):
    cs = screenplay.CommandState()
    cs.mark = True
    getattr(sp, name + "Cmd")(cs)
    sp.cmdPost(cs)


# Shift+Ctrl+Right / Left used to move without starting a selection
def testShiftMoveNextWordSelects():
    sp = u.load()
    assert sp.mark is None
    _shiftCmd(sp, "moveNextWord")
    assert sp.mark == screenplay.Mark(0, 0)
    assert (sp.line, sp.column) != (0, 0)

    # extending the selection keeps the mark where it was
    _shiftCmd(sp, "moveNextWord")
    assert sp.mark == screenplay.Mark(0, 0)


def testShiftMovePrevWordSelects():
    sp = u.load()
    sp.gotoPos(1, 0)
    sp.cmd("moveLineEnd")
    end = len(sp.lines[1].text)
    _shiftCmd(sp, "movePrevWord")
    assert sp.mark == screenplay.Mark(1, end)
    assert (sp.line == 1) and (sp.column < end)


def testMoveWordWithoutShiftDoesntSelect():
    sp = u.load()
    sp.cmd("moveNextWord")
    sp.cmd("movePrevWord")
    assert sp.mark is None
