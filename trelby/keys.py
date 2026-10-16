# key presses, as used for the keyboard commands (see commands.py). this
# doesn't need wx, so the config can be loaded without it.

import trelby.textutil as textutil

# the wx.WXK_* key codes Key uses, so that it and the default key bindings
# don't need to import wx. they're part of the config file format (see
# Key.toInt), and tests/test_keys.py checks they match wx's.
WXK_NONE = 0
WXK_BACK = 8
WXK_TAB = 9
WXK_RETURN = 13
WXK_ESCAPE = 27
WXK_SPACE = 32
WXK_DELETE = 127
WXK_END = 312
WXK_HOME = 313
WXK_LEFT = 314
WXK_UP = 315
WXK_RIGHT = 316
WXK_DOWN = 317
WXK_INSERT = 322
WXK_PAGEUP = 366
WXK_PAGEDOWN = 367
WXK_F1 = 340
WXK_F2 = 341
WXK_F3 = 342
WXK_F4 = 343
WXK_F5 = 344
WXK_F6 = 345
WXK_F7 = 346
WXK_F8 = 347
WXK_F9 = 348
WXK_F10 = 349
WXK_F11 = 350
WXK_F12 = 351
WXK_F13 = 352
WXK_F14 = 353
WXK_F15 = 354
WXK_F16 = 355
WXK_F17 = 356
WXK_F18 = 357
WXK_F19 = 358
WXK_F20 = 359
WXK_F21 = 360
WXK_F22 = 361
WXK_F23 = 362
WXK_F24 = 363


# fake key event, supports same operations as the real one
class MyKeyEvent:
    def __init__(self, kc=0):
        # Unicode code point of the character, or a key code below 32 such
        # as WXK_BACK
        self.kc = kc

        self.controlDown = False
        self.altDown = False
        self.shiftDown = False

    # like real events, characters above 255 have no key code (WXK_NONE),
    # since key codes above 255 are WXK_* constants
    def GetKeyCode(self):
        return self.kc if self.kc < 256 else 0

    def GetUnicodeKey(self):
        return self.kc

    def ControlDown(self):
        return self.controlDown

    def AltDown(self):
        return self.altDown

    def ShiftDown(self):
        return self.shiftDown

    def Skip(self):
        pass


# one key press
class Key:
    # names toStr shows for keys that aren't printable characters. 1-26 are
    # CTRL+A..Z, which Key stores as those codes (see __init__). 8, 9 and
    # 13 (CTRL+H, I and M) have no entries of their own, since they're the
    # same codes as WXK_BACK, TAB and RETURN.
    keyMap = {
        1: "A",
        2: "B",
        3: "C",
        4: "D",
        5: "E",
        6: "F",
        7: "G",
        # CTRL+Enter = 10 in Windows
        10: "Enter (Windows)",
        11: "K",
        12: "L",
        14: "N",
        15: "O",
        16: "P",
        17: "Q",
        18: "R",
        19: "S",
        20: "T",
        21: "U",
        22: "V",
        23: "W",
        24: "X",
        25: "Y",
        26: "Z",
        WXK_BACK: "Backspace",
        WXK_TAB: "Tab",
        WXK_RETURN: "Enter",
        WXK_ESCAPE: "Escape",
        WXK_DELETE: "Delete",
        WXK_END: "End",
        WXK_HOME: "Home",
        WXK_LEFT: "Left",
        WXK_UP: "Up",
        WXK_RIGHT: "Right",
        WXK_DOWN: "Down",
        WXK_PAGEUP: "Page up",
        WXK_PAGEDOWN: "Page down",
        WXK_INSERT: "Insert",
        WXK_F1: "F1",
        WXK_F2: "F2",
        WXK_F3: "F3",
        WXK_F4: "F4",
        WXK_F5: "F5",
        WXK_F6: "F6",
        WXK_F7: "F7",
        WXK_F8: "F8",
        WXK_F9: "F9",
        WXK_F10: "F10",
        WXK_F11: "F11",
        WXK_F12: "F12",
        WXK_F13: "F13",
        WXK_F14: "F14",
        WXK_F15: "F15",
        WXK_F16: "F16",
        WXK_F17: "F17",
        WXK_F18: "F18",
        WXK_F19: "F19",
        WXK_F20: "F20",
        WXK_F21: "F21",
        WXK_F22: "F22",
        WXK_F23: "F23",
        WXK_F24: "F24",
    }

    def __init__(self, kc, ctrl=False, alt=False, shift=False):

        # we don't want to handle ALT+a/ALT+A etc separately, so uppercase
        # input char combinations. a few Latin-1 letters uppercase to
        # characters above 255 ("ÿ" -> "Ÿ"), which would clash with the
        # WXK_ constants, so those are left as they are.
        if (kc < 256) and (ctrl or alt):
            up = ord(textutil.upper(chr(kc)))

            if up < 256:
                kc = up

        # even though the wxWidgets documentation clearly states that
        # CTRL+[A-Z] should be returned as keycodes 1-26, wxGTK2 2.6 does
        # not do this (wxGTK1 and wxMSG do follow the documentation).
        #
        # so, we normalize to the wxWidgets official form here if necessary.

        # "A" - "Z"
        if ctrl and (kc >= 65) and (kc <= 90):
            kc -= 64

        # ASCII/Latin-1 keycode (0-255) or one of the WXK_ constants (>255)
        self.kc = kc

        self.ctrl = ctrl
        self.alt = alt
        self.shift = shift

    # returns True if key is a valid input character
    def isValidInputChar(self):
        return not self.ctrl and not self.alt and self.isChar()

    # returns True if the key code is a character rather than a special key
    # like an arrow or F1. key codes only go up to 255, above that they are
    # WXK_ constants (WXK_LEFT is 314, which as a code point is "ĺ").
    def isChar(self):
        return (self.kc < 256) and textutil.isValidInputChar(self.kc)

    # toInt/fromInt serialize/deserialize to/from a 35-bit integer, laid
    # out like this:
    # bits 0-31:  keycode
    #        32:  Control
    #        33:  Alt
    #        34:  Shift

    def toInt(self):
        return (
            (self.kc & 0xFFFFFFFF)
            | (self.ctrl << 32)
            | (self.alt << 33)
            | (self.shift << 34)
        )

    @staticmethod
    def fromInt(val):
        return Key(val & 0xFFFFFFFF, (val >> 32) & 1, (val >> 33) & 1, (val >> 34) & 1)

    # construct from wx.KeyEvent
    @staticmethod
    def fromKE(ev):
        return Key(ev.GetKeyCode(), ev.ControlDown(), ev.AltDown(), ev.ShiftDown())

    def toStr(self):
        s = ""

        if self.ctrl:
            s += "CTRL+"

        if self.alt:
            s += "ALT+"

        if self.shift:
            s += "SHIFT+"

        if self.isChar():
            if self.kc == WXK_SPACE:
                s += "Space"
            else:
                s += chr(self.kc)
        else:
            kname = self.__class__.keyMap.get(self.kc)

            if kname:
                s += kname
            else:
                s += "UNKNOWN(%d)" % self.kc

        return s
