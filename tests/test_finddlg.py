from unittest import mock

import wx

import tests.u as u
import trelby.config as config
import trelby.finddlg as finddlg
import trelby.screenplay as scr
import trelby.translations as translations
from trelby.line import Line

_ = translations.trelby_translations_load()

# drives Edit / Find & Replace through FindDlg's own handlers, on a
# FindDlg made without a window (FindDlg.__new__) whose controls are
# stand-ins. the message boxes are answered by the test: Yes to "continue
# at the start?", and their texts are kept in Finder.messages.


class Text:
    def __init__(self, value=""):
        self.value = value

    def GetValue(self):
        return self.value

    def SetValue(self, value):
        self.value = value

    def SetSelection(self, a, b):
        pass


class CheckBox:
    def __init__(self, checked=False):
        self.checked = checked

    def IsChecked(self):
        return self.checked

    def GetValue(self):
        return self.checked

    def SetValue(self, checked):
        self.checked = checked


class RadioBox:
    def __init__(self, sel):
        self.sel = sel

    def GetSelection(self):
        return self.sel

    def SetSelection(self, sel):
        self.sel = sel


class CheckList:
    def __init__(self, checked):
        self.checked = list(checked)

    def GetCount(self):
        return len(self.checked)

    def IsChecked(self, i):
        return self.checked[i]

    def Check(self, i, checked=True):
        self.checked[i] = checked


class Ctrl:
    def __init__(self, ed):
        self.ed = ed
        self.sp = ed.sp

    def makeLineVisible(self, line):
        pass

    def updateScreen(self):
        pass


class Finder:
    # types: the element types to search in (the dialog's "More" list),
    # or None for all. continueAtEnd: the answer to "continue at the
    # start / end?".
    def __init__(
        self,
        ed,
        text,
        replace="",
        matchCase=False,
        wholeWord=False,
        up=False,
        types=None,
        continueAtEnd=True,
    ):
        self.ed = ed
        self.continueAtEnd = continueAtEnd
        self.messages = []

        dlg = finddlg.FindDlg.__new__(finddlg.FindDlg)
        dlg.ctrl = Ctrl(ed)
        dlg.searchLine = -1
        dlg.searchColumn = -1
        dlg.searchWidth = -1

        dlg.findEntry = Text(text)
        dlg.replaceEntry = Text(replace)
        dlg.matchCaseCb = CheckBox(matchCase)
        dlg.matchWholeCb = CheckBox(wholeWord)
        dlg.direction = RadioBox(0 if up else 1)

        dlg.elementTypes = [t.lt for t in config.getTIs()]
        dlg.elements = CheckList(
            (types is None) or (lt in types) for lt in dlg.elementTypes
        )
        dlg.useExtra = types is not None

        self.dlg = dlg

    def messageBox(self, message, caption, style, parent):
        self.messages.append(message)

        if style & wx.YES_NO:
            return wx.YES if self.continueAtEnd else wx.NO

        return wx.OK

    def run(self, method):
        with mock.patch.object(wx, "MessageBox", self.messageBox):
            return method()

    # the current match, as (line, column, length), or None
    def match(self):
        if self.dlg.searchLine == -1:
            return None

        return (self.dlg.searchLine, self.dlg.searchColumn, self.dlg.searchWidth)

    # Find next. returns the match, which is also selected.
    def find(self):
        self.run(self.dlg.OnFind)

        m = self.match()
        if m:
            line, col, length = m
            assert (self.ed.line, self.ed.column) == (line, col)
            assert self.ed.mark is not None
            assert (self.ed.mark.line, self.ed.mark.column) == (line, col + length - 1)

        return m

    # Replace: replaces the current match and finds the next one
    def replace(self):
        self.run(self.dlg.OnReplace)

        return self.match()

    def replaceAll(self):
        self.run(self.dlg.OnReplaceAll)

        return self.messages[-1]


