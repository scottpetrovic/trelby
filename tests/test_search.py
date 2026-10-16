import tests.u as u
import trelby.screenplay as scr
import trelby.screenplay.search as search
import trelby.textfmt as textfmt
import trelby.translations as translations
from trelby.line import Line
from trelby.screenplay.search import FindOptions, Match

_ = translations.trelby_translations_load()

# screenplay/search.py on its own. tests/test_finddlg.py drives it
# through the Find dialog.


def makeEd(*paras):
    sp = u.new()
    sp.lines = [Line(scr.LB_LAST, lt, text) for lt, text in paras]
    sp.reformatAll()
    sp.paginate()

    return scr.Editor(sp)


def texts(ed):
    return [ln.text for ln in ed.sp.lines]


def find(sp, line, col, text, **kw):
    return search.findNext(sp, line, col, FindOptions(text=text, **kw))


def testFindNext():
    sp = makeEd((scr.ACTION, "a cat, a CAT"), (scr.DIALOGUE, "cat")).sp

    assert find(sp, 0, 0, "cat") == Match(0, 2, 3)
    assert find(sp, 0, 2, "cat") == Match(0, 2, 3)
    assert find(sp, 0, 3, "cat") == Match(0, 9, 3)
    assert find(sp, 0, 10, "cat") == Match(1, 0, 3)
    assert find(sp, 1, 1, "cat") is None

    # columns past the end of the line are fine
    assert find(sp, 0, 99, "cat") == Match(1, 0, 3)


def testFindNextUp():
    sp = makeEd((scr.ACTION, "a cat, a CAT"), (scr.DIALOGUE, "cat")).sp

    assert find(sp, 1, 3, "cat", up=True) == Match(1, 0, 3)
    assert find(sp, 1, 2, "cat", up=True) == Match(0, 9, 3)
    assert find(sp, 0, 11, "cat", up=True) == Match(0, 2, 3)
    assert find(sp, 0, 4, "cat", up=True) is None
    assert find(sp, *search.startPos(sp, True), "cat", up=True) == Match(1, 0, 3)


def testFindNextOptions():
    sp = makeEd((scr.ACTION, "a cat, a CAT"), (scr.DIALOGUE, "cat")).sp

    assert find(sp, 0, 3, "cat", matchCase=True) == Match(1, 0, 3)
    assert find(sp, 0, 0, "CAT", matchCase=True) == Match(0, 9, 3)
    assert find(sp, 0, 0, "cat", elementTypes=frozenset([scr.DIALOGUE])) == Match(
        1, 0, 3
    )
    assert find(sp, 0, 0, "cat", elementTypes=frozenset()) is None
    assert find(sp, 0, 0, "") is None


def testFindNextWholeWord():
    sp = makeEd((scr.ACTION, "concat cat's cat")).sp

    assert find(sp, 0, 0, "cat", wholeWord=True) == Match(0, 13, 3)
    assert find(sp, 0, 16, "cat", wholeWord=True, up=True) == Match(0, 13, 3)
    assert find(sp, 0, 15, "cat", wholeWord=True, up=True) is None

    # the ends of the line count as word boundaries
    assert find(sp, 0, 0, "concat", wholeWord=True) == Match(0, 0, 6)


def testFindNextOverlapping():
    sp = makeEd((scr.ACTION, "aaaa")).sp

    assert find(sp, 0, 1, "aa") == Match(0, 1, 2)
    assert find(sp, 0, 3, "aa", up=True) == Match(0, 1, 2)


def testStartPos():
    sp = makeEd((scr.ACTION, "one"), (scr.ACTION, "three")).sp

    assert search.startPos(sp, False) == (0, 0)
    assert search.startPos(sp, True) == (1, 5)


def testReplaceRange():
    ed = makeEd((scr.ACTION, "The cat sat."))
    ed.gotoPos(0, 4)
    ed.setMark(0, 6)

    ed.replaceRange(0, 4, 3, "dog")

    assert texts(ed) == ["The dog sat."]
    assert (ed.line, ed.column) == (0, 7)
    assert ed.mark is None
    assert ed.sp.isModified()

    ed.cmd("undo")
    assert texts(ed) == ["The cat sat."]
    assert (ed.line, ed.column) == (0, 4)

    ed.cmd("redo")
    assert texts(ed) == ["The dog sat."]
    assert (ed.line, ed.column) == (0, 7)


