import wx
from wx.lib.wordwrap import wordwrap

import trelby.screenplay as screenplay
import trelby.ui.gutil as gutil
import trelby.ui.icons as icons
import trelby.ui.widgets as widgets
from trelby.ui.theming import blendColors
from trelby.ui.scrollbar import ScrollBar

# max number of lines of summary text shown under each scene
SUMMARY_LINES = 2


# return the colors offered for scenes, as a list of (name, "rrggbb").
# they're light enough that dark text stays readable on them.
def getSceneColors():
    return [
        (_("Red"), "ffb3b3"),
        (_("Orange"), "ffd1a3"),
        (_("Yellow"), "fff2a8"),
        (_("Green"), "c5f0b8"),
        (_("Teal"), "b3ece6"),
        (_("Blue"), "b8d4ff"),
        (_("Purple"), "dcc4ff"),
        (_("Pink"), "ffc4e1"),
        (_("Gray"), "dcdcdc"),
    ]


# return the wx.Colour for a scene color ("rrggbb")
def str2color(s):
    return wx.Colour("#" + s)


# opposite of str2color
def color2str(c):
    return c.GetAsString(wx.C2S_HTML_SYNTAX)[1:].lower()


# return the relative luminance of a color, 0.0 - 1.0
def luminance(c):
    return (0.299 * c.Red() + 0.587 * c.Green() + 0.114 * c.Blue()) / 255.0


# return a menu bitmap showing a swatch of the given color ("rrggbb"), with
# a check mark on it if 'checked' is True
def swatchBitmap(color, checked):
    check = ""

    if checked:
        stroke = "#000000" if luminance(str2color(color)) > 0.5 else "#ffffff"
        check = (
            '<path d="M 4,8.5 L 7,11.5 L 12.5,5" fill="none" stroke="%s"'
            ' stroke-width="1.8" />' % stroke
        )

    svg = (
        '<svg width="16" height="16" viewBox="0 0 16 16"'
        ' xmlns="http://www.w3.org/2000/svg">'
        '<rect x="1.5" y="1.5" width="13" height="13" rx="2" fill="#%s"'
        ' stroke="#808080" />%s</svg>' % (color, check)
    )

    return wx.BitmapBundle.FromSVG(svg.encode(), wx.Size(16, 16))


