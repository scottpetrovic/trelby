import tests.u as u

# tests movement commands


def testMoveRight():
    ed = u.loadEditor()
    ed.cmd("moveRight")
    assert ed.column == 1
    ed.cmd("moveLineEnd")
    ed.cmd("moveRight")
    assert (ed.line == 1) and (ed.column == 0)
    ed.cmd("moveEnd")
    ed.cmd("moveRight")
    assert (ed.line == 161) and (ed.column == 4)


def testMoveLeft():
    ed = u.loadEditor()
    ed.cmd("moveLeft")
    assert (ed.line == 0) and (ed.column == 0)
    ed.cmd("moveDown")
    ed.cmd("moveLeft")
    assert (ed.line == 0) and (ed.column == 23)
    ed.cmd("moveLineStart")
    assert ed.column == 0


def testMoveUp():
    ed = u.loadEditor()
    ed.cmd("moveUp")
    assert (ed.line == 0) and (ed.column == 0)
    ed.cmd("moveDown")
    ed.cmd("moveLineEnd")
    ed.cmd("moveUp")
    assert (ed.line == 0) and (ed.column == 23)


def testMoveDown():
    ed = u.loadEditor()
    ed.cmd("moveDown")
    assert ed.line == 1
    ed.cmd("moveDown")
    ed.cmd("moveDown")
    ed.cmd("moveLineEnd")
    ed.cmd("moveDown")
    assert (ed.line == 4) and (ed.column == 31)
    ed.cmd("moveEnd")
    ed.cmd("moveDown")
    assert ed.line == 161


def testMoveLineEnd():
    ed = u.loadEditor()
    ed.cmd("moveLineEnd")
    assert ed.column == 23


def testMoveLineStart():
    ed = u.loadEditor()
    ed.cmd("moveRight")
    ed.cmd("moveLineStart")
    assert ed.column == 0


def testMoveEnd():
    ed = u.loadEditor()
    ed.cmd("moveEnd")
    assert (ed.line == 161) and (ed.column == 4)


def testMoveStart():
    ed = u.loadEditor()
    ed.cmd("moveEnd")
    ed.cmd("moveStart")
    assert (ed.line == 0) and (ed.column == 0)


def testMoveSceneUp():
    ed = u.loadEditor()
    ed.cmd("moveSceneUp")
    assert (ed.line == 0) and (ed.column == 0)
    ed.gotoPos(18, 1)
    ed.cmd("moveSceneUp")
    assert (ed.line == 14) and (ed.column == 0)
    ed.cmd("moveSceneUp")
    assert (ed.line == 0) and (ed.column == 0)

    # make sure we don't go before the start trying to find scenes
    ed.cmd("toAction")
    ed.cmd("moveSceneUp")
    assert (ed.line == 0) and (ed.column == 0)


def testMoveSceneDown():
    ed = u.loadEditor()
    ed.cmd("moveSceneDown")
    assert (ed.line == 14) and (ed.column == 0)
    ed.cmd("moveDown")
    ed.cmd("moveSceneDown")
    assert (ed.line == 30) and (ed.column == 0)
    ed.cmd("moveEnd")
    ed.cmd("moveSceneDown")
    assert (ed.line == 161) and (ed.column == 0)


def testMoveNextWord():
    ed = u.loadEditor()
    ed.line = 157
    ed.column = 0
    ed.cmd("moveNextWord")
    assert (ed.line == 157) and (ed.column == 4)
    ed.cmd("moveNextWord")
    assert (ed.line == 158) and (ed.column == 0)
    ed.cmd("moveNextWord")
    assert (ed.line == 158) and (ed.column == 4)
    ed.cmd("moveNextWord")
    assert (ed.line == 159) and (ed.column == 0)
    ed.cmd("moveNextWord")
    assert (ed.line == 160) and (ed.column == 0)
    ed.cmd("moveNextWord")
    assert (ed.line == 161) and (ed.column == 0)
    ed.cmd("moveNextWord")
    assert (ed.line == 161) and (ed.column == 3)


def testMovePrevWord():
    ed = u.loadEditor()
    ed.line = 161
    ed.column = 3
    ed.cmd("movePrevWord")
    assert (ed.line == 161) and (ed.column == 0)
    ed.cmd("movePrevWord")
    assert (ed.line == 158) and (ed.column == 0)
    ed.cmd("movePrevWord")
    assert (ed.line == 157) and (ed.column == 0)
