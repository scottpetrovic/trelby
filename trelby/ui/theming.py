import wx

import trelby.misc as misc

# the colors of dialogs and other windows besides the main one. those use
# native controls, which wx draws in the system's light or dark colors.
# themeWindow gives them the theme's colors where the native controls allow
# it, and the classes in widgets stand in for the ones that don't: Separator
# for wx.StaticLine, ThemedListBox for wx.ListBox and wx.CheckListBox, and
# ThemedListbook for wx.Treebook.


# the current configgui.ConfigGui, or None before the app has started
def currentCfgGui():
    gd = getattr(wx.GetApp(), "gd", None)

    return gd.cfgGui if gd else None


# whether the application is currently using a dark theme
def isDarkAppearance():
    return wx.SystemSettings.GetAppearance().IsDark()


# return color c1 mixed with c2, with a being the fraction of c2
def blendColors(c1, c2, a):
    return wx.Colour(
        *[
            int(v1 * (1.0 - a) + v2 * a)
            for v1, v2 in zip(c1.Get(False), c2.Get(False))
        ]
    )


# the colors themeWindow has given windows, as (r, g, b, a), to tell them
# from colors a window's own code has set
_themeColors = set()


# give top-level window 'win' and everything in it the colors of the theme
# in cfgGui (by default the current one): the background like the tab bar,
# and text fields like the page. windows with an applyTheme(cfgGui) method
# theme themselves. colors set by a window's own code, like a red error
# message, are kept. themeAllWindows calls this again when the theme
# changes.
def themeWindow(win, cfgGui=None):
    cfgGui = cfgGui or currentCfgGui()

    if not cfgGui:
        return

    win.themed = True
    setTitleBarColors(win, cfgGui)
    _themeTree(win, cfgGui)
    win.Refresh()


# theme the open windows that have been themed before in the current theme
def themeAllWindows():
    for w in wx.GetTopLevelWindows():
        if getattr(w, "themed", False):
            themeWindow(w)


def _themeTree(w, cfgGui):
    if hasattr(w, "applyTheme"):
        w.applyTheme(cfgGui)

        return

    if isinstance(w, (wx.TextCtrl, wx.SpinCtrl, wx.SpinCtrlDouble, wx.ListCtrl)):
        _setColors(w, cfgGui.textBgColor, cfgGui.textColor)
    elif isinstance(
        w,
        (
            wx.TopLevelWindow,
            wx.Panel,
            wx.Simplebook,
            wx.StaticText,
            wx.StaticBox,
            wx.CheckBox,
            wx.RadioButton,
        ),
    ):
        _setColors(w, cfgGui.tabBarBgColor, cfgGui.tabTextColor)

    for c in w.GetChildren():
        if not c.IsTopLevel():
            _themeTree(c, cfgGui)


# set w's colors, unless its own code has set them. a window whose color
# was never set, or is one an earlier call (of any theme) gave it, gets the
# new one. the catch is that a color some code set on purpose which
# happens to equal a theme color is replaced too.
def _setColors(w, bg, fg):
    if (not w.UseBackgroundColour()) or (
        w.GetBackgroundColour().Get() in _themeColors
    ):
        w.SetBackgroundColour(bg)

    if (not w.UseForegroundColour()) or (
        w.GetForegroundColour().Get() in _themeColors
    ):
        w.SetForegroundColour(fg)

    _themeColors.update((bg.Get(), fg.Get()))


# DwmSetWindowAttribute attributes for the title bar's colors (Windows 11)
_DWMWA_BORDER_COLOR = 34
_DWMWA_CAPTION_COLOR = 35
_DWMWA_TEXT_COLOR = 36


# show the title bar of top-level window 'win' in the theme's colors. does
# nothing before Windows 11, or on other systems.
def setTitleBarColors(win, cfgGui):
    if not misc.isWindows:
        return

    import ctypes

    for attr, color in (
        (_DWMWA_CAPTION_COLOR, cfgGui.tabBarBgColor),
        (_DWMWA_TEXT_COLOR, cfgGui.tabTextColor),
        (_DWMWA_BORDER_COLOR, cfgGui.tabBorderColor),
    ):
        # a COLORREF, 0x00bbggrr
        v = ctypes.c_uint(color.Red() | (color.Green() << 8) | (color.Blue() << 16))

        try:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                win.GetHandle(), attr, ctypes.byref(v), ctypes.sizeof(v)
            )
        except (AttributeError, OSError):
            return
