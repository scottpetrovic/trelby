import types

import wx

import trelby.misc as misc

# the colors of dialogs and other windows besides the main one. those use
# native controls, which wx draws in the system's light or dark colors.
# themeWindow gives them the theme's colors where the native controls allow
# it (including push buttons and drop-down lists), and the classes in
# widgets stand in for the ones that don't: Separator for wx.StaticLine,
# ThemedListBox for wx.ListBox and wx.CheckListBox, ThemedListbook for
# wx.Treebook, and ThemedTextCtrl for a multiline wx.TextCtrl, whose
# scrollbars ignore the colors.


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

        if not isinstance(w, wx.ListCtrl) and _padTextField(w):
            grown.add(w.GetParent())
    elif isinstance(w, wx.Button) and not isinstance(w, wx.BitmapButton):
        # not toggle buttons, which are wx.AnyButtons but not wx.Buttons
        _setColors(w, cfgGui.buttonBgColor, cfgGui.tabTextColor)
        _drawButtonThemed(w)

        if _padButton(w):
            grown.add(w.GetParent())
    elif isinstance(w, (wx.Choice, wx.ComboBox)):
        # drop-down lists look like the buttons
        _setColors(w, cfgGui.buttonBgColor, cfgGui.tabTextColor)

        if isinstance(w, wx.Choice) or w.HasFlag(wx.CB_READONLY):
            _drawChoiceThemed(w)
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


# give text field w (a wx.TextCtrl or a spin control) more room around its
# text than the native field: margins at the sides, and for a single-line
# wx.TextCtrl, more height, half of it above the text. (a spin control's
# native field draws its border inside its client area, so on Windows its
# text can't be moved down from the border.) returns whether its minimum
# size changed.
def _padTextField(w):
    pad = w.FromDIP(5)
    setTextMargins(w, pad, pad)

    if not isinstance(w, wx.TextCtrl) or w.IsMultiLine():
        return False

    vPad = w.FromDIP(3)

    # the best size includes the minimum size, so clear its height first
    old = w.GetMinSize()
    w.SetMinSize(wx.Size(old.width, -1))
    w.InvalidateBestSize()
    size = wx.Size(old.width, max(old.height, w.GetBestSize().height + 2 * vPad))

    w.SetMinSize(size)

    # Windows keeps a single-line field's text at the top, so all the extra
    # height would be below it
    if misc.isWindows:
        _centerEditText(w, vPad)

    return size != old


# the native text field of text field w (a wx.TextCtrl or a spin control).
# Windows only.
def _editHwnd(w):
    hwnd = w.GetHandle()

    if isinstance(w, (wx.SpinCtrl, wx.SpinCtrlDouble)):
        hwnd = sendMessage(hwnd, _UDM_GETBUDDY, 0, 0) or hwnd

    return hwnd


# window messages, hit test results and SetWindowPos flags
_WM_NCDESTROY = 0x82
_WM_NCCALCSIZE = 0x83
_WM_NCHITTEST = 0x84
_WM_NCPAINT = 0x85
_HTNOWHERE = 0
_HTCLIENT = 1
_HTBORDER = 18
_SWP_FRAME = 0x1 | 0x2 | 0x4 | 0x10 | 0x20

# the Win32 functions _centerEditText uses, set up on first use
_win = None

# the fields _centerEditText has done, by native window: (the wx window,
# the pixels taken off the client area at the top and at the bottom)
_centered = {}


# move the text of single-line wx.TextCtrl w down by pad pixels, so that
# with pad pixels more height than the native field, the text is as far
# from the top as from the bottom: the client area, where the native field
# draws, gets pad pixels smaller at the top and at the bottom, and those
# strips are drawn in its background color. clicks in them go to the
# field. Windows only.
def _centerEditText(w, pad):
    _initWin()
    hwnd = w.GetHandle()

    if hwnd not in _centered:
        _win.SetWindowSubclass(hwnd, _win.proc, 1, 0)

    _centered[hwnd] = (w, pad)

    # makes Windows ask for the client area again, and redraw the frame
    _win.user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, _SWP_FRAME)


