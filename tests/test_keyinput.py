from types import SimpleNamespace
from unittest import mock

import wx

import tests.u as u
import trelby.commands as commands
import trelby.config as config
import trelby.keys as keys
import trelby.opts as opts
import trelby.screenplay as screenplay
import trelby.translations as translations
import trelby.trelbyctrl as trelbyctrl

_ = translations.trelby_translations_load()

# tests MyCtrl.OnKeyChar, the editor's keyboard handler, with key events
# shaped like the ones wxMSW sends: a typed character carries its Unicode
# value, while arrows, Home etc. have none and only a key code. see
# https://github.com/trelby/trelby/issues/89


class KeyEvent:
    def __init__(self, uni, kc, ctrl=False, alt=False, shift=False):
        self.uni = uni
        self.kc = kc
        self.ctrl = ctrl
        self.alt = alt
        self.shift = shift
        self.skipped = False

    def GetUnicodeKey(self):
        return self.uni

    def GetKeyCode(self):
        return self.kc

    def ControlDown(self):
        return self.ctrl

    def AltDown(self):
        return self.alt

    def ShiftDown(self):
        return self.shift

    def Skip(self):
        self.skipped = True


# a MyCtrl for sp, without a window: OnKeyChar and the cmd* methods only
# need the script, its Editor and the key bindings, and the screen updates
# do nothing
def makeCtrl(sp):
    ctrl = trelbyctrl.MyCtrl.__new__(trelbyctrl.MyCtrl)
    ctrl.sp = sp
    ctrl.ed = screenplay.Editor(sp)
    ctrl.gd = SimpleNamespace(cfgGl=sp.cfgGl, keyMap=sp.cfgGl.getKeyMap())
    ctrl.makeLineVisible = lambda *args: None
    ctrl.updateScreen = lambda *args: None

    return ctrl


def newCtrl():
    sp = u.new()
    sp.lines[0].lt = screenplay.ACTION

    return makeCtrl(sp)


def press(ctrl, ev):
    with mock.patch.object(opts, "isTest", False, create=True):
        ctrl.OnKeyChar(ev)

    return ev


def typeChars(ctrl, s):
    for c in s:
        # characters outside the locale's code page have no key code
        press(ctrl, KeyEvent(ord(c), ord(c) if ord(c) < 0x80 else wx.WXK_NONE))


def testNordicLetters():
    ctrl = newCtrl()
    sp = ctrl.sp
    typeChars(ctrl, "ÅÄÖåäöØæ")

    assert sp.lines[0].text == "ÅÄÖåäöØæ"


def testArrowKeys():
    ctrl = newCtrl()
    sp = ctrl.sp
    ed = ctrl.ed
    typeChars(ctrl, "abc")

    press(ctrl, KeyEvent(wx.WXK_NONE, wx.WXK_LEFT))
    press(ctrl, KeyEvent(wx.WXK_NONE, wx.WXK_LEFT))
    assert ed.column == 1

    press(ctrl, KeyEvent(wx.WXK_NONE, wx.WXK_HOME))
    assert ed.column == 0

    press(ctrl, KeyEvent(wx.WXK_NONE, wx.WXK_RIGHT))
    typeChars(ctrl, "ä")
    assert sp.lines[0].text == "Aäbc"


def testShiftArrowSelects():
    ctrl = newCtrl()
    ed = ctrl.ed
    typeChars(ctrl, "abc")

    press(ctrl, KeyEvent(wx.WXK_NONE, wx.WXK_LEFT, shift=True))
    assert ed.mark is not None


def testAltShortcut():
    ctrl = newCtrl()
    sp = ctrl.sp
    typeChars(ctrl, "abc")

    press(ctrl, KeyEvent(ord("s"), ord("S"), alt=True))
    assert sp.lines[0].lt == screenplay.SCENE
    assert sp.lines[0].text == "Abc"


def testUnboundKeyIsSkipped():
    ctrl = newCtrl()
    sp = ctrl.sp

    ev = press(ctrl, KeyEvent(ord("q"), ord("Q"), ctrl=True, alt=True))
    assert ev.skipped
    assert sp.lines[0].text == ""


# characters above U+00FF: Polish, Czech, the euro sign, Cyrillic and
# Greek
def testCharsAboveLatin1():
    ctrl = newCtrl()
    sp = ctrl.sp
    typeChars(ctrl, "zażółć gęślą jaźń, čeština 5 €. привет. ωμέγα")

    assert sp.lines[0].text == "Zażółć gęślą jaźń, čeština 5 €. Привет. Ωμέγα"


def testCharsAboveLatin1InSceneHeading():
    ctrl = newCtrl()
    sp = ctrl.sp
    sp.lines[0].lt = screenplay.SCENE
    typeChars(ctrl, "int. łódź")
    press(ctrl, KeyEvent(wx.WXK_NONE, wx.WXK_RETURN))
    typeChars(ctrl, "x")

    assert sp.lines[0].text == "Int. Łódź"
    assert sp.getExportText(0) == "INT. ŁÓDŹ"


def testInvalidCharsNotTyped():
    ctrl = newCtrl()
    sp = ctrl.sp

    # C1 control, soft hyphen, zero-width space, line separator, BOM
    for kc in (0x85, 0xAD, 0x200B, 0x2028, 0xFEFF):
        press(ctrl, KeyEvent(kc, wx.WXK_NONE))

    assert sp.lines[0].text == ""


