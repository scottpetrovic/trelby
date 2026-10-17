import types

import wx

import trelby.misc as misc

# the colors of dialogs and other windows besides the main one. those use
# native controls, which wx draws in the system's light or dark colors.
# themeWindow gives them the theme's colors where the native controls allow
# it (including push buttons, drop-down lists and list controls' column
# headers), and the classes in
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


# how much of the accent color is mixed into the background of a selected
# item in the lists and toolbar controls we draw ourselves, whose text keeps
# its normal color
ACCENT_TINT = 0.15

# how much of the text color is mixed into the background for the borders
# of the buttons and drop-down lists we draw ourselves, so that they don't
# stand out as much as the text
BORDER_STRENGTH = 0.5


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


# give the windows inside win the theme's colors, the way themeWindow does
# a top-level window's, for a window that themes itself (applyTheme) and
# holds native controls, like drop-down lists
def themeChildren(win, cfgGui):
    grown = set()

    for c in win.GetChildren():
        if not c.IsTopLevel():
            _themeTree(c, cfgGui, grown)

    for w in grown:
        w.Layout()


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

        if isinstance(w, wx.ListCtrl):
            if w.InReportView():
                _themeListHeader(w, cfgGui)
        elif _padTextField(w):
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

        if (isinstance(w, wx.Choice) or w.HasFlag(wx.CB_READONLY)) and misc.isWindows:
            _drawChoiceThemed(w, cfgGui)

            if _padChoice(w):
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


# the drop-down lists _padChoice has done, by native window, as
# SimpleNamespaces: ownMinSize, the minimum size their own code gave them,
# and fieldHeight, the height of the field showing the selected item. kept
# here rather than on the wx windows, since wxPython can drop a window's
# Python object, and what was stored on it, while the window lives on.
_choiceFields = {}

# the height wx adds to a drop-down list's field for the whole control
# (wxMSW's COMBO_HEIGHT_ADJ, which isn't scaled by the DPI)
_COMBO_HEIGHT_ADJ = 6


# give drop-down list w (one _drawChoiceThemed draws) more room around its
# text than the native size: more height, like the text fields, and more
# width for _onChoicePaint's margins, unless its own code set a width.
# returns whether its minimum size changed. Windows only.
def _padChoice(w):
    hwnd = w.GetHandle()
    f = _choiceFields.get(hwnd)

    if not f:
        f = _choiceFields[hwnd] = types.SimpleNamespace(ownMinSize=w.GetMinSize())
        w.Bind(wx.EVT_SIZE, _onChoiceSize)
        w.Bind(wx.EVT_WINDOW_DESTROY, _onChoiceDestroy)

    own = f.ownMinSize
    old = w.GetMinSize()

    # the best size includes the minimum size, so clear that first. wx
    # works it out from the font, so it's the native size even when the
    # native control hasn't got its size yet (on a page not shown).
    w.SetMinSize(own)
    w.InvalidateBestSize()
    best = w.GetBestSize()
    height = best.height + w.FromDIP(8)
    size = wx.Size(
        best.width + w.FromDIP(8) if own.width == -1 else own.width,
        max(own.height, height),
    )

    # the height is set on the native control: wx gives it its native
    # height again whenever it's resized to its best height, which
    # includes the minimum size, so _onChoiceSize sets it back
    f.fieldHeight = height - _COMBO_HEIGHT_ADJ
    sendMessage(hwnd, _CB_SETITEMHEIGHT, -1, f.fieldHeight)

    w.SetMinSize(size)

    return size != old


def _onChoiceSize(event):
    event.Skip()
    hwnd = event.GetEventObject().GetHandle()
    f = _choiceFields.get(hwnd)

    if f and sendMessage(hwnd, _CB_GETITEMHEIGHT, -1, 0) != f.fieldHeight:
        sendMessage(hwnd, _CB_SETITEMHEIGHT, -1, f.fieldHeight)


def _onChoiceDestroy(event):
    event.Skip()
    _choiceFields.pop(event.GetWindow().GetHandle(), None)


