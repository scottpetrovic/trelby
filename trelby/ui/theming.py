import wx

import trelby.misc as misc

# the colors of dialogs and other windows besides the main one. those use
# native controls, which wx draws in the system's light or dark colors.
# themeWindow gives them the theme's colors where the native controls allow
# it (including push buttons), and the classes in widgets stand in for the
# ones that don't: Separator for wx.StaticLine, ThemedListBox for wx.ListBox
# and wx.CheckListBox, and ThemedListbook for wx.Treebook.


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

    # the windows holding buttons that _padButton made bigger
    grown = set()
    _themeTree(win, cfgGui, grown)

    for w in grown:
        w.Layout()

    win.Refresh()


# theme the open windows that have been themed before in the current theme
def themeAllWindows():
    for w in wx.GetTopLevelWindows():
        if getattr(w, "themed", False):
            themeWindow(w)


def _themeTree(w, cfgGui, grown):
    if hasattr(w, "applyTheme"):
        w.applyTheme(cfgGui)

        return

    if isinstance(w, (wx.TextCtrl, wx.SpinCtrl, wx.SpinCtrlDouble, wx.ListCtrl)):
        _setColors(w, cfgGui.textBgColor, cfgGui.textColor)
    elif isinstance(w, wx.Button) and not isinstance(w, wx.BitmapButton):
        # not toggle buttons, which are wx.AnyButtons but not wx.Buttons
        _setColors(w, cfgGui.buttonBgColor, cfgGui.tabTextColor)
        _drawButtonThemed(w)

        if _padButton(w):
            grown.add(w.GetParent())
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
            _themeTree(c, cfgGui, grown)


# give push button w more room around its label than the native size, which
# is snug, unless it was made to fit its label exactly. returns whether its
# minimum size changed.
def _padButton(w):
    if w.HasFlag(wx.BU_EXACTFIT):
        return False

    # the best size includes the minimum size, so clear that first
    old = w.GetMinSize()
    w.SetMinSize(wx.DefaultSize)
    w.InvalidateBestSize()
    best = w.GetBestSize()
    textW = w.GetTextExtent(w.GetLabelText()).width
    size = wx.Size(
        max(best.width, textW + w.FromDIP(32)), best.height + w.FromDIP(6)
    )

    w.SetMinSize(size)

    return size != old


# BM_GETSTATE, and the bits of its result we use
_BM_GETSTATE = 0xF2
_BST_PUSHED = 0x4
_BST_FOCUS = 0x8


# draw push button w ourselves from now on, in its background and
# foreground colors: a rounded rectangle with a border in the text's color.
# only on Windows, where the native button's border can't be colored; other
# systems keep it, with the colors.
def _drawButtonThemed(w):
    if not misc.isWindows or getattr(w, "drawnThemed", False):
        return

    w.drawnThemed = True
    w.SetBackgroundStyle(wx.BG_STYLE_PAINT)
    w.Bind(wx.EVT_PAINT, _onButtonPaint)

    for evt in (
        wx.EVT_ENTER_WINDOW,
        wx.EVT_LEAVE_WINDOW,
        wx.EVT_LEFT_DOWN,
        wx.EVT_LEFT_UP,
        wx.EVT_SET_FOCUS,
        wx.EVT_KILL_FOCUS,
        wx.EVT_MOUSE_CAPTURE_LOST,
    ):
        w.Bind(evt, _onButtonStateChange)


def _onButtonStateChange(event):
    event.GetEventObject().Refresh()
    event.Skip()


# user32's SendMessageW, with its argument types (a private copy, so as not
# to change ctypes.windll's for other code), made on first use
_sendMessageW = None


def _sendMessage(hwnd, msg, wParam, lParam):
    global _sendMessageW

    if _sendMessageW is None:
        import ctypes
        from ctypes import wintypes

        f = ctypes.WinDLL("user32").SendMessageW
        f.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        f.restype = wintypes.LPARAM
        _sendMessageW = f

    return _sendMessageW(hwnd, msg, wParam, lParam)


def _onButtonPaint(event):
    w = event.GetEventObject()
    dc = wx.AutoBufferedPaintDC(w)
    dc.SetBackground(wx.Brush(w.GetParent().GetBackgroundColour()))
    dc.Clear()

    # the native button keeps track of being pushed (by the mouse or the
    # keyboard) and focused
    state = _sendMessage(w.GetHandle(), _BM_GETSTATE, 0, 0)
    hover = w.GetScreenRect().Contains(wx.GetMousePosition())

    bg = w.GetBackgroundColour()
    fg = w.GetForegroundColour()

    if not w.IsEnabled():
        fg = blendColors(fg, bg, 0.6)
    elif state & _BST_PUSHED:
        bg = blendColors(bg, fg, 0.25)
    elif hover:
        bg = blendColors(bg, fg, 0.12)

    width, height = w.GetClientSize()
    penW = w.FromDIP(2 if state & _BST_FOCUS else 1)

    gc = wx.GraphicsContext.Create(dc)
    gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(fg).Width(penW)))
    gc.SetBrush(wx.Brush(bg))
    gc.DrawRoundedRectangle(
        penW / 2, penW / 2, width - penW, height - penW, w.FromDIP(5)
    )

    label = w.GetLabelText()
    gc.SetFont(w.GetFont(), fg)
    tw, th = gc.GetTextExtent(label)
    gc.DrawText(label, (width - tw) / 2, (height - th) / 2)

    # the drawing reaches the buffer when gc goes, and the buffer the
    # screen when dc goes, so gc must go first
    del gc
    del dc


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