# key codes above 255 are wx.WXK_ constants, which as code points are
# letters: WXK_HOME is 313 = "Ĺ", WXK_INSERT is 322 = "ł"
def testSpecialKeysNotTypedAsChars():
    ctrl = newCtrl()
    sp = ctrl.sp
    typeChars(ctrl, "abc")

    for kc in (wx.WXK_HOME, wx.WXK_INSERT, wx.WXK_F2, wx.WXK_END):
        press(ctrl, KeyEvent(wx.WXK_NONE, kc))

    assert sp.lines[0].text == "Abc"


def testCtrlWithCharAboveLatin1():
    ctrl = newCtrl()
    ed = ctrl.ed
    typeChars(ctrl, "abc")

    # must not be taken for CTRL+Home (MoveStartOfScript)
    ev = press(ctrl, KeyEvent(wx.WXK_HOME, wx.WXK_NONE, ctrl=True))
    assert ev.skipped
    assert ed.column == 3

    # CTRL+Home itself still works
    press(ctrl, KeyEvent(wx.WXK_NONE, wx.WXK_HOME, ctrl=True))
    assert ed.column == 0


# the character map and the names database insert characters with
# keys.MyKeyEvent
def testFakeKeyEvent():
    ctrl = newCtrl()
    sp = ctrl.sp

    for ch in "łódź €":
        press(ctrl, keys.MyKeyEvent(ord(ch)))

    assert sp.lines[0].text == "Łódź €"

    press(ctrl, keys.MyKeyEvent(wx.WXK_BACK))
    assert sp.lines[0].text == "Łódź "


def testPasteSystemClipboard():
    ctrl = newCtrl()
    sp = ctrl.sp
    text = "Łódź\x85\xad €\r\nc\u030capek\u200b Пётр\tΩ"

    class Clipboard:
        def Open(self):
            return True

        def Close(self):
            pass

        def UsePrimarySelection(self, primary):
            pass

        def IsSupported(self, df):
            return True

        def GetData(self, data):
            data.SetText(text)

    with mock.patch.object(wx, "TheClipboard", Clipboard()):
        ctrl.OnPasteSystemCb()

    assert [ln.text for ln in sp.lines] == ["Łódź €", "čapek Пётр|Ω"]


# in --test mode, typing "\xe5", "\xa4" or "\xbd" runs a debugging hook
# instead of inserting the character. the literals were once lost to a
# re-encoding of trelbyctrl.py, which left the hooks unreachable.
def testTestModeHooks():
    ctrl = newCtrl()
    ctrl.loadFile = mock.Mock()
    ctrl.cmdTest = mock.Mock()
    ctrl.cmdSpeedTest = mock.Mock()

    with mock.patch.object(opts, "isTest", True, create=True):
        for c in "\xe5\xa4\xbd":
            ctrl.OnKeyChar(KeyEvent(ord(c), ord(c)))

    assert ctrl.loadFile.call_count == 1
    assert ctrl.loadFile.call_args[0][0].endswith("sample.trelby")
    assert ctrl.cmdTest.call_count == 1
    assert ctrl.cmdSpeedTest.call_count == 1
    assert ctrl.sp.lines[0].text == ""

    # outside test mode they're ordinary characters
    typeChars(ctrl, "\xe5\xa4\xbd")
    assert ctrl.sp.lines[0].text.lower() == "\xe5\xa4\xbd"
    assert ctrl.loadFile.call_count == 1


def testSpeedTest(capsys):
    ctrl = newCtrl()
    ctrl.Update = lambda: None

    with mock.patch.object(opts, "isTest", False, create=True):
        ctrl.cmdSpeedTest(screenplay.CommandState())

    out = capsys.readouterr().out
    assert "seconds per testUndoFullCopy" in out
    assert not ctrl.sp.isModified()


# commands.resolveKey, which OnKeyChar uses to tell typing from commands
def resolve(uc, kc, **mods):
    cfgGl = config.ConfigGlobal()

    return commands.resolveKey(cfgGl.getKeyMap(), uc, kc, **mods)


def testResolveKeyChars():
    assert resolve(ord("a"), ord("A")) == ("a", None)
    assert resolve(ord("Å"), wx.WXK_NONE) == ("Å", None)
    assert resolve(0x0142, wx.WXK_NONE) == ("ł", None)

    # not typeable: C1 control, zero-width space
    assert resolve(0x85, wx.WXK_NONE) == (None, None)
    assert resolve(0x200B, wx.WXK_NONE) == (None, None)


def testResolveKeyCommands():
    char, cmd = resolve(wx.WXK_NONE, wx.WXK_LEFT)
    assert (char, cmd.name) == (None, "MoveLeft")

    # the SHIFT versions of movement keys select
    char, cmd = resolve(wx.WXK_NONE, wx.WXK_LEFT, shift=True)
    assert cmd.name == "MoveLeft"

    char, cmd = resolve(ord("s"), ord("S"), alt=True)
    assert (char, cmd.name) == (None, "ChangeToScene")

    # a character above 255 isn't a key code: with CTRL, "Ĺ" (313) isn't
    # CTRL+Home
    assert resolve(wx.WXK_HOME, wx.WXK_NONE, ctrl=True) == (None, None)

    char, cmd = resolve(wx.WXK_NONE, wx.WXK_HOME, ctrl=True)
    assert cmd.name == "MoveStartOfScript"

    assert resolve(ord("q"), ord("Q"), ctrl=True, alt=True) == (None, None)


# fixed menu commands' keys are their menu items' accelerators, so they're
# not in the key map
def testKeyMapLeavesOutFixedMenuCommands():
    cfgGl = config.ConfigGlobal()
    names = {cmd.name for cmd in cfgGl.getKeyMap().values()}

    assert "MoveLeft" in names
    assert "ToggleBold" in names
    assert "Undo" not in names
    assert "SaveScript" not in names