def makeEd(*paras):
    sp = u.new()
    sp.lines = [Line(scr.LB_LAST, lt, text) for lt, text in paras]
    sp.reformatAll()
    sp.paginate()

    return scr.Editor(sp)


def texts(ed):
    return [ln.text for ln in ed.sp.lines]


def script():
    return makeEd(
        (scr.SCENE, "INT. KITCHEN - DAY"),
        (scr.ACTION, "The cat sits on the mat. Another cat."),
        (scr.CHARACTER, "BOB"),
        (scr.DIALOGUE, "Cat food, cat."),
        (scr.ACTION, "Concatenate the CAT."),
    )


NO_RESULTS = "Search finished without results."
AT_END = "Search finished at the end of the script. Do\nyou want to continue at the start of the script?"
AT_START = "Search finished at the start of the script. Do\nyou want to continue at the end of the script?"


def findAll(f, n):
    return [f.find() for i in range(n)]


def testFindDown():
    f = Finder(script(), "cat")

    assert findAll(f, 6) == [
        (1, 4, 3),
        (1, 33, 3),
        (3, 0, 3),
        (3, 10, 3),
        (4, 3, 3),
        (4, 16, 3),
    ]
    assert f.messages == []


def testFindUp():
    ed = script()
    ed.gotoPos(4, len(ed.sp.lines[4].text))
    f = Finder(ed, "cat", up=True)

    assert findAll(f, 6) == [
        (4, 16, 3),
        (4, 3, 3),
        (3, 10, 3),
        (3, 0, 3),
        (1, 33, 3),
        (1, 4, 3),
    ]
    assert f.messages == []


def testFindUpFromMiddleOfLine():
    ed = script()

    # going up, a match is found if it ends before the cursor, or at the
    # character under it
    ed.gotoPos(1, 35)
    assert Finder(ed, "cat", up=True).find() == (1, 33, 3)

    ed.gotoPos(1, 34)
    assert Finder(ed, "cat", up=True).find() == (1, 4, 3)


def testFindFromCursor():
    ed = script()
    ed.gotoPos(1, 5)

    assert Finder(ed, "cat").find() == (1, 33, 3)


def testFindMatchCase():
    f = Finder(script(), "cat", matchCase=True)

    assert findAll(f, 3) == [(1, 4, 3), (1, 33, 3), (3, 10, 3)]

    f = Finder(script(), "CAT", matchCase=True)
    assert f.find() == (4, 16, 3)


def testFindIgnoresCaseOfNonAscii():
    ed = makeEd((scr.ACTION, "Über alles, über."))
    f = Finder(ed, "ÜBER")

    assert findAll(f, 2) == [(0, 0, 4), (0, 12, 4)]


def testFindWholeWord():
    ed = makeEd(
        (scr.ACTION, "cat, the cat's cat."),
        (scr.ACTION, "cats cat"),
    )
    f = Finder(ed, "cat", wholeWord=True)

    assert f.find() == (0, 0, 3)

    # only the first match on each line (from the cursor) is checked for
    # being a whole word, and when it isn't, the line's other matches are
    # missed: here it's "cat's" (an apostrophe is part of a word), so the
    # "cat" after it is skipped, and on the next line it's "cats"
    assert f.find() == (0, 0, 3)
    assert f.messages == [AT_END]


def testFindWholeWordMissesLaterMatchOnLine():
    f = Finder(script(), "cat", wholeWord=True)

    # "Concatenate the CAT." has "cat" in "Concatenate" first
    assert findAll(f, 4) == [(1, 4, 3), (1, 33, 3), (3, 0, 3), (3, 10, 3)]
    assert f.find() == (1, 4, 3)
    assert f.messages == [AT_END]


def testFindInElementTypes():
    f = Finder(script(), "cat", types={scr.DIALOGUE})

    assert findAll(f, 3) == [(3, 0, 3), (3, 10, 3), (3, 0, 3)]
    assert f.messages == [AT_END]

    f = Finder(script(), "kitchen", types={scr.ACTION, scr.DIALOGUE})
    assert f.find() is None
    assert f.messages == [NO_RESULTS]


