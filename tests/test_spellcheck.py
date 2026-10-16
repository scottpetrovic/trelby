import contextlib
from unittest import mock

import wx

import tests.u as u
import trelby.screenplay as scr
import trelby.spellcheck as spellcheck
import trelby.dialogs.spellcheckdlg as spellcheckdlg
import trelby.ui.trelbyctrl as trelbyctrl
import trelby.translations as translations
from trelby.screenplay.line import Line

_ = translations.trelby_translations_load()


# the main dictionary as these words, instead of dict_en.dat
@contextlib.contextmanager
def mainDict(*words):
    with mock.patch.multiple(spellcheck, gdict=set(), prefixDict={}):
        spellcheck.loadDict("\n".join(words))

        yield


def userDict(*words):
    d = spellcheck.Dict()
    d.set(words)

    return d


def testSuggest():
    with mainDict("house", "horse", "hose", "mouse", "houses", "household", "ho"):
        # closest first, ties alphabetically. "household" is too much
        # longer, "mouse" starts differently, and two-letter words aren't
        # suggested from the main dictionary
        assert spellcheck.suggest("hous", []) == ["house", "horse", "hose", "houses"]
        assert spellcheck.suggest("hous", [], n=2) == ["house", "horse"]


def testSuggestFromUserDicts():
    with mainDict("house"):
        script = userDict("housekeep", "ho")
        user = userDict("hoose", "house")

        # no duplicates, and the user's two-letter words are suggested
        assert spellcheck.suggest("hous", [user, script]) == ["house", "ho", "hoose"]


def testSuggestKeepsCase():
    with mainDict("house", "horse"):
        assert spellcheck.suggest("HOUS", []) == ["HOUSE", "HORSE"]
        assert spellcheck.suggest("Hous", []) == ["House", "Horse"]
        assert spellcheck.suggest("hoUS", []) == ["house", "horse"]


def testSuggestNothing():
    with mainDict("house"):
        assert spellcheck.suggest("xyzzy", []) == []

        # one letter: there's no prefix set for it
        assert spellcheck.suggest("q", []) == []
        assert spellcheck.suggest("", []) == []


def testSuggestNonAscii():
    with mainDict("über", "überall"):
        assert spellcheck.suggest("Ubr", [userDict("ubre")]) == ["Ubre"]
        assert spellcheck.suggest("übr", []) == ["über"]


def testMatchCase():
    assert spellcheck.matchCase("ÅSA", "åsa") == "ÅSA"
    assert spellcheck.matchCase("Åsa", "åsa") == "Åsa"
    assert spellcheck.matchCase("åSA", "åsa") == "åsa"


# the spell checker's Replace, on a SpellCheckDlg made without a window
class Ctrl:
    def __init__(self, ed):
        self.ed = ed
        self.sp = ed.sp

    def makeLineVisible(self, line):
        pass

    def updateScreen(self):
        pass


class Text:
    def __init__(self):
        self.value = ""

    def GetValue(self):
        return self.value

    def SetValue(self, value):
        self.value = value


def makeDlg(ed):
    sc = spellcheck.SpellChecker(ed.sp, spellcheck.Dict())
    assert sc.findNext()

    dlg = spellcheckdlg.SpellCheckDlg.__new__(spellcheckdlg.SpellCheckDlg)
    dlg.ctrl = Ctrl(ed)
    dlg.sc = sc
    dlg.gScDict = spellcheck.Dict()
    dlg.replaceEntry = Text()
    dlg.EndModal = lambda code: None
    dlg.showWord()

    return dlg


def replace(dlg, word):
    dlg.replaceEntry.SetValue(word)

    with mock.patch.object(wx, "MessageBox"):
        dlg.OnReplace(None)


def testSpellCheckReplace():
    sp = u.new()
    sp.lines = [Line(scr.LB_LAST, scr.ACTION, "The huose is teh best.")]
    ed = scr.Editor(sp)

    with mainDict("the", "is", "best", "house"):
        dlg = makeDlg(ed)
        assert dlg.sc.word == "huose"

        replace(dlg, "house")
        assert sp.lines[0].text == "The house is teh best."
        assert dlg.sc.word == "teh"

        replace(dlg, "the")
        assert sp.lines[0].text == "The house is the best."

    ed.cmd("undo")
    assert sp.lines[0].text == "The house is teh best."


def testSpellCheckReplaceRewraps():
    sp = u.new()
    w = sp.cfg.getType(scr.ACTION).width
    sp.lines = [Line(scr.LB_LAST, scr.ACTION, "x" * (w - 5) + " alot alot")]
    sp.reformatAll()
    assert [ln.text for ln in sp.lines] == ["x" * (w - 5) + " alot", "alot"]
    ed = scr.Editor(sp)

    with mainDict("x" * (w - 5), "a", "lot"):
        dlg = makeDlg(ed)
        assert (dlg.sc.line, dlg.sc.col) == (0, w - 4)

        # "a lot" wraps, so the next word is on the next line
        replace(dlg, "a lot")
        assert [ln.text for ln in sp.lines] == ["x" * (w - 5) + " a", "lot alot"]
        assert (dlg.sc.word, dlg.sc.line, dlg.sc.col) == ("alot", 1, 4)