# the outline's list of items. each row shows the scene number, heading
# and page on one line, with the scene's summary wrapped underneath.
class OutlineList(wx.VListBox):
    def __init__(self, parent):
        wx.VListBox.__init__(self, parent, -1, style=wx.BORDER_NONE)

        # screenplay.OutlineItems shown
        self.items = []

        # index of the item highlighted while its color menu is shown, or
        # None
        self.markIdx = None

        # while dragging a scene: index of the item being dragged, and of
        # the item it would be dropped on (None if dropping isn't possible
        # at the current mouse position)
        self.dragIdx = None
        self.dragDst = None

        self.normalFont = self.GetFont()
        self.boldFont = self.normalFont.Bold()

        # color of the selection, the drag outline and the insert mark.
        # OutlinePanel.applyTheme sets the theme's accent color.
        self.highlight = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)

        self.pad = self.FromDIP(wx.Size(6, 8))
        self.gap = self.FromDIP(8)

        # width of the bar of full color at the left edge of colored rows
        self.barWidth = self.FromDIP(3)
        self.lineHeight = max(
            self.GetFullTextExtent("Ag", font)[1]
            for font in (self.normalFont, self.boldFont)
        )

        # width of the scene number column
        self.nrWidth = 0

        # wrapped summary lines for each item index, valid for summaryWidth
        self.summaryCache = {}
        self.summaryWidth = None

        self.Bind(wx.EVT_SIZE, self.OnSize)

    def setItems(self, items):
        self.items = items
        self.summaryCache = {}

        self.nrWidth = max(
            [self.GetTextExtent("00").width]
            + [self.GetTextExtent(it.sceneNr).width for it in items]
        )

        # also makes the list re-measure all rows
        self.SetItemCount(len(items))
        self.Refresh()

    def refreshRows(self, rows):
        for i in rows:
            if (i is not None) and (i < self.GetItemCount()):
                self.RefreshRow(i)

    def setMarkedIndex(self, idx):
        old = self.markIdx
        self.markIdx = idx
        self.refreshRows({old, idx})

    # show item src as being dragged, and where it would land if dropped
    # on item dst. both None when no drag is in progress.
    def setDrag(self, src, dst):
        if (src, dst) == (self.dragIdx, self.dragDst):
            return

        rows = {self.dragIdx, self.dragDst, src, dst}
        self.dragIdx = src
        self.dragDst = dst
        self.refreshRows(rows)

    # x position of the heading and summary text, relative to the row
    def getTextX(self):
        return self.pad.x + self.nrWidth + self.gap

    # return the summary of item n wrapped to fit the list's width
    def getSummaryLines(self, n):
        width = self.GetClientSize().width - self.getTextX() - self.pad.x

        if width != self.summaryWidth:
            self.summaryCache = {}
            self.summaryWidth = width

        lines = self.summaryCache.get(n)

        if lines is None:
            lines = self.wrapSummary(self.items[n].summary.strip(), width)
            self.summaryCache[n] = lines

        return lines

    def wrapSummary(self, text, width):
        if not text or (width <= 0):
            return []

        dc = wx.ClientDC(self)
        dc.SetFont(self.normalFont)
        lines = [s.strip() for s in wordwrap(text, width, dc).split("\n")]

        if len(lines) > SUMMARY_LINES:
            rest = " ".join(lines[SUMMARY_LINES - 1 :])
            lines = lines[: SUMMARY_LINES - 1] + [
                wx.Control.Ellipsize(rest + " ...", dc, wx.ELLIPSIZE_END, width)
            ]

        return lines

    def isHighlighted(self, n):
        return (n == self.markIdx) or (self.IsSelected(n) and self.HasFocus())

    def OnMeasureItem(self, n):
        lines = 1 + len(self.getSummaryLines(n))

        return self.pad.y * 2 + lines * self.lineHeight

    # return the background color of item n, ignoring selection, or None
    # if it has no color of its own. on dark backgrounds the color is
    # toned down so that light text stays readable on it.
    def getItemColor(self, n):
        color = self.items[n].color

        if not color:
            return None

        c = str2color(color)
        bg = self.GetBackgroundColour()

        if luminance(bg) < 0.5:
            c = blendColors(bg, c, 0.35)

        return c

    # return item n's background, including selection
    def getRowColor(self, n):
        bg = self.getItemColor(n) or self.GetBackgroundColour()
        hl = self.highlight

        if self.isHighlighted(n):
            return blendColors(bg, hl, 0.2)
        elif self.IsSelected(n):
            return blendColors(bg, hl, 0.1)

        return bg

    # return the color to draw item n's text with on the background bg
    def getTextColor(self, n, bg):
        fg = self.GetForegroundColour()

        # a custom color can be too close to the normal text color
        if self.items[n].color and (abs(luminance(fg) - luminance(bg)) < 0.4):
            fg = wx.BLACK if luminance(bg) > 0.5 else wx.WHITE

        return fg

    def OnDrawBackground(self, dc, rect, n):
        bg = self.GetBackgroundColour()
        hl = self.highlight
        fill = self.getRowColor(n)

        if fill != bg:
            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.SetBrush(wx.Brush(fill))
            dc.DrawRectangle(rect)

        if self.items[n].color:
            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.SetBrush(wx.Brush(str2color(self.items[n].color)))
            dc.DrawRectangle(rect.x, rect.y, self.barWidth, rect.height)

        if n == self.markIdx:
            dc.SetPen(wx.Pen(hl))
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.DrawRectangle(rect)

        # separator between rows
        dc.SetPen(wx.Pen(blendColors(bg, self.GetForegroundColour(), 0.12)))
        y = rect.GetBottom()
        dc.DrawLine(rect.GetLeft(), y, rect.GetRight() + 1, y)

        # dashed outline around the item being dragged
        if n == self.dragIdx:
            dc.SetPen(wx.Pen(hl, self.FromDIP(1), wx.PENSTYLE_SHORT_DASH))
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.DrawRectangle(wx.Rect(rect).Deflate(self.FromDIP(1)))

    # draw the line showing where a dragged item would be inserted, at the
    # bottom of row n (in rect) if 'below' is True, otherwise at its top.
    # rows are drawn clipped to their own rect, so it has to fit inside.
    def drawInsertMark(self, dc, rect, n, below):
        hl = self.highlight
        thickness = self.FromDIP(2)
        radius = self.FromDIP(4)

        if below:
            cy = rect.GetBottom() - radius
        else:
            cy = rect.y + radius

        cx = rect.x + self.barWidth + radius + self.FromDIP(1)

        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(hl))
        dc.DrawRectangle(
            cx, cy - thickness // 2, rect.GetRight() - self.pad.x - cx, thickness
        )

        dc.SetPen(wx.Pen(hl, thickness))
        dc.SetBrush(wx.Brush(self.getRowColor(n)))
        dc.DrawCircle(cx, cy, radius - thickness // 2)

    def OnDrawItem(self, dc, rect, n):
        it = self.items[n]
        rowBg = self.getRowColor(n)
        fg = self.getTextColor(n, rowBg)

        # fade out the item being dragged
        if n == self.dragIdx:
            fg = blendColors(fg, rowBg, 0.6)

        x = rect.x + self.pad.x
        y = rect.y + self.pad.y
        right = rect.GetRight() - self.pad.x
        textX = rect.x + self.getTextX()

        dc.SetFont(
            self.boldFont if it.lt == screenplay.ACTBREAK else self.normalFont
        )
        dc.SetTextForeground(fg)

        if it.sceneNr:
            w = dc.GetTextExtent(it.sceneNr).width
            dc.DrawText(it.sceneNr, x + self.nrWidth - w, y)

        pageW = dc.GetTextExtent(it.page).width if it.page else 0

        if it.page:
            dc.DrawText(it.page, right - pageW + 1, y)

        headingW = right - textX - ((pageW + self.gap) if pageW else 0)

        if headingW > 0:
            dc.DrawText(
                wx.Control.Ellipsize(it.heading, dc, wx.ELLIPSIZE_END, headingW),
                textX,
                y,
            )

        dc.SetFont(self.normalFont)

        if self.isHighlighted(n):
            dc.SetTextForeground(fg)
        else:
            dc.SetTextForeground(blendColors(fg, rowBg, 0.4))

        for line in self.getSummaryLines(n):
            y += self.lineHeight
            dc.DrawText(line, textX, y)

        # dropping item dragIdx on item n puts it where n is now, so it
        # lands after n when moving down and before it when moving up
        if (n == self.dragDst) and (n != self.dragIdx):
            self.drawInsertMark(dc, rect, n, n > self.dragIdx)

    def OnSize(self, event):
        event.Skip()

        width = self.GetClientSize().width - self.getTextX() - self.pad.x

        # rows' heights depend on how the summaries wrap
        if width != self.summaryWidth:
            self.SetItemCount(len(self.items))
            self.Refresh()


# side panel showing a script's outline: its scenes and act breaks.
# selecting an item jumps to it in the script, and scenes can be reordered
# by dragging them, with the buttons, or with Ctrl+Up / Ctrl+Down. the
# selection follows the cursor as the user moves around in the script.
class OutlinePanel(wx.Panel):

    # how long to wait after the last change before refreshing, in ms. we
    # don't want to recompute the outline on every keypress.
    REFRESH_DELAY = 300

    # how often to check whether to auto-scroll while dragging, in ms
    DRAG_SCROLL_INTERVAL = 80

    def __init__(self, parent, scriptPanel):
        wx.Panel.__init__(self, parent, -1)

        # trelbypanel.MyPanel whose script we show
        self.scriptPanel = scriptPanel

        # screenplay.OutlineItems currently shown in the list
        self.items = []

        # True while we change the list's selection ourselves, so that we
        # don't mistake it for the user picking an item
        self.updating = False

        # while dragging a scene: index of the item being dragged, and of
        # the item it would be dropped on (None if dropping isn't possible
        # at the current mouse position)
        self.dragIdx = None
        self.dropIdx = None

        # last mouse position seen while dragging, in the list's client
        # coordinates
        self.dragPos = None

        vsizer = wx.BoxSizer(wx.VERTICAL)

        # header: the panel's title, buttons to move the selected scene,
        # and a button to close the panel
        hdr = wx.BoxSizer(wx.HORIZONTAL)

        self.title = wx.StaticText(self, -1, _("Outline"))
        self.title.SetFont(self.title.GetFont().Bold())
        hdr.Add(self.title, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, self.FromDIP(6))

        def addBtn(iconFilename, toolTip):
            bitmap = icons.svgBitmap(iconFilename, wx.Size(16, 16))
            btn = wx.BitmapButton(self, -1, bitmap, style=wx.BORDER_NONE)
            btn.SetToolTip(toolTip)
            hdr.Add(btn, 0, wx.ALL, self.FromDIP(2))

            return btn

        self.upBtn = addBtn("moveup.svg", _("Move the selected scene up (Ctrl+Up)"))
        self.downBtn = addBtn(
            "movedown.svg", _("Move the selected scene down (Ctrl+Down)")
        )
        self.colorBtn = addBtn(
            "scenecolor.svg",
            _("Set the selected scene's color (or right-click a scene)"),
        )
        hdr.AddSpacer(self.FromDIP(6))
        self.closeBtn = addBtn("closepanel.svg", _("Hide the outline"))

        vsizer.Add(hdr, 0, wx.EXPAND)
        self.separator = widgets.Separator(self)
        vsizer.Add(self.separator, 0, wx.EXPAND)

        # the list's native scrollbar ignores the theme's colors, so when
        # the list has one, it's sized to put it just past the right edge of
        # listHolder, out of sight, and scrollBar stands in for it
        self.listHolder = wx.Window(self, -1, style=wx.BORDER_NONE)

        # the scenes are the script's text, which is left to right in a
        # right-to-left interface too
        gutil.keepLeftToRight(self.listHolder)

        self.list = OutlineList(self.listHolder)
        self.scrollBar = ScrollBar(self, self.list)

        lsizer = wx.BoxSizer(wx.HORIZONTAL)
        lsizer.Add(self.listHolder, 1, wx.EXPAND)
        lsizer.Add(self.scrollBar, 0, wx.EXPAND)
        vsizer.Add(lsizer, 1, wx.EXPAND)

        self.SetSizer(vsizer)

        # where the left mouse button was pressed, in the list's client
        # coordinates, and the item under it. a drag starts once the mouse
        # moves far enough with the button held down.
        self.pressPos = None
        self.pressIdx = None

        self.timer = wx.Timer(self)
        self.dragTimer = wx.Timer(self)

        self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)
        self.Bind(wx.EVT_TIMER, self.OnDragTimer, self.dragTimer)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        self.listHolder.Bind(wx.EVT_SIZE, self.OnListHolderSize)
        self.scrollBar.Bind(wx.EVT_COMMAND_SCROLL, self.OnScroll)
        self.list.Bind(wx.EVT_SIZE, self.OnListSize)
        self.list.Bind(wx.EVT_IDLE, self.OnListIdle)
        self.list.Bind(wx.EVT_LISTBOX, self.OnItemSelected)
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, self.OnItemActivated)
        self.list.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.list.Bind(wx.EVT_MOTION, self.OnMouseMotion)
        self.list.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.list.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self.OnCaptureLost)
        self.list.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.list.Bind(wx.EVT_CONTEXT_MENU, self.OnContextMenu)
        self.upBtn.Bind(wx.EVT_BUTTON, self.OnMoveUp)
        self.downBtn.Bind(wx.EVT_BUTTON, self.OnMoveDown)
        self.colorBtn.Bind(wx.EVT_BUTTON, self.OnColorBtn)
        self.closeBtn.Bind(wx.EVT_BUTTON, self.OnClose)

        self.updateButtons()

    def getCtrl(self):
        return self.scriptPanel.ctrl

    # use the colors of the theme in the given configgui.ConfigGui: the header
    # like the tab bar, and the list like the page
    def applyTheme(self, cfgGui):
        self.SetBackgroundColour(cfgGui.tabBarBgColor)
        self.SetForegroundColour(cfgGui.tabTextColor)

        for w in (self.title, self.upBtn, self.downBtn, self.colorBtn, self.closeBtn):
            w.SetBackgroundColour(cfgGui.tabBarBgColor)
            w.SetForegroundColour(cfgGui.tabTextColor)

        self.separator.applyTheme(cfgGui)

        self.list.SetBackgroundColour(cfgGui.textBgColor)
        self.list.SetForegroundColour(cfgGui.textColor)
        self.list.highlight = cfgGui.accentColor
        self.listHolder.SetBackgroundColour(cfgGui.textBgColor)
        self.scrollBar.setColors(cfgGui.textBgColor, cfgGui.textColor)

        self.Refresh()

    # size the list to fill listHolder, plus the width of its native
    # scrollbar if it has one. called again when the scrollbar comes or goes.
    def layoutList(self):
        lc = self.list
        size = self.listHolder.GetClientSize()
        sbWidth = lc.GetSize().width - lc.GetClientSize().width
        rect = wx.Rect(0, 0, size.width + sbWidth, size.height)

        if lc.GetRect() != rect:
            lc.SetSize(rect)

        self.updateScrollBar()

    # make scrollBar match the list's native scrollbar
    def updateScrollBar(self):
        lc = self.list
        thumb = lc.GetScrollThumb(wx.VERTICAL)

        self.scrollBar.SetScrollbar(
            lc.GetScrollPos(wx.VERTICAL), thumb, lc.GetScrollRange(wx.VERTICAL), thumb
        )

    def OnListHolderSize(self, event):
        self.layoutList()

    def OnListSize(self, event):
        event.Skip()
        self.layoutList()

    # the list can scroll in many ways (the mouse wheel, the keyboard, the
    # selection changing, ...), which all end with it going idle
    def OnListIdle(self, event):
        event.Skip()
        self.updateScrollBar()

    def OnScroll(self, event):
        self.list.ScrollToRow(self.scrollBar.GetThumbPosition())

    # refresh the outline once things have been quiet for a moment
    def scheduleRefresh(self):
        if self.IsShown():
            self.timer.StartOnce(self.REFRESH_DELAY)

    # refresh the outline right away
    def refresh(self):
        self.timer.Stop()

        if not self.IsShown():
            return

        # don't shuffle rows around under the mouse; endDrag refreshes
        if self.dragIdx is not None:
            return

        items = self.getCtrl().sp.getOutline()

        # OutlineItems compare by value, so the list is only refilled (and
        # its rows re-measured) when something it shows has changed
        if items != self.items:
            self.items = items
            self.fillList()

        self.selectCurrent()

    # update the list's contents from self.items
    def fillList(self):
        self.list.setItems(self.items)

    # return index of the item containing the given line, or -1
    def findItem(self, line):
        for i, it in enumerate(self.items):
            if it.startLine <= line <= it.endLine:
                return i

        return -1

    # select the item containing the cursor
    def selectCurrent(self):
        lc = self.list
        idx = self.findItem(self.getCtrl().ed.line)

        if idx != lc.GetSelection():
            self.updating = True

            try:
                # also scrolls the item into view
                lc.SetSelection(idx)
            finally:
                self.updating = False

        self.updateButtons()

    def updateButtons(self):
        idx = self.list.GetSelection()

        self.upBtn.Enable(idx > 0)
        self.downBtn.Enable((idx != -1) and (idx < (len(self.items) - 1)))
        self.colorBtn.Enable(idx != -1)

    # move item number idx so that it becomes item number newIndex
    def moveItem(self, idx, newIndex):
        self.getCtrl().moveSceneTo(self.items[idx].startLine, newIndex)
        self.refresh()

    def moveScene(self, direction):
        idx = self.list.GetSelection()

        if idx == -1:
            return

        self.moveItem(idx, idx + direction)

    # return index of the item a dragged scene would be dropped on when
    # the mouse is at pos (in the list's client coordinates), or None if
    # it's outside the list. positions above or below the visible rows map
    # to the first or last visible row, so that auto-scrolling works.
    def getDropIndex(self, pos):
        lc = self.list
        width = lc.GetClientSize().width
        cnt = lc.GetItemCount()

        if (cnt == 0) or (pos.x < 0) or (pos.x >= width):
            return None

        if pos.y < 0:
            return lc.GetVisibleRowsBegin()

        idx = lc.VirtualHitTest(pos.y)

        if idx == wx.NOT_FOUND:
            return min(cnt, lc.GetVisibleRowsEnd()) - 1

        return idx

    # show where the dragged item would be dropped
    def setDropIndex(self, idx):
        lc = self.list
        lc.setDrag(self.dragIdx, idx)

        # scenes can only move up or down
        if idx is not None:
            lc.SetCursor(wx.Cursor(wx.CURSOR_SIZENS))
        else:
            lc.SetCursor(wx.Cursor(wx.CURSOR_NO_ENTRY))

        self.dropIdx = idx

    # scroll the list if the mouse is near (or past) its top or bottom edge
    def autoScroll(self, pos):
        lc = self.list
        edge = lc.lineHeight

        if pos.y < edge:
            lc.ScrollRows(-1)
        elif pos.y >= lc.GetClientSize().height - edge:
            lc.ScrollRows(1)

    def endDrag(self):
        self.dragTimer.Stop()
        self.dropIdx = None

        lc = self.list
        lc.setDrag(None, None)

        if lc.HasCapture():
            lc.ReleaseMouse()

        lc.SetCursor(wx.NullCursor)
        self.dragIdx = None

    def beginDrag(self, idx, pos):
        self.dragIdx = idx
        self.dragPos = pos
        self.setDropIndex(self.dragIdx)

        # so that Escape reaches us
        self.list.SetFocus()

        self.list.CaptureMouse()
        self.dragTimer.Start(self.DRAG_SCROLL_INTERVAL)

    def OnLeftDown(self, event):
        idx = self.list.VirtualHitTest(event.GetPosition().y)

        if idx != wx.NOT_FOUND:
            self.pressPos = event.GetPosition()
            self.pressIdx = idx
        else:
            self.pressPos = None

        event.Skip()

    def OnMouseMotion(self, event):
        if self.dragIdx is None:
            pos = event.GetPosition()

            if (
                (self.pressPos is not None)
                and event.LeftIsDown()
                and (
                    abs(pos.x - self.pressPos.x)
                    > wx.SystemSettings.GetMetric(wx.SYS_DRAG_X)
                    or abs(pos.y - self.pressPos.y)
                    > wx.SystemSettings.GetMetric(wx.SYS_DRAG_Y)
                )
            ):
                self.pressPos = None
                self.beginDrag(self.pressIdx, pos)
            else:
                event.Skip()

            return

        self.dragPos = event.GetPosition()
        self.setDropIndex(self.getDropIndex(self.dragPos))

    # auto-scrolls even if the mouse is held still
    def OnDragTimer(self, event):
        if self.dragIdx is None:
            return

        self.autoScroll(self.dragPos)
        self.setDropIndex(self.getDropIndex(self.dragPos))

    def OnLeftUp(self, event):
        self.pressPos = None

        if self.dragIdx is None:
            event.Skip()

            return

        src = self.dragIdx
        dst = self.getDropIndex(event.GetPosition())

        self.endDrag()

        if (dst is not None) and (dst != src):
            self.moveItem(src, dst)
        else:
            self.refresh()

    def OnCaptureLost(self, event):
        self.endDrag()
        self.refresh()

    def OnTimer(self, event):
        self.refresh()

    def OnDestroy(self, event):
        if event.GetEventObject() is self:
            self.timer.Stop()
            self.dragTimer.Stop()

        event.Skip()

    def OnItemSelected(self, event):
        if self.updating:
            return

        idx = event.GetSelection()

        if not (0 <= idx < len(self.items)):
            return

        it = self.items[idx]
        ctrl = self.getCtrl()

        # selection was caused by the cursor moving into this item
        if it.startLine <= ctrl.ed.line <= it.endLine:
            self.updateButtons()

            return

        ctrl.gotoLine(it.startLine)
        self.updateButtons()

    # Enter / double-click: go to the item and start editing there
    def OnItemActivated(self, event):
        self.activateItem(event.GetSelection())

    def activateItem(self, idx):
        if not (0 <= idx < len(self.items)):
            return

        ctrl = self.getCtrl()

        ctrl.gotoLine(self.items[idx].startLine)
        ctrl.SetFocus()

    def OnKeyDown(self, event):
        kc = event.GetKeyCode()

        if self.dragIdx is not None:
            if kc == wx.WXK_ESCAPE:
                self.endDrag()
                self.refresh()

            return

        if event.ControlDown() and (kc == wx.WXK_UP):
            self.moveScene(-1)
        elif event.ControlDown() and (kc == wx.WXK_DOWN):
            self.moveScene(1)
        elif kc in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.activateItem(self.list.GetSelection())
        elif kc == wx.WXK_ESCAPE:
            self.getCtrl().SetFocus()
        else:
            event.Skip()

    # let the user pick the color of item number idx from a menu shown at
    # pos (in win's client coordinates), and set it
    def showColorMenu(self, idx, win, pos):
        it = self.items[idx]
        colors = getSceneColors()
        menu = wx.Menu()

        noneId = wx.NewIdRef()
        customId = wx.NewIdRef()
        colorIds = {}

        menu.AppendCheckItem(noneId, _("No color")).Check(it.color is None)
        menu.AppendSeparator()

        # ids are only reserved while their WindowIDRefs exist
        idRefs = []

        for name, color in colors:
            idRefs.append(wx.NewIdRef())
            mi = wx.MenuItem(menu, idRefs[-1], name)
            mi.SetBitmap(swatchBitmap(color, color == it.color))
            menu.Append(mi)
            colorIds[mi.GetId()] = color

        menu.AppendSeparator()

        mi = wx.MenuItem(menu, customId, _("Custom color..."))

        # show a custom color the item already has
        if it.color and (it.color not in colorIds.values()):
            mi.SetBitmap(swatchBitmap(it.color, True))

        menu.Append(mi)

        # show which item the menu is for
        self.list.setMarkedIndex(idx)

        try:
            sel = win.GetPopupMenuSelectionFromUser(menu, pos)
        finally:
            self.list.setMarkedIndex(None)
            menu.Destroy()

        if sel == int(noneId):
            color = None
        elif sel in colorIds:
            color = colorIds[sel]
        elif sel == int(customId):
            color = self.askCustomColor(it.color)

            if color is None:
                return
        else:
            return

        self.getCtrl().setSceneColor(it.startLine, color)
        self.refresh()

    # show a color dialog starting at color ("rrggbb" or None) and return
    # the color picked as "rrggbb", or None if cancelled
    def askCustomColor(self, color):
        data = wx.ColourData()
        data.SetChooseFull(True)

        if color:
            data.SetColour(str2color(color))

        dlg = wx.ColourDialog(self, data)
        dlg.SetTitle(_("Scene color"))

        try:
            if dlg.ShowModal() != wx.ID_OK:
                return None

            return color2str(dlg.GetColourData().GetColour())
        finally:
            dlg.Destroy()

    def OnContextMenu(self, event):
        if self.dragIdx is not None:
            return

        lc = self.list
        pos = event.GetPosition()

        # from the keyboard: use the selected item
        if pos == wx.DefaultPosition:
            idx = lc.GetSelection()

            if idx == -1:
                return

            rect = lc.GetItemRect(idx)
            pos = wx.Point(rect.x + lc.getTextX(), rect.GetBottom())
        else:
            pos = lc.ScreenToClient(pos)
            idx = lc.VirtualHitTest(pos.y)

            if idx == wx.NOT_FOUND:
                return

        self.showColorMenu(idx, lc, pos)

    def OnColorBtn(self, event):
        idx = self.list.GetSelection()

        if idx == -1:
            return

        rect = self.colorBtn.GetRect()
        self.showColorMenu(idx, self, wx.Point(rect.x, rect.GetBottom()))

    def OnMoveUp(self, event):
        self.moveScene(-1)

    def OnMoveDown(self, event):
        self.moveScene(1)

    def OnClose(self, event):
        self.scriptPanel.gd.mainFrame.setShowOutline(False)
