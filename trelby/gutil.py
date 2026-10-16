import os
import re
import tempfile
from typing import TYPE_CHECKING

import trelby.misc as misc
import trelby.textutil as textutil
import trelby.util as util
from trelby.error import MiscError, TrelbyError

# only for type hints: misc imports this module, and config imports pml
# and screenplay, which import misc and util, so importing it here makes
# "import trelby.util" (or pml, fontinfo...) as the first import fail
# with a partially initialized module.
if TYPE_CHECKING:
    import trelby.config as config

if "TRELBY_TESTING" in os.environ:
    import unittest.mock as mock

    wx = mock.Mock()
else:
    import wx

# this contains misc GUI-related functions


# load one of the black SVG icons in trelby/resources as a bitmap bundle of
# the given size (in DIPs), recolored to show up on a dark appearance. a
# non-zero padding (in DIPs) adds that much empty space on every side of the
# icon, by growing the SVG's viewBox, so the bundle is size + 2 * padding.
# a color (wx.Colour) draws the icon in that color instead.
#
# the recoloring is a plain text replace, so it only reaches the parts of
# an icon written as "fill:#000000" in a style attribute, which is how all
# the bundled icons do it; any other way of writing black stays black.
def svgBitmap(iconFilename, size, padding=0, color=None):
    filepath = misc.getFullPath("trelby/resources/%s" % iconFilename)

    with open(filepath, "r") as svg_file:
        svg_content = svg_file.read()

    if color is None:
        color = svgIconColor()

    svg_content = svg_content.replace(
        "fill:#000000", "fill:%s" % color.GetAsString(wx.C2S_HTML_SYNTAX)
    )

    if padding:
        svg_content = re.sub(
            r'viewBox="([^"]*)"',
            lambda m: 'viewBox="%s"' % padViewBox(m.group(1), size, padding),
            svg_content,
            count=1,
        )
        size = wx.Size(size.width + padding * 2, size.height + padding * 2)

    return wx.BitmapBundle.FromSVG(svg_content.encode(), size)


# whether the application is currently using a dark theme
def isDarkAppearance():
    return wx.SystemSettings.GetAppearance().IsDark()


# return bitmap created from the given file. argument is as for
# getFullPath.
def getBitmap(filename):
    return wx.Bitmap(misc.getFullPath(filename))


# the color svgBitmap draws icons in by default
def svgIconColor():
    if isDarkAppearance():
        return wx.Colour(0xCC, 0xCC, 0xCC)

    return wx.Colour(0, 0, 0)


# return the SVG viewBox 'box' grown on every side by 'padding' DIPs, for an
# icon drawn at 'size' DIPs
def padViewBox(box, size, padding):
    x, y, w, h = [float(v) for v in box.replace(",", " ").split()]
    padX = w * padding / size.width
    padY = h * padding / size.height

    return "%g %g %g %g" % (x - padX, y - padY, w + padX * 2, h + padY * 2)


# return color c1 mixed with c2, with a being the fraction of c2
def blendColors(c1, c2, a):
    return wx.Colour(
        *[
            int(v1 * (1.0 - a) + v2 * a)
            for v1, v2 in zip(c1.Get(False), c2.Get(False))
        ]
    )


# since at least GTK 1.2's single-selection listbox is buggy in that if we
# don't deselect the old item manually, it does multiple selections, we
# have this function that does the following:
#
#  1) deselects current selection, if any
#  2) select the item with the given index
def listBoxSelect(lb, index):
    old = lb.GetSelection()

    if old != -1:
        lb.SetSelection(old, False)

    lb.SetSelection(index, True)


# add (name, cdata) to the listbox at the correct place, determined by
# cmp(cdata1, cdata2).
def listBoxAdd(lb, name, cdata):
    for i in range(lb.GetCount()):
        if util.cmpfunc(cdata, lb.GetClientData(i)) < 0:
            lb.InsertItems([name], i)
            lb.SetClientData(i, cdata)

            return

    lb.Append(name, cdata)


