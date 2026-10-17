import wx

import trelby.ui.icons as icons
import trelby.ui.widgets as widgets
from trelby.ui.globaldata import GlobalData
from trelby.ui.notesview import NotesPanel
from trelby.ui.outline import OutlinePanel
from trelby.ui.theming import blendColors

# the panel beside the script, with the outline and the notes as tabs.
# its header has the tabs, the shown tab's buttons, and a button that hides
# the panel. which tab is shown, and whether the panel is, is the same in
# every script's tab (GlobalData.sideTab / showSidePanel), so the tabs and
# the close button go through the main frame (showSideTab,
# setShowSidePanel).


# the tabs' labels side by side, the shown one bold and underlined in the
# accent color. clicking one calls onSelect(index).
class SideTabs(wx.Window):

    # space around each label, in DIPs
    PAD_X = 8
    PAD_Y = 5

    # the underline's thickness, in DIPs
    BAR = 2

    def __init__(self, parent, labels, onSelect):
        wx.Window.__init__(self, parent, -1, style=wx.BORDER_NONE)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        self.labels = labels
        self.onSelect = onSelect

        # the index of the shown tab, and of the one under the mouse, or -1
        self.selected = 0
        self.hover = -1

        self.textColor = wx.BLACK
        self.accentColor = wx.BLUE

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeave)

        self.updateSize()

    def applyTheme(self, cfgGui):
        self.SetBackgroundColour(cfgGui.tabBarBgColor)
        self.textColor = cfgGui.tabTextColor
        self.accentColor = cfgGui.accentColor
        self.Refresh()

    def AcceptsFocus(self):
        return False

    def AcceptsFocusFromKeyboard(self):
        return False

    def boldFont(self):
        return self.GetFont().Bold()

    # the width of each tab: its label in bold, so that it doesn't change
    # when the tab is shown, plus the padding
    def getWidths(self, dc):
        dc.SetFont(self.boldFont())

        return [
            dc.GetTextExtent(label).width + 2 * self.FromDIP(self.PAD_X)
            for label in self.labels
        ]

    # the tabs' wx.Rects
    def getRects(self, dc):
        rects = []
        x = 0
        height = self.GetClientSize().height

        for w in self.getWidths(dc):
            rects.append(wx.Rect(x, 0, w, height))
            x += w

        return rects

    # it wants room for all of its tabs, but can make do with less, so that
    # the buttons beside it stay visible in a narrow panel. the labels are
    # cut off then.
    def updateSize(self):
        dc = wx.ClientDC(self)
        dc.SetFont(self.boldFont())
        height = (
            dc.GetTextExtent("Ag").height
            + 2 * self.FromDIP(self.PAD_Y)
            + self.FromDIP(self.BAR)
        )

        self.SetInitialSize(wx.Size(sum(self.getWidths(dc)), height))
        self.SetMinSize(wx.Size(self.FromDIP(40), height))

    def setSelected(self, idx):
        if idx != self.selected:
            self.selected = idx
            self.Refresh(False)

    # the index of the tab at pos, or -1
    def hitTest(self, pos):
        dc = wx.ClientDC(self)

        for i, r in enumerate(self.getRects(dc)):
            if r.Contains(pos):
                return i

        return -1

    def OnLeftDown(self, event):
        idx = self.hitTest(event.GetPosition())

        if idx != -1:
            self.onSelect(idx)

    def OnMotion(self, event):
        self.setHover(self.hitTest(event.GetPosition()))

    def OnLeave(self, event):
        self.setHover(-1)

    def setHover(self, idx):
        if idx != self.hover:
            self.hover = idx
            self.SetCursor(
                wx.Cursor(wx.CURSOR_HAND if idx != -1 else wx.CURSOR_ARROW)
            )
            self.Refresh(False)

    def OnPaint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        bg = self.GetBackgroundColour()
        dc.SetBackground(wx.Brush(bg))
        dc.Clear()

        normal = self.GetFont()
        bold = self.boldFont()
        dimColor = blendColors(bg, self.textColor, 0.65)
        bar = self.FromDIP(self.BAR)

        for i, r in enumerate(self.getRects(dc)):
            shown = i == self.selected
            dc.SetFont(bold if shown else normal)
            dc.SetTextForeground(
                self.textColor if (shown or (i == self.hover)) else dimColor
            )

            size = dc.GetTextExtent(self.labels[i])
            dc.DrawText(
                self.labels[i],
                r.x + (r.width - size.width) // 2,
                r.y + (r.height - bar - size.height) // 2,
            )

            if shown:
                dc.SetPen(wx.TRANSPARENT_PEN)
                dc.SetBrush(wx.Brush(self.accentColor))
                pad = self.FromDIP(self.PAD_X) // 2
                dc.DrawRectangle(r.x + pad, r.GetBottom() - bar + 1, r.width - 2 * pad, bar)


