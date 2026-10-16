import os
import sys

import trelby.keys as keys

if "TRELBY_TESTING" in os.environ:
    import unittest.mock as mock

    wx = mock.Mock()
else:
    import wx

# a menu bar drawn by us, used on Windows instead of the native one, whose
# height is fixed by the system and too cramped. it sits at the top of the
# frame's client area, and opens the menus as popup menus of the frame, so
# their events go to the frame just like with a native menu bar.
#
# to feel like a native menu bar while a menu is open, moving the mouse to
# another title switches to that menu, and so do the Left / Right keys.
# Alt+<mnemonic> and F10 open the menus from the keyboard, and the menu
# items' accelerators (the "\tCTRL-N" part of their labels) are put in the
# frame's accelerator table, since without a native menu bar nothing else
# handles them.


class MyMenuBar(wx.Control):
    def __init__(self, frame, getCfgGui):
        wx.Control.__init__(self, frame, -1, style=wx.BORDER_NONE)

        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        self.frame = frame
        self.getCfgGui = getCfgGui

        # list of (menu, label without the '&', mnemonic key (upper case)
        # or None)
        self.menus = []
        self.rects = []

        # indexes of the hovered and the open menu (-1 = none)
        self.hover = -1
        self.open = -1

        # menu to open once the open one has closed, when switching menus,
        # and whether that's done from the keyboard
        self.pending = -1
        self.pendingFromKeyboard = False

        # see popup
        self.highlightFirst = False

        # mouse position at the previous OnTimer
        self.lastMousePos = None

        self.padX = self.FromDIP(10)
        self.margin = self.FromDIP(4)
        self.SetMinSize(wx.Size(-1, self.GetCharHeight() + self.FromDIP(16)))

        # notices the mouse moving to another title while a menu is open
        # (the open menu has the mouse captured, so we get no motion
        # events then)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDown)
        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeave)

        # on the frame, since the keyboard focus is normally in a script's
        # MyCtrl, and a top-level window sees char hook events before the
        # focused window gets the key
        frame.Bind(wx.EVT_CHAR_HOOK, self.OnCharHook)

    def AcceptsFocus(self):
        return False

    def AcceptsFocusFromKeyboard(self):
        return False

    # add a menu. 'title' may contain a '&' marking its mnemonic.
    def Append(self, menu, title):
        i = title.find("&")
        key = title[i + 1].upper() if 0 <= i < len(title) - 1 else None

        self.menus.append((menu, title.replace("&", ""), key))
        self.calcRects()

    def calcRects(self):
        self.rects = []
        x = self.margin
        h = self.GetClientSize().height or self.GetMinSize().height

        for menu, label, key in self.menus:
            w = self.GetTextExtent(label)[0] + self.padX * 2
            self.rects.append(wx.Rect(x, self.margin, w, h - self.margin * 2))
            x += w

        self.Refresh(False)

    # the same item lookups as wx.MenuBar has
    def FindItemById(self, id):
        for menu, label, key in self.menus:
            item = menu.FindItemById(id)

            if item:
                return item

        return None

    def Check(self, id, check):
        self.FindItemById(id).Check(check)

    def IsChecked(self, id):
        return self.FindItemById(id).IsChecked()

    def Enable(self, id, enable):
        self.FindItemById(id).Enable(enable)

    # accelerator table entries for every menu item with an accelerator in
    # its label
    def getAccelEntries(self):
        entries = []

        def add(menu):
            for item in menu.GetMenuItems():
                if item.IsSubMenu():
                    add(item.GetSubMenu())
                else:
                    accel = item.GetAccel()

                    if accel:
                        entries.append(
                            (accel.GetFlags(), accel.GetKeyCode(), item.GetId())
                        )

        for menu, label, key in self.menus:
            add(menu)

        return entries

    def itemAt(self, pos):
        for i, rect in enumerate(self.rects):
            if rect.Contains(pos):
                return i

        return -1

    def OnSize(self, event):
        self.calcRects()
        event.Skip()

    def OnLeftDown(self, event):
        i = self.itemAt(event.GetPosition())

        if i != -1:
            self.popup(i)

    def OnMotion(self, event):
        i = self.itemAt(event.GetPosition())

        if i != self.hover:
            self.hover = i
            self.Refresh(False)

    def OnLeave(self, event):
        if self.hover != -1:
            self.hover = -1
            self.Refresh(False)

    def OnCharHook(self, event):
        key = event.GetKeyCode()
        mods = event.GetModifiers()
        i = -1

        if (mods == wx.MOD_ALT) and (32 < key < 128):
            for j, (menu, label, mnemonic) in enumerate(self.menus):
                if mnemonic == chr(key).upper():
                    i = j
                    break
        elif (mods == wx.MOD_NONE) and (key == wx.WXK_F10):
            i = 0

        # the user's own key bindings come first
        kbdCommands = getattr(self.frame, "kbdCommands", {})
        bound = (
            keys.Key(
                key, event.ControlDown(), event.AltDown(), event.ShiftDown()
            ).toInt()
            in kbdCommands
        )

        if (i != -1) and self.IsShown() and not bound:
            self.popup(i, True)
        else:
            event.Skip()

    # show menu 'i' below its title, and if the user switches to another
    # menu while it's open, that one after it. a menu opened from the
    # keyboard starts with its first item highlighted, like native ones.
    #
    # PopupMenu doesn't return until the menu is closed, and there's no
    # opening another one from inside it, so switchTo just closes the open
    # one and sets self.pending, and this loop then opens that.
    def popup(self, i, fromKeyboard=False):
        while i != -1:
            self.open = i
            self.pending = -1
            self.highlightFirst = fromKeyboard
            self.lastMousePos = wx.GetMousePosition()
            self.Refresh(False)
            self.Update()

            menu = self.menus[i][0]
            rect = self.rects[i]

            pos = self.frame.ScreenToClient(self.ClientToScreen(rect.GetBottomLeft()))

            # done every time, as the theme may have changed
            cfgGui = self.getCfgGui()
            themeMenu(menu, cfgGui)

            # see OnTimer
            self.timer.Start(50)

            with _MenuKeys(self), _MenuPainter(cfgGui):
                self.frame.PopupMenu(menu, pos)

            self.timer.Stop()
            self.open = -1

            i = self.pending
            fromKeyboard = self.pendingFromKeyboard

        self.hover = self.itemAt(self.ScreenToClient(wx.GetMousePosition()))
        self.Refresh(False)

    # close the open menu, and open menu 'i' after it
    def switchTo(self, i, fromKeyboard=False):
        self.pending = i % len(self.menus)
        self.pendingFromKeyboard = fromKeyboard
        _endMenu()

    # runs while a menu is open
    def OnTimer(self, event):
        if self.highlightFirst:
            self.highlightFirst = False
            _highlightFirstItem()

        # switch to the menu whose title the mouse moves onto. the mouse
        # merely resting on one, e.g. when a menu was opened from the
        # keyboard, doesn't count.
        pos = wx.GetMousePosition()

        if pos == self.lastMousePos:
            return

        self.lastMousePos = pos
        i = self.itemAt(self.ScreenToClient(pos))

        if (i != -1) and (i != self.open):
            self.switchTo(i)

    def OnPaint(self, event):
        cfgGui = self.getCfgGui()

        dc = wx.AutoBufferedPaintDC(self)
        w, h = self.GetClientSize()

        dc.SetBrush(cfgGui.tabBarBgBrush)
        dc.SetPen(cfgGui.tabBarBgPen)
        dc.DrawRectangle(0, 0, w, h)

        dc.SetFont(self.GetFont())
        dc.SetTextForeground(cfgGui.tabTextColor)

        radius = self.FromDIP(4)

        for i, rect in enumerate(self.rects):
            if i in (self.open, self.hover):
                dc.SetBrush(cfgGui.tabNonActiveBgBrush)
                if i == self.open:
                    dc.SetPen(cfgGui.tabBorderPen)
                else:
                    dc.SetPen(cfgGui.tabNonActiveBgPen)

                dc.DrawRoundedRectangle(rect, radius)

            label = self.menus[i][1]
            tw, th = dc.GetTextExtent(label)
            dc.DrawText(
                label, rect.x + (rect.width - tw) // 2, rect.y + (rect.height - th) // 2
            )