# create stock button.
def createStockButton(parent, label):
    # wxMSW does not really have them: it does not have any icons and it
    # inconsistently adds the shortcut key to some buttons, but not to
    # all, so it's better not to use them at all on Windows.
    if misc.isUnix:
        ids = {
            "OK": wx.ID_OK,
            _("Cancel"): wx.ID_CANCEL,
            _("Apply"): wx.ID_APPLY,
            _("Add"): wx.ID_ADD,
            _("Delete"): wx.ID_DELETE,
            _("Preview"): wx.ID_PREVIEW,
        }

        return wx.Button(parent, ids[label])
    else:
        if label == "OK":
            label = wx.GetStockLabel(wx.ID_OK, wx.STOCK_NOFLAGS)

        return wx.Button(parent, -1, label)


# wxWidgets' own translations, which have the labels of its stock buttons
# (OK, Cancel, Yes, Save...) and of its generic dialogs. set by
# loadWxTranslations.
wxTranslations = None


# load wxWidgets' translations for 'language' (e.g. "zh_CN"), the one
# Trelby's own strings are shown in. if they exist, message boxes are
# changed to show the stock labels too, since the system's own buttons
# would be in the language of the operating system instead.
def loadWxTranslations(language):
    global wxTranslations

    # wx's strings are in English already
    if language.startswith("en"):
        return

    wxTranslations = wx.Translations()
    wx.Translations.Set(wxTranslations)
    wxTranslations.SetLanguage(language)

    if wxTranslations.AddStdCatalog():
        # every module calls wx.MessageBox through the wx module, so this
        # reroutes all of them
        wx.MessageBox = messageBox


# wx.MessageBox, but with wx's stock labels on the buttons (see
# loadWxTranslations)
def messageBox(message, caption="Message", style=None, parent=None, x=-1, y=-1):
    if style is None:
        style = wx.OK | wx.CENTRE

    # the icon wx.MessageBox adds when none is given
    if not (style & (wx.ICON_MASK | wx.ICON_NONE)):
        style |= wx.ICON_QUESTION if style & wx.YES else wx.ICON_INFORMATION

    dlg = wx.MessageDialog(parent, message, caption, style)

    if style & wx.YES_NO:
        if style & wx.CANCEL:
            dlg.SetYesNoCancelLabels(wx.ID_YES, wx.ID_NO, wx.ID_CANCEL)
        else:
            dlg.SetYesNoLabels(wx.ID_YES, wx.ID_NO)
    elif style & wx.CANCEL:
        dlg.SetOKCancelLabels(wx.ID_OK, wx.ID_CANCEL)
    else:
        dlg.SetOKLabel(wx.ID_OK)

    ret = dlg.ShowModal()
    dlg.Destroy()

    # wx.MessageBox returns wx.YES etc., not the dialog's wx.ID_YES
    return {
        wx.ID_YES: wx.YES,
        wx.ID_NO: wx.NO,
        wx.ID_OK: wx.OK,
    }.get(ret, wx.CANCEL)


# add a small toggle button showing 'label' in the given font style to
# 'sizer', calling handler(event) when it's toggled, and return it
def addToggle(
    parent,
    sizer,
    label,
    tip,
    handler,
    weight=wx.FONTWEIGHT_NORMAL,
    style=wx.FONTSTYLE_NORMAL,
    underlined=False,
):
    size = parent.FromDIP(wx.Size(30, 28))
    btn = wx.ToggleButton(parent, -1, label, size=size)
    btn.SetToolTip(tip)

    font = btn.GetFont()
    font.SetWeight(weight)
    font.SetStyle(style)
    font.SetUnderlined(underlined)
    btn.SetFont(font)

    btn.Bind(wx.EVT_TOGGLEBUTTON, handler)
    sizer.Add(btn, 0, wx.RIGHT, 2)

    return btn


