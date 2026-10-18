import wx

import trelby.ui.gutil as gutil
from trelby.ui.beatboardview import BeatBoardView
from trelby.ui.scrollbar import ScrollBar
from trelby.ui.sidepanel import SidePanel

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
        self.board.zoom = gd.boardZoom
        self.board.Hide()

        self.splitter = wx.SplitterWindow(
            self, -1, style=wx.SP_LIVE_UPDATE | wx.SP_NOBORDER
        )
        self.splitter.SetMinimumPaneSize(120)

        # the side panel is on the right; it keeps its width when the
        # window is resized
        self.splitter.SetSashGravity(1.0)

        # the side panel, with the outline and the notes as tabs. created
        # before MyCtrl, which refreshes them during its own init.
        self.side = SidePanel(self.splitter, self)
        self.side.Hide()
        self.outline = self.side.outline
        self.notes = self.side.notes

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
        self.splitter.Initialize(self.editor)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.splitter, 1, wx.EXPAND)
        sizer.Add(self.board, 1, wx.EXPAND)
        self.SetSizer(sizer)

        self.applyTheme(gd.cfgGui)

        self.side.setTab(gd.sideTab)
        self.showSide(gd.showSidePanel)
        self.showBeatBoard(gd.showBeatBoard)

    # use the colors of the theme in the given configgui.ConfigGui for the
    # parts not drawn by MyCtrl
    def applyTheme(self, cfgGui):
        # the sash between the script and the outline
        self.splitter.SetBackgroundColour(cfgGui.tabBorderColor)
        self.editor.SetBackgroundColour(cfgGui.workspaceColor)
        self.scrollBar.setColors(cfgGui.workspaceColor, cfgGui.textColor)
        self.side.applyTheme(cfgGui)
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

    # show or hide the side panel
    def showSide(self, show):
        if show:
            if not self.splitter.IsSplit():
                self.side.Show()

                # a negative sash position is the right pane's width
                self.splitter.SplitVertically(
                    self.editor, self.side, -self.gd.sideWidth
                )

            self.side.refresh()

        else:
            self.notes.finishEdit(True)

            if self.splitter.IsSplit():
                self.splitter.Unsplit(self.side)

    # show the side panel's tab at index tab (GlobalData.SIDE_*)
    def showSideTab(self, tab):
        self.side.setTab(tab)

    # sideWidth is what showSide passes to SplitVertically, so it includes
    # the sash
    def OnSashChanged(self, event):
        self.gd.sideWidth = (
            self.splitter.GetClientSize().width - event.GetSashPosition()
        )
        event.Skip()

    # we never want the scrollbar to get the keyboard focus, pass it on to
    # the main widget
    def OnScrollbarFocus(self, event):
        self.ctrl.SetFocus()