# while a menu is open, intercept the Left / Right keys to switch to the
# previous / next menu, as with a native menu bar. that's only done while
# no submenu is open, and for Right, when the highlighted item doesn't
# open a submenu (which is what Right does then). Windows only.
class _MenuKeys:
    def __init__(self, bar):
        self.bar = bar
        self.hook = None

    def __enter__(self):
        if sys.platform == "win32":
            self.hook = _win32().installMenuHook(self.onKey)

        return self

    def __exit__(self, *args):
        if self.hook is not None:
            _win32().removeMenuHook(self.hook)

    # called with the virtual key code of each key pressed in the menu.
    # returns True if the key was handled.
    def onKey(self, vk):
        w32 = _win32()

        if vk not in (w32.VK_LEFT, w32.VK_RIGHT):
            return False

        menus = w32.getOpenMenus()

        if len(menus) != 1:
            return False

        if vk == w32.VK_LEFT:
            self.bar.switchTo(self.bar.open - 1, True)
        elif w32.isSubMenuHighlighted(menus[0]):
            return False
        else:
            self.bar.switchTo(self.bar.open + 1, True)

        return True


# give the items of 'menu' and its submenus the colors of the theme in the
# given configgui.ConfigGui, like the menu bar's, which on Windows makes wx draw
# them itself, instead of the system in its own light or dark colors.
# _MenuPainter then takes care of the parts wx doesn't draw.
def themeMenu(menu, cfgGui):
    if sys.platform != "win32":
        return

    items = list(menu.GetMenuItems())
    states = []

    # wx only makes an item owner-drawn when it's inserted, so each one is
    # taken out and put back with its colors set, keeping its state.
    # separators too, or the system draws them, with its own background.
    for pos, item in enumerate(items):
        if item.IsSubMenu():
            themeMenu(item.GetSubMenu(), cfgGui)

        states.append((item.IsEnabled(), item.IsCheckable() and item.IsChecked()))

        menu.Remove(item)
        item.SetBackgroundColour(cfgGui.tabBarBgColor)
        item.SetTextColour(cfgGui.tabTextColor)

        # wx draws the accelerator as written in the label ("CTRL-Z"),
        # unlike the system ("Ctrl+Z")
        accel = item.GetAccel()

        if accel:
            label = item.GetItemLabel().split("\t")[0]
            item.SetItemLabel(label + "\t" + accel.ToString())

        menu.Insert(pos, item)

    # after all are back, as inserting a radio item can check another one
    for i, (item, (enabled, checked)) in enumerate(zip(items, states)):
        if item.IsSeparator():
            continue

        item.Enable(enabled)

        if item.IsCheck():
            item.Check(checked)
        elif item.IsRadio() and checked:
            # wx ignores checking a radio item it thinks is checked
            # already, even when it isn't anymore, so check a neighbor in
            # its group first
            for j in (i - 1, i + 1):
                if (0 <= j < len(items)) and items[j].IsRadio():
                    items[j].Check(True)
                    break

            item.Check(True)


