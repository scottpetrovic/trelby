import wx

import trelby.screenplay as screenplay

# max length of the summary text shown for each scene
MAX_SUMMARY_LEN = 200


# side panel showing a script's outline: its scenes and act breaks.
# selecting an item jumps to it in the script, and scenes can be reordered
# with the buttons or Ctrl+Up / Ctrl+Down. the selection follows the
# cursor as the user moves around in the script.
class OutlinePanel(wx.Panel):

    # how long to wait after the last change before refreshing, in ms. we
    # don't want to recompute the outline on every keypress.
    REFRESH_DELAY = 300

    def __init__(self, parent, scriptPanel):
        wx.Panel.__init__(self, parent, -1)

        # trelbypanel.MyPanel whose script we show
        self.scriptPanel = scriptPanel

        # screenplay.OutlineItems currently shown in the list
        self.items = []

        # True while we change the list's selection ourselves, so that we
        # don't mistake it for the user picking an item
        self.updating = False

        vsizer = wx.BoxSizer(wx.VERTICAL)

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

        self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        self.list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnItemSelected)
        self.list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnItemActivated)
        self.list.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.upBtn.Bind(wx.EVT_BUTTON, self.OnMoveUp)
        self.downBtn.Bind(wx.EVT_BUTTON, self.OnMoveDown)

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

    def moveScene(self, direction):
        idx = self.list.GetFirstSelected()

        if idx == -1:
            return

        self.getCtrl().moveScene(self.items[idx].startLine, direction)
        self.refresh()

    def OnTimer(self, event):
        self.refresh()

    def OnDestroy(self, event):
        if event.GetEventObject() is self:
            self.timer.Stop()

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
