import tests.u as u
from trelby.textedit import TextEdit

u.init()


def testInit():
    ed = TextEdit(["foo", "barx"])
    assert ed.caret == (1, 4)
    assert not ed.hasSelection()

    assert TextEdit([]).lines == [""]


def testInsert():
    ed = TextEdit(["ab"])
    ed.setCaret((0, 1))
    ed.insert("X")
    assert ed.lines == ["aXb"]
    assert ed.caret == (0, 2)

    ed.insert("1\n2\r\n3")
    assert ed.lines == ["aX1", "2", "3b"]
    assert ed.caret == (2, 1)

    # tabs become |, invalid characters are dropped
    ed = TextEdit([""])
    ed.insert("a\tb\x01\x85c")
    assert ed.lines == ["a|bc"]


def testInsertReplacesSelection():
    ed = TextEdit(["hello", "world"])
    ed.setCaret((0, 2))
    ed.setCaret((1, 3), True)
    assert ed.getSelectedText() == "llo\nwor"

    ed.insert("Z")
    assert ed.lines == ["heZld"]
    assert ed.caret == (0, 3)
    assert not ed.hasSelection()


def testBackspaceDelete():
    ed = TextEdit(["ab", "cd"])
    ed.setCaret((1, 0))
    ed.backspace()
    assert ed.lines == ["abcd"]
    assert ed.caret == (0, 2)

    ed.delete()
    assert ed.lines == ["abd"]

    ed.setCaret((0, 3))
    ed.delete()
    assert ed.lines == ["abd"]

    ed.setCaret((0, 0))
    ed.backspace()
    assert ed.lines == ["abd"]

    ed.selectAll()
    ed.backspace()
    assert ed.lines == [""]
    assert ed.caret == (0, 0)


def testMovement():
    ed = TextEdit(["ab", "cd"])
    ed.setCaret((1, 0))
    ed.moveLeft()
    assert ed.caret == (0, 2)
    ed.moveRight()
    assert ed.caret == (1, 0)

    ed.moveEnd()
    assert ed.caret == (1, 2)
    ed.moveRight()
    assert ed.caret == (1, 2)

    ed.moveHome(doc=True)
    assert ed.caret == (0, 0)
    ed.moveLeft()
    assert ed.caret == (0, 0)

    ed.moveEnd(True, doc=True)
    assert ed.getSelectedText() == "ab\ncd"

    # moving without shift collapses the selection to its edge
    ed.moveLeft()
    assert ed.caret == (0, 0)
    assert not ed.hasSelection()


def testWords():
    ed = TextEdit(["one two  three"])
    ed.moveLeft(word=True)
    assert ed.caret == (0, 9)
    ed.moveLeft(word=True)
    assert ed.caret == (0, 4)
    ed.moveRight(word=True)
    assert ed.caret == (0, 7)

    ed.selectWord((0, 5))
    assert ed.getSelectedText() == "two"


def testSetCaretClamps():
    ed = TextEdit(["ab", "c"])
    ed.setCaret((5, 9))
    assert ed.caret == (1, 1)
    ed.setCaret((-1, -1))
    assert ed.caret == (0, 0)