# while a menu is open, paints the parts of it and its submenus that wx
# doesn't draw in the theme's colors, and the highlighted item and the
# separators, which wx draws in the system's colors. Windows only.
class _MenuPainter:
    def __init__(self, cfgGui):
        self.bg = cfgGui.tabBarBgColor

        # the highlighted item: the accent color blended into the
        # background, like the selected auto-completion item
        self.selected = wx.Colour(
            *[
                int(b * 0.75 + a * 0.25)
                for a, b in zip(cfgGui.accentColor.Get(False), self.bg.Get(False))
            ]
        )

        self.line = cfgGui.tabBorderColor

        # True while having wx draw an item again, see afterDrawItem
        self.redrawing = False

    def __enter__(self):
        if sys.platform == "win32":
            self.hook = _win32().installMenuPaintHook(self)

    def __exit__(self, *args):
        if sys.platform == "win32":
            _win32().removeMenuPaintHook(self.hook)

    # the wx.MenuItem an owner-drawn menu item's DRAWITEMSTRUCT is for
    @staticmethod
    def getItem(dis):
        if not dis.itemData:
            return None

        # wx puts a pointer to the wxMenuItem in the item's data
        import wx.siplib as sip

        return sip.wrapinstance(dis.itemData, wx.MenuItem)

    # called before wx draws a menu item, with its DRAWITEMSTRUCT. wx fills
    # only part of the item's row, leaving the strip at its left to the
    # system, so fill the whole row.
    def beforeDrawItem(self, dis, hwnd, w32):
        item = self.getItem(dis)

        if (item is None) or self.redrawing:
            return

        item.SetBackgroundColour(self.bg)
        w32.fillRect(dis.hDC, dis.rcItem, self.bg)

    # called after wx has drawn a menu item, sent to the window 'hwnd'. wx
    # draws the highlighted item and separators in the system's colors, so
    # draw them again: the highlighted item by having wx draw it as not
    # highlighted, on our highlight color (the DRAWITEMSTRUCT the hooks
    # get is a copy, so changing its state there doesn't reach wx), and
    # separators ourselves.
    def afterDrawItem(self, dis, hwnd, w32):
        item = self.getItem(dis)

        if (item is None) or self.redrawing:
            return

        r = dis.rcItem

        if item.IsSeparator():
            w32.fillRect(dis.hDC, r, self.bg)

            y = (r.top + r.bottom) // 2
            line = type(r)(r.left + 4, y, r.right - 4, y + 1)
            w32.fillRect(dis.hDC, line, self.line)

        elif dis.itemState & w32.ODS_SELECTED:
            color = self.selected if item.IsEnabled() else self.bg

            copy = type(dis).from_buffer_copy(dis)
            copy.itemState &= ~w32.ODS_SELECTED

            item.SetBackgroundColour(color)
            w32.fillRect(dis.hDC, r, color)

            self.redrawing = True

            try:
                w32.sendDrawItem(hwnd, copy)
            finally:
                self.redrawing = False
                item.SetBackgroundColour(self.bg)


