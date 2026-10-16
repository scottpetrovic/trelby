from unittest import mock

import wx

import tests.u as u
import trelby.config as config
import trelby.finddlg as finddlg
import trelby.screenplay as scr
import trelby.screenplay.search as search
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
        dlg.match = None

        dlg.findEntry = Text(text)
        dlg.replaceEntry = Text(replace)
        dlg.matchCaseCb = CheckBox(matchCase)
        dlg.matchWholeCb = CheckBox(wholeWord)
        dlg.direction = RadioBox(0 if up else 1)

        dlg.elementTypes = [t.lt for t in config.getTIs()]
        dlg.elements = CheckList(
            (types is None) or (lt in types) for lt in dlg.elementTypes
        )
        dlg.showTypes = types is not None

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
        m = self.dlg.match

        return m and (m.line, m.col, m.length)

    # Find next. returns the match, which is also selected.
    def find(self):
        self.run(self.dlg.OnFind)

        m = self.match()
        if m:
            line, col, length = m
            assert (self.ed.line, self.ed.column) == (line, col)
            assert self.ed.mark is not None

            # the match's last character, which can be on a later line
            assert (self.ed.mark.line, self.ed.mark.column) == search.advance(
                self.ed.sp, line, col, length - 1
            )

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

    # going up, a match is found if it ends at or before the cursor. (it
    # used to be found when it ended on the character under it, too.)
    ed.gotoPos(1, 36)
    assert Finder(ed, "cat", up=True).find() == (1, 33, 3)

    ed.gotoPos(1, 35)
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

    # an apostrophe is part of a word, so "cat's" isn't "cat". the matches
    # after one that isn't a whole word are still found (they used to be
    # skipped, for the rest of the line).
    assert findAll(f, 4) == [(0, 0, 3), (0, 15, 3), (1, 5, 3), (0, 0, 3)]
    assert f.messages == [AT_END]


def testFindWholeWordLaterMatchOnLine():
    f = Finder(script(), "cat", wholeWord=True)

    # "Concatenate the CAT." has "cat" in "Concatenate" first
    assert findAll(f, 5) == [(1, 4, 3), (1, 33, 3), (3, 0, 3), (3, 10, 3), (4, 16, 3)]
    assert f.messages == []


def testFindWholeWordGoingUp():
    ed = makeEd((scr.ACTION, "cat cats concat"))
    ed.gotoPos(0, 15)
    f = Finder(ed, "cat", wholeWord=True, up=True)

    assert f.find() == (0, 0, 3)


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


def testFindUpWrapsToEndOfLastLine():
    # going up, after wrapping around to the end, the whole last line is
    # searched. (it used to be searched only as far as the first line was
    # long.)
    ed = makeEd(
        (scr.ACTION, "dog"),
        (scr.ACTION, "nothing here"),
        (scr.ACTION, "and at the very end, a cat"),
    )
    ed.gotoPos(1, 0)
    f = Finder(ed, "cat", up=True)

    assert f.find() == (2, 23, 3)
    assert f.messages == [AT_START]


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


# the offset of line, col in its paragraph's text, which starts at line 0
def paraOffset(ed, line, col):
    ls = ed.sp.lines

    return sum(len(ls[i].text) + len(config.lb2str(ls[i].lb)) for i in range(line)) + col


# "a word word ...", which wraps with an odd number of words on the first
# line, so that every other pair of words spans the lines
def words():
    ed = makeEd((scr.ACTION, "a " + "word " * 20))
    assert len(ed.sp.lines) == 2
    assert ed.sp.lines[0].lb == scr.LB_SPACE
    assert ed.sp.lines[0].text.endswith(" word")

    return ed


def testFindSpanningLines():
    ed = words()
    f = Finder(ed, "word word")

    found = findAll(f, 19)
    assert [paraOffset(ed, m[0], m[1]) for m in found] == [2 + 5 * i for i in range(19)]
    assert f.messages == []

    # the pair that wraps is selected over both lines
    spanning = [m for m in found if m[0] == 0 and m[1] + m[2] > len(texts(ed)[0])]
    assert len(spanning) == 1
    line, col, length = spanning[0]
    f.dlg.match = None
    ed.gotoPos(line, col)
    assert f.find() == spanning[0]
    assert ed.mark.line == 1

    # and then the next ones, and the search wraps around after the last
    for m in found[found.index(spanning[0]) + 1 :]:
        assert f.find() == m

    assert f.find() == found[0]
    assert f.messages == [AT_END]


