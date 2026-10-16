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


def width():
    return u.new().cfg.getType(scr.ACTION).width


# a paragraph that wraps after "cat", at an LB_SPACE break: ["xx... cat",
# "sat on it."], the first line being width() long
def catSat():
    w = width()
    ed = makeEd((scr.ACTION, "x" * (w - 4) + " cat sat on it."))
    assert texts(ed) == ["x" * (w - 4) + " cat", "sat on it."]
    assert ed.sp.lines[0].lb == scr.LB_SPACE

    return ed


def testFindNextSpanningLines():
    sp = catSat().sp
    w = width()

    # the break stands for a space
    assert find(sp, 0, 0, "cat sat") == Match(0, w - 3, 7)
    assert find(sp, 0, 0, "CAT SAT on") == Match(0, w - 3, 10)
    assert find(sp, 0, 0, "catsat") is None

    # starting or ending on the space
    assert find(sp, 0, 0, " sat") == Match(0, w, 4)
    assert find(sp, 0, 0, "cat ") == Match(0, w - 3, 4)

    # starting past the space
    assert find(sp, 0, w, " sat") == Match(0, w, 4)
    assert find(sp, 0, w, "sat") == Match(1, 0, 3)
    assert find(sp, 1, 0, " sat") is None


def testFindNextUpSpanningLines():
    sp = catSat().sp
    w = width()

    # the match must end at or before the position, which can be on the
    # next line
    assert find(sp, 1, 3, "cat sat", up=True) == Match(0, w - 3, 7)
    assert find(sp, 1, 2, "cat sat", up=True) is None
    assert find(sp, 1, 0, "cat ", up=True) == Match(0, w - 3, 4)
    assert find(sp, 0, w, "cat ", up=True) is None
    assert find(sp, *search.startPos(sp, True), "t s", up=True) == Match(0, w - 1, 3)


def testFindNextSpanningLinesOptions():
    sp = catSat().sp
    w = width()

    assert find(sp, 0, 0, "cat sat", wholeWord=True) == Match(0, w - 3, 7)
    assert find(sp, 0, 0, "at sa", wholeWord=True) is None
    assert find(sp, 0, 0, "cat SAT", matchCase=True) is None
    assert find(sp, 0, 0, "cat sat", elementTypes=frozenset([scr.ACTION])) == Match(
        0, w - 3, 7
    )
    assert find(sp, 0, 0, "cat sat", elementTypes=frozenset([scr.DIALOGUE])) is None


def testFindNextAcrossLbNone():
    w = width()
    ed = makeEd((scr.ACTION, "y" * (w + 5)))
    assert ed.sp.lines[0].lb == scr.LB_NONE

    # a word broken without a space is still one word
    assert find(ed.sp, 0, 0, "y" * 8) == Match(0, 0, 8)
    assert find(ed.sp, 0, w - 3, "y" * 8) == Match(0, w - 3, 8)
    assert find(ed.sp, 0, 0, "y" * (w + 5), wholeWord=True) == Match(0, 0, w + 5)
    assert find(ed.sp, 0, 0, "y" * w, wholeWord=True) is None

    # a match starting at the break starts on the next line
    assert find(ed.sp, 0, w, "y") == Match(1, 0, 1)


def testFindNextNotAcrossParagraphs():
    ed = makeEd((scr.ACTION, "a cat"), (scr.ACTION, "sat"))
    assert find(ed.sp, 0, 0, "cat sat") is None
    assert find(ed.sp, 0, 0, "catsat") is None

    # a forced line break ends a paragraph, too
    sp = u.new()
    sp.lines = [
        Line(scr.LB_FORCED, scr.ACTION, "a cat"),
        Line(scr.LB_LAST, scr.ACTION, "sat"),
    ]
    assert find(sp, 0, 0, "cat sat") is None
    assert find(sp, 0, 0, "sat") == Match(1, 0, 3)


