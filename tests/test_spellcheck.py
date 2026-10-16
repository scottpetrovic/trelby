import contextlib
from unittest import mock

import wx

import tests.u as u
import trelby.screenplay as scr
import trelby.spellcheck as spellcheck
import trelby.spellcheckdlg as spellcheckdlg
import trelby.translations as translations
from trelby.line import Line

_ = translations.trelby_translations_load()


# the main dictionary as these words, instead of dict_en.dat
@contextlib.contextmanager
def mainDict(*words):
    with mock.patch.multiple(spellcheck, gdict=set(), prefixDict={}):
        spellcheck.loadDict("\n".join(words))

        yield


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