def testFindUpSpanningLines():
    ed = words()
    ed.gotoPos(1, len(texts(ed)[1]))
    f = Finder(ed, "word word", up=True)

    # going up, a match must end at or before the start of the last one,
    # so they don't overlap
    found = findAll(f, 10)
    assert [paraOffset(ed, m[0], m[1]) for m in found] == [
        2 + 10 * i for i in reversed(range(10))
    ]
    assert f.messages == []

    # including the pair that wraps
    assert (0, len(texts(ed)[0]) - 4, 9) in found


def testFindMatchStartingAtLineEnd():
    ed = words()
    f = Finder(ed, " word")

    # " word" at the break starts on the space at the end of the first
    # line. the next search has to step past it onto the next line, rather
    # than find it again.
    found = findAll(f, 20)
    assert [paraOffset(ed, m[0], m[1]) for m in found] == [1 + 5 * i for i in range(20)]
    assert (0, len(texts(ed)[0]), 5) in found

    assert f.find() == found[0]
    assert f.messages == [AT_END]


def testReplaceSpanningLines():
    ed = words()
    before = texts(ed)
    f = Finder(ed, "word word", replace="cat", continueAtEnd=False)

    f.find()
    replaced = 0
    while f.match():
        f.replace()
        replaced += 1

    assert replaced == 10
    assert texts(ed) == ["a " + "cat " * 10]
    assert f.messages == [AT_END]
    ed._validate()

    # one undo step each
    for i in range(10):
        ed.cmd("undo")
    assert texts(ed) == before
    ed._validate()


def testReplaceSpanningMatch():
    ed = words()
    f = Finder(ed, "word word", replace="cat")

    # the pair that wraps
    line0 = texts(ed)[0]
    ed.gotoPos(0, len(line0) - 4)
    assert f.find() == (0, len(line0) - 4, 9)

    with mock.patch.object(f.dlg, "OnFind"):
        f.replace()

    assert texts(ed) == texts(
        makeEd((scr.ACTION, "a " + "word " * 10 + "cat " + "word " * 8))
    )
    assert (ed.line, ed.column) == (0, len(line0) - 1)
    ed._validate()

    ed.cmd("undo")
    assert texts(ed) == texts(words())
    assert (ed.line, ed.column) == (0, len(line0) - 4)


def testReplaceSpanningMatchGoingUp():
    ed = words()
    line0 = texts(ed)[0]
    ed.gotoPos(1, 4)
    f = Finder(ed, "word word", replace="cat", up=True)

    assert f.find() == (0, len(line0) - 4, 9)

    with mock.patch.object(f.dlg, "OnFind"):
        f.replace()

    # going up, the cursor is left at the start of the new text
    assert (ed.line, ed.column) == (0, len(line0) - 4)
    ed._validate()


def testReplaceAllSpanningLines():
    ed = words()
    f = Finder(ed, "WORD WORD", replace="cat")

    assert f.replaceAll() == "Replaced 10 matches"
    assert texts(ed) == ["a " + "cat " * 10]

    ed.cmd("undo")
    assert texts(ed) == texts(words())


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


def testReplaceCursorWhenReplacementWraps():
    w = makeEd((scr.ACTION, "")).sp.cfg.getType(scr.ACTION).width
    ed = makeEd(
        (scr.ACTION, "x" * (w - 5) + " cat " + "y" * 10),
        (scr.ACTION, "One more cat."),
    )
    assert texts(ed)[:2] == ["x" * (w - 5) + " cat", "y" * 10]

    f = Finder(ed, "cat", replace="big dog")
    f.find()

    # replace without finding the next match, to see where the cursor
    # is left
    with mock.patch.object(f.dlg, "OnFind"):
        f.replace()

    assert texts(ed)[:2] == ["x" * (w - 5) + " big", "dog " + "y" * 10]

    # the cursor is just past the replacement, on the next line. (it used
    # to be moved len("big dog") right of the match, past the end of the
    # first line.)
    assert (ed.line, ed.column) == (1, 3)
    ed._validate()

    assert f.find() == (2, 9, 3)


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


