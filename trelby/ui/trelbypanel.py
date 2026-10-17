import wx

import trelby.ui.gutil as gutil
from trelby.ui.beatboardview import BeatBoardView
from trelby.ui.notesview import NotesPanel
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

        # the side panel is on the right; it keeps its width when the
        # window is resized
        self.splitter.SetSashGravity(1.0)

        # the side panel: the outline above the notes, each shown or not
        self.side = wx.SplitterWindow(
            self.splitter, -1, style=wx.SP_LIVE_UPDATE | wx.SP_NOBORDER
        )
        self.side.SetMinimumPaneSize(80)
        self.side.SetSashGravity(0.5)

        # created before MyCtrl, which refreshes them during its own init
        self.outline = OutlinePanel(self.side, self)
        self.notes = NotesPanel(self.side, self)
        self.notes.Hide()
        self.side.Initialize(self.outline)

        # what's shown in the side panel (see showOutline, showNotes)
        self.outlineShown = False
        self.notesShown = False

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
        self.side.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGED, self.OnSideSashChanged)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.splitter, 1, wx.EXPAND)
        sizer.Add(self.board, 1, wx.EXPAND)
        self.SetSizer(sizer)

        self.applyTheme(gd.cfgGui)

        self.outlineShown = gd.showOutline
        self.notesShown = gd.showNotes
        self.layoutSide()
        self.showBeatBoard(gd.showBeatBoard)

    # use the colors of the theme in the given configgui.ConfigGui for the
    # parts not drawn by MyCtrl
    def applyTheme(self, cfgGui):
        # the sash between the script and the outline
        self.splitter.SetBackgroundColour(cfgGui.tabBorderColor)
        self.editor.SetBackgroundColour(cfgGui.workspaceColor)
        self.scrollBar.setColors(cfgGui.workspaceColor, cfgGui.textColor)
        self.side.SetBackgroundColour(cfgGui.tabBorderColor)
        self.outline.applyTheme(cfgGui)
        self.notes.applyTheme(cfgGui)
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
        self.outlineShown = show
        self.layoutSide()

    # show or hide the notes
    def showNotes(self, show):
        if not show:
            self.notes.finishEdit(True)

        self.notesShown = show
        self.layoutSide()

    # show the side panel with the outline and / or the notes, or hide it
    # if neither is shown
    def layoutSide(self):
        outline, notes = self.outlineShown, self.notesShown
        side = self.side

        if outline and notes:
            if not side.IsSplit():
                if side.GetWindow1() is not self.outline:
                    side.ReplaceWindow(side.GetWindow1(), self.outline)

                self.outline.Show()
                self.notes.Show()

                # a negative sash position is the bottom pane's height
                side.SplitHorizontally(self.outline, self.notes, -self.gd.notesHeight)

        elif outline or notes:
            if outline:
                win, other = self.outline, self.notes
            else:
                win, other = self.notes, self.outline

            if side.IsSplit():
                side.Unsplit(other)
            elif side.GetWindow1() is not win:
                side.ReplaceWindow(side.GetWindow1(), win)

            other.Hide()
            win.Show()

        if outline or notes:
            if not self.splitter.IsSplit():
                self.side.Show()

                # a negative sash position is the right pane's width
                self.splitter.SplitVertically(
                    self.editor, self.side, -self.gd.outlineWidth
                )
        else:
            if self.splitter.IsSplit():
                self.splitter.Unsplit(self.side)
            else:
                self.splitter.Initialize(self.editor)
                self.side.Hide()

        if outline:
            self.outline.refresh()

        if notes:
            self.notes.refresh()

    # outlineWidth is what layoutSide passes to SplitVertically, so it
    # includes the sash
    def OnSashChanged(self, event):
        self.gd.outlineWidth = (
            self.splitter.GetClientSize().width - event.GetSashPosition()
        )
        event.Skip()

    # likewise notesHeight, when the notes are below the outline
    def OnSideSashChanged(self, event):
        self.gd.notesHeight = (
            self.side.GetClientSize().height - event.GetSashPosition()
        )
        event.Skip()

    # we never want the scrollbar to get the keyboard focus, pass it on to
    # the main widget
    def OnScrollbarFocus(self, event):
        self.ctrl.SetFocus()