def testFindWrapsAround():
    ed = script()
    ed.gotoPos(4, 0)
    f = Finder(ed, "the")

    assert f.find() == (4, 12, 3)
    assert f.find() == (1, 0, 3)
    assert f.messages == [AT_END]

    assert f.find() == (1, 16, 3)
    assert f.find() == (1, 28, 3)
    assert f.messages == [AT_END]


def testFindDoesNotWrapWhenToldNot():
    ed = script()
    ed.gotoPos(4, 0)
    f = Finder(ed, "the", continueAtEnd=False)

    assert f.find() == (4, 12, 3)
    assert f.find() is None
    assert f.messages == [AT_END]

    # the cursor stays at the last match
    assert (ed.line, ed.column) == (4, 12)


def testFindWrapsAroundGoingUp():
    ed = script()
    ed.gotoPos(1, 0)
    f = Finder(ed, "the", up=True)

    assert f.find() == (4, 12, 3)
    assert f.messages == [AT_START]


def testFindUpAfterWrapUsesFirstLinesLength():
    # going up, after wrapping around to the end, the last line is
    # searched from where the first line's search ended (its length - 1),
    # so a match further right on it is missed
    ed = makeEd(
        (scr.ACTION, "dog"),
        (scr.ACTION, "nothing here"),
        (scr.ACTION, "and at the very end, a cat"),
    )
    ed.gotoPos(1, 0)
    f = Finder(ed, "cat", up=True)

    assert f.find() is None
    assert f.messages == [AT_START, NO_RESULTS]


def testFindNoMatches():
    f = Finder(script(), "dog")

    assert f.find() is None
    assert f.messages == [NO_RESULTS]


def testFindNoMatchesFromMiddle():
    ed = script()
    ed.gotoPos(2, 0)
    f = Finder(ed, "dog")

    assert f.find() is None
    assert f.messages == [AT_END, NO_RESULTS]


def testFindEmptyDoesNothing():
    f = Finder(script(), "")

    assert f.find() is None
    assert f.messages == []


def testFindSpanningLinesNotFound():
    ed = makeEd((scr.ACTION, "word " * 20))
    assert len(ed.sp.lines) > 1

    # "word word" wraps between the first two lines
    assert ed.sp.lines[0].text.endswith("word")
    f = Finder(ed, "word word")

    found = []
    for i in range(30):
        m = f.find()
        if m in found:
            break
        found.append(m)

    assert all(m[0] < len(ed.sp.lines) for m in found)
    assert all(m[1] + m[2] <= len(ed.sp.lines[m[0]].text) for m in found)


def testReplace():
    ed = script()
    f = Finder(ed, "cat", replace="dog")

    assert f.replace() is None
    assert f.find() == (1, 4, 3)

    # replaces the match and finds the next one
    assert f.replace() == (1, 33, 3)
    assert ed.sp.lines[1].text == "The dog sits on the mat. Another cat."
    assert f.replace() == (3, 0, 3)
    assert ed.sp.lines[1].text == "The dog sits on the mat. Another dog."

    assert ed.sp.isModified()
    ed._validate()

    ed.cmd("undo")
    ed.cmd("undo")
    assert texts(ed) == texts(script())


def testReplaceKeepsReplacementCase():
    ed = script()
    f = Finder(ed, "cat", replace="dog")
    ed.gotoPos(3, 0)

    f.find()
    f.replace()
    assert ed.sp.lines[3].text == "dog food, cat."


def testReplaceUp():
    ed = script()
    ed.gotoPos(1, len(ed.sp.lines[1].text))
    f = Finder(ed, "cat", replace="tiger", up=True, continueAtEnd=False)

    assert f.find() == (1, 33, 3)
    assert f.replace() == (1, 4, 3)
    assert f.replace() is None
    assert ed.sp.lines[1].text == "The tiger sits on the mat. Another tiger."
    assert f.messages == [AT_START]
    ed._validate()