def testFindNextOverManyLines():
    ed = makeEd((scr.ACTION, "cat " * 40))
    assert len(ed.sp.lines) == 3

    m = find(ed.sp, 0, 0, ("cat " * 40).strip())
    assert m == Match(0, 0, len("cat " * 40) - 1)
    assert search.advance(ed.sp, m.line, m.col, m.length) == (2, len(texts(ed)[2]) - 1)


def testAdvance():
    sp = catSat().sp
    w = width()

    assert search.advance(sp, 0, 0, 3) == (0, 3)
    assert search.advance(sp, 0, w - 1, 1) == (0, w)

    # past the space, which stays at the end of the first line
    assert search.advance(sp, 0, w, 1) == (1, 0)
    assert search.advance(sp, 0, w - 3, 7) == (1, 3)
    assert search.advance(sp, 1, 3, -7) == (0, w - 3)

    # it stops at the end of the paragraph
    assert search.advance(sp, 1, 0, 99) == (1, 10)

    # at an LB_NONE break, the position is on the next line
    sp = makeEd((scr.ACTION, "y" * (w + 5))).sp
    assert search.advance(sp, 0, w - 1, 1) == (1, 0)


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


def testReplaceRangeSpanningLines():
    ed = catSat()
    w = width()
    before = texts(ed)
    ed.gotoPos(1, 5)

    ed.replaceRange(0, w - 3, 7, "dog")

    assert texts(ed) == ["x" * (w - 4) + " dog", "on it."]
    assert (ed.line, ed.column) == (0, w)
    assert ed.mark is None
    ed._validate()

    # one undo step
    ed.cmd("undo")
    assert texts(ed) == before
    assert (ed.line, ed.column) == (1, 5)
    ed._validate()

    ed.cmd("redo")
    assert texts(ed) == ["x" * (w - 4) + " dog", "on it."]
    ed._validate()


def testReplaceRangeSpanningLinesCursorAtStart():
    ed = catSat()
    w = width()

    ed.replaceRange(0, w - 3, 7, "dog", cursorAtStart=True)
    assert (ed.line, ed.column) == (0, w - 3)


def testReplaceRangeTheSpace():
    w = width()

    # replacing the space at the break joins the words
    ed = catSat()
    ed.replaceRange(0, w, 1, "")
    assert texts(ed) == ["x" * (w - 4), "catsat on it."]
    ed._validate()

    # and replacing a range ending on it keeps the next word separate
    ed = catSat()
    ed.replaceRange(0, w - 3, 4, "a ")
    assert texts(ed) == ["x" * (w - 4) + " a", "sat on it."]
    ed._validate()

    # or starting at it
    ed = catSat()
    ed.replaceRange(0, w, 4, "-mat")
    assert texts(ed) == ["x" * (w - 4), "cat-mat on it."]
    ed._validate()


def testReplaceRangeOverManyLines():
    ed = makeEd((scr.ACTION, "a " + "cat " * 40 + "b"))
    before = texts(ed)
    assert len(before) == 3

    ed.replaceRange(0, 2, len("cat " * 40) - 1, "dog")
    assert texts(ed) == ["a dog b"]
    assert (ed.line, ed.column) == (0, 5)
    ed._validate()

    ed.cmd("undo")
    assert texts(ed) == before
    ed._validate()


def testReplaceRangeSpanningLinesKeepsStyle():
    ed = catSat()
    w = width()
    for ln in ed.sp.lines:
        ln.setText(ln.text, textfmt.char(textfmt.BOLD) * len(ln.text))

    ed.replaceRange(0, w - 3, 7, "dog")

    for ln in ed.sp.lines:
        assert ln.getFmt() == textfmt.char(textfmt.BOLD) * len(ln.text)


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


def testReplaceAllSpanningLines():
    ed = makeEd((scr.ACTION, "a " + "word " * 20))
    before = texts(ed)
    assert len(before) == 2

    # ten pairs, one of which wraps between the lines
    assert before[0].count("word") % 2 == 1
    assert ed.replaceAll(FindOptions(text="word word"), "x") == 10
    assert texts(ed) == ["a " + "x " * 10]
    ed._validate()

    ed.cmd("undo")
    assert texts(ed) == before
    ed._validate()
