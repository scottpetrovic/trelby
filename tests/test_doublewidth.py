import copy
from unittest import mock

import wx

import tests.u as u
import trelby.config as config
import trelby.mypager as mypager
import trelby.pdf as pdf
import trelby.pml as pml
import trelby.screenplay as scr
import trelby.screenplay.render as render
import trelby.translations as translations
import trelby.util as util
from tests.test_keyinput import FakeCtrl, KeyEvent, press

_ = translations.trelby_translations_load()

# tests for double-width characters (config.Config.doubleWidth), where
# every character takes up two columns, for Chinese, Japanese and Korean

# 72 Chinese characters, no spaces
CHINESE = "他走进房间，看见桌子上放着一封信。" * 4 + "她哭了。"


# return a paginated script with a scene heading and the given action
# text, using double-width characters if 'double' is True
def makeScript(text, double=True):
    ed = u.loadStringEditor(
        "\n".join(["#Version 3", "#Start-Script ", ".\\INT. ROOM - DAY", "..%s" % text])
    )

    if double:
        setDoubleWidth(ed)

    ed.sp.paginate()

    return ed


def setDoubleWidth(ed, double=True):
    cfg = copy.deepcopy(ed.sp.cfg)
    cfg.doubleWidth = double
    ed.applyCfg(cfg)


# return the texts of the lines of the action element, the last element
def actionLines(ed):
    return [ln.text for ln in ed.sp.lines if ln.lt == scr.ACTION]


def testWideChars():
    for ch in "中文日本語한국어，。！（ＡＢ":
        assert util.isWideChar(ch), ch

    for ch in "aZ ä€Ω—“…":
        assert not util.isWideChar(ch), ch

    assert util.hasWideChars("hello 世界")
    assert not util.hasWideChars("hello wörld")
    assert not util.hasWideChars("")


def testConfigSaveLoad():
    cfg = config.Config()
    assert not cfg.doubleWidth
    assert not cfg.doubleWidthAsked
    assert cfg.getCharWidth() == 1

    cfg.doubleWidth = True
    cfg.doubleWidthAsked = True
    assert cfg.getCharWidth() == 2

    cfg2 = config.Config()
    cfg2.load(cfg.save())
    assert cfg2.doubleWidth
    assert cfg2.doubleWidthAsked


def testSavedInScript():
    ed = makeScript(CHINESE)
    ed2 = u.loadStringEditor(ed.save().decode("utf-8"))

    assert ed2.sp.cfg.doubleWidth
    assert actionLines(ed2) == actionLines(ed)


def testChineseWrapsAtHalfWidth():
    ed = makeScript(CHINESE)

    # action is 60 columns wide, so 30 characters
    assert [len(t) for t in actionLines(ed)] == [30, 30, 12]
    assert "".join(actionLines(ed)) == CHINESE

    # broken between characters, without spaces
    lns = [ln for ln in ed.sp.lines if ln.lt == scr.ACTION]
    assert [ln.lb for ln in lns] == [scr.LB_NONE, scr.LB_NONE, scr.LB_LAST]

    ed._validate()


def testSingleWidthUnchanged():
    ed = makeScript(CHINESE, double=False)

    assert [len(t) for t in actionLines(ed)] == [60, 12]


def testLatinWrapsAtSpacesInDoubleWidth():
    text = "The quick brown fox jumps over the lazy dog and runs away."
    ed = makeScript(text)

    assert actionLines(ed) == [
        "The quick brown fox jumps over",
        "the lazy dog and runs away.",
    ]
    ed._validate()


def testMixedTextBreaksAtWideChars():
    # the last space is early in the line, but the text can be broken
    # after any Chinese character
    text = "他说 OK，然后" + "我们走吧" * 10
    ed = makeScript(text)
    lines = actionLines(ed)

    assert lines[0] == text[:30]
    assert all(len(t) <= 30 for t in lines)
    assert "".join(lines) == text
    ed._validate()


def testSwitchingRewraps():
    ed = makeScript(CHINESE, double=False)
    assert len(actionLines(ed)) == 2

    setDoubleWidth(ed)
    assert len(actionLines(ed)) == 3

    setDoubleWidth(ed, False)
    assert len(actionLines(ed)) == 2
    ed._validate()


def testCenterOffset():
    ed = makeScript("中文")
    i = ed.sp.getElemFirstIndexFromLine(len(ed.sp.lines) - 1)

    with mock.patch.object(ed.sp, "isCentered", return_value=True):
        # 2 characters take 4 of the 60 columns
        assert ed.sp.getCenterOffset(i) == 28.0

        setDoubleWidth(ed, False)
        assert ed.sp.getCenterOffset(i) == 29.0


def textOps(ed):
    pg = render.generatePMLPage(ed.sp, mypager.Pager(ed.sp.cfg), 1, True, True)

    return [op for op in pg.ops if isinstance(op, pml.TextOp) and (op.line != -1)]


def testPMLCharWidth():
    assert {op.charWidth for op in textOps(makeScript(CHINESE))} == {2}
    assert {op.charWidth for op in textOps(makeScript(CHINESE, False))} == {1}


def testPDFUsesChineseFont():
    ed = makeScript(CHINESE + " Hello")
    doc = render.generatePML(ed.sp)

    assert pdf.unsupportedChars(doc) == ""

    data = pdf.generate(doc)
    assert data[:8] == b"%PDF-1.5"
    assert b"STSong-Light" in data


def testPDFWarnsInSingleWidth():
    ed = makeScript(CHINESE, double=False)

    assert "他" in pdf.unsupportedChars(render.generatePML(ed.sp))


def testPDFWarnsAboutCharsNotInChineseFont():
    # Korean Hangul isn't in the Chinese font
    ed = makeScript("한국어 中文")

    assert pdf.unsupportedChars(render.generatePML(ed.sp)) == "국어한"


def newCtrl(ed):
    ctrl = FakeCtrl(ed.sp)
    ctrl.offers = []
    ctrl.offerDoubleWidth = ctrl.offers.append

    return ctrl


def typeChars(ctrl, s):
    for c in s:
        press(ctrl, KeyEvent(ord(c), ord(c) if ord(c) < 0x80 else wx.WXK_NONE))


def callAfter(fn, *args):
    fn(*args)


@mock.patch.object(wx, "CallAfter", callAfter)
def testTypingChineseOffersOnce():
    ed = u.newEditor()
    ed.sp.lines[0].lt = scr.ACTION
    ctrl = newCtrl(ed)

    typeChars(ctrl, "abc ä")
    assert ctrl.offers == []

    typeChars(ctrl, "你好")
    assert ctrl.offers == [ed.sp]
    assert ed.sp.cfg.doubleWidthAsked

    # asked only once
    typeChars(ctrl, "世界")
    assert ctrl.offers == [ed.sp]


@mock.patch.object(wx, "CallAfter", callAfter)
def testNoOfferInDoubleWidth():
    ed = makeScript("x")
    ctrl = newCtrl(ed)

    ctrl.checkWideChars("你好")
    assert ctrl.offers == []