def testReplaceAllWholeScript():
    ed = script()
    ed.gotoPos(3, 5)
    f = Finder(ed, "cat", replace="dog")

    # the whole script, not just from the cursor on (as it used to be)
    assert f.replaceAll() == "Replaced 6 matches"
    assert texts(ed)[1] == "The dog sits on the mat. Another dog."
    assert texts(ed)[3] == "dog food, dog."
    assert f.messages == ["Replaced 6 matches"]

    # the cursor is past the last replacement
    assert (ed.line, ed.column) == (4, 19)
    assert ed.mark is None


def testReplaceAllGoingUp():
    ed = script()
    ed.gotoPos(3, 5)
    f = Finder(ed, "cat", replace="dog", up=True)

    assert f.find() == (3, 0, 3)
    assert f.replaceAll() == "Replaced 6 matches"
    assert texts(ed)[1] == "The dog sits on the mat. Another dog."
    assert texts(ed)[3] == "dog food, dog."

    # and Find starts afresh
    assert f.match() is None


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
    after = texts(ed)

    # one undo step
    ed.cmd("undo")
    assert texts(ed) == texts(script())
    ed._validate()

    ed.cmd("redo")
    assert texts(ed) == after
    ed._validate()


def testReplaceAllRewraps():
    ed = makeEd((scr.ACTION, "A cat. " * 12), (scr.DIALOGUE, "cat " * 30))
    f = Finder(ed, "cat", replace="hippopotamus")

    assert f.replaceAll() == "Replaced 42 matches"
    assert "".join(texts(ed)).count("hippopotamus") == 42
    ed._validate()

    ed.cmd("undo")
    assert texts(ed) == texts(
        makeEd((scr.ACTION, "A cat. " * 12), (scr.DIALOGUE, "cat " * 30))
    )


def testReplaceAllInElementTypes():
    ed = script()
    f = Finder(ed, "cat", replace="dog", types={scr.DIALOGUE})

    assert f.replaceAll() == "Replaced 2 matches"
    assert texts(ed)[1] == "The cat sits on the mat. Another cat."
    assert texts(ed)[3] == "dog food, dog."


def testReplaceAllWholeWordAndCase():
    ed = script()
    f = Finder(ed, "CAT", replace="dog", wholeWord=True, matchCase=True)

    assert f.replaceAll() == "Replaced 1 matches"
    assert texts(ed)[4] == "Concatenate the dog."


def testReplaceAllWithNothing():
    ed = makeEd((scr.ACTION, "aXbXXc"))
    f = Finder(ed, "x", replace="")

    assert f.replaceAll() == "Replaced 3 matches"
    assert texts(ed) == ["abc"]
    ed._validate()


def testStateOutlivesDialog():
    ed = script()
    f = Finder(
        ed,
        "cat",
        replace="dog",
        matchCase=True,
        up=True,
        types={scr.DIALOGUE, scr.ACTION},
    )
    f.dlg.saveState()

    state = f.dlg.ctrl.findState
    assert state.opts == finddlg.search.FindOptions(
        text="cat",
        matchCase=True,
        up=True,
        elementTypes=frozenset([scr.DIALOGUE, scr.ACTION]),
    )
    assert state.replaceText == "dog"
    assert state.showTypes

    g = Finder(ed, "")
    g.dlg.ctrl.findState = state
    with mock.patch.object(g.dlg, "showExtra") as showExtra:
        g.dlg.loadState()

    showExtra.assert_called_once_with(True)
    g.dlg.showTypes = True
    assert g.dlg.getOptions() == state.opts
    assert g.dlg.replaceEntry.GetValue() == "dog"


def testHiddenTypesAreRememberedButNotUsed():
    ed = script()
    f = Finder(ed, "cat", types={scr.DIALOGUE})
    f.dlg.showTypes = False

    assert f.find() == (1, 4, 3)

    f.dlg.saveState()
    assert f.dlg.ctrl.findState.opts.elementTypes == frozenset([scr.DIALOGUE])
    assert not f.dlg.ctrl.findState.showTypes


def testNewStateSearchesEverything():
    state = finddlg.FindState()

    assert state.opts.elementTypes is None
    assert not state.showTypes