# add bold / italic / underlined toggles to 'sizer', calling
# handler(event) when one is toggled, and return them as a (bold,
# italic, underlined) tuple
def addStyleToggles(parent, sizer, handler):
    return (
        addToggle(parent, sizer, "B", _("Bold"), handler, wx.FONTWEIGHT_BOLD),
        addToggle(
            parent, sizer, "I", _("Italic"), handler, style=wx.FONTSTYLE_ITALIC
        ),
        addToggle(parent, sizer, "U", _("Underlined"), handler, underlined=True),
    )


# add left / center / right alignment toggles to 'sizer', which work like
# radio buttons, and return them as a {util.ALIGN_*: button} dict.
# handler(event) is called after one is clicked.
def addAlignToggles(parent, sizer, handler):
    btns = {}

    def onAlign(event):
        for btn in btns.values():
            btn.SetValue(btn is event.GetEventObject())

        handler(event)

    for align, tip in [
        (util.ALIGN_LEFT, _("Align left")),
        (util.ALIGN_CENTER, _("Center")),
        (util.ALIGN_RIGHT, _("Align right")),
    ]:
        btn = addToggle(parent, sizer, "", tip, onAlign)
        btn.SetBitmap(makeAlignBitmap(btn, align))
        btns[align] = btn

    return btns


# return the alignment selected in alignment toggles made by
# addAlignToggles
def getAlignment(btns):
    for align, btn in btns.items():
        if btn.GetValue():
            return align

    return util.ALIGN_LEFT


# select 'align' in alignment toggles made by addAlignToggles, or none of
# them if it's None
def setAlignment(btns, align):
    for a, btn in btns.items():
        btn.SetValue(a == align)


# return an icon for alignment button 'btn': four lines of text, aligned
# as 'align'
def makeAlignBitmap(btn, align):
    size = btn.FromDIP(16)
    bmp = wx.Bitmap.FromRGBA(size, size, 0, 0, 0, 0)

    dc = wx.MemoryDC(bmp)
    gc = wx.GraphicsContext.Create(dc)

    gc.SetPen(wx.TRANSPARENT_PEN)
    gc.SetBrush(wx.Brush(wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNTEXT)))

    thick = max(1, size // 8)
    gap = (size - 4 * thick) / 5

    for i, frac in enumerate([1.0, 0.6, 0.85, 0.5]):
        w = round(size * frac)

        if align == util.ALIGN_CENTER:
            x = (size - w) / 2
        elif align == util.ALIGN_RIGHT:
            x = size - w
        else:
            x = 0

        gc.DrawRectangle(x, gap + i * (thick + gap), w, thick)

    del gc
    dc.SelectObject(wx.NullBitmap)

    return bmp


# wxWidgets has a bug in 2.6 on wxGTK2 where double clicking on a button
# does not send two wx.EVT_BUTTON events, only one. since the wxWidgets
# maintainers do not seem interested in fixing this
# (http://sourceforge.net/tracker/index.php?func=detail&aid=1449838&group_id=9863&atid=109863),
# we work around it ourselves by binding the left mouse button double
# click event to the same callback function on the buggy platforms.
def btnDblClick(btn, func):
    if misc.isUnix:
        btn.Bind(wx.EVT_LEFT_DCLICK, func)


# show PDF document 'pdfData' in an external viewer program. writes out a
# temporary file, first deleting all old temporary files, then opens PDF
# viewer application. 'mainFrame' is used as a parent for message boxes in
# case there are any errors.
def showTempPDF(
    pdfData: bytes, cfgGl: "config.ConfigGlobal", mainFrame: wx.TopLevelWindow
) -> None:
    try:
        try:
            util.removeTempFiles(misc.tmpPrefix)

            fd, filename = tempfile.mkstemp(prefix=misc.tmpPrefix, suffix=".pdf")

            try:
                if isinstance(pdfData, str):
                    os.write(fd, pdfData)
                else:
                    os.write(fd, pdfData)
            finally:
                os.close(fd)

            util.showPDF(filename, cfgGl, mainFrame)

        except IOError as xxx_todo_changeme:
            (errno, strerror) = xxx_todo_changeme.args
            raise MiscError("IOError: %s" % strerror)

    except TrelbyError as e:
        wx.MessageBox(
            _("Error writing temporary PDF file: {}").format(e),
            _("Error"),
            wx.OK,
            mainFrame,
        )


# the colors of dialogs and other windows besides the main one. those use
# native controls, which wx draws in the system's light or dark colors.
# themeWindow gives them the theme's colors where the native controls allow
# it, and the classes below stand in for the ones that don't: Separator for
# wx.StaticLine, ThemedListBox for wx.ListBox and wx.CheckListBox, and
# ThemedListbook for wx.Treebook.


# the current configgui.ConfigGui, or None before the app has started
def currentCfgGui():
    gd = getattr(wx.GetApp(), "gd", None)

    return gd.cfgGui if gd else None


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


# a horizontal line between parts of a window, in the theme's border color
class Separator(wx.Window):
    def __init__(self, parent):
        wx.Window.__init__(self, parent, -1, style=wx.BORDER_NONE)

        self.SetMinSize(wx.Size(-1, 1))
        self.applyTheme(currentCfgGui())

    def applyTheme(self, cfgGui):
        if cfgGui:
            self.SetBackgroundColour(cfgGui.tabBorderColor)
        else:
            self.SetBackgroundColour(
                wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DSHADOW)
            )

        self.Refresh()

    def AcceptsFocus(self):
        return False

    def AcceptsFocusFromKeyboard(self):
        return False


