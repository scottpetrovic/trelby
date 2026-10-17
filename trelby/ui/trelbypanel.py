import wx

import trelby.ui.gutil as gutil
from trelby.ui.beatboardview import BeatBoardView
from trelby.ui.outline import OutlinePanel
from trelby.ui.scrollbar import ScrollBar

# temporary until we can find out a way to separate MyCtrl
from trelby.ui.trelbyctrl import MyCtrl


class MyPanel(wx.Panel):

    def __init__(self, parent, id, gd):
        wx.Panel.__init__(
            self,
            parent,
            id,
            # wxMSW/Windows does not seem to support
            # wx.NO_BORDER, which sucks
            style=wx.WANTS_CHARS | wx.NO_BORDER,
        )

        self.gd = gd

        # whether the beat board is shown instead of the script and the
        # outline (see showBeatBoard)
        self.boardShown = False

        # the beat board, hidden until it's shown. created before MyCtrl,
        # which reloads it when it gets a new script.
        self.board = BeatBoardView(self, self)
        self.board.Hide()

        self.splitter = wx.SplitterWindow(
            self, -1, style=wx.SP_LIVE_UPDATE | wx.SP_NOBORDER
        )
        self.splitter.SetMinimumPaneSize(120)

        # the outline is on the right; it keeps its width when the window
        # is resized
        self.splitter.SetSashGravity(1.0)

        # created before MyCtrl, which refreshes it during its own init
        self.outline = OutlinePanel(self.splitter, self)

        self.editor = wx.Panel(self.splitter, -1, style=wx.WANTS_CHARS | wx.NO_BORDER)

        # the script and its scroll bar stay left to right in a
        # right-to-left interface. before they're created, so they take it
        # from here.
        gutil.keepLeftToRight(self.editor)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        self.scrollBar = ScrollBar(self.editor)
        self.ctrl = MyCtrl(self.editor, -1, gd, self)
        self.scrollBar.wheelTarget = self.ctrl

        hsizer.Add(self.ctrl, 1, wx.EXPAND)
        hsizer.Add(self.scrollBar, 0, wx.EXPAND)

        self.editor.SetSizer(hsizer)

        self.scrollBar.Bind(wx.EVT_COMMAND_SCROLL, self.ctrl.OnScroll)

        self.scrollBar.Bind(wx.EVT_SET_FOCUS, self.OnScrollbarFocus)

        self.splitter.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGED, self.OnSashChanged)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.splitter, 1, wx.EXPAND)
        sizer.Add(self.board, 1, wx.EXPAND)
        self.SetSizer(sizer)

        self.applyTheme(gd.cfgGui)

        self.showOutline(gd.showOutline)
        self.showBeatBoard(gd.showBeatBoard)

    # use the colors of the theme in the given configgui.ConfigGui for the
    # parts not drawn by MyCtrl
    def applyTheme(self, cfgGui):
        # the sash between the script and the outline
        self.splitter.SetBackgroundColour(cfgGui.tabBorderColor)
        self.editor.SetBackgroundColour(cfgGui.workspaceColor)
        self.scrollBar.setColors(cfgGui.workspaceColor, cfgGui.textColor)
        self.outline.applyTheme(cfgGui)
        self.board.applyTheme(cfgGui)
        self.splitter.Refresh()

    # show the script's beat board in place of the script and the outline,
    # or the other way around. while the board is shown, the script keeps
    # its cursor and selection, and MyCtrl.SetFocus gives the board the
    # keyboard focus instead.
    def showBeatBoard(self, show):
        if show == self.boardShown:
            return

        if show:
            self.board.reload()
        else:
            self.board.finishEdit(True)

        self.boardShown = show
        self.splitter.Show(not show)
        self.board.Show(show)
        self.Layout()

        if show:
            self.board.updateVirtualSize()

    # show or hide the outline view
    def showOutline(self, show):
        if show:
            if not self.splitter.IsSplit():
                self.outline.Show()
                # a negative sash position is the right pane's width
                self.splitter.SplitVertically(
                    self.editor, self.outline, -self.gd.outlineWidth
                )

            self.outline.refresh()
        else:
            if self.splitter.IsSplit():
                self.splitter.Unsplit(self.outline)
            else:
                self.splitter.Initialize(self.editor)
                self.outline.Hide()

    # outlineWidth is what showOutline passes to SplitVertically, so it
    # includes the sash
    def OnSashChanged(self, event):
        self.gd.outlineWidth = (
            self.splitter.GetClientSize().width - event.GetSashPosition()
        )
        event.Skip()

    # we never want the scrollbar to get the keyboard focus, pass it on to
    # the main widget
    def OnScrollbarFocus(self, event):
        self.ctrl.SetFocus()
