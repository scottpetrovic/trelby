import wx
from wx.lib.wordwrap import wordwrap

import trelby.gutil as gutil
import trelby.screenplay as screenplay

# max number of lines of summary text shown under each scene
SUMMARY_LINES = 2


# return color c1 mixed with c2, with a being the fraction of c2
def blendColors(c1, c2, a):
    return wx.Colour(
        *[
            int(v1 * (1.0 - a) + v2 * a)
            for v1, v2 in zip(c1.Get(False), c2.Get(False))
        ]
    )


# the outline's list of items. each row shows the scene number, heading
# and page on one line, with the scene's summary wrapped underneath.
class OutlineList(wx.VListBox):
    def __init__(self, parent):
        wx.VListBox.__init__(self, parent, -1, style=wx.BORDER_NONE)

        # screenplay.OutlineItems shown
        self.items = []

        # index of the item highlighted as a drop target, or None
        self.dropIdx = None

        self.normalFont = self.GetFont()
        self.boldFont = self.normalFont.Bold()

        self.pad = self.FromDIP(wx.Size(6, 8))
        self.gap = self.FromDIP(8)
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

    def setDropIndex(self, idx):
        old = self.dropIdx
        self.dropIdx = idx

        for i in (old, idx):
            if (i is not None) and (i < self.GetItemCount()):
                self.RefreshRow(i)

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
        return (n == self.dropIdx) or (self.IsSelected(n) and self.HasFocus())

    def OnMeasureItem(self, n):
        lines = 1 + len(self.getSummaryLines(n))

        return self.pad.y * 2 + lines * self.lineHeight

    def OnDrawBackground(self, dc, rect, n):
        bg = self.GetBackgroundColour()
        hl = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)

        if self.isHighlighted(n):
            fill = blendColors(bg, hl, 0.45)
        elif self.IsSelected(n):
            fill = blendColors(bg, hl, 0.25)
        else:
            fill = None

        if fill is not None:
            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.SetBrush(wx.Brush(fill))
            dc.DrawRectangle(rect)

        if n == self.dropIdx:
            dc.SetPen(wx.Pen(hl))
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.DrawRectangle(rect)

        # separator between rows
        dc.SetPen(wx.Pen(blendColors(bg, self.GetForegroundColour(), 0.12)))
        y = rect.GetBottom()
        dc.DrawLine(rect.GetLeft(), y, rect.GetRight() + 1, y)

    def OnDrawItem(self, dc, rect, n):
        it = self.items[n]
        fg = self.GetForegroundColour()

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
            dc.SetTextForeground(
                blendColors(fg, self.GetBackgroundColour(), 0.4)
            )

        for line in self.getSummaryLines(n):
            y += self.lineHeight
            dc.DrawText(line, textX, y)

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

        title = wx.StaticText(self, -1, _("Outline"))
        title.SetFont(title.GetFont().Bold())
        hdr.Add(title, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, self.FromDIP(6))

        def addBtn(iconFilename, toolTip):
            bitmap = gutil.svgBitmap(iconFilename, wx.Size(16, 16))
            btn = wx.BitmapButton(self, -1, bitmap, style=wx.BORDER_NONE)
            btn.SetToolTip(toolTip)
            hdr.Add(btn, 0, wx.ALL, self.FromDIP(2))

            return btn

        self.upBtn = addBtn("moveup.svg", _("Move the selected scene up (Ctrl+Up)"))
        self.downBtn = addBtn(
            "movedown.svg", _("Move the selected scene down (Ctrl+Down)")
        )
        hdr.AddSpacer(self.FromDIP(6))
        self.closeBtn = addBtn("closepanel.svg", _("Hide the outline"))

        vsizer.Add(hdr, 0, wx.EXPAND)
        vsizer.Add(wx.StaticLine(self, -1), 0, wx.EXPAND)

        self.list = OutlineList(self)

        vsizer.Add(self.list, 1, wx.EXPAND)

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
        self.list.Bind(wx.EVT_LISTBOX, self.OnItemSelected)
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, self.OnItemActivated)
        self.list.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.list.Bind(wx.EVT_MOTION, self.OnMouseMotion)
        self.list.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.list.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self.OnCaptureLost)
        self.list.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.upBtn.Bind(wx.EVT_BUTTON, self.OnMoveUp)
        self.downBtn.Bind(wx.EVT_BUTTON, self.OnMoveDown)
        self.closeBtn.Bind(wx.EVT_BUTTON, self.OnClose)

        self.updateButtons()

    def getCtrl(self):
        return self.scriptPanel.ctrl

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
        idx = self.findItem(self.getCtrl().sp.line)

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

    # show the drop target as highlighted
    def setDropIndex(self, idx):
        lc = self.list
        lc.setDropIndex(idx)

        if idx is not None:
            lc.SetCursor(wx.Cursor(wx.CURSOR_HAND))
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
        self.setDropIndex(None)

        lc = self.list

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
        if it.startLine <= ctrl.sp.line <= it.endLine:
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

    def OnMoveUp(self, event):
        self.moveScene(-1)

    def OnMoveDown(self, event):
        self.moveScene(1)

    def OnClose(self, event):
        self.scriptPanel.gd.mainFrame.setShowOutline(False)