# a label that wraps its text to the width it's given, and wraps it again
# when that changes, e.g. when the window is resized. add it to its sizer
# with wx.EXPAND, or it stays at its minimum width, 'width' DIPs. line
# breaks in the text are kept, so use "\n\n" between paragraphs and no
# single line breaks.
class WrappedText(wx.StaticText):
    def __init__(self, parent, text, width=300):
        wx.StaticText.__init__(self, parent, -1, "", style=wx.ST_NO_AUTORESIZE)

        self.text = text
        self.minWidth = self.FromDIP(width)

        # how much taller the native control is than its text
        dc = wx.ClientDC(self)
        dc.SetFont(self.GetFont())
        self.SetLabelText("Ag")
        self.InvalidateBestSize()
        self.extraHeight = max(
            0, self.GetBestSize().height - dc.GetTextExtent("Ag")[1]
        )

        # width the text is wrapped to
        self.wrapWidth = None

        self.rewrap(self.minWidth)

        self.Bind(wx.EVT_SIZE, self.OnSize)

    def rewrap(self, width):
        self.wrapWidth = width

        dc = wx.ClientDC(self)
        dc.SetFont(self.GetFont())

        label = textutil.wrapText(self.text, width, lambda s: dc.GetTextExtent(s)[0])
        self.SetLabelText(label)

        # tall enough for the wrapped text. GetBestSize can't be used, as
        # it isn't updated for the new label.
        height = dc.GetMultiLineTextExtent(label)[1] + self.extraHeight
        self.SetMinSize(wx.Size(self.minWidth, height))

    def OnSize(self, event):
        event.Skip()

        width = event.GetSize().width

        if (width <= 0) or (width == self.wrapWidth):
            return

        height = self.GetMinSize().height
        self.rewrap(width)
        self.Refresh()

        # the new height only takes effect on the next layout, which can't
        # be done in the middle of this one
        if self.GetMinSize().height != height:
            wx.CallAfter(self.relayout)

    def relayout(self):
        if not self:
            return

        # the nearest window that lays out its children with a sizer
        w = self.GetParent()

        while w and not w.GetSizer():
            w = w.GetParent()

        if w:
            w.Layout()