def testReplaceUpAtStartOfScript():
    ed = makeEd((scr.ACTION, "cat cat"))
    ed.gotoPos(0, 3)
    f = Finder(ed, "cat", replace="dog", up=True, continueAtEnd=False)

    assert f.find() == (0, 0, 3)
    assert f.replace() is None
    assert ed.sp.lines[0].text == "dog cat"
    assert f.messages == [AT_START]
    assert (ed.line, ed.column) == (0, 0)


def testReplaceWithLongerTextRewraps():
    ed = makeEd((scr.ACTION, "A cat. " * 12))
    lines = len(ed.sp.lines)
    f = Finder(ed, "cat", replace="hippopotamus")

    f.find()
    for i in range(12):
        f.replace()

    assert len(ed.sp.lines) > lines
    assert "".join(texts(ed)).count("hippopotamus") == 12
    ed._validate()


def testReplaceCursorDriftWhenReplacementWraps():
    w = makeEd((scr.ACTION, "")).sp.cfg.getType(scr.ACTION).width
    ed = makeEd(
        (scr.ACTION, "x" * (w - 5) + " cat " + "y" * 10),
        (scr.ACTION, "One more cat."),
    )
    assert texts(ed)[:2] == ["x" * (w - 5) + " cat", "y" * 10]

    f = Finder(ed, "cat", replace="big dog")
    f.find()
    f.run(f.dlg.getParams)

    # replace without finding the next match, to see where the cursor
    # is left
    with mock.patch.object(f.dlg, "OnFind"):
        f.replace()

    assert texts(ed)[:2] == ["x" * (w - 5) + " big", "dog " + "y" * 10]

    # the cursor is moved len("big dog") right of the match, on the first
    # line, which is now shorter than that
    assert (ed.line, ed.column) == (0, w - 4 + 7)
    assert ed.column > len(ed.sp.lines[0].text)


def testReplaceAll():
    ed = script()
    f = Finder(ed, "cat", replace="dog")

    assert f.replaceAll() == "Replaced 6 matches"
    assert texts(ed) == [
        "INT. KITCHEN - DAY",
        "The dog sits on the mat. Another dog.",
        "BOB",
        "dog food, dog.",
        "Condogenate the dog.",
    ]
    ed._validate()


def testReplaceAllFromCursorToEnd():
    ed = script()
    ed.gotoPos(3, 5)
    f = Finder(ed, "cat", replace="dog")

    # nothing before the cursor is replaced
    assert f.replaceAll() == "Replaced 3 matches"
    assert texts(ed)[1] == "The cat sits on the mat. Another cat."
    assert texts(ed)[3] == "Cat food, dog."
    assert f.messages == ["Replaced 3 matches"]


def testReplaceAllIncludesCurrentMatch():
    ed = script()
    ed.gotoPos(3, 5)
    f = Finder(ed, "cat", replace="dog", up=True)

    assert f.find() == (3, 0, 3)
    assert f.replaceAll() == "Replaced 3 matches"
    assert texts(ed)[1] == "The dog sits on the mat. Another dog."
    assert texts(ed)[3] == "dog food, cat."


def testReplaceAllWithTextContainingMatch():
    ed = script()
    f = Finder(ed, "cat", replace="cats")

    assert f.replaceAll() == "Replaced 6 matches"
    assert texts(ed)[1] == "The cats sits on the mat. Another cats."


def testReplaceAllNothing():
    ed = script()
    f = Finder(ed, "dog", replace="cat")

    assert f.replaceAll() == "Replaced 0 matches"
    assert f.messages == ["Replaced 0 matches"]
    assert not ed.sp.isModified()


def testReplaceAllUndo():
    ed = script()
    f = Finder(ed, "cat", replace="dog")
    f.replaceAll()

    # one undo step per match
    for i in range(6):
        ed.cmd("undo")

    assert texts(ed) == texts(script())