def testReplaceRangeCursorAtStart():
    ed = makeEd((scr.ACTION, "The cat sat."))
    ed.replaceRange(0, 4, 3, "tiger", cursorAtStart=True)

    assert texts(ed) == ["The tiger sat."]
    assert (ed.line, ed.column) == (0, 4)


def testReplaceRangeCleansText():
    ed = makeEd((scr.ACTION, "a b"))
    ed.replaceRange(0, 1, 1, "\tx\f")

    assert texts(ed) == ["a|xb"]


def testReplaceRangeKeepsStyle():
    ed = makeEd((scr.ACTION, "The cat sat."))
    ln = ed.sp.lines[0]
    ln.setText(ln.text, textfmt.char(textfmt.BOLD) * len(ln.text))

    ed.replaceRange(0, 4, 3, "dog")

    assert ed.sp.lines[0].getFmt() == textfmt.char(textfmt.BOLD) * len("The dog sat.")


def testReplaceRangeRewraps():
    w = makeEd((scr.ACTION, "")).sp.cfg.getType(scr.ACTION).width
    ed = makeEd((scr.ACTION, "x" * (w - 5) + " cat " + "y" * 10))

    ed.replaceRange(0, w - 4, 3, "big dog")

    assert texts(ed) == ["x" * (w - 5) + " big", "dog " + "y" * 10]
    assert (ed.line, ed.column) == (1, 3)

    # the space before the deleted word stays at the end of the first line
    ed.replaceRange(1, 0, 3, "", cursorAtStart=True)
    assert texts(ed) == ["x" * (w - 5) + " big ", "y" * 10]
    assert (ed.line, ed.column) == (0, w)
    ed._validate()

    # shrinking it moves the rest back up
    ed = makeEd((scr.ACTION, "x" * (w - 5) + " cat " + "y" * 10))
    ed.replaceRange(0, 0, w - 5, "x")
    assert texts(ed) == ["x cat " + "y" * 10]
    assert (ed.line, ed.column) == (0, 1)


def testReplaceAt():
    ed = makeEd((scr.ACTION, "The cat sat."))

    ed.replaceAt(Match(0, 4, 3), "tiger")
    assert (ed.line, ed.column) == (0, 9)

    ed.replaceAt(Match(0, 4, 5), "cat", up=True)
    assert (ed.line, ed.column) == (0, 4)
    assert texts(ed) == ["The cat sat."]


def testReplaceAll():
    ed = makeEd((scr.ACTION, "cat cat"), (scr.DIALOGUE, "Cat, concat"))
    ed.gotoPos(1, 5)

    assert ed.replaceAll(FindOptions(text="cat", up=True), "dog") == 4
    assert texts(ed) == ["dog dog", "dog, condog"]
    assert (ed.line, ed.column) == (1, 11)

    ed.cmd("undo")
    assert texts(ed) == ["cat cat", "Cat, concat"]
    assert (ed.line, ed.column) == (1, 5)


def testReplaceAllNoMatches():
    ed = makeEd((scr.ACTION, "cat"))

    assert ed.replaceAll(FindOptions(text="dog"), "cat") == 0
    assert ed.replaceAll(FindOptions(text=""), "cat") == 0
    assert ed.undoHistory.isEmpty()
    assert not ed.sp.isModified()


def testReplaceAllReplacementContainsMatch():
    ed = makeEd((scr.ACTION, "aa"))

    assert ed.replaceAll(FindOptions(text="a"), "aa") == 2
    assert texts(ed) == ["aaaa"]


def testReplaceAllAcrossWrappedLines():
    ed = makeEd((scr.ACTION, "cat " * 40))
    assert len(ed.sp.lines) == 3

    assert ed.replaceAll(FindOptions(text="cat"), "x") == 40
    assert " ".join(texts(ed)) == "x " * 40
    assert len(ed.sp.lines) == 2
    ed._validate()