class SidePanel(wx.Panel):
    def __init__(self, parent, scriptPanel):
        wx.Panel.__init__(self, parent, -1)

        # trelbypanel.MyPanel whose script we show
        self.scriptPanel = scriptPanel

        vsizer = wx.BoxSizer(wx.VERTICAL)
        hdr = wx.BoxSizer(wx.HORIZONTAL)

        self.tabs = SideTabs(self, [_("Outline"), _("Notes")], self.OnTabClicked)
        hdr.Add(self.tabs, 1, wx.ALIGN_BOTTOM | wx.LEFT, self.FromDIP(2))

        # GlobalData.SIDE_OUTLINE / SIDE_NOTES index this
        self.outline = OutlinePanel(self, scriptPanel, self)
        self.notes = NotesPanel(self, scriptPanel, self)
        self.pages = [self.outline, self.notes]

        for page in self.pages:
            hdr.Add(page.tools, 0, wx.ALIGN_CENTER_VERTICAL)

        hdr.AddSpacer(self.FromDIP(6))

        bitmap = icons.svgBitmap("closepanel.svg", wx.Size(16, 16))
        self.closeBtn = wx.BitmapButton(self, -1, bitmap, style=wx.BORDER_NONE)
        self.closeBtn.SetToolTip(_("Hide the side panel"))
        hdr.Add(self.closeBtn, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, self.FromDIP(2))

        vsizer.Add(hdr, 0, wx.EXPAND)
        self.separator = widgets.Separator(self)
        vsizer.Add(self.separator, 0, wx.EXPAND)

        for page in self.pages:
            vsizer.Add(page, 1, wx.EXPAND)

        self.SetSizer(vsizer)

        self.closeBtn.Bind(wx.EVT_BUTTON, self.OnClose)

        # the index of the tab shown. not refreshed yet: MyPanel makes us
        # before the MyCtrl with the script.
        self.tab = None
        self.showTab(GlobalData.SIDE_OUTLINE)

    def applyTheme(self, cfgGui):
        self.SetBackgroundColour(cfgGui.tabBarBgColor)
        self.closeBtn.SetBackgroundColour(cfgGui.tabBarBgColor)
        self.tabs.applyTheme(cfgGui)
        self.separator.applyTheme(cfgGui)

        for page in self.pages:
            page.applyTheme(cfgGui)

        self.Refresh()

    # the page shown
    def getPage(self):
        return self.pages[self.tab]

    # show the tab at index tab (GlobalData.SIDE_*), up to date
    def setTab(self, tab):
        if tab == self.tab:
            return

        self.notes.finishEdit(True)
        self.showTab(tab)
        self.refresh()

    def showTab(self, tab):
        self.tab = tab
        self.tabs.setSelected(tab)

        for i, page in enumerate(self.pages):
            page.Show(i == tab)
            page.tools.Show(i == tab)

        self.Layout()

    # refresh the page shown right away
    def refresh(self):
        self.getPage().refresh()

    def OnTabClicked(self, tab):
        self.scriptPanel.gd.mainFrame.showSideTab(tab)

    def OnClose(self, event):
        self.scriptPanel.gd.mainFrame.setShowSidePanel(False)