def _initWin():
    global _win

    if _win:
        return

    import ctypes
    from ctypes import wintypes

    LRESULT = ctypes.c_ssize_t
    SUBCLASSPROC = ctypes.WINFUNCTYPE(
        LRESULT,
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
        ctypes.c_size_t,
        ctypes.c_size_t,
    )

    comctl32 = ctypes.WinDLL("comctl32")
    user32 = ctypes.WinDLL("user32")
    gdi32 = ctypes.WinDLL("gdi32")

    for f, res, args in (
        (
            comctl32.SetWindowSubclass,
            wintypes.BOOL,
            [wintypes.HWND, SUBCLASSPROC, ctypes.c_size_t, ctypes.c_size_t],
        ),
        (
            comctl32.RemoveWindowSubclass,
            wintypes.BOOL,
            [wintypes.HWND, SUBCLASSPROC, ctypes.c_size_t],
        ),
        (
            comctl32.DefSubclassProc,
            LRESULT,
            [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM],
        ),
        (user32.GetWindowDC, wintypes.HDC, [wintypes.HWND]),
        (user32.ReleaseDC, ctypes.c_int, [wintypes.HWND, wintypes.HDC]),
        (
            user32.GetWindowRect,
            wintypes.BOOL,
            [wintypes.HWND, ctypes.POINTER(wintypes.RECT)],
        ),
        (
            user32.GetClientRect,
            wintypes.BOOL,
            [wintypes.HWND, ctypes.POINTER(wintypes.RECT)],
        ),
        (
            user32.ClientToScreen,
            wintypes.BOOL,
            [wintypes.HWND, ctypes.POINTER(wintypes.POINT)],
        ),
        (
            user32.FillRect,
            ctypes.c_int,
            [wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.HBRUSH],
        ),
        (
            user32.SetWindowPos,
            wintypes.BOOL,
            [wintypes.HWND, wintypes.HWND] + [ctypes.c_int] * 4 + [wintypes.UINT],
        ),
        (gdi32.CreateSolidBrush, wintypes.HBRUSH, [wintypes.DWORD]),
        (gdi32.DeleteObject, wintypes.BOOL, [wintypes.HGDIOBJ]),
    ):
        f.restype = res
        f.argtypes = args

    def proc(hwnd, msg, wParam, lParam, idSubclass, refData):
        res = comctl32.DefSubclassProc(hwnd, msg, wParam, lParam)
        w, pad = _centered.get(hwnd, (None, 0))

        if msg == _WM_NCDESTROY:
            comctl32.RemoveWindowSubclass(hwnd, _win.proc, 1)
            _centered.pop(hwnd, None)
        elif not w:
            pass
        elif msg == _WM_NCCALCSIZE:
            # the new client area is the first rectangle lParam points to,
            # whatever wParam says
            rc = wintypes.RECT.from_address(lParam)

            if rc.bottom - rc.top > 2 * pad:
                rc.top += pad
                rc.bottom -= pad
        elif msg == _WM_NCPAINT:
            _paintStrips(hwnd, w, pad)
        elif msg == _WM_NCHITTEST and res in (_HTNOWHERE, _HTBORDER):
            res = _HTCLIENT

        return res

    _win = types.SimpleNamespace(
        proc=SUBCLASSPROC(proc),
        SetWindowSubclass=comctl32.SetWindowSubclass,
        user32=user32,
        gdi32=gdi32,
        ctypes=ctypes,
        wintypes=wintypes,
    )


# draw the strips _centerEditText took off native window hwnd's client
# area, in the background color of w, the wx window it belongs to
def _paintStrips(hwnd, w, pad):
    wt = _win.wintypes
    u = _win.user32

    wr = wt.RECT()
    cr = wt.RECT()
    pt = wt.POINT(0, 0)
    u.GetWindowRect(hwnd, _win.ctypes.byref(wr))
    u.GetClientRect(hwnd, _win.ctypes.byref(cr))
    u.ClientToScreen(hwnd, _win.ctypes.byref(pt))

    # the client area in window coordinates
    x = pt.x - wr.left
    y = pt.y - wr.top

    c = w.GetBackgroundColour()
    brush = _win.gdi32.CreateSolidBrush(c.Red() | (c.Green() << 8) | (c.Blue() << 16))
    hdc = u.GetWindowDC(hwnd)

    for top in (y - pad, y + cr.bottom):
        r = wt.RECT(x, top, x + cr.right, top + pad)
        u.FillRect(hdc, _win.ctypes.byref(r), brush)

    u.ReleaseDC(hwnd, hdc)
    _win.gdi32.DeleteObject(brush)


# EM_SETMARGINS, and its flags for the left and right margins
_EM_SETMARGINS = 0xD3
_EC_LEFTMARGIN = 0x1
_EC_RIGHTMARGIN = 0x2

# UDM_GETBUDDY: the text field a spin control's arrows belong to
_UDM_GETBUDDY = 0x46A


# set the space between the edges of text field w (a wx.TextCtrl or a spin
# control) and its text, in pixels. the right margin is only set on
# Windows.
def setTextMargins(w, left, right):
    if not misc.isWindows:
        if hasattr(w, "SetMargins"):
            w.SetMargins(left)

        return

    sendMessage(
        _editHwnd(w),
        _EM_SETMARGINS,
        _EC_LEFTMARGIN | _EC_RIGHTMARGIN,
        (left & 0xFFFF) | ((right & 0xFFFF) << 16),
    )


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
_sendMessageFn = None


