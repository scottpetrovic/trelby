from types import SimpleNamespace
from unittest import mock

import wx

import tests.u as u
import trelby.config as config
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


# stands in for the wx control: OnKeyChar and the cmd* methods come from
# MyCtrl, while the screen updates do nothing
class FakeCtrl:
    def __init__(self, sp):
        cfgGl = config.ConfigGlobal()
        cfgGl.addShiftKeys()
        kbdCommands = {}

        for cmd in cfgGl.commands:
            if not (cmd.isFixed and cmd.isMenu):
                for key in cmd.keys:
                    kbdCommands[key] = cmd

        self.sp = sp
        self.gd = SimpleNamespace(
            cfgGl=cfgGl, mainFrame=SimpleNamespace(kbdCommands=kbdCommands)
        )

    def __getattr__(self, name):
        return getattr(trelbyctrl.MyCtrl, name).__get__(self)

    def makeLineVisible(self, *args):
        pass

    def updateScreen(self):
        pass


def newCtrl():
    sp = u.new()
    sp.lines[0].lt = screenplay.ACTION

    return FakeCtrl(sp)


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
    typeChars(ctrl, "abc")

    press(ctrl, KeyEvent(wx.WXK_NONE, wx.WXK_LEFT))
    press(ctrl, KeyEvent(wx.WXK_NONE, wx.WXK_LEFT))
    assert sp.column == 1

    press(ctrl, KeyEvent(wx.WXK_NONE, wx.WXK_HOME))
    assert sp.column == 0

    press(ctrl, KeyEvent(wx.WXK_NONE, wx.WXK_RIGHT))
    typeChars(ctrl, "ä")
    assert sp.lines[0].text == "Aäbc"


def testShiftArrowSelects():
    ctrl = newCtrl()
    sp = ctrl.sp
    typeChars(ctrl, "abc")

    press(ctrl, KeyEvent(wx.WXK_NONE, wx.WXK_LEFT, shift=True))
    assert sp.mark is not None


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