# a list box in the theme's colors, with the selection in its accent color.
# it has the parts of wx.ListBox's interface we use, and with checkable set,
# those of wx.CheckListBox. it sends the same events with the control's id:
# EVT_LISTBOX when the user changes the selection, EVT_LISTBOX_DCLICK, and
# EVT_CHECKLISTBOX. style wx.LB_EXTENDED (or wx.LB_MULTIPLE, which works
# the same) allows selecting several items.
#
# the list (self.list) is a wx.VListBox inside a 1-pixel border. like the
# outline's list, it's sized to put its native scrollbar out of sight, and a
# ScrollBar stands in for it.
class ThemedListBox(wx.Panel):

    # events that aren't passed on to parent windows, so Bind binds them on
    # self.list, where they arrive
    LIST_EVENTS = (
        wx.EVT_CHAR,
        wx.EVT_KEY_DOWN,
        wx.EVT_KEY_UP,
        wx.EVT_SET_FOCUS,
        wx.EVT_KILL_FOCUS,
        wx.EVT_LEFT_DOWN,
        wx.EVT_LEFT_DCLICK,
    )

    def __init__(
        self,
        parent,
        id=-1,
        size=wx.DefaultSize,
        style=0,
        choices=(),
        checkable=False,
    ):
        # imported here, since scrollbar imports this module
        from trelby.scrollbar import ScrollBar

        wx.Panel.__init__(self, parent, id, style=wx.BORDER_NONE)

        self.checkable = checkable
        self.multiple = bool(style & (wx.LB_EXTENDED | wx.LB_MULTIPLE))

        # [text, client data, checked, dimmed] for each item
        self.items = []

        self.holder = wx.Panel(self, -1, style=wx.BORDER_NONE)
        self.list = _ListBoxImpl(self, self.holder)
        self.scrollBar = ScrollBar(self, self.list)
        self.scrollBar.Hide()

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        hsizer.Add(self.holder, 1, wx.EXPAND)
        hsizer.Add(self.scrollBar, 0, wx.EXPAND)

        vsizer = wx.BoxSizer(wx.VERTICAL)
        vsizer.Add(hsizer, 1, wx.EXPAND | wx.ALL, 1)
        self.SetSizer(vsizer)

        self.holder.Bind(wx.EVT_SIZE, self.OnHolderSize)
        self.scrollBar.Bind(wx.EVT_COMMAND_SCROLL, self.OnScroll)
        self.list.Bind(wx.EVT_SIZE, self.OnListSize)
        self.list.Bind(wx.EVT_IDLE, self.OnListIdle)

        self.applyTheme(currentCfgGui())
        self.Set(choices)
        self.SetInitialSize(size)
        self.Layout()

    def Bind(self, event, handler, source=None, id=wx.ID_ANY, id2=wx.ID_ANY):
        if event in self.LIST_EVENTS:
            self.list.Bind(event, handler, source, id, id2)
        else:
            wx.Panel.Bind(self, event, handler, source, id, id2)

    def SetFocus(self):
        self.list.SetFocus()

    def applyTheme(self, cfgGui):
        if cfgGui:
            border = cfgGui.tabBorderColor
            bg, fg = cfgGui.textBgColor, cfgGui.textColor
            accent, accentText = cfgGui.accentColor, cfgGui.accentTextColor
        else:
            sc = wx.SystemSettings.GetColour
            border = sc(wx.SYS_COLOUR_3DSHADOW)
            bg, fg = sc(wx.SYS_COLOUR_WINDOW), sc(wx.SYS_COLOUR_WINDOWTEXT)
            accent = sc(wx.SYS_COLOUR_HIGHLIGHT)
            accentText = sc(wx.SYS_COLOUR_HIGHLIGHTTEXT)

        self.SetBackgroundColour(border)
        self.holder.SetBackgroundColour(bg)
        self.list.SetBackgroundColour(bg)
        self.list.SetForegroundColour(fg)
        self.list.accent = accent
        self.list.accentText = accentText
        self.scrollBar.setColors(bg, fg)

        self.Refresh()

    # wide enough for the longest item, and high enough for a few items
    def DoGetBestSize(self):
        lc = self.list
        w = max(
            [self.FromDIP(60)] + [lc.GetTextExtent(it[0]).width for it in self.items]
        )
        w += lc.textX + lc.pad + self.scrollBar.GetMinSize().width + 2
        h = min(max(len(self.items), 3), 10) * lc.rowHeight + 2

        return wx.Size(w, h)

    # size the list to fill holder, plus the width of its native scrollbar
    # if it has one
    def layoutList(self):
        lc = self.list
        size = self.holder.GetClientSize()
        sbWidth = lc.GetSize().width - lc.GetClientSize().width
        rect = wx.Rect(0, 0, size.width + sbWidth, size.height)

        if lc.GetRect() != rect:
            lc.SetSize(rect)

        self.updateScrollBar()

    # make scrollBar match the list's native scrollbar, and show it only
    # when the list can scroll
    def updateScrollBar(self):
        lc = self.list
        thumb = lc.GetScrollThumb(wx.VERTICAL)

        self.scrollBar.SetScrollbar(
            lc.GetScrollPos(wx.VERTICAL), thumb, lc.GetScrollRange(wx.VERTICAL), thumb
        )

        show = self.scrollBar.canScroll()

        if show != self.scrollBar.IsShown():
            self.scrollBar.Show(show)
            self.Layout()

    def OnHolderSize(self, event):
        self.layoutList()

    def OnListSize(self, event):
        event.Skip()
        self.layoutList()

    def OnListIdle(self, event):
        event.Skip()
        self.updateScrollBar()

    def OnScroll(self, event):
        self.list.ScrollToRow(self.scrollBar.GetThumbPosition())

    # call change(), which changes self.items, and update the list. the
    # selected items stay selected, wherever they moved to.
    def changeItems(self, change):
        selected = [self.items[i] for i in self.GetSelections()]

        change()

        lc = self.list
        lc.SetItemCount(len(self.items))

        indexes = [
            i for i, it in enumerate(self.items) if any(it is s for s in selected)
        ]

        if self.multiple:
            lc.DeselectAll()

            for i in indexes:
                lc.Select(i)
        else:
            sel = indexes[0] if indexes else wx.NOT_FOUND

            if lc.GetSelection() != sel:
                lc.SetSelection(sel)

        lc.Refresh()
        self.InvalidateBestSize()
        self.updateScrollBar()

    def GetCount(self):
        return len(self.items)

    def GetString(self, n):
        return self.items[n][0]

    def GetStrings(self):
        return [it[0] for it in self.items]

    def SetString(self, n, text):
        self.items[n][0] = text
        self.list.RefreshRow(n)
        self.InvalidateBestSize()

    def FindString(self, text):
        for i, it in enumerate(self.items):
            if it[0] == text:
                return i

        return wx.NOT_FOUND

    def GetClientData(self, n):
        return self.items[n][1]

    def SetClientData(self, n, data):
        self.items[n][1] = data

    def Append(self, text, clientData=None):
        self.Insert(text, len(self.items), clientData)

        return len(self.items) - 1

    def Insert(self, text, pos, clientData=None):
        def change():
            self.items.insert(pos, [text, clientData, False, False])

        self.changeItems(change)

    def InsertItems(self, texts, pos):
        def change():
            self.items[pos:pos] = [[t, None, False, False] for t in texts]

        self.changeItems(change)

    def Set(self, texts):
        def change():
            self.items = [[t, None, False, False] for t in texts]

        self.changeItems(change)

    def Clear(self):
        self.Set([])

    def Delete(self, n):
        def change():
            del self.items[n]

        self.changeItems(change)

    # the selected item, or the first one of several, or wx.NOT_FOUND
    def GetSelection(self):
        sel = self.GetSelections()

        return sel[0] if sel else wx.NOT_FOUND

    def GetSelections(self):
        if self.multiple:
            return [i for i in range(len(self.items)) if self.list.IsSelected(i)]

        sel = self.list.GetSelection()

        return [sel] if sel != wx.NOT_FOUND else []

    def GetStringSelection(self):
        sel = self.GetSelection()

        return self.items[sel][0] if sel != wx.NOT_FOUND else ""

    def IsSelected(self, n):
        return self.list.IsSelected(n)

    # select item n, or deselect it if select is False. in a
    # single-selection list, n can be wx.NOT_FOUND to select nothing.
    def SetSelection(self, n, select=True):
        lc = self.list

        if self.multiple:
            lc.Select(n, select)
        elif select:
            lc.SetSelection(n)
        elif n == lc.GetSelection():
            lc.SetSelection(wx.NOT_FOUND)

    def IsChecked(self, n):
        return self.items[n][2]

    def Check(self, n, check=True):
        self.items[n][2] = bool(check)
        self.list.RefreshRow(n)

    # show item n's text grayed out, e.g. for something that doesn't exist yet
    def SetItemDimmed(self, n, dimmed=True):
        self.items[n][3] = dimmed
        self.list.RefreshRow(n)

    def GetCheckedItems(self):
        return [i for i, it in enumerate(self.items) if it[2]]

    def SetCheckedItems(self, indexes):
        indexes = set(indexes)

        for i, it in enumerate(self.items):
            it[2] = i in indexes

        self.list.Refresh()