# give text field w (a wx.TextCtrl or a spin control) more room around its
# text than the native field, about as much as Windows 11's own text
# fields have: margins at the sides, and unless it has several lines, more
# height, half of it above the text. a spin control gets wider by its
# margins, since its native width only just fits its widest number.
# returns whether its minimum size changed.
def _padTextField(w):
    pad = w.FromDIP(8)
    setTextMargins(w, pad, pad)

    if isinstance(w, wx.TextCtrl) and w.IsMultiLine():
        return False

    vPad = w.FromDIP(4)
    isSpin = not isinstance(w, wx.TextCtrl)

    # the minimum size its own code gave it, before ours
    if not hasattr(w, "ownMinSize"):
        w.ownMinSize = w.GetMinSize()

    own = w.ownMinSize
    old = w.GetMinSize()

    # the best size includes the minimum size, so clear that first
    w.SetMinSize(own)
    w.InvalidateBestSize()
    best = w.GetBestSize()
    size = wx.Size(
        best.width + 2 * pad if (isSpin and own.width == -1) else own.width,
        max(own.height, best.height + 2 * vPad),
    )

    w.SetMinSize(size)

    # Windows keeps a single-line field's text at the top, so all the extra
    # height would be below it
    if misc.isWindows:
        _centerEditText(w, vPad, isSpin)

    return size != old


# the native text field of text field w (a wx.TextCtrl or a spin control).
# Windows only.
def _editHwnd(w):
    hwnd = w.GetHandle()

    if isinstance(w, (wx.SpinCtrl, wx.SpinCtrlDouble)):
        hwnd = sendMessage(hwnd, _UDM_GETBUDDY, 0, 0) or hwnd

    return hwnd


# window messages, hit test results and SetWindowPos flags
_WM_SETREDRAW = 0xB
_WM_PAINT = 0xF
_WM_ERASEBKGND = 0x14
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

# the fields _centerEditText has done, by native window, as
# SimpleNamespaces: w, the wx window; pad, the pixels taken off the client
# area at the top and at the bottom; ownBorder, whether we draw its border
# (see _centerEditText); and borderColor, that border's color as a
# COLORREF, or None until the field has drawn it.
_centered = {}