# close the open popup menu, if any
def _endMenu():
    if sys.platform == "win32":
        _win32().user32.EndMenu()


# highlight the first item of the open popup menu, if any
def _highlightFirstItem():
    if sys.platform == "win32":
        _win32().highlightFirstItem()


class _Win32:
    VK_LEFT = 0x25
    VK_RIGHT = 0x27
    VK_DOWN = 0x28

    WH_MSGFILTER = -1
    WH_CALLWNDPROC = 4
    WH_CALLWNDPROCRET = 12
    WM_INITMENUPOPUP = 0x117
    WM_DRAWITEM = 0x2B
    ODT_MENU = 1
    ODS_SELECTED = 0x1
    MSGF_MENU = 2
    WM_KEYDOWN = 0x100
    MN_GETHMENU = 0x1E1
    MF_BYPOSITION = 0x400
    MF_POPUP = 0x10
    MF_HILITE = 0x80
    MIM_BACKGROUND = 0x2

    def __init__(self):
        import ctypes
        from ctypes import wintypes

        self.ctypes = ctypes

        LRESULT = ctypes.c_ssize_t

        self.HOOKPROC = ctypes.WINFUNCTYPE(
            LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
        )

        class MSG(ctypes.Structure):
            _fields_ = [
                ("hwnd", wintypes.HWND),
                ("message", wintypes.UINT),
                ("wParam", wintypes.WPARAM),
                ("lParam", wintypes.LPARAM),
            ]

        self.MSG = MSG

        class CWPSTRUCT(ctypes.Structure):
            _fields_ = [
                ("lParam", wintypes.LPARAM),
                ("wParam", wintypes.WPARAM),
                ("message", wintypes.UINT),
                ("hwnd", wintypes.HWND),
            ]

        self.CWPSTRUCT = CWPSTRUCT

        class CWPRETSTRUCT(ctypes.Structure):
            _fields_ = [
                ("lResult", LRESULT),
                ("lParam", wintypes.LPARAM),
                ("wParam", wintypes.WPARAM),
                ("message", wintypes.UINT),
                ("hwnd", wintypes.HWND),
            ]

        self.CWPRETSTRUCT = CWPRETSTRUCT

        class DRAWITEMSTRUCT(ctypes.Structure):
            _fields_ = [
                ("CtlType", wintypes.UINT),
                ("CtlID", wintypes.UINT),
                ("itemID", wintypes.UINT),
                ("itemAction", wintypes.UINT),
                ("itemState", wintypes.UINT),
                ("hwndItem", wintypes.HWND),
                ("hDC", wintypes.HDC),
                ("rcItem", wintypes.RECT),
                ("itemData", ctypes.c_size_t),
            ]

        self.DRAWITEMSTRUCT = DRAWITEMSTRUCT

        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32

        self.user32.SetWindowsHookExW.argtypes = [
            ctypes.c_int,
            self.HOOKPROC,
            wintypes.HINSTANCE,
            wintypes.DWORD,
        ]
        self.user32.SetWindowsHookExW.restype = wintypes.HHOOK
        self.user32.CallNextHookEx.argtypes = [
            wintypes.HHOOK,
            ctypes.c_int,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        self.user32.CallNextHookEx.restype = LRESULT
        self.user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]

        self.WNDENUMPROC = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
        )
        self.user32.EnumThreadWindows.argtypes = [
            wintypes.DWORD,
            self.WNDENUMPROC,
            wintypes.LPARAM,
        ]
        self.user32.GetClassNameW.argtypes = [
            wintypes.HWND,
            wintypes.LPWSTR,
            ctypes.c_int,
        ]
        self.user32.IsWindowVisible.argtypes = [wintypes.HWND]
        self.user32.PostMessageW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        self.user32.SendMessageW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        self.user32.SendMessageW.restype = wintypes.HMENU
        self.user32.GetMenuItemCount.argtypes = [wintypes.HMENU]

        class MENUINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("fMask", wintypes.DWORD),
                ("dwStyle", wintypes.DWORD),
                ("cyMax", wintypes.UINT),
                ("hbrBack", wintypes.HBRUSH),
                ("dwContextHelpID", wintypes.DWORD),
                ("dwMenuData", ctypes.c_size_t),
            ]

        self.MENUINFO = MENUINFO
        self.user32.SetMenuInfo.argtypes = [wintypes.HMENU, ctypes.POINTER(MENUINFO)]
        self.gdi32 = ctypes.windll.gdi32
        self.gdi32.CreateSolidBrush.argtypes = [wintypes.COLORREF]
        self.gdi32.CreateSolidBrush.restype = wintypes.HBRUSH
        self.user32.FillRect.argtypes = [
            wintypes.HDC,
            ctypes.POINTER(wintypes.RECT),
            wintypes.HBRUSH,
        ]
        self.user32.GetMenuState.argtypes = [
            wintypes.HMENU,
            wintypes.UINT,
            wintypes.UINT,
        ]

        # key = (r, g, b), value = HBRUSH. kept for the life of the program,
        # as menus keep using them, and there are only a few.
        self.brushes = {}

    # a brush of the wx.Colour 'color'
    def getBrush(self, color):
        rgb = (color.Red(), color.Green(), color.Blue())
        brush = self.brushes.get(rgb)

        if brush is None:
            brush = self.gdi32.CreateSolidBrush(rgb[0] | (rgb[1] << 8) | (rgb[2] << 16))
            self.brushes[rgb] = brush

        return brush

    # fill the background of the menu (an HMENU) with the given brush
    def setMenuBackground(self, hmenu, brush):
        info = self.MENUINFO()
        info.cbSize = self.ctypes.sizeof(info)
        info.fMask = self.MIM_BACKGROUND
        info.hbrBack = brush
        self.user32.SetMenuInfo(hmenu, self.ctypes.byref(info))

    # press Down in the open menu, which highlights its first item
    def highlightFirstItem(self):
        for hwnd in self.getMenuWindows():
            self.user32.PostMessageW(hwnd, self.WM_KEYDOWN, self.VK_DOWN, 0)

    # the HMENUs of the menus currently shown by this thread: the popup
    # menu, and any submenus open on top of it
    def getOpenMenus(self):
        return [
            self.user32.SendMessageW(h, self.MN_GETHMENU, 0, 0)
            for h in self.getMenuWindows()
        ]

    # the windows of the menus currently shown by this thread
    def getMenuWindows(self):
        ctypes = self.ctypes
        hwnds = []
        buf = ctypes.create_unicode_buffer(16)

        def proc(hwnd, lParam):
            self.user32.GetClassNameW(hwnd, buf, len(buf))

            # the window class of menus
            if (buf.value == "#32768") and self.user32.IsWindowVisible(hwnd):
                hwnds.append(hwnd)

            return True

        self.user32.EnumThreadWindows(
            self.kernel32.GetCurrentThreadId(), self.WNDENUMPROC(proc), 0
        )

        return hwnds

    # whether the highlighted item of the menu opens a submenu
    def isSubMenuHighlighted(self, hmenu):
        for i in range(self.user32.GetMenuItemCount(hmenu)):
            state = self.user32.GetMenuState(hmenu, i, self.MF_BYPOSITION)

            if state & self.MF_HILITE:
                return bool(state & self.MF_POPUP)

        return False

    # call onKey(virtualKeyCode) for each key pressed while a menu is open,
    # and swallow the key if it returns True. returns a handle for
    # removeMenuHook.
    def installMenuHook(self, onKey):
        def proc(code, wParam, lParam):
            if code == self.MSGF_MENU:
                msg = self.MSG.from_address(lParam)

                if msg.message == self.WM_KEYDOWN:
                    try:
                        if onKey(msg.wParam):
                            return 1
                    except Exception:
                        pass

            return self.user32.CallNextHookEx(None, code, wParam, lParam)

        # the ctypes callback must stay alive as long as the hook does
        cb = self.HOOKPROC(proc)
        hook = self.user32.SetWindowsHookExW(
            self.WH_MSGFILTER, cb, None, self.kernel32.GetCurrentThreadId()
        )

        return (hook, cb)

    # while installed, call painter.beforeDrawItem(DRAWITEMSTRUCT, hwnd,
    # self) before each owner-drawn menu item of this thread is drawn by the
    # window hwnd, and
    # painter.afterDrawItem the same way after it, and set the background
    # of each menu shown to painter.bg. returns a handle for
    # removeMenuPaintHook.
    def installMenuPaintHook(self, painter):
        brush = self.getBrush(painter.bg)

        def handle(msg, before):
            try:
                if msg.message == self.WM_INITMENUPOPUP:
                    if before:
                        self.setMenuBackground(msg.wParam, brush)

                elif msg.message == self.WM_DRAWITEM:
                    dis = self.DRAWITEMSTRUCT.from_address(msg.lParam)

                    if dis.CtlType == self.ODT_MENU:
                        if before:
                            painter.beforeDrawItem(dis, msg.hwnd, self)
                        else:
                            painter.afterDrawItem(dis, msg.hwnd, self)
            except Exception:
                pass

        def proc(code, wParam, lParam):
            if code >= 0:
                handle(self.CWPSTRUCT.from_address(lParam), True)

            return self.user32.CallNextHookEx(None, code, wParam, lParam)

        def retProc(code, wParam, lParam):
            if code >= 0:
                handle(self.CWPRETSTRUCT.from_address(lParam), False)

            return self.user32.CallNextHookEx(None, code, wParam, lParam)

        tid = self.kernel32.GetCurrentThreadId()
        handles = []

        for hookType, func in (
            (self.WH_CALLWNDPROC, proc),
            (self.WH_CALLWNDPROCRET, retProc),
        ):
            # the ctypes callback must stay alive as long as the hook does
            cb = self.HOOKPROC(func)
            handles.append(
                (self.user32.SetWindowsHookExW(hookType, cb, None, tid), cb)
            )

        return handles

    def removeMenuPaintHook(self, handles):
        for handle in handles:
            self.removeMenuHook(handle)

    # send WM_DRAWITEM with the DRAWITEMSTRUCT 'dis' to the window 'hwnd'
    def sendDrawItem(self, hwnd, dis):
        self.user32.SendMessageW(
            hwnd, self.WM_DRAWITEM, 0, self.ctypes.addressof(dis)
        )

    # fill the RECT 'rect' in the HDC 'hdc' with the wx.Colour 'color'
    def fillRect(self, hdc, rect, color):
        self.user32.FillRect(hdc, self.ctypes.byref(rect), self.getBrush(color))

    def removeMenuHook(self, handle):
        hook, cb = handle

        if hook:
            self.user32.UnhookWindowsHookEx(hook)


_win32Funcs = None


# the _Win32 instance, created on first use
def _win32():
    global _win32Funcs

    if _win32Funcs is None:
        _win32Funcs = _Win32()

    return _win32Funcs