# the list in a ThemedListBox
class _ListBoxImpl(wx.VListBox):
    def __init__(self, owner, parent):
        style = wx.BORDER_NONE

        if owner.multiple:
            style |= wx.LB_MULTIPLE

        # the ThemedListBox's id, for the events it sends
        wx.VListBox.__init__(self, parent, owner.GetId(), style=style)

        self.owner = owner

        # set by ThemedListBox.applyTheme
        self.accent = None
        self.accentText = None

        self.pad = self.FromDIP(6)
        self.lineHeight = self.GetCharHeight()
        self.boxSize = self.FromDIP(14) if owner.checkable else 0
        self.rowHeight = max(self.lineHeight, self.boxSize) + self.FromDIP(6)

        # x position of the text
        self.textX = self.pad

        if owner.checkable:
            self.textX += self.boxSize + self.pad

        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDown)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind(wx.EVT_SET_FOCUS, self.OnFocus)
        self.Bind(wx.EVT_KILL_FOCUS, self.OnFocus)

    def OnMeasureItem(self, n):
        return self.rowHeight

    def OnDrawBackground(self, dc, rect, n):
        if self.IsSelected(n):
            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.SetBrush(wx.Brush(self.accent))
            dc.DrawRectangle(rect)

        # in a multiple-selection list, the item the keyboard is at
        elif self.owner.multiple and (n == self.GetCurrent()) and self.HasFocus():
            dc.SetPen(wx.Pen(self.accent))
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.DrawRectangle(rect)

    def OnDrawItem(self, dc, rect, n):
        text, data, checked, dimmed = self.owner.items[n]

        if self.IsSelected(n):
            bg, fg = self.accent, self.accentText
        else:
            bg, fg = self.GetBackgroundColour(), self.GetForegroundColour()

        if dimmed or not self.IsEnabled():
            fg = blendColors(fg, bg, 0.5)

        if self.owner.checkable:
            y = rect.y + (rect.height - self.boxSize) // 2
            box = wx.Rect(rect.x + self.pad, y, self.boxSize, self.boxSize)
            self.drawCheckBox(dc, box, checked, bg, fg)

        dc.SetFont(self.GetFont())
        dc.SetTextForeground(fg)
        dc.DrawText(
            text, rect.x + self.textX, rect.y + (rect.height - self.lineHeight) // 2
        )

    # draw a check box in rect r, on background color bg, with fg the text
    # color: filled with the accent color (or on a selected item, which has
    # the accent color as its background, with fg) when checked, and an
    # outline when not
    def drawCheckBox(self, dc, r, checked, bg, fg):
        gc = wx.GraphicsContext.Create(dc)
        radius = self.FromDIP(2)

        if checked:
            onAccent = bg == self.accent
            fill = fg if onAccent else self.accent
            mark = self.accent if onAccent else self.accentText

            gc.SetPen(wx.TRANSPARENT_PEN)
            gc.SetBrush(wx.Brush(fill))
            gc.DrawRoundedRectangle(r.x, r.y, r.width, r.height, radius)

            gc.SetPen(wx.Pen(mark, self.FromDIP(2)))
            gc.StrokeLines(
                [
                    (r.x + r.width * 0.22, r.y + r.height * 0.52),
                    (r.x + r.width * 0.42, r.y + r.height * 0.72),
                    (r.x + r.width * 0.78, r.y + r.height * 0.3),
                ]
            )
        else:
            gc.SetPen(wx.Pen(blendColors(bg, fg, 0.6)))
            gc.SetBrush(wx.TRANSPARENT_BRUSH)
            gc.DrawRoundedRectangle(
                r.x + 0.5, r.y + 0.5, r.width - 1, r.height - 1, radius
            )

    # toggle item n's check box
    def toggle(self, n):
        self.owner.Check(n, not self.owner.IsChecked(n))

        event = wx.CommandEvent(wx.wxEVT_CHECKLISTBOX, self.GetId())
        event.SetEventObject(self.owner)
        event.SetInt(n)
        self.GetEventHandler().ProcessEvent(event)

    def OnLeftDown(self, event):
        if self.owner.checkable and (event.GetX() < self.textX):
            n = self.VirtualHitTest(event.GetY())

            if n != wx.NOT_FOUND:
                self.toggle(n)

        # selects the item
        event.Skip()

    def OnKeyDown(self, event):
        n = self.GetCurrent()

        if (
            self.owner.checkable
            and (event.GetKeyCode() == wx.WXK_SPACE)
            and (n != wx.NOT_FOUND)
        ):
            self.toggle(n)
        else:
            event.Skip()

    def OnFocus(self, event):
        event.Skip()

        if self.owner.multiple and (self.GetCurrent() != wx.NOT_FOUND):
            self.RefreshRow(self.GetCurrent())