# send Windows message msg to window hwnd, and return the result. Windows
# only.
def sendMessage(hwnd, msg, wParam, lParam):
    global _sendMessageFn

    if _sendMessageFn is None:
        import ctypes
        from ctypes import wintypes

        f = ctypes.WinDLL("user32").SendMessageW
        f.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        f.restype = wintypes.LPARAM
        _sendMessageFn = f

    return _sendMessageFn(hwnd, msg, wParam, lParam)


def _onButtonPaint(event):
    w = event.GetEventObject()
    dc = wx.AutoBufferedPaintDC(w)

    # the native button keeps track of being pushed (by the mouse or the
    # keyboard) and focused
    state = sendMessage(w.GetHandle(), _BM_GETSTATE, 0, 0)
    gc, fg = _paintFrame(w, dc, state & _BST_PUSHED, state & _BST_FOCUS)

    width, height = w.GetClientSize()
    label = w.GetLabelText()
    tw, th = gc.GetTextExtent(label)
    gc.DrawText(label, (width - tw) / 2, (height - th) / 2)

    # the drawing reaches the buffer when gc goes, and the buffer the
    # screen when dc goes, so gc must go first
    del gc
    del dc


# CB_GETDROPPEDSTATE: whether a combo box's list is open
_CB_GETDROPPEDSTATE = 0x157


# draw drop-down list w (a wx.Choice or a read-only wx.ComboBox) ourselves
# from now on, like _drawButtonThemed's buttons, with an arrow at the right.
# the list that drops down stays native. only on Windows, like the buttons.
def _drawChoiceThemed(w):
    if not misc.isWindows or getattr(w, "drawnThemed", False):
        return

    w.drawnThemed = True
    w.SetBackgroundStyle(wx.BG_STYLE_PAINT)
    w.Bind(wx.EVT_PAINT, _onChoicePaint)

    for evt in (
        wx.EVT_ENTER_WINDOW,
        wx.EVT_LEAVE_WINDOW,
        wx.EVT_SET_FOCUS,
        wx.EVT_KILL_FOCUS,
        wx.EVT_COMBOBOX_DROPDOWN,
        wx.EVT_COMBOBOX_CLOSEUP,
    ):
        w.Bind(evt, _onButtonStateChange)


def _onChoicePaint(event):
    w = event.GetEventObject()
    dc = wx.AutoBufferedPaintDC(w)

    dropped = sendMessage(w.GetHandle(), _CB_GETDROPPEDSTATE, 0, 0)
    gc, fg = _paintFrame(w, dc, dropped, w.HasFocus())

    width, height = w.GetClientSize()

    # the native size leaves 28 pixels beside the longest item, which this
    # layout fits in
    pad = w.FromDIP(6)

    # the arrow: a chevron pointing down, at the right
    arrowW = w.FromDIP(8)
    ax = width - w.FromDIP(7) - arrowW
    ay = (height - arrowW / 2) / 2
    gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(fg).Width(w.FromDIP(3) / 2)))
    gc.StrokeLines([(ax, ay), (ax + arrowW / 2, ay + arrowW / 2), (ax + arrowW, ay)])

    gc.Clip(pad, 0, ax - w.FromDIP(4) - pad, height)
    label = w.GetStringSelection()
    th = gc.GetTextExtent(label)[1]
    gc.DrawText(label, pad, (height - th) / 2)

    del gc
    del dc


# fill the paint dc of a control we draw ourselves (w) with its parent's
# background, and draw w's frame on it: a rounded rectangle in w's colors,
# lighter or darker when the mouse is over it or it's pushed, with a thicker
# border when it has the focus. returns a GraphicsContext on dc, with w's
# font set, and the text color.
def _paintFrame(w, dc, pushed, focused):
    dc.SetBackground(wx.Brush(w.GetParent().GetBackgroundColour()))
    dc.Clear()

    hover = w.GetScreenRect().Contains(wx.GetMousePosition())

    bg = w.GetBackgroundColour()
    fg = w.GetForegroundColour()

    if not w.IsEnabled():
        fg = blendColors(fg, bg, 0.6)
    elif pushed:
        bg = blendColors(bg, fg, 0.25)
    elif hover:
        bg = blendColors(bg, fg, 0.12)

    width, height = w.GetClientSize()
    penW = w.FromDIP(2 if focused else 1)

    gc = wx.GraphicsContext.Create(dc)
    gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(fg).Width(penW)))
    gc.SetBrush(wx.Brush(bg))
    gc.DrawRoundedRectangle(
        penW / 2, penW / 2, width - penW, height - penW, w.FromDIP(5)
    )
    gc.SetFont(w.GetFont(), fg)

    return gc, fg


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
