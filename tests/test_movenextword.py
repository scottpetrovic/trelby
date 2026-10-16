import tests.u as u

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