# move the text of single-line text field w (a wx.TextCtrl or a spin
# control) down by pad pixels, so that with pad pixels more height than the
# native field, the text is as far from the top as from the bottom: the
# client area of its native field, where the field draws, gets pad pixels
# smaller at the top and at the bottom, and those strips are drawn in its
# background color. clicks in them go to the field.
#
# a wx.TextCtrl's border is outside the client area (wx draws it), but a
# spin control's field draws its own, 1 pixel wide, at the edges of the
# client area, which would leave the strips outside it. so with ownBorder,
# its top and bottom lines are covered up after the field draws, and the
# border is drawn again around the whole field, in the color the field
# used. Windows only.
def _centerEditText(w, pad, ownBorder=False):
    _initWin()
    hwnd = _editHwnd(w)

    if hwnd not in _centered:
        _win.SetWindowSubclass(hwnd, _win.proc, 1, 0)
        _centered[hwnd] = types.SimpleNamespace(borderColor=None)

    f = _centered[hwnd]
    f.w = w
    f.pad = pad
    f.ownBorder = ownBorder

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
        (
            user32.ScreenToClient,
            wintypes.BOOL,
            [wintypes.HWND, ctypes.POINTER(wintypes.POINT)],
        ),
        (user32.GetCursorPos, wintypes.BOOL, [ctypes.POINTER(wintypes.POINT)]),
        (user32.GetCapture, wintypes.HWND, []),
        (
            user32.InvalidateRect,
            wintypes.BOOL,
            [wintypes.HWND, ctypes.c_void_p, wintypes.BOOL],
        ),
        (user32.BeginPaint, wintypes.HDC, [wintypes.HWND, ctypes.c_void_p]),
        (user32.EndPaint, wintypes.BOOL, [wintypes.HWND, ctypes.c_void_p]),
        (
            gdi32.BitBlt,
            wintypes.BOOL,
            [wintypes.HDC] + [ctypes.c_int] * 4 + [wintypes.HDC]
            + [ctypes.c_int] * 2 + [wintypes.DWORD],
        ),
        (gdi32.CreateSolidBrush, wintypes.HBRUSH, [wintypes.DWORD]),
        (gdi32.DeleteObject, wintypes.BOOL, [wintypes.HGDIOBJ]),
        (gdi32.GetPixel, wintypes.DWORD, [wintypes.HDC, ctypes.c_int, ctypes.c_int]),
        (gdi32.GetLayout, wintypes.DWORD, [wintypes.HDC]),
    ):
        f.restype = res
        f.argtypes = args

    def proc(hwnd, msg, wParam, lParam, idSubclass, refData):
        res = comctl32.DefSubclassProc(hwnd, msg, wParam, lParam)
        f = _centered.get(hwnd)

        if msg == _WM_NCDESTROY:
            comctl32.RemoveWindowSubclass(hwnd, _win.proc, 1)
            _centered.pop(hwnd, None)
        elif not f:
            pass
        elif msg == _WM_NCCALCSIZE:
            # the new client area is the first rectangle lParam points to,
            # whatever wParam says
            rc = wintypes.RECT.from_address(lParam)

            if rc.bottom - rc.top > 2 * f.pad:
                rc.top += f.pad
                rc.bottom -= f.pad
        elif msg == _WM_NCPAINT:
            _paintPadding(hwnd, f, False)
        elif msg == _WM_PAINT and f.ownBorder:
            _paintPadding(hwnd, f, True)
        elif msg == _WM_NCHITTEST and res in (_HTNOWHERE, _HTBORDER):
            res = _HTCLIENT

        return res

    # the subclass procedure of the list control headers _themeListHeader
    # has done
    def headerProc(hwnd, msg, wParam, lParam, idSubclass, refData):
        h = _headers.get(hwnd)

        if msg == _WM_NCDESTROY:
            comctl32.RemoveWindowSubclass(hwnd, _win.headerProc, 2)
            _headers.pop(hwnd, None)
        elif h and h.w and msg == _WM_PAINT:
            _paintListHeader(hwnd, h)

            return 0
        elif h and msg == _WM_ERASEBKGND:
            return 1

        return comctl32.DefSubclassProc(hwnd, msg, wParam, lParam)

    # the subclass procedure of the drop-down lists' lists that
    # _drawChoiceThemed has done
    def listProc(hwnd, msg, wParam, lParam, idSubclass, refData):
        def default():
            return comctl32.DefSubclassProc(hwnd, msg, wParam, lParam)

        lst = _choiceLists.get(hwnd)

        if msg == _WM_NCDESTROY:
            comctl32.RemoveWindowSubclass(hwnd, _win.listProc, 3)
            _choiceLists.pop(hwnd, None)
        elif not lst:
            pass
        elif msg == _WM_PAINT:
            _paintChoiceList(hwnd, lst, None)

            return 0
        elif msg == _WM_PRINTCLIENT:
            _paintChoiceList(hwnd, lst, wParam)

            return 0
        elif msg == _WM_ERASEBKGND:
            return 1
        elif msg == _WM_NCPAINT:
            res = default()
            hdc = user32.GetWindowDC(hwnd)
            _paintChoiceListBorder(hwnd, lst, hdc)
            user32.ReleaseDC(hwnd, hdc)

            return res
        elif msg == _WM_PRINT:
            # what the drop-down animation draws from
            res = default()

            if lParam & _PRF_NONCLIENT:
                _paintChoiceListBorder(hwnd, lst, wParam)

            return res
        elif msg in _LIST_INPUT:
            # the list draws the item under the mouse or the keyboard
            # straight on the screen, not through WM_PAINT, unless its
            # drawing is turned off. so it is, and the list is drawn again
            # if that changed which item is selected or at the top.
            before = _choiceListState(hwnd)
            comctl32.DefSubclassProc(hwnd, _WM_SETREDRAW, 0, 0)

            try:
                res = default()
            finally:
                comctl32.DefSubclassProc(hwnd, _WM_SETREDRAW, 1, 0)

            if _choiceListState(hwnd) != before:
                user32.InvalidateRect(hwnd, None, False)

            return res

        return default()

    class COMBOBOXINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcItem", wintypes.RECT),
            ("rcButton", wintypes.RECT),
            ("stateButton", wintypes.DWORD),
            ("hwndCombo", wintypes.HWND),
            ("hwndItem", wintypes.HWND),
            ("hwndList", wintypes.HWND),
        ]

    user32.GetComboBoxInfo.restype = wintypes.BOOL
    user32.GetComboBoxInfo.argtypes = [wintypes.HWND, ctypes.POINTER(COMBOBOXINFO)]

    class HDITEMW(ctypes.Structure):
        _fields_ = [
            ("mask", wintypes.UINT),
            ("cxy", ctypes.c_int),
            ("pszText", wintypes.LPWSTR),
            ("hbm", wintypes.HBITMAP),
            ("cchTextMax", ctypes.c_int),
            ("fmt", ctypes.c_int),
            ("lParam", wintypes.LPARAM),
            ("iImage", ctypes.c_int),
            ("iOrder", ctypes.c_int),
            ("type", wintypes.UINT),
            ("pvFilter", ctypes.c_void_p),
            ("state", wintypes.UINT),
        ]

    _win = types.SimpleNamespace(
        proc=SUBCLASSPROC(proc),
        headerProc=SUBCLASSPROC(headerProc),
        listProc=SUBCLASSPROC(listProc),
        HDITEMW=HDITEMW,
        COMBOBOXINFO=COMBOBOXINFO,
        SetWindowSubclass=comctl32.SetWindowSubclass,
        user32=user32,
        gdi32=gdi32,
        ctypes=ctypes,
        wintypes=wintypes,
    )