def testLineWords():
    assert spellcheck.lineWords("") == []
    assert spellcheck.lineWords("Joe's 'BAR', 2nd_floor -- 'em") == [
        (0, "Joe's"),
        (7, "BAR"),
        (13, "2nd"),
        (17, "floor"),
        (27, "em"),
    ]


def testWordAt():
    text = "a 'quote' here"

    assert spellcheck.wordAt(text, 0) == (0, "a")
    assert spellcheck.wordAt(text, 1) == (0, "a")
    assert spellcheck.wordAt(text, 3) == (3, "quote")
    assert spellcheck.wordAt(text, 8) == (3, "quote")
    assert spellcheck.wordAt(text, 9) is None
    assert spellcheck.wordAt(text, 100) is None


def testIsKnownQuotesAndPossessives():
    sp = u.new()
    sp.lines = [Line(scr.LB_LAST, scr.CHARACTER, "ZOLTAN")]

    with mainDict("house"):
        sc = spellcheck.SpellChecker(sp, spellcheck.Dict())

        assert sc.isKnown("'house'")
        assert sc.isKnown("House's")
        assert sc.isKnown("ZOLTAN'S")
        assert sc.isKnown("'")
        assert not sc.isKnown("houses")
        assert not sc.isKnown("hou'se")


def testLineErrors():
    sp = u.new()
    sp.lines = [Line(scr.LB_LAST, scr.ACTION, "The huose, 'teh' end.")]

    with mainDict("the", "end"):
        sc = spellcheck.SpellChecker(sp, userDict(), 0)

        assert sc.lineErrors(0) == [(4, 5), (12, 3)]

        # the word just typed isn't underlined, even if it's misspelled,
        # but other words with the cursor in them are
        assert sc.lineErrors(0, 9) == [(12, 3)]
        assert sc.lineErrors(0, 6) == [(4, 5), (12, 3)]

        sp.scDict.add("teh")
        assert sc.lineErrors(0) == [(4, 5)]

        sc = spellcheck.SpellChecker(sp, userDict("huose"))
        assert sc.lineErrors(0) == []


# the right-click menu's spelling items, on a MyCtrl made without a window
class MenuEvent:
    def __init__(self, id):
        self.id = id

    def GetId(self):
        return self.id


def makeCtrl(text):
    sp = u.new()
    sp.lines = [Line(scr.LB_LAST, scr.ACTION, text)]

    ctrl = trelbyctrl.MyCtrl.__new__(trelbyctrl.MyCtrl)
    ctrl.sp = sp
    ctrl.ed = scr.Editor(sp)
    ctrl.gd = mock.Mock(cfgGl=sp.cfgGl, scDict=spellcheck.Dict())
    ctrl.suggestionIds = [101, 102, 103, 104, 105]
    ctrl.addWordId = 106
    ctrl.addScriptWordId = 107
    ctrl.clearAutoComp = lambda: None
    ctrl.makeLineVisible = lambda line: None
    ctrl.updateScreen = lambda: None

    return ctrl


def testSpellingMenu():
    ctrl = makeCtrl("The housw is red.")

    with mainDict("the", "is", "red", "house", "horse"):
        # a known word, or no word, gets no items
        assert ctrl.spellingMenu(0, 1) is None
        assert ctrl.spellingMenu(0, 16) is None
        assert ctrl.spellingMenu(None, None) is None

        items = ctrl.spellingMenu(0, 6)
        assert items == [
            (None, "Spelling"),
            (101, "house"),
            (102, "horse"),
            (106, 'Add "housw" to dictionary'),
            (107, 'Add "housw" to script dictionary'),
        ]

        ctrl.OnSpellingMenu(MenuEvent(101))
        assert ctrl.sp.lines[0].text == "The house is red."
        assert ctrl.sp.isModified()

        ctrl.ed.cmd("undo")
        assert ctrl.sp.lines[0].text == "The housw is red."

        ctrl.gd.cfgGl.checkSpelling = False
        assert ctrl.spellingMenu(0, 6) is None
        ctrl.gd.cfgGl.checkSpelling = True


def testSpellingMenuAddWord():
    ctrl = makeCtrl("Xyzzy and plugh.")

    with mainDict("and"):
        items = ctrl.spellingMenu(0, 0)
        assert (None, "No suggestions") in items

        ctrl.OnSpellingMenu(MenuEvent(106))
        assert ctrl.gd.scDict.isKnown("xyzzy")
        ctrl.gd.saveScDict.assert_called_once()

        ctrl.spellingMenu(0, 12)
        ctrl.OnSpellingMenu(MenuEvent(107))
        assert ctrl.sp.scDict.isKnown("plugh")
        assert ctrl.sp.isModified()

        assert ctrl.spellingMenu(0, 0) is None
        assert ctrl.spellingMenu(0, 12) is None
