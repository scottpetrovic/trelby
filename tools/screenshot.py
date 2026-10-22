"""Take the README's screenshot: Trelby on the sample script, in page view
with the outline open and the light theme, saved to media/screenshot.png.

Run from the repo root: .venv/Scripts/python tools/screenshot.py [out.png]
Windows only (it grabs the window from the screen). Uses --test, so the
config in ./.trelby/ is used, and quits without saving any state."""

import ctypes
import ctypes.wintypes
import os
import sys

import wx
from PIL import ImageGrab

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import trelby.screenplay as screenplay
import trelby.trelby as app
import trelby.ui.themes as themes

OUT = sys.argv[1] if len(sys.argv) > 1 else "media/screenshot.png"
SIZE = (1600, 1000)
# the scene the cursor goes to, a few lines into it, with the end of the
# scene before it at the top of the window
SCENE = 2


def capture(frame, path):
    hwnd = frame.GetHandle()

    # the window without its invisible resize borders, in physical pixels
    rect = ctypes.wintypes.RECT()
    ctypes.windll.dwmapi.DwmGetWindowAttribute(
        hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect)
    )
    box = (rect.left, rect.top, rect.right, rect.bottom)
    ImageGrab.grab(box, all_screens=True).save(path)


def setUp():
    gd = wx.GetApp().gd
    frame = gd.mainFrame
    frame.SetSize(frame.FromDIP(wx.Size(*SIZE)))
    frame.Center()
    frame.setViewMode(gd.VIEWMODE_LAYOUT)
    frame.showSideTab(gd.SIDE_OUTLINE)

    ctrl = frame.panel.ctrl
    sp = ctrl.sp
    heads = [i for i, ln in enumerate(sp.lines) if ln.lt == screenplay.SCENE]
    line = heads[SCENE] + 6
    ctrl.ed.gotoPos(line, 9)
    ctrl.ed.setTopLine(heads[SCENE] - 9)
    ctrl.updateScreen()
    # on top, since it's grabbed from the screen
    frame.SetWindowStyle(frame.GetWindowStyle() | wx.STAY_ON_TOP)
    frame.Raise()

    wx.CallLater(1500, finish, frame)


def finish(frame):
    try:
        capture(frame, OUT)
        print("saved", OUT)
    finally:
        os._exit(0)


def onInit(self, orig=app.MyApp.OnInit):
    ok = orig(self)
    wx.CallLater(1500, setUp)

    return ok


def loadGlobalCfg(s, orig=app.loadGlobalCfg):
    cfgGl = orig(s)
    cfgGl.theme = themes.LIGHT.name

    return cfgGl


app.MyApp.OnInit = onInit
app.loadGlobalCfg = loadGlobalCfg
sys.argv = [sys.argv[0], "--test", "trelby/sample.trelby"]
app.main()