# draw the strips _centerEditText took off native window hwnd's client
# area, in the background color of its wx window, and with f.ownBorder, the
# border around them. afterPaint is whether the field has just drawn its
# client area, and with it the border we cover up and take the color of.
def _paintPadding(hwnd, f, afterPaint):
    wt = _win.wintypes
    u = _win.user32
    gdi = _win.gdi32
    byref = _win.ctypes.byref

    wr = wt.RECT()
    cr = wt.RECT()
    pt = wt.POINT(0, 0)
    u.GetWindowRect(hwnd, byref(wr))
    u.GetClientRect(hwnd, byref(cr))
    u.ClientToScreen(hwnd, byref(pt))

    # the window's size, and its client area's position in it
    ww = wr.right - wr.left
    wh = wr.bottom - wr.top
    x = pt.x - wr.left
    y = pt.y - wr.top

    def fill(hdc, brush, *rects):
        for left, top, right, bottom in rects:
            u.FillRect(hdc, byref(wt.RECT(left, top, right, bottom)), brush)

    c = f.w.GetBackgroundColour()
    bg = gdi.CreateSolidBrush(c.Red() | (c.Green() << 8) | (c.Blue() << 16))
    hdc = u.GetWindowDC(hwnd)

    fill(
        hdc,
        bg,
        (x, y - f.pad, x + cr.right, y),
        (x, y + cr.bottom, x + cr.right, y + cr.bottom + f.pad),
    )

    if f.ownBorder:
        if afterPaint and cr.bottom > 2:
            # the field's border's left side, halfway down
            f.borderColor = gdi.GetPixel(hdc, x, y + cr.bottom // 2)

            # its top and bottom
            fill(
                hdc,
                bg,
                (x + 1, y, x + cr.right - 1, y + 1),
                (x + 1, y + cr.bottom - 1, x + cr.right - 1, y + cr.bottom),
            )

        # 0xFFFFFFFF: GetPixel's "no color"
        if f.borderColor not in (None, 0xFFFFFFFF):
            border = gdi.CreateSolidBrush(f.borderColor)
            fill(
                hdc,
                border,
                (0, 0, ww, 1),
                (0, wh - 1, ww, wh),
                (0, 0, 1, wh),
                (ww - 1, 0, ww, wh),
            )
            gdi.DeleteObject(border)

    u.ReleaseDC(hwnd, hdc)
    gdi.DeleteObject(bg)


# LVM_GETHEADER: a list control's header. HDM_GETITEMCOUNT, HDM_GETITEMRECT
# and HDM_HITTEST: a header's columns, and which one a point is on
# (HHT_ONHEADER: on a column, not on the divider between two).
_LVM_GETHEADER = 0x101F
_HDM_GETITEMCOUNT = 0x1200
_HDM_HITTEST = 0x1206
_HDM_GETITEMRECT = 0x1207
_HHT_ONHEADER = 0x2

# HDM_GETITEMW: a header column's HDITEMW, with the parts in its mask: the
# text and the format, whose justification bits say how the text is aligned
_HDM_GETITEMW = 0x120B
_HDI_TEXT = 0x2
_HDI_FORMAT = 0x4
_HDF_JUSTIFYMASK = 0x3
_HDF_RIGHT = 0x1
_HDF_CENTER = 0x2

# BitBlt's plain copy, and its flag for not mirroring the bitmap when the
# target is mirrored (a right-to-left window's), and GetLayout's flag for
# that
_SRCCOPY = 0xCC0020
_NOMIRRORBITMAP = 0x80000000
_LAYOUT_RTL = 0x1

# the list control headers _themeListHeader has done, by native window, as
# SimpleNamespaces: w, the wx.ListCtrl, and bg and fg, the colors.
_headers = {}


# give the column headers of report-view list control w the push buttons'
# colors. wx can only change the native header's text color, so on Windows
# we draw the header ourselves (_paintListHeader).
def _themeListHeader(w, cfgGui):
    bg, fg = cfgGui.buttonBgColor, cfgGui.tabTextColor
    w.SetHeaderAttr(wx.ItemAttr(fg, bg, wx.NullFont))

    if not misc.isWindows:
        return

    hwnd = sendMessage(w.GetHandle(), _LVM_GETHEADER, 0, 0)

    if not hwnd:
        return

    _initWin()

    if hwnd not in _headers:
        _win.SetWindowSubclass(hwnd, _win.headerProc, 2, 0)

    _headers[hwnd] = types.SimpleNamespace(w=w, bg=bg, fg=fg)
    _win.user32.InvalidateRect(hwnd, None, True)


# paint native list control header hwnd, for its WM_PAINT: the column
# labels on h.bg, lighter or darker under the mouse if the columns can be
# clicked, with lines between the columns and below them. it's drawn into
# a bitmap and copied to the header. a right-to-left header's dc is
# mirrored, which would mirror the text too, so there the bitmap is drawn
# with the columns where they appear on screen, and copied unmirrored.
def _paintListHeader(hwnd, h):
    wt = _win.wintypes
    u = _win.user32
    ctypes = _win.ctypes
    byref = ctypes.byref

    # a PAINTSTRUCT is 72 bytes on 64-bit Windows, 64 on 32-bit
    ps = ctypes.create_string_buffer(72)
    hdc = u.BeginPaint(hwnd, ps)

    try:
        cr = wt.RECT()
        u.GetClientRect(hwnd, byref(cr))
        width, height = cr.right, cr.bottom

        if width <= 0 or height <= 0:
            return

        rtl = bool(_win.gdi32.GetLayout(hdc) & _LAYOUT_RTL)

        # the column under the mouse, or -1
        info = (ctypes.c_int * 4)()
        pt = wt.POINT.from_buffer(info)
        u.GetCursorPos(byref(pt))
        u.ScreenToClient(hwnd, byref(pt))
        sendMessage(hwnd, _HDM_HITTEST, 0, ctypes.addressof(info))
        hot = info[3] if (info[2] & _HHT_ONHEADER) else -1

        w = h.w

        if w.HasFlag(wx.LC_NO_SORT_HEADER):
            hot = -1

        pressed = u.GetCapture() == hwnd

        bmp = wx.Bitmap(width, height)
        dc = wx.MemoryDC(bmp)
        dc.SetBackground(wx.Brush(h.bg))
        dc.Clear()
        # the memory dc has the system's DPI, not w's
        dc.SetFont(w.GetFont().Scaled(w.GetDPI().height / dc.GetPPI().height))
        dc.SetTextForeground(h.fg)

        line = wx.Pen(blendColors(h.bg, h.fg, 0.3))
        pad = w.FromDIP(6)
        r = wt.RECT()
        text = ctypes.create_unicode_buffer(256)
        item = _win.HDITEMW(
            mask=_HDI_TEXT | _HDI_FORMAT,
            pszText=ctypes.cast(text, wt.LPWSTR),
            cchTextMax=len(text),
        )

        for i in range(sendMessage(hwnd, _HDM_GETITEMCOUNT, 0, 0)):
            sendMessage(hwnd, _HDM_GETITEMRECT, i, ctypes.addressof(r))
            sendMessage(hwnd, _HDM_GETITEMW, i, ctypes.addressof(item))
            rect = wx.Rect(r.left, r.top, r.right - r.left, r.bottom - r.top)

            if rtl:
                rect.x = width - rect.x - rect.width

            if i == hot:
                dc.SetPen(wx.TRANSPARENT_PEN)
                dc.SetBrush(
                    wx.Brush(blendColors(h.bg, h.fg, 0.25 if pressed else 0.12))
                )
                dc.DrawRectangle(rect)

            # the alignment is from the start of the column, which in a
            # right-to-left one is its right
            if rtl:
                start, end = wx.ALIGN_RIGHT, wx.ALIGN_LEFT
            else:
                start, end = wx.ALIGN_LEFT, wx.ALIGN_RIGHT

            align = {
                _HDF_RIGHT: end,
                _HDF_CENTER: wx.ALIGN_CENTER_HORIZONTAL,
            }.get(item.fmt & _HDF_JUSTIFYMASK, start)
            label = wx.Control.Ellipsize(
                text.value, dc, wx.ELLIPSIZE_END, rect.width - 2 * pad
            )
            dc.DrawLabel(
                label,
                wx.Rect(rect).Deflate(pad, 0),
                align | wx.ALIGN_CENTER_VERTICAL,
            )

            # the line after the column
            x = rect.x - 1 if rtl else rect.right
            dc.SetPen(line)
            dc.DrawLine(x, rect.top, x, rect.bottom + 1)

        dc.SetPen(line)
        dc.DrawLine(0, height - 1, width, height - 1)

        rop = _SRCCOPY | (_NOMIRRORBITMAP if rtl else 0)
        _win.gdi32.BitBlt(hdc, 0, 0, width, height, int(dc.GetHandle()), 0, 0, rop)
        dc.SelectObject(wx.NullBitmap)
    finally:
        u.EndPaint(hwnd, ps)


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
# foreground colors: a rounded rectangle with a border (see _paintFrame).
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

    if w.GetLayoutDirection() == wx.Layout_RightToLeft:
        # see _prepareLabel
        del gc
        tw, th = _prepareLabel(w, dc, label, fg)
        dc.DrawText(label, (width - tw) // 2, (height - th) // 2)
    else:
        tw, th = gc.GetTextExtent(label)
        gc.DrawText(label, (width - tw) / 2, (height - th) / 2)

        # the drawing reaches the buffer when gc goes, and the buffer the
        # screen when dc goes, so gc must go first
        del gc

    del dc


# get dc ready for drawing label 'label' of right-to-left window w in
# color fg, and return the label's size. it's drawn on dc rather than a
# GraphicsContext, whose text is left to right (see
# gutil.setLanguageDirection), which would put punctuation at the wrong
# end. call this only once the GraphicsContext on dc is gone: until then,
# what's drawn on dc isn't mirrored.
def _prepareLabel(w, dc, label, fg):
    dc.SetFont(w.GetFont())
    dc.SetTextForeground(fg)

    return dc.GetTextExtent(label)


# CB_GETDROPPEDSTATE: whether a combo box's list is open. CB_SETITEMHEIGHT
# and CB_GETITEMHEIGHT: the height of its list's items (wParam 0), or of the
# field showing the selected one (-1).
_CB_GETDROPPEDSTATE = 0x157
_CB_SETITEMHEIGHT = 0x153
_CB_GETITEMHEIGHT = 0x154

# list box messages: LB_GETCURSEL, the selected item (the one under the
# mouse, in a drop-down list), LB_GETCOUNT, LB_GETTOPINDEX, the first item
# shown, and LB_GETITEMRECT
_LB_GETCURSEL = 0x188
_LB_GETCOUNT = 0x18B
_LB_GETTOPINDEX = 0x18E
_LB_GETITEMRECT = 0x198

# WM_PRINT, with its flag for drawing the frame, and WM_PRINTCLIENT
_WM_PRINT = 0x317
_WM_PRINTCLIENT = 0x318
_PRF_NONCLIENT = 0x2

# the messages after which a drop-down list's list may have to be drawn
# again: the mouse, the keyboard, scrolling, the focus, and the combo box
# setting the selection or the top item
_LIST_INPUT = frozenset(
    (
        0x7,  # WM_SETFOCUS
        0x8,  # WM_KILLFOCUS
        0x100,  # WM_KEYDOWN
        0x102,  # WM_CHAR
        0x113,  # WM_TIMER
        0x115,  # WM_VSCROLL
        0x186,  # LB_SETCURSEL
        0x197,  # LB_SETTOPINDEX
        0x200,  # WM_MOUSEMOVE
        0x201,  # WM_LBUTTONDOWN
        0x202,  # WM_LBUTTONUP
        0x203,  # WM_LBUTTONDBLCLK
        0x20A,  # WM_MOUSEWHEEL
        0x215,  # WM_CAPTURECHANGED
    )
)

# the lists of the drop-down lists _drawChoiceThemed has done, by native
# window, as SimpleNamespaces: w, the wx.Choice or wx.ComboBox, and
# selectionBg, the background of the selected item.
_choiceLists = {}


# draw drop-down list w (a wx.Choice or a read-only wx.ComboBox) ourselves
# from now on, like _drawButtonThemed's buttons, with an arrow at the right,
# and the list that drops down too (_paintChoiceList), in w's colors with
# room around the items. only on Windows, like the buttons.
def _drawChoiceThemed(w, cfgGui):
    if not misc.isWindows:
        return

    _initWin()
    hwnd = w.GetHandle()
    info = _win.COMBOBOXINFO(cbSize=_win.ctypes.sizeof(_win.COMBOBOXINFO))

    if _win.user32.GetComboBoxInfo(hwnd, _win.ctypes.byref(info)) and info.hwndList:
        if info.hwndList not in _choiceLists:
            _win.SetWindowSubclass(info.hwndList, _win.listProc, 3, 0)

        _choiceLists[info.hwndList] = types.SimpleNamespace(
            w=w,
            selectionBg=blendColors(
                cfgGui.buttonBgColor, cfgGui.accentColor, ACCENT_TINT
            ),
        )

    if getattr(w, "drawnThemed", False):
        return

    w.drawnThemed = True
    sendMessage(hwnd, _CB_SETITEMHEIGHT, 0, w.GetCharHeight() + w.FromDIP(10))
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

    # the native size leaves 28 pixels beside the longest item, and
    # _padChoice adds 8, which this layout fits in
    pad = w.FromDIP(10)

    # the arrow: a chevron pointing down, at the right
    arrowW = w.FromDIP(8)
    ax = width - w.FromDIP(7) - arrowW
    ay = (height - arrowW / 2) / 2
    gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(fg).Width(w.FromDIP(3) / 2)))
    gc.StrokeLines([(ax, ay), (ax + arrowW / 2, ay + arrowW / 2), (ax + arrowW, ay)])

    label = w.GetStringSelection()
    clip = (pad, 0, ax - w.FromDIP(4) - pad, height)

    if w.GetLayoutDirection() == wx.Layout_RightToLeft:
        del gc
        th = _prepareLabel(w, dc, label, fg)[1]
        dc.SetClippingRegion(*clip)
        dc.DrawText(label, pad, (height - th) // 2)
        dc.DestroyClippingRegion()
    else:
        gc.Clip(*clip)
        th = gc.GetTextExtent(label)[1]
        gc.DrawText(label, pad, (height - th) / 2)

        del gc

    del dc


# the selected item and the first one shown of native list box hwnd
def _choiceListState(hwnd):
    return (
        sendMessage(hwnd, _LB_GETCURSEL, 0, 0),
        sendMessage(hwnd, _LB_GETTOPINDEX, 0, 0),
    )


# paint the list of a drop-down list, native list box hwnd: for its
# WM_PAINT, or into hdc for WM_PRINTCLIENT. the items are drawn in the
# drop-down list's colors, with the same margin as its text
# (_onChoicePaint), and the selected one on lst.selectionBg. in a
# right-to-left list the items are aligned right, and the bitmap they're
# drawn into is copied without mirroring.
def _paintChoiceList(hwnd, lst, hdc):
    wt = _win.wintypes
    u = _win.user32
    ctypes = _win.ctypes
    byref = ctypes.byref

    ps = None

    if not hdc:
        # a PAINTSTRUCT is 72 bytes on 64-bit Windows, 64 on 32-bit
        ps = ctypes.create_string_buffer(72)
        hdc = u.BeginPaint(hwnd, ps)

    try:
        cr = wt.RECT()
        u.GetClientRect(hwnd, byref(cr))
        width, height = cr.right, cr.bottom

        if width <= 0 or height <= 0:
            return

        rtl = bool(_win.gdi32.GetLayout(hdc) & _LAYOUT_RTL)

        w = lst.w
        bg = w.GetBackgroundColour()
        fg = w.GetForegroundColour()

        bmp = wx.Bitmap(width, height)
        dc = wx.MemoryDC(bmp)
        dc.SetBackground(wx.Brush(bg))
        dc.Clear()
        # the memory dc has the system's DPI, not w's
        dc.SetFont(w.GetFont().Scaled(w.GetDPI().height / dc.GetPPI().height))
        dc.SetTextForeground(fg)

        pad = w.FromDIP(10)
        sel, top = _choiceListState(hwnd)
        r = wt.RECT()

        for i in range(max(top, 0), sendMessage(hwnd, _LB_GETCOUNT, 0, 0)):
            sendMessage(hwnd, _LB_GETITEMRECT, i, ctypes.addressof(r))

            if r.top >= height:
                break

            rect = wx.Rect(r.left, r.top, r.right - r.left, r.bottom - r.top)

            if i == sel:
                dc.SetPen(wx.TRANSPARENT_PEN)
                dc.SetBrush(wx.Brush(lst.selectionBg))
                dc.DrawRectangle(rect)

            label = wx.Control.Ellipsize(
                w.GetString(i), dc, wx.ELLIPSIZE_END, rect.width - 2 * pad
            )
            dc.DrawLabel(
                label,
                wx.Rect(rect).Deflate(pad, 0),
                (wx.ALIGN_RIGHT if rtl else wx.ALIGN_LEFT) | wx.ALIGN_CENTER_VERTICAL,
            )

        rop = _SRCCOPY | (_NOMIRRORBITMAP if rtl else 0)
        _win.gdi32.BitBlt(hdc, 0, 0, width, height, int(dc.GetHandle()), 0, 0, rop)
        dc.SelectObject(wx.NullBitmap)
    finally:
        if ps:
            u.EndPaint(hwnd, ps)


# draw the 1-pixel border of a drop-down list's list, native list box hwnd,
# halfway between its colors (BORDER_STRENGTH), on hdc, a dc for the whole
# window
def _paintChoiceListBorder(hwnd, lst, hdc):
    wt = _win.wintypes
    u = _win.user32
    gdi = _win.gdi32

    wr = wt.RECT()
    u.GetWindowRect(hwnd, _win.ctypes.byref(wr))
    ww = wr.right - wr.left
    wh = wr.bottom - wr.top

    c = blendColors(
        lst.w.GetBackgroundColour(), lst.w.GetForegroundColour(), BORDER_STRENGTH
    )
    brush = gdi.CreateSolidBrush(c.Red() | (c.Green() << 8) | (c.Blue() << 16))

    for rect in ((0, 0, ww, 1), (0, wh - 1, ww, wh), (0, 0, 1, wh), (ww - 1, 0, ww, wh)):
        u.FillRect(hdc, _win.ctypes.byref(wt.RECT(*rect)), brush)

    gdi.DeleteObject(brush)


# fill the paint dc of a control we draw ourselves (w) with its parent's
# background, and draw w's frame on it: a rounded rectangle in w's colors,
# lighter or darker when the mouse is over it or it's pushed, with a border
# halfway between its colors, or a thicker one in the text color when it has
# the focus. returns a GraphicsContext on dc, with w's
# font set, and the text color.
def _paintFrame(w, dc, pushed, focused):
    dc.SetBackground(wx.Brush(w.GetParent().GetBackgroundColour()))
    dc.Clear()

    hover = w.GetScreenRect().Contains(wx.GetMousePosition())

    bg = w.GetBackgroundColour()
    fg = w.GetForegroundColour()

    if not w.IsEnabled():
        fg = blendColors(fg, bg, 0.6)

    # the focus border keeps the full text color, to show the focus
    border = fg if focused else blendColors(bg, fg, BORDER_STRENGTH)

    if w.IsEnabled() and pushed:
        bg = blendColors(bg, fg, 0.25)
    elif w.IsEnabled() and hover:
        bg = blendColors(bg, fg, 0.12)

    width, height = w.GetClientSize()
    penW = w.FromDIP(2 if focused else 1)

    gc = wx.GraphicsContext.Create(dc)
    gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(border).Width(penW)))
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