# a book control whose pages are picked from a ThemedListBox, in place of a
# wx.Listbook or wx.Treebook. pages are created with self.book as their
# parent.
class ThemedListbook(wx.Panel):
    def __init__(self, parent, id=-1):
        wx.Panel.__init__(self, parent, id)

        self.list = ThemedListBox(self)
        self.book = wx.Simplebook(self)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        hsizer.Add(self.list, 0, wx.EXPAND | wx.RIGHT, self.FromDIP(15))
        hsizer.Add(self.book, 1, wx.EXPAND)
        self.SetSizer(hsizer)

        self.list.Bind(wx.EVT_LISTBOX, self.OnList)

    def AddPage(self, page, text):
        self.book.AddPage(page, text)
        self.list.Append(text)

        if self.list.GetSelection() == wx.NOT_FOUND:
            self.list.SetSelection(0)

    def DeleteAllPages(self):
        self.book.DeleteAllPages()
        self.list.Clear()

    def GetPageCount(self):
        return self.book.GetPageCount()

    def GetPage(self, i):
        return self.book.GetPage(i)

    def GetPageText(self, i):
        return self.list.GetString(i)

    def GetSelection(self):
        return self.book.GetSelection()

    def SetSelection(self, i):
        self.book.SetSelection(i)
        self.list.SetSelection(i)

    def OnList(self, event):
        self.book.SetSelection(event.GetSelection())
