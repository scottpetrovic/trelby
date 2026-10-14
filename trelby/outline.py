import wx

import trelby.screenplay as screenplay

# max length of the summary text shown for each scene
MAX_SUMMARY_LEN = 200


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

        # header: the panel's title and a button to close it
        hdr = wx.BoxSizer(wx.HORIZONTAL)

        title = wx.StaticText(self, -1, _("Outline"))
        title.SetFont(title.GetFont().Bold())
        hdr.Add(title, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, self.FromDIP(6))

        self.closeBtn = wx.Button(
            self, -1, "\u2715", style=wx.BU_EXACTFIT | wx.BORDER_NONE
        )
        self.closeBtn.SetToolTip(_("Hide the outline"))
        hdr.Add(self.closeBtn, 0, wx.ALL, self.FromDIP(2))

        vsizer.Add(hdr, 0, wx.EXPAND)
        vsizer.Add(wx.StaticLine(self, -1), 0, wx.EXPAND)

        self.list = wx.ListCtrl(
            self, -1, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_NONE
        )
        self.list.InsertColumn(0, "#", wx.LIST_FORMAT_RIGHT, 36)
        self.list.InsertColumn(1, _("Scene"), width=190)
        self.list.InsertColumn(2, _("Page"), wx.LIST_FORMAT_RIGHT, 44)
        self.list.InsertColumn(3, _("Summary"), width=300)

        vsizer.Add(self.list, 1, wx.EXPAND)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        self.upBtn = wx.Button(self, -1, _("Move up"))
        self.upBtn.SetToolTip(_("Move the selected scene up (Ctrl+Up)"))
        hsizer.Add(self.upBtn, 1, wx.ALL, 4)

        self.downBtn = wx.Button(self, -1, _("Move down"))
        self.downBtn.SetToolTip(_("Move the selected scene down (Ctrl+Down)"))
        hsizer.Add(self.downBtn, 1, wx.TOP | wx.BOTTOM | wx.RIGHT, 4)

        vsizer.Add(hsizer, 0, wx.EXPAND)

        self.SetSizer(vsizer)

        self.normalFont = self.list.GetFont()
        self.boldFont = self.normalFont.Bold()

        self.timer = wx.Timer(self)
        self.dragTimer = wx.Timer(self)

        self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)
        self.Bind(wx.EVT_TIMER, self.OnDragTimer, self.dragTimer)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        self.list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnItemSelected)
        self.list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnItemActivated)
        self.list.Bind(wx.EVT_LIST_BEGIN_DRAG, self.OnBeginDrag)
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

    # update the list's contents from self.items. existing rows are reused
    # so that the list's scroll position is kept.
    def fillList(self):
        lc = self.list
        lc.Freeze()

        try:
            while lc.GetItemCount() > len(self.items):
                lc.DeleteItem(lc.GetItemCount() - 1)

            while lc.GetItemCount() < len(self.items):
                lc.InsertItem(lc.GetItemCount(), "")

            for i, it in enumerate(self.items):
                summary = it.summary

                if len(summary) > MAX_SUMMARY_LEN:
                    summary = summary[:MAX_SUMMARY_LEN] + "..."

                lc.SetItem(i, 0, it.sceneNr)
                lc.SetItem(i, 1, it.heading)
                lc.SetItem(i, 2, str(it.page))
                lc.SetItem(i, 3, summary)

                if it.lt == screenplay.ACTBREAK:
                    lc.SetItemFont(i, self.boldFont)
                else:
                    lc.SetItemFont(i, self.normalFont)
        finally:
            lc.Thaw()

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

        if idx != lc.GetFirstSelected():
            self.updating = True

            try:
                sel = lc.GetFirstSelected()

                if sel != -1:
                    lc.Select(sel, False)

                if idx != -1:
                    lc.Select(idx)
                    lc.Focus(idx)
            finally:
                self.updating = False

        self.updateButtons()

    def updateButtons(self):
        idx = self.list.GetFirstSelected()

        self.upBtn.Enable(idx > 0)
        self.downBtn.Enable((idx != -1) and (idx < (len(self.items) - 1)))

    # move item number idx so that it becomes item number newIndex
    def moveItem(self, idx, newIndex):
        self.getCtrl().moveSceneTo(self.items[idx].startLine, newIndex)
        self.refresh()

    def moveScene(self, direction):
        idx = self.list.GetFirstSelected()

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

        top = lc.GetTopItem()
        last = min(cnt - 1, top + lc.GetCountPerPage())

        for i in range(top, last + 1):
            if pos.y <= lc.GetItemRect(i).GetBottom():
                return i

        return last

    # show the drop target as highlighted
    def setDropIndex(self, idx):
        lc = self.list
        state = wx.LIST_STATE_DROPHILITED

        if self.dropIdx is not None:
            lc.SetItemState(self.dropIdx, 0, state)

        if idx is not None:
            lc.SetItemState(idx, state, state)
            lc.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        else:
            lc.SetCursor(wx.Cursor(wx.CURSOR_NO_ENTRY))

        self.dropIdx = idx

    # scroll the list if the mouse is at (or past) its top or bottom row
    def autoScroll(self, pos):
        lc = self.list
        cnt = lc.GetItemCount()

        if cnt == 0:
            return

        top = lc.GetTopItem()
        perPage = lc.GetCountPerPage()

        if (top > 0) and (pos.y <= lc.GetItemRect(top).GetBottom()):
            lc.EnsureVisible(top - 1)
        elif (top + perPage < cnt) and (
            pos.y >= lc.GetItemRect(top + perPage - 1).GetTop()
        ):
            lc.EnsureVisible(top + perPage)

    def endDrag(self):
        self.dragTimer.Stop()
        self.setDropIndex(None)

        lc = self.list

        if lc.HasCapture():
            lc.ReleaseMouse()

        lc.SetCursor(wx.NullCursor)
        self.dragIdx = None

    def OnBeginDrag(self, event):
        if not self.items:
            return

        self.dragIdx = event.GetIndex()
        self.dragPos = event.GetPoint()
        self.setDropIndex(self.dragIdx)

        # so that Escape reaches us
        self.list.SetFocus()

        self.list.CaptureMouse()
        self.dragTimer.Start(self.DRAG_SCROLL_INTERVAL)

    def OnMouseMotion(self, event):
        if self.dragIdx is None:
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

        it = self.items[event.GetIndex()]
        ctrl = self.getCtrl()

        # selection was caused by the cursor moving into this item
        if it.startLine <= ctrl.sp.line <= it.endLine:
            self.updateButtons()

            return

        ctrl.gotoLine(it.startLine)
        self.updateButtons()

    # Enter / double-click: go to the item and start editing there
    def OnItemActivated(self, event):
        ctrl = self.getCtrl()

        ctrl.gotoLine(self.items[event.GetIndex()].startLine)
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
